"""Server-calibrated benchmark: candidate pool, calibration and release.

The benchmark is raw VIOBench episodes (official archive format), generated with the upstream generator's
*default* spec (60 s, 48 waypoints, 1 s hover, FOV 120 +/- 15 deg, nominal camera, upstream IMU noise): exactly
what the public set is. No model, ours or anyone's, is used to choose flights. The selection step uses only
trajectory/IMU statistics that implementation-independent baselines reveal (see CALIBRATION in this file).

    python server_benchmark.py roster                        # write configs/server_benchmark_pool.json
    python native_campaign.py generate --gen-roster configs/server_benchmark_pool.json \\
        --gen-raw /data/backups/rganapa/Sebastian/gen/raw-bench --worker W --workers N     (simulator env)

Scene groups (flag `group`), so learned models can be scored on scenes they never trained on:
  clean  ProcTHOR 150-161 and 176-179: in no training, development or reserved-test split of the native campaign
         (150-161 only appeared in the old proxy-validation pool).
  dev    ProcTHOR 166-171 and the 15 HSSD Val43 development houses: fresh flights, but models were tuned on
         other flights in these scenes.
  seen   a sample of campaign training scenes: fresh flights, scenes seen in training.
The 84 reserved campaign-test flights and their scenes (ProcTHOR 162-165/172-175, 28 HSSD Val43 houses) are not used.
"""
import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POOL = ROOT/"configs"/"server_benchmark_pool.json"
CAMPAIGN = ROOT/"configs"/"native_campaign.json"
SEED = 20261119
OBSERVED_TRAVEL_MEAN = 59.6  # mean path length of the server's 12 episodes (configs/server_observed.json)
FIRST_FLIGHT_SEED = 800000  # the native campaign used 700000-700747
CRASHING_PROCTHOR = {121, 124}  # the simulator aborts in these scenes
CRASHING_HSSD = {"103997940_171031257"}

# Anchors from the course server's current set (`private_stage2`, 12 episodes of 1200 frames), mean unaligned ATE.
# Supplied by the user from the server's leaderboard; the episode archives themselves are hidden and are not used.
SERVER = {
    "cpp_minimal": {"mean_ate_m": 4.694450928701121, "max_fuel": 113, "note": "identity pose: ATE is the RMS distance of the truth from its start"},
    "dead_reckoning": {"mean_ate_m": 9.065463414163448, "max_fuel": 5148278},
    "tiny_cnn": {"mean_ate_m": 5.824925111846599, "max_fuel": 14684708, "note": "trained by the instructors; weights not available locally"},
    "openvins": {"mean_ate_m": 0.5532605176928356, "max_fuel": 3955863154},
    "vins_mono": {"mean_ate_m": 0.47537535896686567, "max_fuel": 3400397390},
    "submitted_b_d0_seed217": {"mean_ate_m": 4.55, "max_fuel": 1100000000},
    "compact_camera_direction_blended_speed": {"mean_ate_m": 3.98, "max_fuel": 16000000},
}


def build_pool(per_scene=None):
    campaign = json.loads(CAMPAIGN.read_text())["flights"]
    hssd_dev = sorted({f["scene"] for f in campaign if f["split"] == "dev" and f["catalog"] == "hssd-val"})
    hssd_train = sorted({f["scene"] for f in campaign if f["split"] == "train" and f["catalog"] == "hssd-train"} - CRASHING_HSSD)
    procthor_train = sorted({int(f["scene"].rsplit("-", 1)[1]) for f in campaign
                             if f["split"] == "train" and f["catalog"] == "procthor"} - CRASHING_PROCTHOR)
    rng = random.Random(SEED)
    plan = [("clean", "procthor", [f"ProcTHOR-Train-{i}" for i in [*range(150, 162), *range(176, 180)]], 12),
            ("dev", "procthor", [f"ProcTHOR-Train-{i}" for i in range(166, 172)], 6),
            ("dev", "hssd-val", hssd_dev, 3),
            ("seen", "procthor", [f"ProcTHOR-Train-{i}" for i in rng.sample(procthor_train, 36)], 3),
            ("seen", "hssd-train", rng.sample(hssd_train, 30), 2)]
    flights = []
    for group, catalog, scenes, count in plan:
        for scene in scenes:
            for index in range(count):
                flights.append({"id": f"bench-{scene}-{index:02d}", "split": "bench", "group": group, "catalog": catalog,
                                "scene": scene, "seed": FIRST_FLIGHT_SEED + len(flights), "seconds": 60,
                                "regime": "benchmark", "hold_seconds": 1.0, "waypoints_per_second": 0.8})
    rng.shuffle(flights)  # workers take every N-th flight: spread scenes and groups across workers
    return {"seed": SEED, "spec": "upstream default: 60 s, 48 waypoints, 1 s hover, FOV 120+-15, nominal camera",
            "flights": flights}


def build_round2(raw, threshold=3.5, per_scene=8, first_seed=801000):
    """Second candidate round: more flights in scenes whose first-round mean extent (zero-motion ATE) is at least
    `threshold`. Uses only truth statistics; no guest result is involved."""
    import collections
    flights = load_pool(raw)
    zero = collections.defaultdict(list)
    meta = {}
    for f in flights:
        zero[f["scene"]].append(f["zero"]); meta[f["scene"]] = f
    out = []
    for scene in sorted(zero):
        if sum(zero[scene])/len(zero[scene]) < threshold:
            continue
        for index in range(len(zero[scene]), len(zero[scene])+per_scene):
            out.append({"id": f"bench-{scene}-{index:02d}", "split": "bench", "group": meta[scene]["group"],
                        "catalog": meta[scene]["catalog"], "scene": scene, "seed": first_seed+len(out), "seconds": 60,
                        "regime": "benchmark", "hold_seconds": 1.0, "waypoints_per_second": 0.8})
    random.Random(SEED+1).shuffle(out)
    return {"seed": SEED+1, "spec": "round 2: upstream default spec in scenes with round-1 mean extent >= %.1f m" % threshold, "flights": out}


def load_pool(raw):
    """Per-flight metadata and truth statistics from the generator's audit files."""
    import glob
    flights = []
    for path in sorted(glob.glob(f"{raw}/bench/*.json")):
        d = json.loads(Path(path).read_text())
        flights.append({"id": d["id"], "group": d["group"], "catalog": d["catalog"], "scene": d["scene"],
                        "zero": d["audit"]["zero_motion_ate_m"], "travel": d["audit"]["travel_m"],
                        "speed_p50": d["audit"]["speed_p10_p50_p90"][1], "flags": d["audit"]["flags"]})
    return flights


def tilt(values, base, target):
    """Weights base*exp(lam*value) whose weighted mean of `values` equals `target` (bisection on lam)."""
    import numpy as np
    values, base = np.asarray(values, float), np.asarray(base, float)
    lo, hi = -6.0, 6.0
    for _ in range(80):
        lam = (lo+hi)/2
        w = base*np.exp(lam*(values-values.mean()))
        mean = float((w*values).sum()/w.sum())
        lo, hi = (lam, hi) if mean < target else (lo, lam)
    return w/w.sum(), lam


def tilt2(features, base, targets, iterations=200):
    """Weights base*exp(features @ lam) whose weighted feature means equal `targets` (Newton on the convex dual).
    Returns (weights, lam, achieved_means); if the targets are outside the pool's reach the means are the nearest found."""
    import numpy as np
    X = np.asarray(features, float); base = np.asarray(base, float); t = np.asarray(targets, float)
    mu, sd = X.mean(0), X.std(0)+1e-9
    Z = (X-mu)/sd; tz = (t-mu)/sd
    lam = np.zeros(Z.shape[1])
    for _ in range(iterations):
        w = base*np.exp(Z@lam); w /= w.sum()
        m = w@Z; cov = (Z*w[:, None]).T@Z-np.outer(m, m)
        step = np.linalg.solve(cov+1e-9*np.eye(len(lam)), m-tz)
        lam = lam-np.clip(step, -1, 1)
        if np.abs(m-tz).max() < 1e-6: break
    w = base*np.exp(Z@lam); w /= w.sum()
    return w, lam, w@X


def calibrate(args):
    """Choose flight weights from the extent anchor alone; every other guest is a held-out check.

    The anchor: cpp_minimal outputs an identity pose, so its server score is the mean RMS distance of the truth from its
    start over the server's flights. Weights are the pool's scene-balanced base weights tilted exponentially in each
    flight's own zero-motion ATE until the weighted mean equals the server value. No guest result enters the weights.
    """
    import numpy as np
    flights = load_pool(args.raw)
    matrix = json.loads(Path(args.matrix).read_text())["ate_full"] if args.matrix else {}
    selection_file = json.loads(Path(args.selection).read_text()) if getattr(args, "selection", None) else None
    selection = selection_file["selected"] if selection_file else None
    if selection is not None:  # flights drawn with the calibrated weights: each carries its draw count as weight
        keep = set(selection); flights = [f for f in flights if f["id"] in keep]
        draws = selection_file["selection_weights"]
    n = len(flights)
    scene_count = {}
    for f in flights:
        scene_count[f["scene"]] = scene_count.get(f["scene"], 0)+1
    base = np.array([1.0/scene_count[f["scene"]] for f in flights])
    zero = np.array([f["zero"] for f in flights])
    target = SERVER["cpp_minimal"]["mean_ate_m"]
    travel = np.array([f["travel"] for f in flights])
    if getattr(args, "path_anchor", True) and travel.mean() > 30:  # second anchor: the server's mean path length (59.6 m)
        weights, lam, got = tilt2(np.column_stack([zero, travel]), base, [target, OBSERVED_TRAVEL_MEAN])
        lam = list(map(float, lam)); anchors = f"extent {got[0]:.3f} (server {target:.3f}), path {got[1]:.1f} m (server {OBSERVED_TRAVEL_MEAN:.1f})"
    else:
        weights, lam = tilt(zero, base, target); anchors = f"extent {np.average(zero, weights=weights):.3f} (server {target:.3f}), path {np.average(travel, weights=weights):.1f} m (server {OBSERVED_TRAVEL_MEAN:.1f}, not matched)"
    if selection is not None:
        SELECT_TOTAL = int(sum(draws.values()))
        weights = np.array([draws[f["id"]] for f in flights], float); weights /= weights.sum(); lam = None
        zero_w, travel_w = float(weights@zero), float(weights@travel)
        anchors = f"{SELECT_TOTAL} draws -> {n} distinct flights; weighted extent {zero_w:.3f} (server {target:.3f}), path {travel_w:.1f} m (server {OBSERVED_TRAVEL_MEAN:.1f})"
    ess = 1.0/float((weights**2).sum())
    print(f"{n} flights; pool zero-ATE mean {zero.mean():.3f} path {travel.mean():.1f} m (scene-balanced {np.average(zero, weights=base):.3f}); "
          f"tilted to {anchors}; effective sample {ess:.0f}")
    rng = np.random.default_rng(SEED)
    report = {"lambda": lam, "effective_sample": ess, "anchors": anchors, "guests": {}}
    guests = sorted({g for row in matrix.values() for g in row})
    names = [f["id"] for f in flights]
    for guest in guests:
        ate = np.array([matrix.get(i, {}).get(guest) if matrix.get(i, {}).get(guest) is not None else np.nan for i in names])
        ok = ~np.isnan(ate)
        if ok.sum() < 5:
            continue
        w = weights[ok]/weights[ok].sum()
        weighted = float((w*ate[ok]).sum())
        draws = [float(np.mean(rng.choice(ate[ok], 12, p=w))) for _ in range(4000)]  # what a 12-episode server set would show
        lo, hi = np.percentile(draws, [5, 95])
        server = {"b_d0": SERVER["submitted_b_d0_seed217"]["mean_ate_m"]}.get(guest, SERVER.get(guest, {}).get("mean_ate_m"))
        inside = None if server is None else bool(lo <= server <= hi)
        report["guests"][guest] = {"pool_mean": float(ate[ok].mean()), "calibrated_mean": weighted, "p5_p95_of_12": [float(lo), float(hi)],
                                   "server": server, "server_inside_12_episode_interval": inside, "n": int(ok.sum())}
        print(f"  {guest:16s} pool {ate[ok].mean():7.3f}  calibrated {weighted:7.3f}  12-episode 90% [{lo:6.2f}, {hi:6.2f}]  "
              f"server {server if server is not None else '-'}  {'' if inside is None else ('INSIDE' if inside else 'outside')}")
    if selection is not None:
        report["selected"] = sorted(keep)
    if args.select:
        chosen = rng.choice(n, args.select, replace=True, p=weights)  # with replacement: unbiased for the calibrated weights
        ids, counts = np.unique(chosen, return_counts=True)
        report["selected"] = sorted(names[i] for i in ids)
        report["selection_weights"] = {names[i]: int(c) for i, c in zip(ids, counts)}
        print(f"{args.select} draws -> {len(ids)} distinct flights; weighted zero-ATE mean {np.average(zero[ids], weights=counts):.3f}, "
              f"path {np.average(travel[ids], weights=counts):.1f} m")
        for guest in guests:
            ate = np.array([matrix.get(names[i], {}).get(guest, np.nan) or np.nan for i in chosen])
            if np.isfinite(ate).sum() > 5:
                print(f"  {guest:16s} selected-set mean {np.nanmean(ate):7.3f}")
    Path(args.output).write_text(json.dumps(report, indent=1) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("roster", "roster2", "calibrate"))
    parser.add_argument("--raw", default="/data/backups/rganapa/Sebastian/gen/raw-bench")
    parser.add_argument("--matrix", help="calibrate: matrix.json from bench_eval.py")
    parser.add_argument("--selection", help="calibrate: calibration JSON whose `selected` flights are scored with equal weight (no re-tilting)")
    parser.add_argument("--select", type=int, help="calibrate: also draw this many flights with the calibrated weights")
    parser.add_argument("--output", default=str(ROOT/"results"/"eval"/"server-benchmark"/"calibration.json"))
    args = parser.parse_args()
    if args.action == "calibrate":
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        calibrate(args); return
    if args.action == "roster2":
        pool = build_round2(args.raw)
        path = POOL.with_name("server_benchmark_pool_r2.json"); path.write_text(json.dumps(pool, indent=1) + "\n")
        from collections import Counter
        print(len(pool["flights"]), "flights in", len({f["scene"] for f in pool["flights"]}), "scenes;", dict(Counter(f["group"] for f in pool["flights"]))); return
    pool = build_pool()
    POOL.write_text(json.dumps(pool, indent=1) + "\n")
    from collections import Counter
    print(len(pool["flights"]), "flights;", dict(Counter((f["group"], f["catalog"]) for f in pool["flights"])))


if __name__ == "__main__":
    main()
