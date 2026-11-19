"""Frozen-velocity attitude arms for a cheaper kf_grid measurement (peak-fuel workstream, predeclared 2026-11-19).

    python fuel_attitude.py --set public|campaign-dev --velocities <attitude_bias.py output>/attitudes --output <dir>

Torch-free (runs in the OpenCV 4.12 venv, the wasm guest's OpenCV version). Each replay's six frozen model velocity
streams (B-D0 and N2, seeds 217-219) are read from the npz files that attitude_bias.py saved, and integrated through
every arm's attitude with the same reference integration, so differences are attitude-only.

Arms (all ungated, like the deployed default C++ build; parameters: corners per 4x4 cell, KLT window, KLT pyramid
levels, essential RANSAC max iterations, update delay in frames):
  kf_grid      reference, measurement and update on the window's last frame (10, 21, 3, 500, 0)
  split        the -DODO_KF_GRID_SPLIT schedule: identical measurement, Kalman update 2 frames later (10, 21, 3, 500, 2)
  split_l2     split with 2 pyramid levels                                                        (10, 21, 2, 500, 2)
  split_w15    split with a 15x15 KLT window                                                      (10, 15, 3, 500, 2)
  split_c6     split with 6 corners per cell                                                      (6, 21, 3, 500, 2)
  split_r100   split with at most 100 RANSAC iterations                                           (10, 21, 3, 100, 2)
  split_lite   split with (6, 15, 2, 100)
  staged4      the -DODO_KF_GRID_STAGED schedule with 1 track slice: identical measurement, update 4 frames later
  staged6      -DODO_KF_GRID_STAGED with 2 track slices: identical measurement, update 6 frames later
               (staged4/staged6 added 2026-11-19 after the split wasm's stage profile, before running them; same gate
               as split: within +0.010 m of kf_grid on public and campaign dev)
  staged6r     staged6 plus replay (6th parameter): the delayed update uses the covariance saved at the window's
               last frame b, then re-integrates the gyro rows of frames b+1..k from the attitude at b with the new
               bias and re-adds the covariance walk, so the filter state after frame k equals kf_grid's (only the
               attitudes reported at b+1..k-1 keep the old bias). Dropped if the static window reset the bias in
               between (kf_grid's reset overrides it too). Added 2026-11-19 after staged6 failed the public gate.
  staged8r     staged6r with 3 track slices (update 8 frames later)
  staged6r_r30 / staged6r_r15   staged6r with at most 30 / 15 essential RANSAC iterations (numerics change)
Gate (predeclared): a numerics-changing arm is acceptable for porting if its 6-model mean full ATE is within +0.010 m of
`split` on public AND on campaign dev (120 replays). `split` itself is acceptable within +0.010 m of `kf_grid`.
Which arms are actually ported depends on the measured per-stage fuel of the split wasm (largest stage first).
"""
import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from attitude_bias import GYRO_INIT, GYRO_WALK, GYRO_WHITE, gray, integrate_packet
from common import Flight
from orientation import fit_visual_rotation

ARMS = {"kf_grid": (10, 21, 3, 500, 0), "split": (10, 21, 3, 500, 2), "split_l2": (10, 21, 2, 500, 2),
        "split_w15": (10, 15, 3, 500, 2), "split_c6": (6, 21, 3, 500, 2), "split_r100": (10, 21, 3, 100, 2),
        "split_lite": (6, 15, 2, 100, 2),
        "staged4": (10, 21, 3, 500, 4), "staged6": (10, 21, 3, 500, 6),
        "staged6r": (10, 21, 3, 500, 6, True), "staged8r": (10, 21, 3, 500, 8, True),
        "staged6r_r30": (10, 21, 3, 30, 6, True), "staged6r_r15": (10, 21, 3, 15, 6, True)}


def grid_rotation(first, last, K, relative, corners, win, levels, iters):
    """attitude_bias.grid_rotation with the cost parameters exposed (defaults there: 10, 21, 3, 500)."""
    h, w = first.shape
    points = []
    for gy in range(4):
        for gx in range(4):
            found = cv2.goodFeaturesToTrack(first[gy*h//4:(gy+1)*h//4, gx*w//4:(gx+1)*w//4], corners, 0.003, 5)
            if found is not None:
                points.append(found[:, 0] + [gx*w//4, gy*h//4])
    if not points:
        return None, "no corners"
    points = np.concatenate(points).astype(np.float32)[:, None]
    if len(points) < 16:
        return None, "few corners"
    guess = cv2.perspectiveTransform(points, K @ relative.T @ np.linalg.inv(K)).astype(np.float32)
    lk = dict(winSize=(win, win), maxLevel=levels, flags=cv2.OPTFLOW_USE_INITIAL_FLOW,
              criteria=(cv2.TERM_CRITERIA_COUNT + cv2.TERM_CRITERIA_EPS, 30, 0.01))
    tracked, found, _ = cv2.calcOpticalFlowPyrLK(first, last, points, guess.copy(), **lk)
    back, returned, _ = cv2.calcOpticalFlowPyrLK(last, first, tracked, points.copy(), **lk)
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
    E, mask = cv2.findEssentialMat(old, new, K, method=cv2.RANSAC, prob=0.999, threshold=1.0, maxIters=iters)
    if E is None or E.shape != (3, 3):
        return None, "essential"
    count, old_to_new, _, _ = cv2.recoverPose(E, old, new, K, mask=mask)
    if count < max(12, 0.5 * len(old)):
        return None, "cheirality"
    return cv2.Rodrigues(relative.T @ old_to_new.T)[0].ravel(), 0.004


def attitudes(flight, params):
    """attitude_bias.attitudes(arm="kf_grid") with cost parameters and an update delay (frames)."""
    corners, win, levels, iters, delay = params[:5]
    replay = len(params) > 5 and params[5]
    resets = 0
    cv2.setRNGSeed(217)
    t, windows = flight.ft, flight.win
    K = np.array([[flight.K["fx"], 0, flight.K["cx"]], [0, flight.K["fy"], flight.K["cy"]], [0, 0, 1.]])
    R_bc = flight.T_bc[:3, :3]
    bias, P = np.zeros(3), np.full(3, GYRO_INIT**2)
    decided = False
    R, previous = np.eye(3), t[0]
    out = [R.copy()]
    images = [gray(flight.frames[0])]
    anchor, count, pending = 0, {"accepted": 0, "rejected": 0}, None
    for k in range(1, len(t)):
        packet = windows[k]
        if not decided and (not len(packet) or packet[0, 0] >= t[0] + 0.8):
            decided = True
            still = np.concatenate([w for w in windows[1:k] if len(w)]) if k > 1 else np.empty((0, 7))
            if len(still) > 40:
                rates, accel = still[:, 4:7], np.linalg.norm(still[:, 1:4], axis=1)
                if np.linalg.norm(rates.mean(0)) < 0.1 and np.std(rates, 0).max() < 0.12 and \
                        abs(accel.mean() - 9.81) < 0.3 and np.std(accel) < 0.5:
                    bias, P = rates.mean(0), np.full(3, GYRO_WHITE**2 / len(rates) + 1e-8)
                    resets += 1
                    R, previous = np.eye(3), t[0]
                    for j in range(1, k):
                        R, previous = integrate_packet(R, previous, t[j], windows[j], bias)
        R, previous = integrate_packet(R, previous, t[k], packet, bias)
        P = P + GYRO_WALK**2 * (t[k] - t[k - 1])
        images.append(gray(flight.frames[k]))
        if t[k] - t[anchor] >= 0.5 - 1e-8:
            # a pending update always lands before the next window ends (delay < 10 frames)
            dt = t[k] - t[anchor]
            relative = R_bc.T @ (out[anchor].T @ R) @ R_bc
            delta, sigma = grid_rotation(images[anchor], images[k], K, relative, corners, win, levels, iters)
            pending = (k + delay, delta, sigma, dt, P.copy(), k, resets)
            images[anchor] = None
            anchor = k
        if pending is not None and pending[0] == k:
            _, delta, sigma, dt, P_b, b, resets_b = pending
            pending = None
            if replay and resets != resets_b:
                delta = None  # the static-window reset overrode this update in kf_grid as well
            elif replay:
                P_now, P = P, P_b
            if delta is not None and np.linalg.norm(delta) <= 0.05:
                residual = R_bc @ delta
                sigma = sigma / dt
                gain = P / (P + sigma**2)
                bias = bias + gain * (-(residual / dt))
                P = (1 - gain) * P
                count["accepted"] += 1
                if replay:
                    R, previous = out[b], t[b]
                    for j in range(b + 1, k + 1):
                        R, previous = integrate_packet(R, previous, t[j], windows[j], bias)
                        P = P + GYRO_WALK**2 * (t[j] - t[j - 1])
            else:
                count["rejected"] += 1
                if replay and resets == resets_b:
                    P = P_now
        out.append(R.copy())
    return np.stack(out), count


def integrate(v, row):  # odometry_eval.integrate (torch-free copy)
    world = (row["R"] @ v[..., None]).squeeze(-1)
    p = np.zeros_like(world)
    p[1:] = np.cumsum(.5*(world[1:]+world[:-1])*np.diff(row["times"])[:, None], axis=0)
    arm, rot = row["T_bc"][:3, 3], row["T_bc"][:3, :3]
    return (p+row["R"]@arm-arm)@rot


def ate(p, truth):
    return float(np.sqrt(np.mean(np.sum((p - truth)**2, axis=1))))


def motion(v, times):  # odometry_data.motion_labels backward/lateral (torch-free copy)
    n = 5
    pad = np.pad(np.asarray(v, float), [(2, 2), (0, 0)], mode="edge")
    v = np.stack([np.convolve(pad[:, c], np.ones(n)/n, mode="valid") for c in range(3)], 1)
    moving = np.linalg.norm(v, axis=1) > .2
    backward, lateral = moving & (v[:, 0] < -.2), moving & (np.abs(v[:, 1]) > .2)
    return "backward/lateral" if backward.mean() > .05 or lateral.mean() > .1 else "ordinary"


def episode(job):
    archive, crop, shard, velocities_file, meta, arms = job
    cv2.setNumThreads(1)
    with np.load(shard) as d:
        row = {k: d[k] for k in ("R", "T_bc", "times", "cam_gt", "v")}
    with np.load(velocities_file) as d:
        velocities = {k[2:]: d[k] for k in d.files if k.startswith("v_")}
    flight = Flight(archive, crop=crop)
    n = len(row["times"])
    assert np.allclose(flight.ft[:n], row["times"] - row["times"][0], atol=1e-6), archive
    meta = {**meta, "motion": motion(row["v"], row["times"])}
    rows, info = [], {}
    rotations = {}
    for arm in arms:
        R, count = attitudes(flight, ARMS[arm])
        rotations[arm], info[arm] = R[:n], count
    for run, v in velocities.items():
        r = {**meta, "run": run}
        for arm, R in rotations.items():
            r[arm] = ate(integrate(v, {**row, "R": R}), row["cam_gt"])
        rows.append(r)
    return rows, {meta["file"]: info}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--set", choices=("public", "campaign-dev"), required=True)
    parser.add_argument("--velocities", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--arms", nargs="+", default=list(ARMS))
    parser.add_argument("--workers", type=int, default=24)
    args = parser.parse_args()
    if args.set == "public":
        root = Path("/data/backups/rganapa/Sebastian/baselines/public-prepared")
        records = json.loads((root / "records.json").read_text())["records"]
        archive = lambda r: next(Path("/data/backups/rganapa/Sebastian/tmp/viobench-public-replay").glob(f"*/{r['parent_file']}"))
    else:
        root = Path("data/native-campaign/shards")
        records = json.loads(Path("data/native-campaign/dev-records.json").read_text())["records"]
        archive = lambda r: Path("/data/backups/rganapa/Sebastian/gen/raw/dev") / r["parent_file"]
    jobs = [(archive(r), float(r.get("crop_s", 0)), root / r["file"], args.velocities / f"{r['file']}.npz",
             {"file": r["file"], "catalog": r.get("catalog"), "start": "moving" if r.get("crop_s") else "static"},
             args.arms) for r in records]
    rows, info = [], {}
    with ProcessPoolExecutor(args.workers) as pool:
        for r, i in pool.map(episode, jobs):
            rows += r; info.update(i)
            print(r[0]["file"][:12], {a: round(float(np.mean([x[a] for x in r])), 3) for a in args.arms}, flush=True)
    groups = {"all": lambda r: True, "ordinary": lambda r: r["motion"] == "ordinary",
              "backward/lateral": lambda r: r["motion"] != "ordinary", "static": lambda r: r["start"] == "static",
              "moving": lambda r: r["start"] == "moving", "procthor": lambda r: r["catalog"] == "procthor",
              "hssd": lambda r: r["catalog"] == "hssd-val"}
    summary = {}
    for name, sel in groups.items():
        sub = [r for r in rows if sel(r)]
        if sub:
            summary[name] = {a: round(float(np.mean([r[a] for r in sub])), 4) for a in args.arms} | {"replays": len(sub)}
    by_run = {run: {a: round(float(np.mean([r[a] for r in rows if r["run"] == run])), 4) for a in args.arms}
              for run in sorted({r["run"] for r in rows})}
    windows = {a: {k: int(sum(v[a][k] for v in info.values())) for k in ("accepted", "rejected")} for a in args.arms}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps({"set": args.set, "arms": {a: ARMS[a] for a in args.arms},
                                                          "summary": summary, "by_run": by_run, "windows": windows,
                                                          "rows": rows}, indent=1))
    print(json.dumps({"summary": summary, "by_run": by_run, "windows": windows}, indent=1))


if __name__ == "__main__":
    main()
