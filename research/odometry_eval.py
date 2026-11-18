"""Full-trajectory evaluation of trained odometry runs and deployed baselines on identical flights.

    ./odometry_env.sh odometry_eval.py --runs results/loop/D0-ssm results/loop/D2-ssm \
        --deployed ema ssm --control D0-ssm --output results/eval/d-series [--set dev|proxy-val]

Every replay carries state continuously through the whole (cropped) flight. Trained models run on
the prepared shards (the training preprocessing); deployed models replay the raw flight
through their own guest preprocessing; all are scored against the same camera-frame-zero
ground truth. Overlapping crops of one parent are reported but never counted as independent
trials: scene-level paired comparisons average a scene's rows first.
"""
import argparse
import io
import json
from pathlib import Path

import numpy as np
import torch
from safetensors.torch import load_file

from odometry_data import load_row, CATEGORIES, motion_labels
from odometry_models import OdometryNet, split_output
from odometry_store import open_store

ROOT = Path(__file__).resolve().parent
# Submitted guest models (only needed for --deployed). Override with GUEST_DIR elsewhere.
import os
GUEST = Path(os.environ.get("GUEST_DIR",
             "/Users/School/Desktop/Fa26 Berkeley/EECS 116/eecs116_projects/.claude/worktrees/"
             "metric-speed-sources-9eeecc/research/results/20261118T024046Z-robust-guest-7e90eb87"))


def metrics(p, truth, times, v_pred=None, v_true=None):
    err = np.linalg.norm(p-truth, axis=1)
    out = {"ate": float(np.sqrt(np.mean(err**2))), "final_error": float(err[-1])}
    for lo, hi in ((0, 10), (10, 20), (20, 30), (30, 60), (60, 90)):
        m = (times >= lo) & (times < hi)
        if m.any(): out[f"ate_{lo}_{hi}s"] = float(np.sqrt(np.mean(err[m]**2)))
    if v_pred is not None:
        sp, st = np.linalg.norm(v_pred, axis=1), np.linalg.norm(v_true, axis=1)
        moving = st > .2
        out.update({"velocity_rmse": float(np.sqrt(np.mean(np.sum((v_pred-v_true)**2, axis=1)))),
                    "speed_rmse": float(np.sqrt(np.mean((sp-st)**2))), "speed_bias": float(np.mean(sp-st)),
                    "signed_velocity_error_xyz": np.mean(v_pred-v_true, axis=0).round(4).tolist()})
        if moving.any():
            cos = np.sum(v_pred[moving]*v_true[moving], 1)/np.maximum(sp[moving]*st[moving], 1e-9)
            out["direction_error_deg"] = float(np.degrees(np.median(np.arccos(np.clip(cos, -1, 1)))))
        back = v_true[:, 0] < -.2
        out["backward_frames"] = int(back.sum())
        if back.any():
            out["backward_sign_accuracy"] = float(np.mean(v_pred[back, 0] < 0))
            out["backward_velocity_rmse"] = float(np.sqrt(np.mean(np.sum((v_pred[back]-v_true[back])**2, 1))))
            out["backward_forward_speed_ratio"] = float(np.mean(v_pred[back, 0])/np.mean(v_true[back, 0]))
    return out


def integrate(v, row):
    world = (row["R"] @ v[..., None]).squeeze(-1)
    p = np.zeros_like(world)
    p[1:] = np.cumsum(.5*(world[1:]+world[:-1])*np.diff(row["times"])[:, None], axis=0)
    arm, rot = row["T_bc"][:3, 3], row["T_bc"][:3, :3]
    return (p+row["R"]@arm-arm)@rot


# Causal velocity/IMU fusion (opt-in post-processor, --ekf). Fixed-size dense state so it ports to C:
#   p (3) body origin and v (3) velocity in the attitude's world frame (camera frame zero for the
#   origin, not gravity aligned), g (3) gravity in that frame (absorbs the initial tilt and slow
#   tilt drift), optionally a body-frame accelerometer bias (3), and with "attitude":
#   phi (3) world-frame attitude error of R and b (3) residual gyro
#   bias, R_true = Exp(phi) R. Propagation uses the per-frame mean accelerometer (imu[:, 0:3], in g,
#   body axes, specific force); the update is the network's body velocity with a fixed per-axis
#   covariance, or exp(log-variance) * variance_scale from the uncertainty head.
# Defaults describe the prototype. The training-selected settings are recorded with the experiment.
EKF = {"attitude": False, "accel_sigma": 2.0, "gravity_walk": 0.05, "gravity_sigma": 0.5,
       "accel_bias_sigma": 0.0, "accel_bias_walk": 0.02,
       "attitude_walk": 1e-3, "gyro_bias_walk": 1e-4, "gyro_bias_sigma": 2e-3,
       "velocity_sigma": [0.15, 0.15, 0.15], "variance_scale": 1.0, "use_variance": True}


def skew(a):
    return np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])


def so3_exp(phi):
    angle = np.linalg.norm(phi)
    if angle < 1e-9: return np.eye(3)+skew(phi)
    k = skew(phi/angle)
    return np.eye(3)+np.sin(angle)*k+(1-np.cos(angle))*k@k


def ekf_fuse(v, row, params=None, log_variance=None, R=None, check=False):
    """Fuse network body velocities `v` (N, 3) with the accelerometer. `R` overrides row["R"] (e.g. a
    corrected attitude). Returns camera positions (like integrate), fused body velocities, and info
    (mean normalized innovation squared; with check=True the minimum covariance eigenvalue)."""
    q = {**EKF, **(params or {})}
    R = row["R"] if R is None else R
    times, accel, packet = row["times"], row["imu"][:, :3].astype(np.float64)*9.81, row["imu"][:, 12] > 0
    estimate_attitude = q["attitude"]
    estimate_bias = q["accel_bias_sigma"] > 0
    bias_start = 15 if estimate_attitude else 9
    iC = slice(bias_start, bias_start+3)
    n = bias_start + 3*estimate_bias
    iP, iV, iG, iA, iB = slice(0, 3), slice(3, 6), slice(6, 9), slice(9, 12), slice(12, 15)
    eye = np.eye(3)
    def noise(k):
        return (np.diag(np.exp(log_variance[k]))*q["variance_scale"] if log_variance is not None and q["use_variance"]
                else np.diag(np.square(q["velocity_sigma"])))
    def attitude(k):
        return so3_exp(x[iA])@R[k] if estimate_attitude else R[k]
    x, P = np.zeros(n), np.zeros((n, n))
    x[iV], x[iG] = R[0]@v[0], [0, 0, -9.81]
    P[iP, iP], P[iV, iV], P[iG, iG] = 1e-6*eye, R[0]@noise(0)@R[0].T, q["gravity_sigma"]**2*eye
    if estimate_attitude:
        P[iA, iA], P[iB, iB] = 1e-8*eye, q["gyro_bias_sigma"]**2*eye
    if estimate_bias:
        P[iC, iC] = q["accel_bias_sigma"]**2*eye
    positions, fused, rotations = np.zeros((len(v), 3)), np.zeros((len(v), 3)), np.zeros((len(v), 3, 3))
    rotations[0], fused[0], nis = R[0], v[0], []
    min_eig = float(np.linalg.eigvalsh(P).min()) if check else None
    for k in range(1, len(v)):
        dt = times[k]-times[k-1]
        Rc = attitude(k)
        F, Q, sa2 = np.eye(n), np.zeros((n, n)), q["accel_sigma"]**2
        F[iP, iV] = dt*eye
        if packet[k]:
            body_force = accel[k]-x[iC] if estimate_bias else accel[k]
            specific = Rc@body_force
            a = specific+x[iG]
            F[iP, iG], F[iV, iG] = .5*dt*dt*eye, dt*eye
            if estimate_attitude:
                F[iP, iA], F[iV, iA] = -.5*dt*dt*skew(specific), -dt*skew(specific)
            if estimate_bias:
                F[iP, iC], F[iV, iC] = -.5*dt*dt*Rc, -dt*Rc
        else:  # no IMU samples in this frame: constant velocity with inflated acceleration noise
            a, sa2 = np.zeros(3), 100*sa2
        Q[iP, iP], Q[iV, iV] = .25*dt**4*sa2*eye, dt*dt*sa2*eye
        Q[iP, iV] = Q[iV, iP] = .5*dt**3*sa2*eye
        Q[iG, iG] = q["gravity_walk"]**2*dt*eye
        if estimate_bias:
            Q[iC, iC] = q["accel_bias_walk"]**2*dt*eye
        x[iP] += x[iV]*dt+.5*a*dt*dt
        x[iV] += a*dt
        if estimate_attitude:
            F[iA, iB] = -dt*Rc
            x[iA] -= Rc@x[iB]*dt
            Q[iA, iA], Q[iB, iB] = q["attitude_walk"]**2*dt*eye, q["gyro_bias_walk"]**2*dt*eye
        P = F@P@F.T+Q
        # Update with the body-frame velocity measurement h = Rc^T v_world.
        Rc = attitude(k)
        H = np.zeros((3, n))
        H[:, iV] = Rc.T
        if estimate_attitude:
            H[:, iA] = Rc.T@skew(x[iV])
        Rm = noise(k)
        innovation = v[k]-Rc.T@x[iV]
        S = H@P@H.T+Rm
        K = np.linalg.solve(S, H@P).T
        x = x+K@innovation
        IKH = np.eye(n)-K@H
        P = IKH@P@IKH.T+K@Rm@K.T  # Joseph form: stays symmetric positive definite
        P = .5*(P+P.T)
        nis.append(float(innovation@np.linalg.solve(S, innovation)))
        if check: min_eig = min(min_eig, float(np.linalg.eigvalsh(P).min()))
        Rc = attitude(k)
        positions[k], rotations[k], fused[k] = x[iP], Rc, Rc.T@x[iV]
    arm, rot = row["T_bc"][:3, 3], row["T_bc"][:3, :3]
    camera = (positions+rotations@arm-arm)@rot
    return camera, fused, {"nis": float(np.mean(nis)) if nis else None, "min_eigenvalue": min_eig}


def load_model(run, weights, device):
    cfg = json.loads((run/"config.json").read_text())
    net = OdometryNet(cfg["model"]).to(device).eval()
    net.load_state_dict(weights)
    return net


def model_velocities(run, weights, row, device, chunk=32, with_variance=False):
    return replay_velocities(load_model(run, weights, device), row, device, chunk, with_variance)


@torch.no_grad()
def replay_velocities(net, row, device, chunk=32, with_variance=False):
    out, variance, state = [], [], None
    for b in range(0, len(row["v"]), chunk):
        im = torch.as_tensor(row["images"][b:b+chunk], device=device)[None]
        u = torch.as_tensor(row["imu"][b:b+chunk], device=device)[None]
        rot = torch.as_tensor(row["R"][b:b+chunk], device=device, dtype=torch.float32)[None]
        pred, state = net(im, u, state, rot)
        velocity, log_variance = split_output(pred)
        out.append(velocity[0].cpu().numpy())
        if log_variance is not None: variance.append(log_variance[0].cpu().numpy())
    v = np.concatenate(out).astype(np.float64)
    if not with_variance: return v
    return v, (np.concatenate(variance).astype(np.float64) if variance else None)


def load_weights(run, which):
    if which == "best":
        return load_file(str(run/"best.safetensors"))
    last = sorted(run.glob("checkpoints/epoch-*/complete.json"))[-1].parent
    if (last/"pytorch_model.bin").exists():
        return torch.load(last/"pytorch_model.bin", map_location="cpu", weights_only=True)
    return load_file(str(last/"model.safetensors"))  # older checkpoints (incomplete for GRU heads on CUDA)


def deployed_trajectory(kind, raw_path, crop):
    """Host replay of a submitted guest model on the raw flight (its own preprocessing)."""
    import sys
    from common import Flight
    from pairs import variant_rows
    from robust_replay import camera_config, prepare_pixels
    sys.path.insert(0, str(GUEST/kind))
    from streaming import Estimator  # guest copy shadows the research module for exactness
    settings = json.loads((GUEST/kind/"config.json").read_text())
    with np.load(GUEST/kind/"weights.npz", allow_pickle=False) as archive:
        weights = dict(archive)
    model = {"variant": settings["variant"], "kind": settings["kind"], "settings": settings.get("settings"),
             "rotation_method": settings.get("rotation_method"), "rotation_weights": weights.get("rotation"),
             "encoder": {k[4:]: v for k, v in weights.items() if k.startswith("enc/")},
             "temporal": {k[5:]: v for k, v in weights.items() if k.startswith("head/")}}
    flight = prepare_pixels(Flight(raw_path, crop=crop), settings["config"])
    est = Estimator(camera_config(flight), model, settings["config"])
    states = np.array([est.step(t, frame, packet) for t, frame, packet in variant_rows(flight, "clean", 217)])
    sys.path.remove(str(GUEST/kind))
    return states[:, :3], flight.cam_gt, flight.ft


def scene_paired(results, name, control, key="ate"):
    """Paired scene-level differences (scene means first), with a bootstrap 90% interval."""
    def by_scene(model):
        acc = {}
        for r in results[model]: acc.setdefault(r["scene"], []).append(r[key])
        return {s: float(np.mean(v)) for s, v in acc.items()}
    a, b = by_scene(name), by_scene(control)
    scenes = sorted(set(a) & set(b))
    d = np.array([a[s]-b[s] for s in scenes])
    rng = np.random.default_rng(0)
    boot = [rng.choice(d, len(d)).mean() for _ in range(4000)] if len(d) > 1 else [d.mean()]
    return {"scenes": len(scenes), "mean_difference": float(d.mean()), "relative": float(d.mean()/np.mean([b[s] for s in scenes])),
            "interval90": [float(np.percentile(boot, 5)), float(np.percentile(boot, 95))],
            "per_scene": {s: round(float(x), 4) for s, x in zip(scenes, d)}}


def plot(args, curves, out):
    """Learning curves (development nominal, moving-start and selection mean ATE per epoch, log scale)
    and mean position error over time. Mean unaligned ATE is the only metric."""
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for run in map(Path, args.runs):
        history = json.loads((run/"metrics.json").read_text())
        epochs = [h["epoch"] for h in history]
        line, = axes[0].plot(epochs, [h["selection_score"] for h in history], marker="o", label=run.name)
        axes[1].plot(epochs, [h["nominal_ate"] for h in history], marker="o", color=line.get_color(), label=run.name)
        axes[1].plot(epochs, [h["moving_ate"] for h in history], ls="--", color=line.get_color())
    for ax, title in zip(axes, ("selection: mean ATE (m)", "nominal (solid) / moving start (dashed) mean ATE (m)")):
        ax.set_xlabel("epoch"); ax.set_title(title); ax.set_yscale("log"); ax.grid(alpha=.3, which="both")
    axes[0].legend(fontsize=7); fig.tight_layout(); fig.savefig(out/"learning-curves.png", dpi=120); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    for name, series in curves.items():
        grid = np.arange(.5, min(t[-1] for t, _ in series), .5)  # log axis: skip t = 0
        ax.plot(grid, np.mean([np.interp(grid, t, e) for t, e in series], 0), label=name)
    ax.set_xlabel("time since start (s)"); ax.set_ylabel("mean position error (m)"); ax.set_yscale("log")
    ax.set_title(f"{args.set}: static-start replays, {args.checkpoint} checkpoint"); ax.grid(alpha=.3); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(out/(f"{args.set}-{args.checkpoint}" + (f"-{args.max_seconds:g}s" if args.max_seconds else "") + "-error-over-time.png"), dpi=120); plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="*", default=[])
    parser.add_argument("--checkpoint", choices=("best", "last"), default="best")
    parser.add_argument("--deployed", nargs="*", default=[])
    parser.add_argument("--control")
    parser.add_argument("--set", default="dev", choices=("dev", "proxy-val", "campaign-dev"))
    parser.add_argument("--ledger", default="data/ledger/ledger.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-seconds", type=float, help="Score only each replay's first N seconds (all models are causal)")
    parser.add_argument("--plots", action="store_true", help="Write learning curves and error-over-time figures")
    parser.add_argument("--ekf", action="store_true", help="Also score each run through the EKF post-processor (<run>+ekf)")
    parser.add_argument("--ekf-params", default="{}", help="JSON overrides of odometry_eval.EKF")
    args = parser.parse_args()
    store = open_store("hf:teacher-full", "data/hub-cache", 20)
    if args.set == "dev":
        records = json.loads(store.manifest_path().read_text())["datasets"]["development"]
    elif args.set == "proxy-val":
        records = json.loads(Path("data/expand/proxy-proxy_validation-0.json").read_text())["records"]
        records = [r for r in records if r["crop_s"] == 0]
    else:  # native campaign dev flights (native_campaign.py publish --split dev); both crops, like dev
        records = json.loads(Path("data/native-campaign/dev-records.json").read_text())["records"]
    ledger = {r["sha256"]: r for r in json.loads(Path(args.ledger).read_text())["rows"]}
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    results, curves = {}, {}  # curves: model -> list of (times, position error) per static-start replay
    rows_cache = {}
    for record in records:
        row = load_row(store, record)
        if args.max_seconds:
            keep = int(np.sum(row["times"]-row["times"][0] <= args.max_seconds+1e-6))
            row = {k: (v[:keep] if k != "T_bc" else v) for k, v in row.items()}
        rows_cache[record["file"]] = row
    def describe(record, row):
        parent = ledger.get(record.get("parent_sha256"), {})
        lab = motion_labels(row["v"], row["times"], row["cam_gt"])
        return {"scene": record["scene"], "file": record["file"], "crop_s": record["crop_s"], "catalog": record.get("catalog"),
                "domain": parent.get("domain", record.get("domain")), "tier": parent.get("tier", record.get("tier")),
                "regime": "backward/lateral" if lab["backward"].mean() > .05 or lab["lateral"].mean() > .1 else "ordinary",
                "start": "static" if record["crop_s"] == 0 else "moving"}
    # Zero output: the trivial baseline every model must beat.
    results["zero"] = []
    for record in records:
        row = rows_cache[record["file"]]
        results["zero"].append({**describe(record, row), **metrics(np.zeros_like(row["cam_gt"]), row["cam_gt"], row["times"])})
    # Rotation floor: true body velocity through our estimated attitude and the same integrator.
    # Bounds what a perfect velocity head could reach with the current attitude path.
    results["true-velocity"] = []
    for record in records:
        row = rows_cache[record["file"]]
        results["true-velocity"].append({**describe(record, row), **metrics(integrate(row["v"], row), row["cam_gt"], row["times"])})
    for run in map(Path, args.runs):
        name = run.name
        weights = load_weights(run, args.checkpoint)
        results[name] = []
        for record in records:
            row = rows_cache[record["file"]]
            v, log_variance = model_velocities(run, weights, row, device, with_variance=True)
            p = integrate(v, row)
            extra = {}
            if log_variance is not None:  # calibration: fraction of per-axis errors within 1 and 2 sigma
                z = np.abs(v-row["v"])*np.exp(-.5*log_variance)
                extra = {"within_1sigma": float(np.mean(z < 1)), "within_2sigma": float(np.mean(z < 2)),
                         "within_1sigma_xyz": np.mean(z < 1, 0).round(4).tolist()}
            results[name].append({**describe(record, row), **metrics(p, row["cam_gt"], row["times"], v, row["v"]), **extra})
            if record["crop_s"] == 0:
                curves.setdefault(name, []).append((row["times"]-row["times"][0], np.linalg.norm(p-row["cam_gt"], axis=1)))
            if args.ekf:
                pe, ve, info = ekf_fuse(v, row, json.loads(args.ekf_params), log_variance)
                results.setdefault(name+"+ekf", []).append(
                    {**describe(record, row), **metrics(pe, row["cam_gt"], row["times"], ve, row["v"]), "nis": info["nis"]})
    for kind in args.deployed:
        name = f"deployed-{kind}"
        results[name] = []
        for record in records:
            raw = ledger[record["parent_sha256"]]["path"]
            p, truth, times = deployed_trajectory(kind, raw, record["crop_s"])
            row = rows_cache[record["file"]]
            if not np.allclose(truth, row["cam_gt"], atol=1e-4):
                raise ValueError("Deployed replay truth differs from the shard truth")
            results[name].append({**describe(record, row), **metrics(p, truth, times)})
    summary = {}
    for name, rows in results.items():
        def mean(sel, key="ate"):
            vals = [r[key] for r in rows if sel(r) and key in r]
            return round(float(np.mean(vals)), 4) if vals else None
        summary[name] = {"equal_flight_mean_ate": mean(lambda r: True),
                         "worst_flight_ate": round(max(r["ate"] for r in rows), 4),
                         "ordinary_ate": mean(lambda r: r["regime"] == "ordinary"),
                         "backward_lateral_ate": mean(lambda r: r["regime"] != "ordinary"),
                         "static_start_ate": mean(lambda r: r["start"] == "static"),
                         "moving_start_ate": mean(lambda r: r["start"] == "moving"),
                         "speed_rmse": mean(lambda r: True, "speed_rmse"),
                         "direction_error_deg": mean(lambda r: True, "direction_error_deg"),
                         "backward_sign_accuracy": mean(lambda r: True, "backward_sign_accuracy"),
                         "backward_velocity_rmse": mean(lambda r: True, "backward_velocity_rmse")}
        for key in ("within_1sigma", "within_2sigma", "nis"):  # uncertainty head / EKF diagnostics
            if any(key in r for r in rows): summary[name][key] = mean(lambda r: True, key)
        for catalog in sorted({r["catalog"] for r in rows if r.get("catalog")}):
            summary[name][f"{catalog}_ate"] = mean(lambda r: r.get("catalog") == catalog)
        if args.control and name != args.control and args.control in results:
            summary[name]["vs_control"] = scene_paired(results, name, args.control)
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    if args.plots:
        plot(args, curves, out)
    tag = f"{args.set}-{args.checkpoint}" + (f"-{args.max_seconds:g}s" if args.max_seconds else "")
    (out/f"{tag}.json").write_text(json.dumps({"summary": summary, "rows": results}, indent=1))
    width = max(len(n) for n in summary)
    print(f"{'model':{width}}  mean   worst  ordin  bk/lat  static moving spdRMSE dirdeg bksign")
    for name, s in summary.items():
        cells = [s[k] for k in ("equal_flight_mean_ate", "worst_flight_ate", "ordinary_ate", "backward_lateral_ate",
                                "static_start_ate", "moving_start_ate", "speed_rmse",
                                "direction_error_deg", "backward_sign_accuracy")]
        print(f"{name:{width}}  " + "  ".join("  –  " if c is None else f"{c:5.3f}" if c < 10 else f"{c:5.1f}" for c in cells))
        by_catalog = {k[:-4]: v for k, v in s.items() if k.endswith("_ate") and k[:-4] in ("procthor", "hssd-val", "hssd-train")}
        if by_catalog: print(f"{'':{width}}  by catalog: " + ", ".join(f"{k} {v:.3f}" for k, v in by_catalog.items()))
        if "vs_control" in s:
            c = s["vs_control"]; print(f"{'':{width}}  vs {args.control}: {c['mean_difference']:+.3f} m ({c['relative']:+.1%}), 90% {c['interval90']}, scenes {c['scenes']}")


if __name__ == "__main__":
    main()
