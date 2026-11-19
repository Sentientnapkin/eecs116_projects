"""Frozen-velocity attitude ablations: continuous visual gyro-bias estimation (predeclared, 2026-11-19).

    python attitude_bias.py --set public|campaign-dev --runs <run dirs...> --output <dir> [--workers 24]

Every arm integrates the SAME frozen learned body velocities (each run's own predictions on the prepared row) through
a different attitude sequence, with `odometry_eval.integrate`, so differences are attitude-only:

  control      the prepared row's attitude (our rolling-calibrated gyro integration; what deployed models use)
  static08     gyro integration with bias from the first 0.8 s if that window is still (OpenVINS's static window),
               then held fixed; 0 when the start is moving. Causal: bias 0 until the window has arrived, then the
               stored history is re-integrated (fixed 2026-11-19 after a first version applied it from frame 1)
  kf           static08 initialization plus a 3-state Kalman filter on gyro bias, measured by visual relative
               rotations every 0.5 s: residual = log(gyro_rel^T visual_rel) ~ (b_hat - b_true) * dt. Prior and
               random walk from the simulator's documented IMU model (init uniform +-0.02 rad/s, walk 0.0006).
               The visual measurement is visual_attitude.visual_delta (gyro-compensated KLT, forward/backward check,
               essential RANSAC + cheirality + parallax gates, low-parallax rotation fit).
  kf_att       kf plus applying the accepted visual window correction to the attitude itself (gain 1)
  oracle_bias  DIAGNOSTIC ONLY: gyro minus the true bias (from truth angular velocity); never deployable

What is new versus the earlier visual-attitude arm (0.79% dev gain): that arm nudged the attitude by 35% of each
window's residual and never changed the gyro bias, so every later window drifted at the same rate. Here the residuals
estimate the bias, which then corrects every later gyro increment.
"""
import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from common import Flight
from orientation import exp_so3

GYRO_INIT = 0.02 / np.sqrt(3)          # std of U(-0.02, 0.02)
GYRO_WALK = 0.0006                       # rad/s/sqrt(s)
GYRO_WHITE = 0.07                        # per 200 Hz sample
ARMS = ("control", "static08", "kf", "kf_att", "kf_grid", "kf_grid_att", "kf_grid_gated", "oracle_bias")


def log_so3(R):
    return cv2.Rodrigues(np.asarray(R, dtype=np.float64))[0].ravel()


def gray(frame):
    frame = np.asarray(frame)
    return cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY) if frame.ndim == 3 else frame


def grid_rotation(first, last, K, relative):
    """kf_grid's measurement (OpenVINS-style support): corners detected per 4x4 grid cell at a low quality threshold,
    gyro-predicted forward KLT, backward check, then essential RANSAC + cheirality when parallax supports it, else a
    robust rotation-only fit. Returns (right-multiplicative camera correction, sigma rad) or (None, reason)."""
    from orientation import fit_visual_rotation
    h, w = first.shape
    points = []
    for gy in range(4):
        for gx in range(4):
            cell = first[gy*h//4:(gy+1)*h//4, gx*w//4:(gx+1)*w//4]
            found = cv2.goodFeaturesToTrack(cell, 10, 0.003, 5)
            if found is not None:
                points.append(found[:, 0] + [gx*w//4, gy*h//4])
    if not points:
        return None, "no corners"
    points = np.concatenate(points).astype(np.float32)[:, None]
    if len(points) < 16:
        return None, "few corners"
    guess = cv2.perspectiveTransform(points, K @ relative.T @ np.linalg.inv(K)).astype(np.float32)
    tracked, found, _ = cv2.calcOpticalFlowPyrLK(first, last, points, guess.copy(), flags=cv2.OPTFLOW_USE_INITIAL_FLOW)
    back, returned, _ = cv2.calcOpticalFlowPyrLK(last, first, tracked, points.copy(), flags=cv2.OPTFLOW_USE_INITIAL_FLOW)
    good = found.ravel().astype(bool) & returned.ravel().astype(bool) & (np.linalg.norm((back - points)[:, 0], axis=1) < 0.8)
    old, new = points[good, 0], tracked[good, 0]
    cells = {(int(4*x/w), int(4*y/h)) for x, y in old}
    if len(old) < 16 or len(cells) < 5:
        return None, "few tracks"
    inverse = np.linalg.inv(K)
    flow = np.linalg.norm((tracked - guess)[good, 0], axis=1)
    if np.median(flow) <= 1.0:
        fit = fit_visual_rotation(np.c_[old, np.ones(len(old))] @ inverse.T, np.c_[new, np.ones(len(new))] @ inverse.T, relative)
        if fit is None or fit[1] > 0.012:
            return None, "rotation fit"
        return fit[0], 0.002
    E, mask = cv2.findEssentialMat(old, new, K, method=cv2.RANSAC, prob=0.999, threshold=1.0, maxIters=500)
    if E is None or E.shape != (3, 3):
        return None, "essential"
    count, old_to_new, _, cheiral = cv2.recoverPose(E, old, new, K, mask=mask)
    if count < max(12, 0.5 * len(old)):
        return None, "cheirality"
    return cv2.Rodrigues(relative.T @ old_to_new.T)[0].ravel(), 0.004


def integrate_packet(R, previous, t, packet, bias):
    """Orientation.step's integration: each IMU row's rate held until the next row, the last up to the frame time."""
    if not len(packet):
        return R, t
    last = packet[0, 4:7]
    for row in packet:
        row_time = max(previous, min(float(row[0]), t))
        R = R @ exp_so3((row[4:7] - bias) * (row_time - previous))
        previous, last = row_time, row[4:7]
    return R @ exp_so3((last - bias) * (t - previous)), t


def attitudes(flight, arm, true_bias=None):
    """Causal attitude for every frame (world_from_body, identity at frame 0, like the prepared rows).

    Static window (OpenVINS-style, 0.8 s): frames are integrated with bias 0 until the first frame whose IMU packet
    starts at or after 0.8 s; then, if the window was still, the bias is set and the stored history re-integrated
    (past data only). Already-emitted attitudes keep their bias-0 values."""
    cv2.setRNGSeed(217)  # RANSAC stream restarts per flight, as in the C++ guest
    t, windows = flight.ft, flight.win
    K = np.array([[flight.K["fx"], 0, flight.K["cx"]], [0, flight.K["fy"], flight.K["cy"]], [0, 0, 1.]])
    R_bc = flight.T_bc[:3, :3]
    bias, P = np.zeros(3), np.full(3, GYRO_INIT**2)
    decided = arm == "oracle_bias"
    R, previous = np.eye(3), t[0]
    out = [R.copy()]
    images = [gray(flight.frames[0])] if arm.startswith("kf") else None
    anchor, count = 0, {"accepted": 0, "rejected": 0}
    for k in range(1, len(t)):
        packet = windows[k]
        if not decided and (not len(packet) or packet[0, 0] >= t[0] + 0.8):
            decided = True
            still = np.concatenate([w for w in windows[1:k] if len(w)]) if k > 1 else np.empty((0, 7))
            if len(still) > 40:
                rates, accel = still[:, 4:7], np.linalg.norm(still[:, 1:4], axis=1)
                # still: small mean rate, rate and specific-force spread near sensor noise (0.07 rad/s, 0.28 m/s^2)
                if np.linalg.norm(rates.mean(0)) < 0.1 and np.std(rates, 0).max() < 0.12 and \
                        abs(accel.mean() - 9.81) < 0.3 and np.std(accel) < 0.5:
                    bias, P = rates.mean(0), np.full(3, GYRO_WHITE**2 / len(rates) + 1e-8)
                    R, previous = np.eye(3), t[0]
                    for j in range(1, k):
                        R, previous = integrate_packet(R, previous, t[j], windows[j], bias)
        b = true_bias[k] if arm == "oracle_bias" else bias
        R, previous = integrate_packet(R, previous, t[k], packet, b)
        P = P + GYRO_WALK**2 * (t[k] - t[k - 1])
        if images is not None:
            images.append(gray(flight.frames[k]))
            if t[k] - t[anchor] >= 0.5 - 1e-8:
                dt = t[k] - t[anchor]
                relative = R_bc.T @ (out[anchor].T @ R) @ R_bc
                if arm.startswith("kf_grid"):
                    delta, sigma = grid_rotation(images[anchor], images[k], K, relative)
                else:
                    from visual_attitude import visual_delta  # torch-free callers use kf_grid only
                    delta, method = visual_delta(images[anchor], images[k], K, relative)
                    sigma = 0.0015 if method == "low_parallax" else 0.003
                innovation_ok = True
                if delta is not None and arm == "kf_grid_gated":
                    # 3-sigma innovation gate per axis (added 2026-11-19 after wasm/Python divergence from one outlier)
                    innovation = -(R_bc @ delta) / dt
                    innovation_ok = bool(np.all(np.abs(innovation) <= 3 * np.sqrt(P + (sigma / dt)**2)))
                if delta is not None and np.linalg.norm(delta) <= 0.05 and innovation_ok:
                    residual = R_bc @ delta                     # body frame, ~ (b_hat - b_true) * dt
                    sigma = sigma / dt
                    gain = P / (P + sigma**2)
                    bias = bias + gain * (-(residual / dt))
                    P = (1 - gain) * P
                    if arm.endswith("_att"):
                        R = R @ exp_so3(residual)
                    count["accepted"] += 1
                else:
                    count["rejected"] += 1
                images[anchor] = None
                anchor = k
        out.append(R.copy())
    return np.stack(out), count, bias


def true_gyro_bias(flight):
    """DIAGNOSTIC: per-frame mean (measured - true) angular rate in body axes, from truth attitude."""
    t, R = flight.ft, flight.R
    bias = np.zeros((len(t), 3))
    for k in range(1, len(t)):
        omega = log_so3(R[k - 1].T @ R[k]) / (t[k] - t[k - 1])
        packet = flight.win[k]
        bias[k] = (packet[:, 4:7].mean(0) if len(packet) else omega) - omega
    # smooth over 2 s (the true bias is a slow random walk; this removes per-frame noise of the difference)
    kernel = np.ones(41) / 41
    return np.stack([np.convolve(np.pad(bias[:, i], 20, mode="edge"), kernel, "valid") for i in range(3)], 1)


def episode(job):
    archive, crop, velocities, row_R, row_T_bc, row_times, cam_gt, meta = job
    from odometry_eval import integrate, metrics
    flight = Flight(archive, crop=crop)
    n = len(row_times)
    assert len(flight.ft) >= n and np.allclose(flight.ft[:n], row_times - row_times[0], atol=1e-6), archive
    row = {"R": row_R, "T_bc": row_T_bc, "times": row_times}
    tb = true_gyro_bias(flight)
    rotations, info = {"control": row_R}, {}
    for arm in ARMS[1:]:
        R, count, bias = attitudes(flight, arm, tb)
        rotations[arm], info[arm] = R[:n], {"windows": count, "final_bias_error": float(np.linalg.norm(bias - tb[-1]))}
    if meta.get("save_dir"):
        np.savez(Path(meta["save_dir"]) / f"{meta['file']}.npz", kf_grid=rotations["kf_grid"], kf_grid_gated=rotations["kf_grid_gated"], times=row_times,
                 **{f"v_{run}": v for run, v in velocities.items()})
    rows = []
    for run, v in velocities.items():
        r = {**meta, "run": run}
        for arm, R in rotations.items():
            p = integrate(v, {**row, "R": R})
            r[arm] = metrics(p, cam_gt, row_times)["ate"]
            for horizon in (30, 60):
                keep = int(np.sum(row_times - row_times[0] <= horizon + 1e-6))
                if row_times[-1] - row_times[0] >= horizon - 0.1:
                    r[f"{arm}_{horizon}s"] = metrics(p[:keep], cam_gt[:keep], row_times[:keep])["ate"]
        r.pop("save_dir", None)
        rows.append(r)
    return rows, {meta["file"]: info}


def main():
    import torch
    from odometry_data import load_row, motion_labels
    from odometry_eval import load_weights, model_velocities
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--set", choices=("public", "campaign-dev"), required=True)
    parser.add_argument("--runs", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    cv2.setNumThreads(1); cv2.setRNGSeed(217)
    if args.set == "public":
        root = Path("/data/backups/rganapa/Sebastian/baselines/public-prepared")
        records = json.loads((root / "records.json").read_text())["records"]
        archive = lambda r: next(Path("/data/backups/rganapa/Sebastian/tmp/viobench-public-replay").glob(f"*/{r['parent_file']}"))
    else:
        root = Path("data/native-campaign/shards")
        records = json.loads(Path("data/native-campaign/dev-records.json").read_text())["records"]
        archive = lambda r: Path("/data/backups/rganapa/Sebastian/gen/raw/dev") / r["parent_file"]
    records = records[:args.limit]
    weights = {run.name: load_weights(run, "best") for run in args.runs}
    device = "cuda" if torch.cuda.is_available() else "cpu"
    jobs = []
    for record in records:
        row = load_row(root, record)
        lab = motion_labels(row["v"], row["times"], row["cam_gt"])
        meta = {"file": record["file"], "scene": record["scene"], "catalog": record.get("catalog"),
                "start": "moving" if record.get("crop_s") else "static", "seconds": float(row["times"][-1] - row["times"][0]),
                "motion": "backward/lateral" if lab["backward"].mean() > .05 or lab["lateral"].mean() > .1 else "ordinary"}
        velocities = {name: model_velocities(run, weights[name], row, device) for name, run in
                      ((r.name, r) for r in args.runs)}
        jobs.append((archive(record), float(record.get("crop_s", 0)), velocities, row["R"], row["T_bc"],
                     row["times"], row["cam_gt"], meta))
    (args.output / "attitudes").mkdir(parents=True, exist_ok=True)
    for job in jobs:
        job[-1]["save_dir"] = str(args.output / "attitudes")
    rows, info = [], {}
    with ProcessPoolExecutor(args.workers) as pool:
        for r, i in pool.map(episode, jobs):
            rows += r; info.update(i)
            print(r[0]["file"][:12], {a: round(float(np.mean([x[a] for x in r])), 3) for a in ARMS}, flush=True)
    summary = {}
    for group, sel in (("all", lambda r: True), ("ordinary", lambda r: r["motion"] == "ordinary"),
                       ("backward/lateral", lambda r: r["motion"] != "ordinary"),
                       ("static", lambda r: r["start"] == "static"), ("moving", lambda r: r["start"] == "moving"),
                       ("procthor", lambda r: r["catalog"] == "procthor"), ("hssd", lambda r: r["catalog"] == "hssd-val")):
        group_rows = [r for r in rows if sel(r)]
        if group_rows:
            summary[group] = {f"{a}{h}": round(float(np.mean([r[f'{a}{h}'] for r in group_rows if f'{a}{h}' in r])), 4)
                              for a in ARMS for h in ("", "_30s", "_60s")
                              if any(f"{a}{h}" in r for r in group_rows)}
            summary[group]["replays"] = len(group_rows)
    by_run = {run: {a: round(float(np.mean([r[a] for r in rows if r["run"] == run])), 4) for a in ARMS}
              for run in weights}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps({"set": args.set, "summary": summary, "by_run": by_run,
                                                          "rows": rows, "windows": info}, indent=1))
    print(json.dumps({"summary": summary, "by_run": by_run}, indent=1))


if __name__ == "__main__":
    main()
