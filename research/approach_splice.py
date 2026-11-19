"""Offline splice of EXISTING guest outputs: learned odometry before OpenVINS initializes, OpenVINS after (predeclared,
2026-11-19, before any spliced number was computed).

    env -i PATH=/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin:/usr/bin:/bin \
        python approach_splice.py --ov RUN_DIR --learned RUN_DIR [--ov ... --learned ...] --output OUT.json

RUN_DIRs are `wasm_eval.py run` outputs (guest.json + <episode>/report/logs/*/estimate.tum). Nothing is re-run: the
spliced trajectories are built from the two guests' saved per-frame poses and scored with the pinned evaluator's own
`evaluate_trajectory` (mean unaligned ATE). This is a feasibility bound for a C++ guest that runs both estimators.

Hypothesis: the provided OpenVINS example's catastrophic tails come from (a) zero translation output before its late
initialization on moving starts, and (b) `imu_pose_at_first_frame`, which double-integrates buffered IMU BACKWARDS
from the initial state over the whole pre-init interval, so first-camera anchoring error grows ~quadratically with the
initialization delay (0.5 * 0.2 m/s^2 * 15^2 s^2 = 22 m from accel bias alone). OpenVINS' *relative* motion after
initialization does not depend on that anchor.

Arms (all causal; OpenVINS' init time is read from its own stdout, which a combined guest knows at that frame):
  ov             OpenVINS as submitted (reproduces wasm_eval scores)
  learned        learned guest as submitted (reproduces)
  handoff        learned pose until the first frame at/after OpenVINS init; afterwards
                 T(t) = T_learned(t_i) * T_ov(t_i)^-1 * T_ov(t)   (OpenVINS relative motion; its anchor cancels)
  handoff_guard  handoff plus a predeclared divergence guard, evaluated causally on every frame >= t_i + 1 s:
                 d_x = |p_x(t) - p_x(t - 1 s)| for x in {ov, learned}; trip if d_ov > d_learned + 0.5 m or
                 d_ov > 2.5 m. After a trip the output follows the learned guest's relative motion from the trip frame
                 (permanent; no switching back).
  late_skip      OpenVINS as submitted if it initialized within 3.0 s of the first frame, else the learned guest
DIAGNOSTIC ONLY (uses truth): oracle_min = per-replay min(ov, learned).

Predeclared reading: handoff_guard is worth a C++ guest if, on campaign dev (120 replays), its mean full ATE is below
both inputs' means and below 1.2 m, and on public it does not exceed OpenVINS' 1.108 m by more than 5%. Thresholds
(0.5 m, 2.5 m, 3.0 s) are fixed here and are not tuned on these replays; any sensitivity sweep is labelled diagnostic.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

SRC = Path(os.environ.get("VIOBENCH_SRC", "/dev/shm/sebastian-vio/viobench"))
sys.path.insert(0, str(SRC))
from viobench.tools.datasets.storage import read_episode  # noqa: E402
from viobench.tools.geometry import invert, matrices_to_poses, poses_to_matrices  # noqa: E402
from viobench.tools.runner.metrics import evaluate_trajectory  # noqa: E402
from viobench.tools.runner.score import load_estimates  # noqa: E402

INIT = re.compile(r"initialized at t=([0-9.]+)")
GUARD_EXCESS, GUARD_ABS, LATE = 0.5, 2.5, 3.0


def to_states(T, template):
    """(N,4,4) camera poses -> (N,13) states with template's twist columns."""
    out = template.copy()
    out[:, :7] = matrices_to_poses(T)  # x y z qx qy qz qw
    return out


def splice(T_a, T_b, k):
    """T_a before frame k, then T_b's motion relative to frame k composed onto T_a[k]."""
    out = T_a.copy()
    out[k:] = T_a[k] @ invert(T_b[k]) @ T_b[k:]
    return out


def episode_rows(archive, ov_dir, learned_dir):
    name = Path(archive).stem
    e = read_episode(archive, frames="none")
    times = e.frame_times
    truth = e.ground_truth_state()
    ov_log = next((ov_dir / name / "report" / "logs").glob("*/estimate.tum"))
    le_log = next((learned_dir / name / "report" / "logs").glob("*/estimate.tum"))
    ov, le = load_estimates(ov_log, times), load_estimates(le_log, times)
    found = INIT.search((ov_log.parent / "stdout.txt").read_text())
    t_init = float(found.group(1)) if found else None
    T_ov, T_le = poses_to_matrices(ov), poses_to_matrices(le)
    n = len(times)
    arms = {"ov": ov, "learned": le}
    if t_init is None:
        arms["handoff"] = arms["handoff_guard"] = arms["late_skip"] = le
        k = trip = None
    else:
        k = int(np.searchsorted(times, t_init - 1e-6))
        k = min(k, n - 1)
        T_h = splice(T_le, T_ov, k)
        arms["handoff"] = to_states(T_h, ov)
        lag = int(round(1.0 / np.median(np.diff(times))))
        trip = None
        for j in range(k + lag, n):
            d_ov = np.linalg.norm(T_ov[j, :3, 3] - T_ov[j - lag, :3, 3])
            d_le = np.linalg.norm(T_le[j, :3, 3] - T_le[j - lag, :3, 3])
            if d_ov > d_le + GUARD_EXCESS or d_ov > GUARD_ABS:
                trip = j
                break
        T_g = T_h if trip is None else splice(T_h, T_le, trip)
        arms["handoff_guard"] = to_states(T_g, ov)
        arms["late_skip"] = ov if t_init - times[0] <= LATE else le
    row = {"episode": name, "scene": e.meta.get("scene"), "duration_s": float(times[-1] - times[0]),
           "init_s": None if t_init is None else float(t_init - times[0]),
           "trip_s": None if trip is None else float(times[trip] - times[0])}
    for arm, est in arms.items():
        row[arm] = float(evaluate_trajectory(truth, est, times).ate_rmse)
    row["oracle_min"] = min(row["ov"], row["learned"])
    return row


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ov", nargs="+", required=True)
    p.add_argument("--learned", nargs="+", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    report = {}
    for ov_dir, le_dir in zip(args.ov, args.learned):
        ov_dir, le_dir = Path(ov_dir), Path(le_dir)
        archives = json.loads((ov_dir / "guest.json").read_text())["archives"]
        rows = [episode_rows(a, ov_dir, le_dir) for a in archives]
        arms = ["ov", "learned", "handoff", "handoff_guard", "late_skip", "oracle_min"]
        summary = {a: {"mean": float(np.mean([r[a] for r in rows])), "median": float(np.median([r[a] for r in rows])),
                       "max": float(np.max([r[a] for r in rows])), "n_over_5m": int(sum(r[a] > 5 for r in rows))}
                   for a in arms}
        for dom in ("ProcTHOR", "HSSD"):
            sub = [r for r in rows if ("ProcTHOR" in r["episode"]) == (dom == "ProcTHOR")]
            if sub:
                for a in arms:
                    summary[a][f"mean_{dom}"] = float(np.mean([r[a] for r in sub]))
        summary["guard_trips"] = int(sum(r["trip_s"] is not None for r in rows))
        report[str(ov_dir)] = {"learned": str(le_dir), "replays": len(rows), "summary": summary, "rows": rows}
        print(ov_dir.name, len(rows), json.dumps({a: round(v["mean"], 3) for a, v in summary.items() if isinstance(v, dict)}),
              "trips", summary["guard_trips"], flush=True)
    Path(args.output).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
