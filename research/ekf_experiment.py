"""CPU replay for the predeclared B-D0 fixed-covariance comparison."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from itertools import product
import json
import multiprocessing
from pathlib import Path

import numpy as np
import torch

from odometry_data import load_row, motion_labels, write_json
from odometry_eval import ekf_fuse, integrate, load_model, load_weights, replay_velocities
from pairs import digest

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT/"configs/experiments.json").read_text())["postprocessing"]["B-D0-fixed-ekf"]


def initialize(runs):
    global models
    torch.set_num_threads(1)
    models = [load_model(run, load_weights(run, "best"), "cpu") for run in runs]


def replay(task):
    shard_dir, record, seconds = task
    row = load_row(shard_dir, record)
    if seconds is not None:
        keep = np.searchsorted(row["times"], row["times"][0]+seconds+1e-6, side="right")
        row = {k: v if k == "T_bc" else v[:keep] for k, v in row.items()}
    velocities = [replay_velocities(model, row, "cpu") for model in models]
    del row["images"]
    return record, row, velocities


def replay_all(workers, runs, task_rows):
    with ProcessPoolExecutor(max_workers=workers, initializer=initialize, initargs=(runs,),
                             mp_context=multiprocessing.get_context("spawn")) as pool:
        for i, result in enumerate(pool.map(replay, task_rows), 1):
            if i % 10 == 0 or i == len(task_rows):
                print(f"Replayed {i}/{len(task_rows)} crops", flush=True)
            yield result


def tune_tasks(data):
    cfg = PLAN["tune"]
    records = json.loads((data/"native-campaign/train-records.json").read_text())["records"]
    by_group = defaultdict(set)
    by_parent = defaultdict(list)
    for record in records:
        if record["split"] != "train":
            raise ValueError("Non-training record in tuning input")
        parent = record["parent_sha256"]
        by_group[record["catalog"], record["regime"]].add(parent)
        by_parent[parent].append(record)
    rng = np.random.default_rng(cfg["rng_seed"])
    tasks = []
    for _, parents in sorted(by_group.items()):
        for parent in rng.choice(sorted(parents), cfg["parents_per_catalog_regime"], replace=False):
            crops = sorted(by_parent[parent], key=lambda r: r["crop_s"])
            if [r["crop_s"] for r in crops] != [0, 5]:
                raise ValueError(f"Unexpected crops for {parent}")
            tasks.extend((data/"native-campaign/shards", r, cfg["seconds"]) for r in crops)
    return tasks


def evaluation_tasks(data, suite):
    if suite == "dev":
        records = json.loads((data/"hub-cache/manifests/teacher-full.json").read_text())["datasets"]["development"]
        shards = data/"hub-cache/shards"
    elif suite == "proxy-val":
        records = json.loads((data/"expand/proxy-proxy_validation-0.json").read_text())["records"]
        records = [r for r in records if r["crop_s"] == 0]
        shards = data/"hub-cache/shards"
    else:
        records = json.loads((data/"native-campaign/dev-records.json").read_text())["records"]
        if any(r["split"] != "dev" for r in records):
            raise ValueError("Non-development record in campaign evaluation")
        shards = data/"native-campaign/shards"
    return [(shards, r, PLAN["evaluate"][suite]) for r in records]


def ate(track, row):
    return float(np.sqrt(np.mean(np.sum((track-row["cam_gt"])**2, axis=1))))


def tune(replays):
    cfg = PLAN["tune"]
    squared_error = np.zeros(3)
    frames = 0
    for _, row, predictions in replays:
        error = np.asarray(predictions)-row["v"]
        squared_error += np.square(error).sum(axis=(0, 1))
        frames += error.shape[0]*error.shape[1]
    sigma = np.maximum(np.sqrt(squared_error/frames), .01).tolist()
    grid = []
    controls = [[ate(integrate(v, row), row) for v in predictions] for _, row, predictions in replays]
    for accel, gravity, bias in product(cfg["accel_sigma"], cfg["gravity_walk"], cfg["accel_bias_sigma"]):
        params = dict(attitude=False, use_variance=False, accel_sigma=accel, gravity_walk=gravity,
                      gravity_sigma=.5, accel_bias_sigma=bias, accel_bias_walk=.02, velocity_sigma=sigma)
        scores = [ate(ekf_fuse(v, row, params)[0], row) for _, row, predictions in replays for v in predictions]
        grid.append({"params": params, "train_ate": float(np.mean(scores))})
        print(f"Tuned accel={accel:g} gravity={gravity:g} bias={bias:g}: {grid[-1]['train_ate']:.4f} m", flush=True)
    return {"selected": min(grid, key=lambda entry: entry["train_ate"]), "grid": grid,
            "train_control_ate": float(np.mean(controls)), "calibration_frames": frames,
            "training_records": [{k: record[k] for k in ("flight_id", "crop_s", "sha256")}
                                 for record, _, _ in replays]}


def evaluate(replays, params):
    rows = []
    for record, row, predictions in replays:
        labels = motion_labels(row["v"], row["times"], row["cam_gt"])
        ordinary = labels["backward"].mean() <= .05 and labels["lateral"].mean() <= .1
        paired = []
        for seed, v in zip(PLAN["seeds"], predictions, strict=True):
            fused, _, info = ekf_fuse(v, row, params)
            paired.append({"seed": seed, "direct": ate(integrate(v, row), row),
                           "ekf": ate(fused, row), "nis": info["nis"]})
        rows.append({"file": record["file"], "scene": record["scene"], "catalog": record.get("catalog"),
                     "crop_s": record["crop_s"], "ordinary": bool(ordinary), "paired": paired})
    return rows


def summarize(rows):
    groups = {"all": rows, "ordinary": [r for r in rows if r["ordinary"]],
              "backward_lateral": [r for r in rows if not r["ordinary"]]}
    for catalog in sorted({r["catalog"] for r in rows if r["catalog"]}):
        groups[catalog] = [r for r in rows if r["catalog"] == catalog]
    summary = {}
    for name, group in groups.items():
        if not group:
            continue
        samples = np.asarray([[[p["direct"], p["ekf"]] for p in r["paired"]] for r in group])
        direct, ekf = samples.mean(axis=(0, 1))
        summary[name] = {"replays": len(group), "scenes": len({r["scene"] for r in group}),
                         "direct": float(direct), "ekf": float(ekf), "relative": float(ekf/direct-1),
                         "per_seed": {str(s): {"direct": float(d), "ekf": float(e)}
                                      for s, (d, e) in zip(PLAN["seeds"], samples.mean(0), strict=True)}}
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("tune", *PLAN["evaluate"]))
    parser.add_argument("--runs", nargs=3, type=Path, required=True, help="Runs in declared seed order")
    parser.add_argument("--data", type=Path, default=ROOT/"data")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, help="Replay process count (one CPU thread per worker)")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    workers = args.workers if args.workers is not None else (4 if args.stage == "tune" else 12)
    frozen = args.output/"frozen.json"
    fingerprints = {}
    for seed, run in zip(PLAN["seeds"], args.runs, strict=True):
        if json.loads((run/"config.json").read_text())["seed"] != seed:
            raise ValueError(f"Unexpected seed for {run}")
        fingerprints[str(seed)] = {k: digest(run/k) for k in ("best.safetensors", "config.json")}
    if args.stage == "tune":
        if frozen.exists():
            raise FileExistsError(frozen)
        replays = list(replay_all(workers, args.runs, tune_tasks(args.data)))
        write_json(frozen, {"checkpoints": fingerprints, "plan": PLAN, **tune(replays)})
    else:
        selection = json.loads(frozen.read_text())
        if selection["checkpoints"] != fingerprints or selection["plan"] != PLAN:
            raise ValueError("Checkpoint or experiment declaration differs from frozen tuning")
        params = selection["selected"]["params"]
        rows = evaluate(replay_all(workers, args.runs, evaluation_tasks(args.data, args.stage)), params)
        summary = summarize(rows)
        write_json(args.output/f"{args.stage}.json", {"summary": summary, "rows": rows})
        print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
