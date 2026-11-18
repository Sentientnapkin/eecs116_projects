"""Audit training rosters and replay the N2 window plan without loading imagery or scoring flights."""
import argparse
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from odometry_data import WindowPlan, load_fields, motion_labels
from odometry_store import LocalStore
from odometry_train import apply_overrides
from launch import resolve
from pairs import digest


HARD_KINDS = ("backward", "lateral")
SEEDS = (217, 218, 219)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audits", required=True, type=Path, help="Raw native campaign train JSON directory")
    parser.add_argument("--manifest", required=True, type=Path, help="Frozen N2 manifest")
    parser.add_argument("--shards", required=True, type=Path, help="Local N2 shard directory")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    audits = [json.loads(path.read_text()) for path in sorted(args.audits.glob("*.json"))]
    if not audits or any(row["split"] != "train" for row in audits):
        raise ValueError("Audit directory must contain training flights")
    by_id = {row["id"]: row for row in audits}
    if len(by_id) != len(audits):
        raise ValueError("Training audit IDs must be unique")
    records = json.loads(args.manifest.read_text())["datasets"]["train"]
    campaign = [row for row in records if row["domain"] == "native-campaign"]
    observed = Counter((row["flight_id"], row["crop_s"]) for row in campaign)
    expected = Counter((flight_id, crop) for flight_id in by_id for crop in (0, 5))
    if observed != expected or any(row["split"] != "train" or
            any(row[meta] != by_id[row["flight_id"]][meta] for meta in ("catalog", "scene", "regime")) or
            row["parent_sha256"] != by_id[row["flight_id"]]["sha256"] for row in campaign):
        raise ValueError("Training records do not match the two audited crops per native parent")

    _, _, cli = resolve("N2-ssm-x3")
    cfg = json.loads((Path(__file__).resolve().parent / "configs/odometry.json").read_text())
    apply_overrides(cfg, [cli[index+1] for index, item in enumerate(cli) if item == "--set"])
    options = cfg["training"]
    length, burn = options["window_frames"], options["burn_in"]
    epochs = int(cli[max(i for i, item in enumerate(cli) if item == "--epochs") + 1])
    size = length + burn
    dataset = LocalStore(args.shards)

    def labels_for(row):
        fields = load_fields(dataset, row, ("v", "times", "cam_gt"))
        return motion_labels(fields["v"], fields["times"], fields["cam_gt"])

    with ThreadPoolExecutor(max_workers=12) as pool:
        labels = list(pool.map(labels_for, records))
    plan = WindowPlan(records, labels, size, burn, options["sampler"], SEEDS[0])
    _, _, candidate_cli = resolve("N2-early-native-x3")
    apply_overrides(cfg, [candidate_cli[i+1] for i, item in enumerate(candidate_cli) if item == "--set"])
    candidate = WindowPlan(records, labels, size, burn, options["sampler"], SEEDS[0])
    target_options = options["sampler"]["native_early"]

    coverage = defaultdict(lambda: defaultdict(Counter))
    for index, row in enumerate(records):
        if row["domain"] != "native-campaign":
            continue
        cohort = f'{row["catalog"]}/{row["regime"]}/crop-{row["crop_s"]}s'
        coverage[cohort]["roster"]["parents"] += 1
        for kind in HARD_KINDS:
            starts = plan.eligible[index][kind]
            values = coverage[cohort][kind]
            values["parents_with_window"] += int(len(starts) > 0)
            values["starts"] += len(starts)
            for name, ceiling in (("at_crop_start", 0), ("within_1s", 20), ("within_5s", 100)):
                values[f"parents_{name}"] += int(len(starts) > 0 and starts[0] <= ceiling)

    exposure = {}
    for seed in SEEDS:
        plan.seed = candidate.seed = seed
        by_group = defaultdict(Counter)
        early_changes, early_target = Counter(), Counter()
        hard_parents, targeted_parents, replacement_parents = set(), set(), set()
        for epoch in range(epochs):
            baseline = plan.plan(epoch)
            targeted = candidate.plan(epoch)
            stratum_draws, stratum_early = Counter(), Counter()
            for before, after in zip(baseline, targeted, strict=True):
                old, old_start, old_kind = before
                index, start, kind = after
                fields = ("domain", "catalog", "crop_s")
                if kind != old_kind or any(records[index].get(k) != records[old].get(k) for k in fields):
                    raise ValueError(f"Draw stratum changed for seed {seed}, epoch {epoch}")
                key = (kind, records[index].get("catalog"), records[index]["crop_s"])
                if records[index]["domain"] == "native-campaign" and key in candidate.native_early_pools:
                    group = f"{kind}/{key[1]}/crop-{key[2]}s"
                    stratum_draws[group] += 1
                    if start <= target_options["max_start"]:
                        stratum_early[group] += 1
                        early_target[group] += 1
                        targeted_parents.add(records[index]["parent_sha256"])
                    if before != after:
                        early_changes[group] += 1
                        replacement_parents.add(records[index]["parent_sha256"])
                elif before != after:
                    raise ValueError(f"Untargeted draw changed for seed {seed}, epoch {epoch}")
            if any(stratum_early[group] < int(np.ceil(target_options["fraction"]*count))
                   for group, count in stratum_draws.items()):
                raise ValueError(f"Early-window quota not met for seed {seed}, epoch {epoch}")
            for index, start, kind in baseline:
                row = records[index]
                cohort = f'{row["domain"]}/{row.get("catalog") or "uncatalogued"}/crop-{row["crop_s"]}s'
                by_group[kind][cohort] += 1
                if kind in HARD_KINDS and row["domain"] == "native-campaign":
                    hard_parents.add(row["parent_sha256"])
                    if start <= 20:
                        by_group[f"{kind}_within_1s"][cohort] += 1
        exposure[seed] = {"draws": by_group, "distinct_campaign_hard_parents": len(hard_parents),
                          "retargeted_draws": early_changes, "candidate_early_draws": early_target,
                          "distinct_candidate_early_parents": len(targeted_parents),
                          "distinct_replacement_parents": len(replacement_parents)}

    result = {
        "n2_manifest_sha256": digest(args.manifest),
        "native_audits": {"parents": len(audits), "scenes": len({row["scene"] for row in audits}),
                          "configured_seconds": sum(row["seconds"] for row in audits),
                          "parents_by_catalog_and_regime": Counter(f'{row["catalog"]}/{row["regime"]}' for row in audits),
                          "flags": Counter(flag for row in audits for flag in row["audit"]["flags"])},
        "window": {"burn_in_frames": burn, "scored_frames": length, "epochs": epochs,
                   "windows_per_epoch": options["sampler"]["windows_per_epoch"],
                   "minimum_label_frames": max(3, int(np.ceil(options["sampler"].get("min_fraction", .1)*length)))},
        "eligible_native_windows": coverage,
        "candidate_native_early": target_options,
        "n2_exposure": exposure,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
