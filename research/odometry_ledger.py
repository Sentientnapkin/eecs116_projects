"""Audited ledger of every raw parent flight available for training.

One row per parent: identity and checksum, scene/seed/domain/tier, measured duration and
frame rate (from timestamps, not frame counts), calibration, realized motion statistics,
consistency checks, and split by scene. Splits are assigned by scene, so every crop or
augmentation of a parent inherits its parent's split.

    ./odometry_env.sh odometry_ledger.py --source <research dir with data/> --output data/ledger
"""
import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from common import Flight
from pairs import digest

# Scene policy. Development and final-test scenes are fixed by earlier work; the
# confirmation scenes and previously scored final-test scenes are quarantined from any
# future claim of untouched testing.
DEVELOPMENT = set(range(166, 172))
FINAL_TEST = set(range(162, 166)) | set(range(172, 176))
CONFIRMATION = set(range(176, 180))
PROXY_VALIDATION = set(range(150, 162))
SPEED_STILL, SPEED_MOVING = .05, .2


def scene_number(scene):
    m = re.search(r"ProcTHOR-Train-(\d+)$", scene)
    return int(m[1]) if m else None


def split_for(scene):
    n = scene_number(scene)
    if n is None:
        return "train"  # HSSD scenes are only used by the generated pool
    if n in DEVELOPMENT: return "development"
    if n in FINAL_TEST: return "final_test"
    if n in CONFIRMATION: return "confirmation"
    if n in PROXY_VALIDATION: return "proxy_validation"
    return "train"


def intervals(mask, times, minimum):
    """Contiguous runs of True lasting at least `minimum` seconds: (count, total seconds)."""
    runs, start = [], None
    for i, flag in enumerate(np.r_[mask, False]):
        if flag and start is None: start = i
        if not flag and start is not None:
            if times[i-1]-times[start] >= minimum: runs.append(times[i-1]-times[start])
            start = None
    return len(runs), float(sum(runs))


def audit(path, meta):
    row = {"path": str(path), "file": Path(path).name, "sha256": digest(path), **meta}
    problems = []
    try:
        f = Flight(path)
    except Exception as error:
        return {**row, "eligible": False, "problems": [f"unreadable: {error!r}"[:200]]}
    t = np.asarray(f.ft, float)
    dt = np.diff(t)
    if not np.all(dt > 0): problems.append("non-monotonic frame times")
    if not (np.all(np.isfinite(f.v_body)) and np.all(np.isfinite(f.cam_gt))): problems.append("non-finite truth")
    imu_t = f.imu[:, 0]
    if len(f.imu) == 0 or imu_t[0] > t[0]+.06 or imu_t[-1] < t[-1]-.06: problems.append("IMU does not cover frames")
    if len(f.frames) != len(t): problems.append("frame/timestamp count mismatch")
    v = f.v_body
    speed = np.linalg.norm(v, axis=1)
    gyro = np.linalg.norm(f.imu[:, 4:7], axis=1) if f.imu.shape[1] >= 7 else np.zeros(1)
    still = intervals(speed < SPEED_STILL, t, 1.)
    row.update({
        "scene": row.get("scene") or f.scene, "split": split_for(row.get("scene") or f.scene),
        "duration_s": round(float(t[-1]-t[0]), 3), "frames": int(len(t)),
        "frame_rate_hz": round(float(1/np.median(dt)), 3) if len(dt) else None,
        "image_shape": list(np.asarray(f.frames[0]).shape),
        "K": f.K if isinstance(f.K, dict) else np.asarray(f.K).round(4).tolist(),
        "T_body_camera_sha": hashlib.sha256(np.asarray(f.T_bc, np.float64).tobytes()).hexdigest()[:16],
        "speed_p10_p50_p90": [round(float(np.percentile(speed, q)), 3) for q in (10, 50, 90)],
        "travel_m": round(float(np.sum(np.linalg.norm(np.diff(f.cam_gt, axis=0), axis=1))), 2),
        "backward_frames": int(np.sum(v[:, 0] < -SPEED_MOVING)),
        "lateral_frames": int(np.sum(np.abs(v[:, 1]) > SPEED_MOVING)),
        "vertical_frames": int(np.sum(np.abs(v[:, 2]) > SPEED_MOVING)),
        "turning_samples_fraction": round(float(np.mean(gyro > .5)), 3),
        "stationary_intervals": still[0], "stationary_seconds": round(still[1], 2),
        "initial_speed_m_s": round(float(speed[0]), 3),
    })
    row["problems"] = problems
    row["eligible"] = not problems
    return row


def collect(source):
    """Raw parents under a research directory, with labels from file names and manifests."""
    source = Path(source)
    items = []
    for split_dir in ("train", "val"):
        for p in sorted((source/"data"/split_dir).glob("*.npz")):
            m = re.match(r"(\w+)-(ProcTHOR-Train-\d+)-s(\d+)-(\d+)\.npz", p.name)
            items.append((p, {"domain": "proxy", "tier": m[1], "scene": m[2], "seed": int(m[3]),
                              "source_folder": f"data/{split_dir}"}))
    for p in sorted(source.glob("data/*native-data*/*/*.zip")):
        scene = re.search(r"(ProcTHOR-Train-\d+)", p.name)[1]
        items.append((p, {"domain": "native", "tier": "benchmark", "scene": scene, "seed": None,
                          "source_folder": str(p.parent.relative_to(source))}))
    for p in sorted(source.glob("data/*robust-*/*.zip")):
        scene = re.search(r"(ProcTHOR-Train-\d+)", p.name)[1]
        regime = "independent-yaw" if "yaw" in p.name else "benchmark"
        items.append((p, {"domain": "native", "tier": regime, "scene": scene, "seed": None,
                          "source_folder": str(p.parent.relative_to(source))}))
    return items


def checks(rows):
    """Parent/scene leakage and duplicate detection across splits."""
    issues = []
    by_sha = defaultdict(list)
    for r in rows: by_sha[r["sha256"]].append(r["path"])
    issues += [f"duplicate content: {paths}" for paths in by_sha.values() if len(paths) > 1]
    scene_splits = defaultdict(set)
    for r in rows: scene_splits[r["scene"]].add(r["split"])
    issues += [f"scene {s} in several splits {sorted(v)}" for s, v in scene_splits.items() if len(v) > 1]
    return issues


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Research directory holding data/ with raw parents")
    parser.add_argument("--pool", help="Generated pool manifest JSON (raw flights no longer on disk)")
    parser.add_argument("--output", default="data/ledger")
    args = parser.parse_args()
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, (path, meta) in enumerate(collect(args.source)):
        rows.append(audit(path, meta))
        if i % 25 == 0: print(i, rows[-1]["file"], rows[-1]["eligible"], flush=True)
    pool_rows = []
    if args.pool:
        pool = json.loads(Path(args.pool).read_text())
        parents = {}
        for r in pool["datasets"]["train"]:
            parents.setdefault(r["parent_sha256"], {"sha256": r["parent_sha256"], "scene": r["scene"],
                               "domain": "native-generated", "tier": r.get("regime"), "pass": r.get("pass"),
                               "split": split_for(r["scene"]), "frames": r["frames"],
                               "crops": []})["crops"].append(r["file"])
        pool_rows = list(parents.values())
    ledger = {"rows": rows, "generated_pool_parents": pool_rows,
              "issues": checks(rows),
              "pool_scene_conflicts": sorted({p["scene"] for p in pool_rows if p["split"] != "train"}),
              "policy": {"development": sorted(DEVELOPMENT), "final_test": sorted(FINAL_TEST),
                         "confirmation_quarantine": sorted(CONFIRMATION),
                         "proxy_validation": sorted(PROXY_VALIDATION),
                         "moving_speed_m_s": SPEED_MOVING, "still_speed_m_s": SPEED_STILL}}
    (out/"ledger.json").write_text(json.dumps(ledger, indent=1))
    summary = Counter((r["split"], r["domain"], r["tier"], r["eligible"]) for r in rows)
    lines = ["split,domain,tier,eligible,parents"] + [",".join(map(str, k+(n,))) for k, n in sorted(summary.items())]
    (out/"summary.csv").write_text("\n".join(lines)+"\n")
    print("\n".join(lines)); print("issues:", ledger["issues"][:10])
    print("generated pool parents:", len(pool_rows), "in non-train scenes:", ledger["pool_scene_conflicts"])


if __name__ == "__main__":
    main()
