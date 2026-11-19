"""Per-frame fuel profile and trajectory equality for wasm_eval.py run directories (peak-fuel workstream).

    python fuel_report.py <run dir> [--control <run dir>]

Prints mean/median full ATE, peak/median fuel over all flights, the fuel profile by frame offset from the 0.5 s
kf_grid measurement frames (frame index multiple of 10 at 20 Hz on public flights; offset 0 = window's last frame),
and, with --control, whether every estimate.tum is identical (max absolute difference of all columns).
"""
import argparse
import json
from pathlib import Path

import numpy as np


def load(run):
    run = Path(run)
    scores = json.loads((run / "scores.json").read_text())
    out = {}
    for row in scores["rows"]:
        logs = next((run / row["episode"] / "report" / "logs").glob("*/"))
        out[row["episode"]] = (row, np.load(logs / "fuel.npy"), np.loadtxt(logs / "estimate.tum"))
    return scores["guest"], out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run")
    parser.add_argument("--control")
    parser.add_argument("--period", type=int, default=10)
    args = parser.parse_args()
    guest, runs = load(args.run)
    ate = [r["ate_full"] for r, _, _ in runs.values()]
    fuel = np.concatenate([f for _, f, _ in runs.values()])
    print(f"{Path(args.run).name}: sha256 {guest['sha256'][:16]} flights {len(ate)} mean ATE {np.mean(ate):.4f} "
          f"median ATE {np.median(ate):.4f} peak fuel {fuel.max():,.0f} median {np.median(fuel):,.0f} "
          f"p95 {np.percentile(fuel, 95):,.0f}")
    base = np.median(fuel)
    for off in range(args.period):
        sel = np.concatenate([f[np.arange(len(f)) % args.period == off][2:] for _, f, _ in runs.values()])
        print(f"  offset {off}: median {np.median(sel)/1e6:8.1f}M  max {sel.max()/1e6:8.1f}M  "
              f"max-over-median {(sel.max()-base)/1e6:7.1f}M")
    print("  per-flight ATE:", " ".join(f"{a:.3f}" for a in ate))
    if args.control:
        _, control = load(args.control)
        worst = max(float(np.abs(runs[k][2] - control[k][2]).max()) for k in runs)
        same = all(np.array_equal(runs[k][2], control[k][2]) for k in runs)
        print(f"  vs control {Path(args.control).name}: estimate.tum identical={same} max abs diff {worst:.3g}; "
              f"control mean ATE {np.mean([control[k][0]['ate_full'] for k in runs]):.4f}")


if __name__ == "__main__":
    main()
