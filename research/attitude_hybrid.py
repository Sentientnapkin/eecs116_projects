"""Compare four causal attitude paths with identical frozen B-D0 body velocities."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from odometry_data import load_row
from odometry_eval import integrate, load_weights, metrics, replay_model
from odometry_models import OdometryNet


SEEDS = (217, 218, 219)
METHODS = ("control", "visual", "learned", "hybrid")


def join_attitudes(learned, visual, anchors):
    """Use learned increments between accepted visual interval endpoints."""
    corrected = learned.copy()
    for k in range(1, len(learned)):
        anchor = anchors[k]
        if anchor >= 0:
            corrected[k] = corrected[anchor] @ (visual[anchor].T @ visual[k])
        else:
            corrected[k] = corrected[k - 1] @ (learned[k - 1].T @ learned[k])
    return corrected


def load_networks(paths, device):
    networks = {}
    for seed, path in zip(SEEDS, paths):
        config = json.loads((path / "config.json").read_text())
        if (config["seed"] != seed or not config["model"].get("gyro_bias_correction") or
                not (path / "checkpoints/epoch-0036/complete.json").is_file()):
            raise ValueError(f"Expected completed learned-attitude run for seed {seed}: {path}")
        net = OdometryNet(config["model"]).to(device).eval()
        net.load_state_dict(load_weights(path, "best"))
        networks[seed] = net
    return networks


def get_records(data_root, split):
    if split == "dev":
        cache = data_root / "hub-cache/B-D0-ssm-x3-gpu"
        records = json.loads((cache / "manifests/teacher-full.json").read_text())["datasets"]["development"]
        return records, cache / "shards"
    campaign = data_root / "native-campaign"
    records = json.loads((campaign / "dev-records.json").read_text())["records"]
    if any(r["split"] != "dev" for r in records):
        raise ValueError("Hybrid campaign replay requires dev records")
    return records, campaign / "shards"


def summarize(rows):
    filters = {"all": rows}
    for key in ("catalog", "motion", "start"):
        for value in sorted({r[key] for r in rows if r[key]}):
            filters[value] = [r for r in rows if r[key] == value]
    for catalog in sorted({r["catalog"] for r in rows if r["catalog"]}):
        for start in ("static", "moving"):
            filters[f"{catalog}/{start}"] = [r for r in rows if r["catalog"] == catalog and r["start"] == start]
    return {key: {m: float(np.mean([r[m] for r in subset])) for m in METHODS}
            for key, subset in filters.items() if subset}


def evaluate(split, data_root, visual_dir, networks, device):
    visual_report = json.loads((visual_dir / "summary.json").read_text())
    if visual_report["set"] != split:
        raise ValueError(f"Visual artifacts were scored on {visual_report['set']}, expected {split}")
    visual_rows = {(r["file"], r["run"]): r for r in visual_report["rows"]}
    records, shards = get_records(data_root, split)
    scored = []
    for record in records:
        row = load_row(shards, record)
        if split == "campaign-dev":
            keep = np.searchsorted(row["times"], 30 + 1e-6, side="right")
            row = {k: v if k == "T_bc" else v[:keep] for k, v in row.items()}
        steps = len(row["times"])
        with np.load(visual_dir / record["file"], allow_pickle=False) as artifact:
            velocities, visual, anchors = (artifact[k] for k in ("velocity", "rotation", "anchors"))
        if (velocities.shape != (len(SEEDS), steps, 3) or visual.shape != (steps, 3, 3) or
                anchors.shape != (steps,) or anchors[0] >= 0 or np.any(anchors >= np.arange(steps))):
            raise ValueError(f"Mismatched visual trajectory or anchors: {record['file']}")
        for seed, velocity in zip(SEEDS, velocities):
            control_run = "B-D0-ssm-x3-gpu" if seed == 217 else f"B-D0-ssm-x3-s{seed}-gpu"
            source = visual_rows[record["file"], control_run]
            _, learned = replay_model(networks[seed], row, device, return_attitude=True)
            hybrid = join_attitudes(learned, visual, anchors)
            rotations = (row["R"], visual, learned, hybrid)
            scores = {name: metrics(integrate(velocity, {**row, "R": attitude}), row["cam_gt"], row["times"])["ate"]
                      for name, attitude in zip(METHODS, rotations)}
            if any(not np.isclose(scores[m], source[m], rtol=0., atol=1e-6) for m in ("control", "visual")):
                raise ValueError(f"Frozen replay ATE mismatch for {record['file']} seed {seed}")
            scored.append({**{k: source[k] for k in ("file", "scene", "catalog", "motion", "start")},
                           "seed": seed, **scores})
    return {"summary": summarize(scored),
            "by_seed": {seed: summarize([r for r in scored if r["seed"] == seed]) for seed in SEEDS},
            "rows": scored}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--learned-runs", nargs=3, type=Path, required=True)
    parser.add_argument("--visual-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    visual_dev = json.loads((args.visual_root / "dev/summary.json").read_text())
    if visual_dev["dev_gate_passed"] is not True:
        parser.error("Hybrid evaluation requires the visual dev gate to pass")
    torch.set_num_threads(4)
    networks = load_networks(args.learned_runs, args.device)
    args.output.mkdir(parents=True, exist_ok=True)
    for split in ("dev", "campaign-dev"):
        result = evaluate(split, args.data_root, args.visual_root / split, networks, args.device)
        if split == "dev":
            summary = result["summary"]
            result["dev_gate_passed"] = (
                summary["all"]["hybrid"] <= .90 * min(summary["all"][m] for m in ("learned", "visual"))
                and all(summary[g]["hybrid"] <= 1.05 * min(summary[g][m] for m in ("learned", "visual"))
                        for g in ("ordinary", "static", "moving"))
            )
        (args.output / f"hybrid-{split}.json").write_text(json.dumps(result, indent=2) + "\n")
        print(split, json.dumps(result["summary"], indent=2), flush=True)


if __name__ == "__main__":
    main()
