"""Audit available development rosters without accessing reserved flight data."""
from collections import Counter, defaultdict
import json
from pathlib import Path

import numpy as np

from odometry_data import motion_labels


def read(path):
    return json.loads(path.read_text())


def audit(records, cache_paths, max_seconds=None):
    rows = []
    for record in records:
        path = next((p / record["file"] for p in cache_paths if (p / record["file"]).is_file()), None)
        if path is None:
            raise FileNotFoundError(record["file"])
        with np.load(path, allow_pickle=False) as shard:
            times = shard["times"]
            n = len(times) if max_seconds is None else np.searchsorted(times, times[0] + max_seconds + 1e-6, side="right")
            v, truth = shard["v"][:n], shard["cam_gt"][:n]
            labels = motion_labels(v, times[:n], truth)
        backward, lateral = float(labels["backward"].mean()), float(labels["lateral"].mean())
        rows.append({
            "parent": record["parent_sha256"], "scene": record["scene"], "file": record["file"],
            "catalog": record.get("catalog") or ("procthor" if record["scene"].startswith("ProcTHOR-") else "unknown"),
            "regime": record.get("regime"), "start": "moving-crop" if record["crop_s"] else "nominal",
            "crop_s": record["crop_s"], "frames": int(n), "end_s": record["crop_s"] + float(times[n - 1] - times[0]),
            "start_speed_mps": float(np.linalg.norm(v[0])),
            "backward_fraction": backward, "lateral_fraction": lateral,
            "motion": "backward/lateral" if backward > .05 or lateral > .10 else "ordinary",
        })
    def counts(group):
        return {"replays": len(group), "parents": len({r["parent"] for r in group}),
                "scenes": len({r["scene"] for r in group}),
                "above_0_1_mps_at_start": sum(r["start_speed_mps"] > .1 for r in group)}
    groups = defaultdict(list)
    parents = defaultdict(list)
    for row in rows:
        for key in ("all", row["catalog"], row["start"], row["motion"], f"{row['catalog']}/{row['motion']}",
                    f"{row['catalog']}/{row['start']}", f"{row['motion']}/{row['start']}"):
            groups[key].append(row)
        parents[row["parent"]].append(row)
    overlap = []
    for crops in parents.values():
        if len(crops) == 2 and len({r["crop_s"] for r in crops}) == 2:
            first, second = sorted(crops, key=lambda r: r["crop_s"])
            overlap.append(max(0., min(first["end_s"], second["end_s"]) - second["crop_s"]))
    return {"counts": {k: counts(v) for k, v in sorted(groups.items())},
            "by_scene": {scene: counts([r for r in rows if r["scene"] == scene])
                         for scene in sorted({r["scene"] for r in rows})},
            "by_commanded_regime": {regime: counts([r for r in rows if r["regime"] == regime])
                                    for regime in sorted({r["regime"] for r in rows if r["regime"]})},
            "parent_crop_histogram": dict(Counter(map(len, parents.values()))),
            "shared_footage_seconds": {"pairs": len(overlap), "min": min(overlap), "max": max(overlap),
                                       "median": float(np.median(overlap))} if overlap else None,
            "rows": rows}


def main():
    base = Path(__file__).resolve().parent
    data = base / "data"
    cache = data / "hub-cache"
    original = cache / "B-D0-ssm-x3-gpu"
    dev = read(original / "manifests/teacher-full.json")["datasets"]["development"]
    campaign = data / "native-campaign"
    campaign_rows = read(campaign / "dev-records.json")["records"]
    if any(record["split"] != "dev" for record in campaign_rows):
        raise ValueError("Campaign audit accepts development records only")
    proxy = read(data / "expand/proxy-proxy_validation-0.json")["records"]
    result = {
        "original-dev": audit(dev, [original / "shards", cache / "shards"]),
        "campaign-dev-30s": audit(campaign_rows, [campaign / "shards"], 30),
        "proxy-validation-30s": audit([r for r in proxy if r["crop_s"] == 0],
                                      [cache / "proxy-val/shards", cache / "shards"], 30),
    }
    path = base / "results/eval/evaluation-coverage.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    for roster, summary in result.items():
        print(roster, summary["counts"], summary["shared_footage_seconds"])


if __name__ == "__main__":
    main()
