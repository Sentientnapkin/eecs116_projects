"""Diagnose the provided OpenVINS example's campaign-dev failures from saved evaluator outputs (truth for diagnosis only).

    python openvins_diag.py timeline --runs <wasm_eval out dir> [--json out.json]

Per replay: error-over-time (position error |p_est - p_true| in the first-camera frame), the first time the error
exceeds 1 / 5 m, estimated vs true speed around that time, initialization time and start type (full recording =
static hold start; crop5 = moving start), catalog and regime (benchmark autopilot vs independent-yaw) from the
campaign records. Run with the pinned viobench venv.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

SRC = Path(os.environ.get("VIOBENCH_SRC", "/dev/shm/sebastian-vio/viobench"))
sys.path.insert(0, str(SRC))
from viobench.tools.datasets.storage import read_episode  # noqa: E402
from viobench.tools.runner.score import load_estimates  # noqa: E402
from viobench.tools.runner.metrics import fill_missing_states  # noqa: E402

RECORDS = Path("/data/backups/rganapa/Sebastian/gen/raw/dev")


def record(name):
    base = name.replace("-crop5", "")
    return json.loads((RECORDS / f"{base}.json").read_text())


def timeline(archive, work):
    e = read_episode(archive, frames="none")
    logs = list((Path(work) / "report" / "logs").glob("*/estimate.tum"))
    est = fill_missing_states(load_estimates(logs[0], e.frame_times))
    gt = e.ground_truth_state()
    t = e.frame_times - e.frame_times[0]
    err = np.linalg.norm(est[:, :3] - gt[:, :3], axis=1)
    vs = np.linalg.norm(est[:, 7:10], axis=1)
    vt = np.linalg.norm(gt[:, 7:10], axis=1)
    out = {"t": t, "err": err, "v_est": vs, "v_true": vt}
    stdout = (logs[0].parent / "stdout.txt").read_text()
    return out, stdout


def first(t, mask):
    i = np.flatnonzero(mask)
    return float(t[i[0]]) if len(i) else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("timeline",))
    p.add_argument("--runs", required=True)
    p.add_argument("--json")
    a = p.parse_args()
    runs = Path(a.runs)
    guest = json.loads((runs / "guest.json").read_text())
    rows = []
    for archive in guest["archives"]:
        name = Path(archive).stem
        work = runs / name
        if not (work / "report" / "report.json").exists():
            continue
        tl, stdout = timeline(archive, work)
        t, err, vs, vt = tl["t"], tl["err"], tl["v_est"], tl["v_true"]
        rec = record(name)
        import re
        m = re.search(r"initialized at t=([0-9.]+)", stdout)
        f = re.search(r"full VIO at ([0-9.]+) after (\d+) rotation updates", stdout)
        t1, t5 = first(t, err > 1), first(t, err > 5)
        # speed blow-up: first time the estimated speed exceeds 2x true + 0.5 m/s, sustained for 1 s
        bad = vs > 2 * vt + 0.5
        sustained = np.convolve(bad.astype(float), np.ones(20), "valid") >= 20
        tv = float(t[np.flatnonzero(sustained)[0]]) if sustained.any() else None
        row = {"episode": name, "catalog": rec["catalog"], "regime": rec["regime"], "hold": rec["hold_seconds"],
               "start": "moving" if name.endswith("crop5") else "static", "duration": float(t[-1]),
               "ate": float(np.sqrt(np.mean(err ** 2))), "final_err": float(err[-1]), "max_err": float(err.max()),
               "init": float(m.group(1)) if m else None, "full": float(f.group(1)) if f else None,
               "rot_updates": int(f.group(2)) if f else None, "t_err1": t1, "t_err5": t5, "t_speed_blowup": tv,
               "v_est_max": float(vs.max()), "v_true_max": float(vt.max()),
               "flags": rec["audit"]["flags"], "back": rec["audit"]["backward_fraction"],
               "lat": rec["audit"]["lateral_fraction"], "turn": rec["audit"]["turning_fraction"],
               "flat": rec["audit"]["flat_fraction"]}
        # error at 10 s checkpoints
        row["err_at"] = {int(s): float(np.interp(s, t, err)) for s in range(10, int(t[-1]) + 1, 10)}
        rows.append(row)
    rows.sort(key=lambda r: -r["ate"])
    for r in rows:
        print(f"{r['episode']:36s} {r['catalog'][:4]} {r['regime'][:5]} {r['start'][:3]} h={r['hold']:.1f} "
              f"ate={r['ate']:8.2f} init={r['init']} full={r['full']} rot={r['rot_updates']} e1={r['t_err1']} "
              f"e5={r['t_err5']} vblow={r['t_speed_blowup']} vmax={r['v_est_max']:.1f}/{r['v_true_max']:.1f} "
              f"fin={r['final_err']:.1f}")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
