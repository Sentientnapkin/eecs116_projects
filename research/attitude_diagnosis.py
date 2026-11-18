"""Attitude diagnosis on native campaign flights, where the raw archives carry full truth attitude.

    python attitude_diagnosis.py --runs results/loop/B-D0-ssm-x3-gpu ... --output results/eval/attitude

Our attitude `R` (shard field) is gyro integration from the first frame, so it lives in the
first body frame. Its error E = R R_true_rel^T (R_true_rel = R_true[0]^T R_true[k]) is split by a
swing-twist decomposition about the first-frame gravity axis into tilt and yaw. Gravity can
constrain tilt when the vehicle's specific force is known.
True body velocity and each model's velocities are integrated through: our R, truth, our R with
only the yaw error kept ("tilt fixed") and with only the tilt error kept ("yaw fixed").
Mean unaligned ATE only.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import interpolate_poses, matrix_to_quaternion, poses_to_matrices

from odometry_data import load_fields, load_row
from odometry_eval import integrate, model_velocities, load_weights
from orientation import Orientation

RAW = Path("/data/backups/rganapa/Sebastian/gen/raw")


def axis_angle(axis, angle):
    k = np.zeros((len(angle), 3, 3))
    x, y, z = axis
    k[:, 0, 1], k[:, 0, 2], k[:, 1, 2] = -z, y, -x
    k[:, 1, 0], k[:, 2, 0], k[:, 2, 1] = z, -y, x
    s, c = np.sin(angle)[:, None, None], np.cos(angle)[:, None, None]
    return np.eye(3)+s*k+(1-c)*(k@k)


def decompose(R_est, R_true_rel, gravity):
    """Total, tilt and yaw error angles (rad) and the yaw-only / tilt-only attitudes."""
    E = R_est @ np.transpose(R_true_rel, (0, 2, 1))
    q = matrix_to_quaternion(E)
    w, v = q[:, 3], q[:, :3]
    total = 2*np.arctan2(np.linalg.norm(v, axis=1), w)
    yaw = 2*np.arctan2(v @ gravity, w)
    yaw = (yaw+np.pi) % (2*np.pi)-np.pi
    twist = axis_angle(gravity, yaw)  # E = swing @ twist
    swing = E @ np.transpose(twist, (0, 2, 1))
    tilt = np.arccos(np.clip(np.einsum("nij,j,i->n", E, gravity, gravity), -1, 1))
    return total, tilt, np.abs(yaw), twist @ R_true_rel, swing @ R_true_rel


def ate(p, truth):
    return float(np.sqrt(np.mean(np.sum((p-truth)**2, 1))))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="*", default=[])
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-seconds", type=float)
    parser.add_argument("--probe-uncalibrated", action="store_true",
                        help="Measure a raw-gyro attitude oracle with rolling calibration disabled")
    args = parser.parse_args()
    campaign = Path("data/native-campaign")
    records = json.loads((campaign/"dev-records.json").read_text())["records"]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    runs = [(Path(r), load_weights(Path(r), "best")) for r in args.runs]
    rows, curves = [], {}
    for record in records:
        row = (load_row(campaign/"shards", record) if runs else
               load_fields(campaign/"shards", record, ("R", "v", "times", "cam_gt", "T_bc")))
        ep = read_episode(RAW/record["split"]/record["parent_file"], frames="none")
        start = np.searchsorted(ep.frame_times, ep.frame_times[0] + record["crop_s"] - 1e-8)
        times = ep.frame_times[start:]
        gt = ep.ground_truth
        body = poses_to_matrices(interpolate_poses(gt[:, 0], gt[:, 1:8], times))
        camera = body @ ep.T_body_camera
        p = camera[:, :3, 3]
        cam_gt = (p - p[0]) @ camera[0, :3, :3]
        if (len(times) != len(row["times"]) or
                not np.allclose(times - times[0], row["times"], atol=1e-6) or
                not np.allclose(cam_gt, row["cam_gt"], atol=1e-4)):
            raise ValueError(f"Raw truth differs from shard: {record['file']}")
        rotation = body[:, :3, :3]
        if args.max_seconds:
            keep = int(np.sum(row["times"]-row["times"][0] <= args.max_seconds+1e-6))
            row = {k: (v[:keep] if k != "T_bc" else v) for k, v in row.items()}
            rotation = rotation[:keep]
        rel = rotation[0].T @ rotation
        gravity = rotation[0].T @ np.array([0., 0., 1.])
        total, tilt, yaw, yaw_only, tilt_only = decompose(row["R"].astype(np.float64), rel, gravity)
        attitudes = {"ours": row["R"].astype(np.float64), "truth": rel, "tilt_fixed": yaw_only, "yaw_fixed": tilt_only}
        if args.probe_uncalibrated:
            gyro = Orientation({"policy": "none", "startup_seconds": 1.})
            indices = range(start, start + len(rotation))
            packets = (ep.imu_window(k) if k > start else ep.imu[:0] for k in indices)
            attitudes["uncalibrated"] = np.stack([gyro.step(t, packet, 0.)
                                                  for t, packet in zip(times, packets)])
        out = {"file": record["file"], "flight": record["flight_id"], "crop_s": record["crop_s"],
               "seconds": float(row["times"][-1]-row["times"][0]),
               "final_deg": {"total": float(np.degrees(total[-1])), "tilt": float(np.degrees(tilt[-1])),
                             "yaw": float(np.degrees(yaw[-1]))},
               "rms_deg": {"total": float(np.degrees(np.sqrt(np.mean(total**2)))),
                           "tilt": float(np.degrees(np.sqrt(np.mean(tilt**2)))),
                           "yaw": float(np.degrees(np.sqrt(np.mean(yaw**2))))}}
        velocities = {"true-velocity": row["v"].astype(np.float64)}
        for run, weights in runs:
            velocities[run.name] = model_velocities(run, weights, row, device)
        out["ate"] = {name: {key: ate(integrate(v, {**row, "R": R}), row["cam_gt"]) for key, R in attitudes.items()}
                      for name, v in velocities.items()}
        rows.append(out)
        if record["crop_s"] == 0:
            t = row["times"]-row["times"][0]
            curves.setdefault("t", []).append((t, np.degrees(total), np.degrees(tilt), np.degrees(yaw)))
    summary = {"replays": len(rows)}
    for horizon in (10, 30, 60, 90):
        vals = [(np.interp(horizon, t, a), np.interp(horizon, t, b), np.interp(horizon, t, c))
                for t, a, b, c in curves["t"] if t[-1] >= horizon-.1]
        if vals:
            summary[f"static_start_deg_at_{horizon}s"] = {"flights": len(vals), **{
                k: [round(float(np.mean(x)), 2), round(float(np.median(x)), 2)] for k, x in zip(("total", "tilt", "yaw"), zip(*vals))}}
    names = list(rows[0]["ate"])
    summary["mean_ate"] = {n: {k: round(float(np.mean([r["ate"][n][k] for r in rows])), 4) for k in rows[0]["ate"][n]} for n in names}
    for seconds in (30, 60, 90):
        sub = [r for r in rows if abs(r["seconds"]-seconds) < 6]
        if sub:
            summary[f"mean_ate_{seconds}s_flights"] = {"replays": len(sub), **{n: {k: round(float(np.mean([r["ate"][n][k] for r in sub])), 4)
                                                        for k in sub[0]["ate"][n]} for n in names}}
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    tag = "campaign-dev" + (f"-{args.max_seconds:g}s" if args.max_seconds else "")
    (out/f"attitude-{tag}.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
