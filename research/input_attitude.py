"""Re-derive prepared shards with a different INPUT attitude policy (predeclared 2026-11-19, branch odometry/retrain-attitude).

Question: does the velocity network improve when its inputs (gyro-derotated image history, bias-corrected gyro
features, bias features, and the integration attitude R) use a better attitude, instead of only integrating its
frozen velocities through that attitude (attitude_bias.py)?

Most training parents (proxy domain) have no raw archive on this machine, so new shards are derived from the
existing rolling-policy shards, which hold everything the input pipeline consumed, except per-sample IMU rows:
  * per-frame gyro mean minus the bias in effect (imu[3:6]) and the bias itself (imu[43:46], learned bias = 0), so
    the raw packet mean gyro is recoverable; 4 ordered sub-packet means and counts; per-packet std;
  * R (rolling attitude): its per-frame increment dR_k = R_{k-1}^T R_k was integrated with the bias in effect at the
    START of step k (the previous frame's bias feature). With a new bias b' constant over the step,
    dR'_k = dR_k exp((b_old - b') dt_k) up to O(|w||db|dt^2) (exact for commuting rates; ~1e-5 rad per frame);
  * channel 0 = the resized current frame, which is exactly the history frame later warps use.
Then the image history is re-warped with streaming.portable_warp ("remap", bit-identical arithmetic to the
guest) using the new attitudes; gyro, sub-packet gyro, bias and "activated" features are rewritten; std,
accelerometer, availability and dt features are unchanged. --policy rolling is an identity check of this pipeline.

Policies (causal; no truth):
  static08  attitude_bias.py's "static08": bias 0 until the first frame whose packet starts at/after 0.8 s; if that
            window was still, bias = its mean gyro and the stored history (attitudes of past frames, used by later
            warps) is re-integrated; no later recalibration. Already-emitted R values keep their bias-0 values.
            Pooled stillness statistics come from per-packet means/stds/counts (gyro: exact; accelerometer norm:
            approximated by the norm of packet means and the pooled variance projected on gravity).
  kf_grid   static08 + attitude_bias.py's ungated "kf_grid" 3-state gyro-bias Kalman filter, measured every
            >=0.5 s by grid_rotation on the 128x96 channel-0 frames (K from imu[14], centred principal point).
            Validation (before training): at 128x96 the measurement is much worse than at native resolution
            (public mean attitude error 12.0 deg vs 6.1; campaign dev 15.0 vs 7.7; rolling 17.7 / 17.8), because
            grid_rotation's pixel thresholds were set for 160-320 px images. Not used for training.
  kf_grid_native  kf_grid computed by attitude_bias.attitudes on the native-resolution raw flight where this machine
            has it (campaign train/dev, public); otherwise (proxy, native D0 parents/dev, proxy-val) kf_grid at 128x96.
            The derived R and bias features then replace those of the shard as above.

    python input_attitude.py derive --policy static08 --manifest M.json --split train development \
        --sources DIR [DIR ...] --out DIR --workers 64
"""
import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from orientation import exp_so3
from streaming import portable_warp

BASELINES = (0.25, 1.0)
GYRO_INIT = 0.02 / np.sqrt(3)
GYRO_WALK = 0.0006
GYRO_WHITE = 0.07


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def counts(imu):
    """Samples per packet from the 4 ordered sub-packet count features (min(n/4,1); unclipped at 200/20 Hz)."""
    return np.rint(imu[:, [21, 28, 35, 42]] * 4).sum(1) * imu[:, 12]


def still_window(imu, n, upto):
    """attitude_bias.static08's stillness test over frames 1..upto-1 from pooled packet statistics."""
    sel = slice(1, upto)
    w = n[sel]
    N = w.sum()
    if N <= 40:
        return None
    bias_after = imu[:, 43:46] + imu[:, 46:49]
    gyro = imu[sel, 3:6] + bias_after[sel]
    accel = imu[sel, 0:3] * 9.81
    g_mean = (w[:, None] * gyro).sum(0) / N
    g_var = (w[:, None] * (imu[sel, 9:12] ** 2 + gyro ** 2)).sum(0) / N - g_mean ** 2
    a_mean = (w[:, None] * accel).sum(0) / N
    a_var = (w[:, None] * (imu[sel, 6:9] ** 2 + accel ** 2)).sum(0) / N - a_mean ** 2
    up = a_mean / max(np.linalg.norm(a_mean), 1e-9)
    norm_mean = (w * np.linalg.norm(accel, axis=1)).sum() / N
    norm_std = np.sqrt(max(float(up ** 2 @ a_var), 0.))
    still = (np.linalg.norm(g_mean) < 0.1 and np.sqrt(np.maximum(g_var, 0)).max() < 0.12 and
             abs(norm_mean - 9.81) < 0.3 and norm_std < 0.5)
    return g_mean if still else None


def derive(row, policy, external=None):
    """external: (R, bias_after) per frame from attitude_bias.attitudes(flight, "kf_grid") at native resolution."""
    from attitude_bias import grid_rotation
    imu, R0, t = row["imu"].astype(np.float64), row["R"].astype(np.float64), row["times"].astype(np.float64)
    images = row["images"]
    T = len(t)
    R_bc = row["T_bc"][:3, :3].astype(np.float64)
    h, w = images.shape[-2:]
    fx = float(row["imu"][0, 14]) * w
    K = np.array([[fx, 0, (w - 1) / 2], [0, fx, (h - 1) / 2], [0, 0, 1.]])
    Kinv = np.linalg.inv(K)
    bias_after = imu[:, 43:46] + imu[:, 46:49]
    b_old = np.vstack([np.zeros(3), bias_after[:-1]])      # bias integrated at step k
    has = imu[:, 12] > 0
    dt = np.r_[0., np.diff(t)]
    dR = np.einsum("kji,kjl->kil", R0[:-1], R0[1:])        # R_{k-1}^T R_k
    dR = np.concatenate([np.eye(3)[None], dR])
    n = counts(imu)
    if policy == "rolling":
        bias_new_after = bias_after.copy()
        activated = imu[:, 49].copy()
    else:
        bias_new_after = np.zeros((T, 3)); activated = np.zeros(T)

    def step(k, b):
        return dR[k] @ exp_so3((b_old[k] - b) * dt[k]) if has[k] else dR[k]

    R_hist = np.zeros((T, 3, 3)); R_out = np.zeros((T, 3, 3))
    R = np.eye(3); R_hist[0] = R_out[0] = R
    bias, P = np.zeros(3), np.full(3, GYRO_INIT ** 2)
    decided, anchor = False, 0
    windows = {"accepted": 0, "rejected": 0}
    for k in range(1, T):
        if policy == "rolling":
            R = R0[k]
        else:
            if not decided and (not has[k] or t[k - 1] >= t[0] + 0.8 - 1e-6):
                decided = True
                b = still_window(imu, n, k)
                if b is not None:
                    bias, P = b, np.full(3, GYRO_WHITE ** 2 / n[1:k].sum() + 1e-8)
                    Rr = np.eye(3)
                    for j in range(1, k):
                        Rr = Rr @ step(j, bias)
                        R_hist[j] = Rr               # past attitudes as now known (used by later warps)
                    R = Rr
            R = R @ step(k, bias)
            P = P + GYRO_WALK ** 2 * dt[k]
            if external is not None:
                R, bias = external[0][k], external[1][k]
            elif policy == "kf_grid" and t[k] - t[anchor] >= 0.5 - 1e-8:
                d = t[k] - t[anchor]
                relative = R_bc.T @ (R_out[anchor].T @ R) @ R_bc
                if row["imu"][anchor, 50] > 0 and row["imu"][k, 50] > 0:
                    delta, sigma = grid_rotation(images[anchor, 0], images[k, 0], K, relative)
                else:
                    delta, sigma = None, "unavailable"
                if delta is not None and np.linalg.norm(delta) <= 0.05:
                    residual = R_bc @ delta
                    s = sigma / d
                    gain = P / (P + s ** 2)
                    bias = bias + gain * (-(residual / d))
                    P = (1 - gain) * P
                    windows["accepted"] += 1
                else:
                    windows["rejected"] += 1
                anchor = k
            bias_new_after[k] = bias
            activated[k] = float(decided and (np.any(bias != 0)))
        R_out[k] = R
        R_hist[k] = R
    # features
    new_imu = row["imu"].copy()
    shift = bias_after - bias_new_after                      # gyro features are mean - bias
    new_imu[:, 3:6] = (imu[:, 3:6] + shift * has[:, None]).astype(np.float32)
    for i in range(4):
        cols = slice(15 + 7 * i + 3, 15 + 7 * i + 6)
        nonempty = imu[:, 15 + 7 * i + 6] > 0
        new_imu[:, cols] = (imu[:, cols] + shift * nonempty[:, None]).astype(np.float32)
    new_imu[:, 43:46] = bias_new_after.astype(np.float32)
    new_imu[:, 49] = activated.astype(np.float32)
    # re-warp the image history with the new attitudes (history R values as known at each frame)
    yy, xx = np.indices((h, w))
    pixels = np.stack((xx.ravel(), yy.ravel(), np.ones(xx.size)))
    out = images.copy()
    history = []                                             # (time, index)
    avail = row["imu"][:, 50] > 0
    known = R_hist.copy() if policy == "rolling" else None
    # For static08/kf_grid the history attitudes change once (at the static decision); reproduce what was known
    # at frame k: frames < decision frame were re-integrated at the decision, which happens before frame k's warps.
    decision = next((k for k in range(1, T) if not has[k] or t[k - 1] >= t[0] + 0.8 - 1e-6), T)
    for k in range(T):
        out[k, 1:] = 0
        for index, age in enumerate(BASELINES):
            match = next((j for (tj, j) in reversed(history) if tj <= t[k] - age + 1e-8), None)
            if match is None:
                continue
            if policy == "rolling":
                previous_R = R0[match]
            else:
                previous_R = R_hist[match] if k >= decision else R_out[match]
            rotation = R_bc.T @ R_out[k].T @ previous_R @ R_bc
            inverse = K @ rotation.T @ Kinv
            out[k, 1 + index], out[k, 3 + index] = portable_warp(images[match, 0], inverse, pixels, True)
        if avail[k]:
            history.append((t[k], k))
        while len(history) > 2 and history[1][0] <= t[k] - BASELINES[-1] + 1e-8:
            history.pop(0)
    return {**row, "images": out, "imu": new_imu, "R": R_out}, windows


def raw_archive(record):
    """Native-resolution raw flight for a record, when this machine has it (campaign train/dev, public)."""
    name = record.get("parent_file") or ""
    if record.get("domain") == "native-campaign":
        split = record.get("split") or name.split("-")[0]
        path = Path("/data/backups/rganapa/Sebastian/gen/raw") / split / name
        return path if path.exists() else None
    if record.get("domain") == "public":
        return next(Path("/data/backups/rganapa/Sebastian/tmp/viobench-public-replay").glob(f"*/{name}"), None)
    return None


def job(args):
    record, source, out_dir, policy = args
    with np.load(source, allow_pickle=False) as data:
        row = {k: data[k] for k in data.files}
    cv2.setNumThreads(1); cv2.setRNGSeed(217)
    external, resolution = None, "shard"
    if policy == "kf_grid_native":
        archive = raw_archive(record)
        if archive is not None:
            from attitude_bias import attitudes
            from common import Flight
            flight = Flight(archive, crop=float(record.get("crop_s", 0)))
            n = len(row["times"])
            assert len(flight.ft) >= n and np.allclose(flight.ft[:n], row["times"] - row["times"][0], atol=1e-6)
            trace = []
            R_ext, windows, _ = attitudes(flight, "kf_grid", trace=trace)
            external, resolution = (R_ext[:n], np.asarray(trace)[:n]), "native"
    new, kf = derive(row, "kf_grid" if policy == "kf_grid_native" else policy, external)
    windows = windows if external is not None else kf
    tmp = Path(out_dir) / f"tmp-{record['sha256'][:16]}.npz"
    np.savez_compressed(tmp, **new)
    digest = sha(tmp)
    final = Path(out_dir) / f"{digest}.npz"
    tmp.replace(final)
    return {**record, "file": final.name, "sha256": digest, "derived_from": record["sha256"],
            "input_policy": policy, "kf_windows": windows, "kf_resolution": resolution}


def find(record, sources):
    for s in sources:
        p = Path(s) / record["file"]
        if p.exists():
            return p
    raise FileNotFoundError(record["file"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("derive",))
    parser.add_argument("--policy", choices=("rolling", "static08", "kf_grid", "kf_grid_native"), required=True)
    parser.add_argument("--manifest", type=Path, required=True, help="manifest (datasets) or records JSON")
    parser.add_argument("--split", nargs="+", default=["train", "development"])
    parser.add_argument("--sources", nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=32)
    args = parser.parse_args()
    src = json.loads(args.manifest.read_text())
    groups = {s: src["datasets"][s] for s in args.split} if "datasets" in src else {"records": src["records"]}
    args.out.mkdir(parents=True, exist_ok=True)
    done = {}
    result = {k: [] for k in groups}
    with ProcessPoolExecutor(args.workers) as pool:
        for name, records in groups.items():
            jobs = [(r, find(r, args.sources), str(args.out), args.policy) for r in records]
            for i, r in enumerate(pool.map(job, jobs, chunksize=1)):
                result[name].append(r)
                if i % 100 == 0:
                    print(name, i, len(records), flush=True)
    if "datasets" in src:
        manifest = {**src, "datasets": result, "status": "completed",
                    "input_policy": args.policy, "derived_from_manifest_sha256": sha(args.manifest),
                    "sources": {**src.get("sources", {}), "input_attitude.py": sha(Path(__file__))}}
        (args.out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    else:
        (args.out / "records.json").write_text(json.dumps({"records": result["records"], "input_policy": args.policy,
                                                           "derived_from_sha256": sha(args.manifest)}, indent=1))


if __name__ == "__main__":
    main()
