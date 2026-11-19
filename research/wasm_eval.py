"""Evaluate any VIOBench Wasm guest with a pinned upstream evaluator on public or campaign-dev archives.

    python wasm_eval.py crop  --archives <zip>... --start 5 --out <dir>          # fresh-recording crops
    python wasm_eval.py run   --wasm x.wasm --archives <zip>... --out <dir> [--workers 48]
    python wasm_eval.py score --runs <dir> [--catalog-from <records.json>]        # tables

Every guest is run by `python -m viobench evaluate` from the pinned checkout (VIOBENCH_SRC), one process per episode,
so all compared guests share the evaluator, scoring and missing-frame rule (unusable estimates count as the origin
with identity rotation, i.e. the harness's own fill). Scoring re-applies the harness's `evaluate_trajectory` to the
saved estimate.tum for 30 s / 60 s prefixes; the guests are causal, so a prefix of the full run equals a shorter run.
Mean unaligned (raw) ATE is the decision metric. Fuel is the per-step maximum over all attempted frames.

Run this file with the pinned viobench venv (see research/baselines/openvins-9b1b079.md), not the training venv.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

SRC = Path(os.environ.get("VIOBENCH_SRC", "/dev/shm/sebastian-vio/viobench"))
sys.path.insert(0, str(SRC))
from viobench.tools.datasets.storage import read_episode, write_episode  # noqa: E402
from viobench.tools.datasets.episode import Episode  # noqa: E402
from viobench.tools.runner.metrics import evaluate_trajectory  # noqa: E402
from viobench.tools.runner.score import load_estimates  # noqa: E402

INIT = re.compile(r"initialized at t=([0-9.]+)")
FULL = re.compile(r"full VIO at ([0-9.]+)")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def crop(archive, start, out):
    """A fresh-recording crop: frames from the first frame at or after `start` s; times shifted so that frame sits
    where a recording's first frame does; IMU keeps one frame interval before it (what the harness delivers to a
    first frame); ground truth keeps a margin for the twist's central difference."""
    e = read_episode(archive, frames="memory")
    k = int(np.searchsorted(e.frame_times, e.frame_times[0] + start - 1e-9))
    shift = e.frame_times[k] - e.frame_times[0]
    t0 = e.frame_times[k] - e.frame_interval - 1e-6
    imu = e.imu[e.imu[:, 0] > t0].copy(); imu[:, 0] -= shift
    gt = e.ground_truth[e.ground_truth[:, 0] >= t0 - 0.02].copy(); gt[:, 0] -= shift
    config = json.loads(json.dumps(e.config))
    config["episode"]["num_frames"] = int(e.num_frames - k)
    config["episode"]["name"] = f"{config['episode']['name']}-crop{start:g}"
    cropped = Episode(name=config["episode"]["name"], config=config, frame_times=e.frame_times[k:] - shift,
                      frames=np.asarray(e.frames)[k:], imu=imu, ground_truth=gt, T_body_camera=e.T_body_camera,
                      meta={k2: v for k2, v in e.meta.items() if k2 not in ("hash", "path")} | {"crop_start_s": start})
    cropped.check_consistency()
    target = Path(out) / f"{Path(archive).stem}-crop{start:g}.zip"
    write_episode(cropped, target)
    return target


def run_one(wasm, archive, out):
    work = Path(out) / Path(archive).stem
    report = work / "report" / "report.json"
    if report.exists():
        return report
    work.mkdir(parents=True, exist_ok=True)
    env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp"), "PYTHONPATH": str(SRC),
           "XDG_CACHE_HOME": str(work / "cache"), "TMPDIR": os.environ.get("TMPDIR", "/tmp")}
    with (work / "evaluate.log").open("w") as log:
        subprocess.run([sys.executable, "-B", "-m", "viobench", "evaluate", str(wasm), str(archive), "-o",
                        str(work / "report")], cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
    return report


def score_one(archive, work):
    report_path = Path(work) / "report" / "report.json"
    if not report_path.exists():
        return {"episode": Path(archive).stem, "error": "no report"}
    report = json.loads(report_path.read_text())
    ep = report["episodes"][0]
    e = read_episode(archive, frames="none")
    row = {"episode": Path(archive).stem, "frames": ep["frames"], "frames_attempted": ep["frames_attempted"],
           "completed": ep["completed"], "failure": ep["failure"], "peak_fuel_per_frame": ep["fuel_per_frame_max"],
           "median_fuel_per_frame": ep["fuel_per_frame_median"], "p95_fuel_per_frame": ep["fuel_per_frame_p95"],
           "scene": e.meta.get("scene"), "duration_s": ep["duration_s"]}
    logs = list((Path(work) / "report" / "logs").glob("*/estimate.tum"))
    if logs and ep["frames_attempted"]:
        estimates = load_estimates(logs[0], e.frame_times)
        truth = e.ground_truth_state()
        for label, seconds in (("30s", 30), ("60s", 60), ("full", None)):
            n = e.num_frames if seconds is None else int(np.sum(e.frame_times - e.frame_times[0] < seconds - 1e-6))
            if seconds is not None and e.duration < seconds - 0.1:
                continue
            m = evaluate_trajectory(truth[:n], estimates[:n], e.frame_times[:n])
            row[f"ate_{label}"] = m.ate_rmse if hasattr(m, "ate_rmse") else m["ate_rmse"]
            row[f"filled_{label}"] = getattr(m, "filled_frames", None) if not isinstance(m, dict) else m.get("filled_frames")
        stdout = logs[0].parent / "stdout.txt"
        text = stdout.read_text() if stdout.exists() else ""
        found, full = INIT.search(text), FULL.search(text)
        row["initialized_at_s"] = float(found.group(1)) if found else None
        row["full_vio_at_s"] = float(full.group(1)) if full else None
    row["ate_reported_full"] = ep["metrics"]["ate_rmse"] if ep.get("metrics") else None
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("crop", "run", "score"))
    parser.add_argument("--archives", nargs="*", default=[])
    parser.add_argument("--wasm")
    parser.add_argument("--start", type=float, default=5.0)
    parser.add_argument("--out", required=True)
    parser.add_argument("--workers", type=int, default=32)
    args = parser.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    if args.action == "crop":
        with ThreadPoolExecutor(args.workers) as pool:
            for t in pool.map(lambda a: crop(a, args.start, out), args.archives):
                print(t, flush=True)
    elif args.action == "run":
        (out / "guest.json").write_text(json.dumps({"wasm": str(args.wasm), "sha256": sha256(args.wasm),
                                                    "evaluator_src": str(SRC), "archives": args.archives}, indent=1))
        with ThreadPoolExecutor(args.workers) as pool:
            for r in pool.map(lambda a: run_one(args.wasm, a, out), args.archives):
                print(r, "ok" if r.exists() else "MISSING", flush=True)
    else:
        guest = json.loads((out / "guest.json").read_text())
        rows = [score_one(a, out / Path(a).stem) for a in guest["archives"]]
        (out / "scores.json").write_text(json.dumps({"guest": guest, "rows": rows}, indent=1))
        ok = [r for r in rows if "ate_full" in r]
        print(f"{len(ok)}/{len(rows)} scored; mean full ATE {np.mean([r['ate_full'] for r in ok]):.3f} m; "
              f"peak fuel {max(r['peak_fuel_per_frame'] for r in ok):,}")


if __name__ == "__main__":
    main()
