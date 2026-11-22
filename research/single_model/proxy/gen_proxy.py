"""New proxy-test flights (WSL simulator env): unseen scenes, a spread of planner speeds, >= server length (1200 frames).

  ~/.venv/bin/python gen_proxy.py roster --out roster.json              (Windows or WSL; needs the scene lists below)
  ~/.venv/bin/python gen_proxy.py generate --roster roster.json --raw ~/data/proxy --worker W --workers N

Scenes: HSSD Val43 houses and ProcTHOR 162-165/172-175 (the HF campaign's reserved test scenes), minus every scene that
appears in our training records (disp teacher, server folds) or the HF server-calibrated benchmark.
Speed settings (planner overrides, same knobs as the HF 'fast' pool):
  D default planner (cruise 0.45-0.8 m/s) | M 1.5-2.5 | K 3-4.5 (HF) | K2 4-6 (HF) | K3 6-8
Length: 60 s (1200 frames), 75 s or 90 s; half start mid-flight (generated longer, first 3-30 s cropped, final length kept).
"""
import argparse, json, os, random, shutil, sys, time, traceback
from pathlib import Path
import numpy as np

SPEEDS = {
    "D": {},
    "M": dict(CRUISE_SPEED_MIN=1.5, CRUISE_SPEED_MAX=2.5, MAX_ACCELERATION=3.0, MAX_JERK=15.0, MAX_YAW_RATE=1.5,
              ROADMAP_SPACING=1.0, CONNECTION_DISTANCE=5.0),
    "K": dict(CRUISE_SPEED_MIN=3.0, CRUISE_SPEED_MAX=4.5, MAX_ACCELERATION=6.0, MAX_JERK=30.0, MAX_YAW_RATE=2.0,
              ROADMAP_SPACING=1.0, CONNECTION_DISTANCE=6.0),
    "K2": dict(CRUISE_SPEED_MIN=4.0, CRUISE_SPEED_MAX=6.0, MAX_ACCELERATION=8.0, MAX_JERK=40.0, MAX_YAW_RATE=2.0,
               ROADMAP_SPACING=1.0, CONNECTION_DISTANCE=6.0),
    "K3": dict(CRUISE_SPEED_MIN=6.0, CRUISE_SPEED_MAX=8.0, MAX_ACCELERATION=10.0, MAX_JERK=50.0, MAX_YAW_RATE=2.5,
               ROADMAP_SPACING=1.0, CONNECTION_DISTANCE=6.0),
}
SPEED_W = {"D": .10, "M": .25, "K": .25, "K2": .25, "K3": .15}
WAYPOINTS = 96  # constant (the route cycles): one JIT build per speed setting, not per flight length
PROCTHOR_TEST = [f"ProcTHOR-Train-{i}" for i in (*range(162, 166), *range(172, 176))]


def roster(args):
    used = set()
    for p in args.used:
        d = json.load(open(p))
        recs = d["episodes"] if isinstance(d, dict) and "episodes" in d else d
        used |= {str(r["scene"]) for r in recs}
    hval = [("hssd-val", s) for s in json.load(open(args.hssd_val)) if s not in used]
    proc = [("procthor", f"ProcTHOR-Train-{i}") for i in range(200)
            if f"ProcTHOR-Train-{i}" not in used and i not in (121, 124)]  # 121/124 crash the simulator
    rng = random.Random(20261121)
    rng.shuffle(hval); rng.shuffle(proc)
    flights = []
    for i in range(args.n):  # 2 of 3 flights in ProcTHOR (llvmpipe cannot render some large HSSD houses)
        cat, sc = (proc[(i - i // 3) % len(proc)] if i % 3 else hval[(i // 3) % len(hval)])
        sp = rng.choices(list(SPEED_W), list(SPEED_W.values()))[0]
        secs = rng.choices([60, 75, 90], [.6, .25, .15])[0]
        crop = round(rng.uniform(3, 30), 1) if rng.random() < .5 else 0.0
        flights.append(dict(id=f"px-{sp}-{sc}-{i:03d}", catalog=cat, scene=sc, speed=sp, seconds=secs, crop_start_s=crop,
                            seed=990000 + i, task_overrides=SPEEDS[sp]))
    Path(args.out).write_text(json.dumps({"flights": flights, "excluded_scenes": len(used)}, indent=1))
    print(len(flights), "flights;", len(proc), "ProcTHOR +", len(hval), "HSSD-val unseen scenes")


def apply_task_overrides(overrides):
    import hashlib
    import viobench.tools.datasets.generate.simulation as simulation
    stock = Path(simulation.__file__).with_name("hyperdrone_world.h.in")
    if not overrides:
        simulation.TEMPLATE = stock; return
    anchor = "        static constexpr TI INITIALIZATION_HOLD_STEPS"
    text = stock.read_text(); assert anchor in text
    lines = "".join(f"        static constexpr T {k} = {float(v)!r};\n" for k, v in sorted(overrides.items()))
    text = text.replace(anchor, lines + anchor, 1)
    path = Path(os.environ.get("TMPDIR", "/tmp")) / f"hyperdrone_world_{hashlib.sha256(text.encode()).hexdigest()[:10]}.h.in"
    if not path.exists():
        tmp = path.with_suffix(f".{os.getpid()}"); tmp.write_text(text); tmp.replace(path)
    simulation.TEMPLATE = path


def crop_episode(e, start):
    from viobench.tools.datasets.episode import Episode
    k = int(np.searchsorted(e.frame_times, e.frame_times[0] + start - 1e-9))
    shift = e.frame_times[k] - e.frame_times[0]
    t0 = e.frame_times[k] - e.frame_interval - 1e-6
    imu = e.imu[e.imu[:, 0] > t0].copy(); imu[:, 0] -= shift
    gt = e.ground_truth[e.ground_truth[:, 0] >= t0 - 0.02].copy(); gt[:, 0] -= shift
    config = json.loads(json.dumps(e.config)); config["episode"]["num_frames"] = int(e.num_frames - k)
    out = Episode(name=e.name, config=config, frame_times=e.frame_times[k:] - shift, frames=np.asarray(e.frames)[k:],
                  imu=imu, ground_truth=gt, T_body_camera=e.T_body_camera,
                  meta={k2: v for k2, v in e.meta.items() if k2 not in ("hash", "path")} | {"crop_start_s": start})
    out.check_consistency()
    return out


def generate(args):
    """Run each flight in a child process: llvmpipe aborts the whole process on scenes too large for it."""
    import subprocess
    raw = Path(args.raw).expanduser(); raw.mkdir(parents=True, exist_ok=True)
    fl = json.load(open(args.roster))["flights"]
    for i, f in enumerate(fl):
        if i % args.workers != args.worker:
            continue
        if (raw / f"{f['id']}.zip").exists() or (raw / f"{f['id']}.failed").exists():
            continue
        if (raw / f"badscene_{f['scene']}").exists():
            (raw / f"{f['id']}.failed").write_text("scene crashed the renderer earlier"); continue
        t0 = time.time()
        p = subprocess.run([sys.executable, __file__, "one", "--roster", args.roster, "--raw", str(raw), "--id", f["id"]])
        if p.returncode != 0 and not (raw / f"{f['id']}.zip").exists():
            (raw / f"{f['id']}.failed").write_text(f"exit {p.returncode}")
            if p.returncode < 0 or p.returncode > 1:
                (raw / f"badscene_{f['scene']}").write_text(f["id"])
        print(time.strftime("%H:%M:%S"), f["id"], "exit", p.returncode, round(time.time() - t0), "s", flush=True)


def one(args):
    from viobench.tools.datasets.generate.simulation import SimConfig, scene_references, simulate, hssd_scenes
    from viobench.tools.datasets.storage import write_episode
    raw = Path(args.raw).expanduser(); raw.mkdir(parents=True, exist_ok=True)
    fl = json.load(open(args.roster))["flights"]
    mine = [f for f in fl if f["id"] == args.id]
    hval = None
    for f in mine:
        target = raw / f"{f['id']}.zip"
        if target.exists() or (raw / f"{f['id']}.failed").exists():
            continue
        t0 = time.time(); status = "ok"
        try:
            apply_task_overrides(f["task_overrides"])
            total = f["seconds"] + f["crop_start_s"]
            sim = SimConfig(instances=1, duration_seconds=total, hold_seconds=1.0, waypoints=WAYPOINTS)
            if f["catalog"] == "hssd-val":
                hval = hval or hssd_scenes("val"); refs = {f["scene"]: hval[f["scene"]]}
            else:
                refs = scene_references([f["scene"]])
            ep, = simulate(sim, refs, 1, seed=f["seed"], name="proxy", log=lambda m: None)
            ep.check_consistency()
            if f["crop_start_s"]:
                ep = crop_episode(ep, f["crop_start_s"])
            gt = np.asarray(ep.ground_truth)
            if not (np.isfinite(gt).all() and np.isfinite(np.asarray(ep.imu)).all()):
                raise ValueError("non-finite truth/IMU")
            part = raw / "partial"; part.mkdir(exist_ok=True)
            write_episode(ep, part / target.name)
            (part / target.name).rename(target)
            p = gt[:, 1:4]
            meta = dict(f, frames=int(ep.num_frames), travel_m=float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum()),
                        extent_m=float(np.sqrt(((p - p[0]) ** 2).sum(1).mean())))
            (raw / f"{f['id']}.json").write_text(json.dumps(meta, indent=1))
        except Exception as e:
            status = f"failed: {e!r}"[:300]; traceback.print_exc()
            (raw / f"{f['id']}.failed").write_text(status); sys.exit(1)
        print(time.strftime("%H:%M:%S"), f["id"], status, round(time.time() - t0), "s", flush=True)


def warmup(args):
    """Compile the simulator once per speed setting, serially (parallel first-use compiles collide)."""
    from viobench.tools.datasets.generate.simulation import SimConfig, scene_references, simulate
    for sp, ov in SPEEDS.items():
        apply_task_overrides(ov); t0 = time.time()
        sim = SimConfig(instances=1, duration_seconds=0.5, hold_seconds=1.0, waypoints=WAYPOINTS)
        list(simulate(sim, scene_references(["ProcTHOR-Train-162"]), 1, seed=1, name="warm", log=lambda m: None))
        print("warm", sp, round(time.time() - t0), "s", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("roster"); r.add_argument("--out", required=True); r.add_argument("--n", type=int, default=120)
    r.add_argument("--hssd_val", required=True); r.add_argument("--used", nargs="+", default=[])
    g = sub.add_parser("generate"); g.add_argument("--roster", required=True); g.add_argument("--raw", required=True)
    g.add_argument("--worker", type=int, default=0); g.add_argument("--workers", type=int, default=1)
    o = sub.add_parser("one"); o.add_argument("--roster", required=True); o.add_argument("--raw", required=True); o.add_argument("--id", required=True)
    sub.add_parser("warmup")
    a = ap.parse_args()
    {"roster": roster, "generate": generate, "one": one, "warmup": warmup}[a.cmd](a)
