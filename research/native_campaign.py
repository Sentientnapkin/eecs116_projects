"""Native flight campaign: a fixed, split-safe roster of simulated flights, kept raw.

    python native_campaign.py roster                         # write configs/native_campaign.json (deterministic)
    python native_campaign.py generate --worker 0 --workers 8 [--split train] [--limit N]   (simulator env)
    python native_campaign.py upload [--raw]                 # roster + audits (+ raw archives) -> private Hub repo
    python native_campaign.py prepare --split train --worker 0 --workers 32   # raw -> training shards (training env)
    python native_campaign.py publish --split train          # shards -> data repo; records file for compose
    python odometry_store.py compose --name <name> --base teacher-full-labeled --records data/native-campaign/train-records.json

Splits never share a scene with each other or with earlier splits:
  train  ProcTHOR-Train 0-9, 46-149, 180-199 and HSSD Train125 (training-only scenes; earlier
         generated pools used some of them, which is train-on-train and harmless).
  dev    new flights in the existing development scenes ProcTHOR 166-171 (continuity with the
         7-parent roster) plus 15 HSSD Val43 houses no earlier work has used (reported separately:
         the benchmark is ProcTHOR-like, HSSD dev measures transfer to unseen house styles).
  test   reserved: new flights in the final-test scenes ProcTHOR 162-165/172-175 plus the other
         28 HSSD Val43 houses. Generated and archived, never prepared or scored until a final
         candidate is frozen.
  ProcTHOR 150-161 (proxy validation, contaminated by gen-pool-v1) and 176-179 (confirmation,
  quarantined) are not used.

Each flight varies length (30/60/90 s), autopilot (benchmark, or independent yaw for backward and
lateral motion), hover before the route (0.2/1/3 s) and route density (turn rate). Raw archives
keep 640x480 frames and 200 Hz IMU so later visual encoders can use them. Only simulator failures
are rejected (exceptions, non-finite truth, archive consistency, truth that does not integrate);
hover, stalls, darkness and low texture are flagged in the audit, never dropped.
"""
import argparse
import json
import os
import random
import shutil
import time
import traceback
from dataclasses import asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
ROSTER = ROOT/"configs"/"native_campaign.json"
RAW = Path("/data/backups/rganapa/Sebastian/gen/raw")
RAW_REPO = "SentientNapkin/viobench-native-campaign"
CAMPAIGN_SEED = 20261118

TRAIN_PROCTHOR = [*range(0, 10), *range(46, 150), *range(180, 200)]
DEV_PROCTHOR = list(range(166, 172))
TEST_PROCTHOR = [*range(162, 166), *range(172, 176)]
EXCLUDED_PROCTHOR = set(range(150, 162)) | set(range(176, 180)) | set(range(10, 46))


def flight_variation(rng, split):
    """Per-flight simulator settings. Dev/test use the same distribution as train."""
    return {"seconds": rng.choices([30, 60, 90], [.5, .35, .15])[0],
            "regime": "independent-yaw" if rng.random() < .25 else "benchmark",
            "hold_seconds": rng.choices([.2, 1., 3.], [.25, .5, .25])[0],
            "waypoints_per_second": rng.choice([.5, .8, 1.2])}


def build_roster(hssd_train, hssd_val, train_flights=600):
    rng = random.Random(CAMPAIGN_SEED)
    val = sorted(hssd_val); rng.shuffle(val)
    dev_hssd, test_hssd = val[:15], val[15:]
    train_scenes = [("procthor", f"ProcTHOR-Train-{i}") for i in TRAIN_PROCTHOR] + \
                   [("hssd-train", s) for s in sorted(hssd_train)]
    flights = []

    def add(split, catalog, scene):
        index = sum(f["scene"] == scene for f in flights)
        flights.append({"id": f"{split}-{scene}-{index:02d}", "split": split, "catalog": catalog, "scene": scene,
                        "seed": 700000 + len(flights), **flight_variation(rng, split)})
    # Train: two thirds ProcTHOR (benchmark-like), one third HSSD; each list cycles through
    # reshuffled passes so every scene is used before any repeats.
    def cycle(scenes, n):
        out = []
        while len(out) < n: out += rng.sample(scenes, len(scenes))
        return out[:n]
    n_procthor = round(train_flights*2/3)
    for catalog, scene in cycle([s for s in train_scenes if s[0] == "procthor"], n_procthor) + \
            cycle([s for s in train_scenes if s[0] != "procthor"], train_flights-n_procthor):
        add("train", catalog, scene)
    for i in DEV_PROCTHOR:
        for _ in range(5): add("dev", "procthor", f"ProcTHOR-Train-{i}")
    for scene in dev_hssd:
        for _ in range(2): add("dev", "hssd-val", scene)
    for i in TEST_PROCTHOR:
        for _ in range(4): add("test", "procthor", f"ProcTHOR-Train-{i}")
    for scene in test_hssd:
        for _ in range(2): add("test", "hssd-val", scene)
    check_splits(flights)
    return {"seed": CAMPAIGN_SEED, "flights": flights,
            "policy": __doc__.split("Splits never")[1].split("Each flight")[0].strip()}


def check_splits(flights):
    scenes = {}
    for f in flights:
        scenes.setdefault(f["scene"], set()).add(f["split"])
    shared = {s: v for s, v in scenes.items() if len(v) > 1}
    if shared:
        raise ValueError(f"scenes in more than one split: {list(shared)[:5]}")
    for f in flights:
        if f["catalog"] == "procthor":
            n = int(f["scene"].rsplit("-", 1)[1])
            allowed = {"train": TRAIN_PROCTHOR, "dev": DEV_PROCTHOR, "test": TEST_PROCTHOR}[f["split"]]
            if n not in allowed or n in EXCLUDED_PROCTHOR:
                raise ValueError(f"{f['id']}: ProcTHOR scene {n} not allowed in {f['split']}")
        if f["catalog"] == "hssd-val" and f["split"] == "train":
            raise ValueError("HSSD Val43 houses are evaluation-only")


def truth_integration_error(flight):
    """RMS (m) between ground-truth positions and trapezoid-integrated ground-truth world velocity.
    Millimetres when frames and twists agree; metres if a velocity is in the wrong frame."""
    dt = np.diff(flight.ft)[:, None]
    p = np.zeros_like(flight.v)
    p[1:] = np.cumsum(.5*(flight.v[1:]+flight.v[:-1])*dt, axis=0)
    return float(np.sqrt(np.mean(np.sum((p-(flight.p-flight.p[0]))**2, axis=1))))


def audit(flight):
    v, t = flight.v_body, flight.ft
    speed = np.linalg.norm(v, axis=1)
    travel = float(np.sum(np.linalg.norm(np.diff(flight.cam_gt, axis=0), axis=1)))
    tail = flight.cam_gt[int(.6*len(flight.cam_gt)):]
    sample = np.asarray(flight.frames[::20], dtype=np.float32)
    gray = sample.mean(-1) if sample.ndim == 4 else sample
    out = {"frames": int(len(t)), "seconds": round(float(t[-1]), 2), "travel_m": round(travel, 2),
           "zero_motion_ate_m": round(float(np.sqrt(np.mean(np.sum(flight.cam_gt**2, axis=1)))), 3),
           "speed_p10_p50_p90": [round(float(np.percentile(speed, q)), 3) for q in (10, 50, 90)],
           "hover_fraction": round(float(np.mean(speed < .05)), 3),
           "backward_fraction": round(float(np.mean(v[:, 0] < -.2)), 3),
           "lateral_fraction": round(float(np.mean(np.abs(v[:, 1]) > .2)), 3),
           "vertical_fraction": round(float(np.mean(np.abs(v[:, 2]) > .2)), 3),
           "turning_fraction": round(float(np.mean(np.linalg.norm(flight.w, axis=1) > .5)), 3),
           "dark_fraction": round(float(np.mean(gray.mean((1, 2)) < 15)), 3),
           "flat_fraction": round(float(np.mean(gray.std((1, 2)) < 6)), 3),
           "stalled": bool(np.max(np.linalg.norm(tail-tail[0], axis=1)) < .5),
           "truth_integration_rms_m": round(truth_integration_error(flight), 5)}
    out["flags"] = [name for name, bad in (("travel<2m", travel < 2), ("stalled", out["stalled"]),
                    ("hover>50%", out["hover_fraction"] > .5), ("dark", out["dark_fraction"] > .2),
                    ("textureless", out["flat_fraction"] > .2)) if bad]
    return out


def apply_task_overrides(overrides):
    """Point the simulator at the stock world template, or at a copy whose TASK_SPEC shadows constants such as
    CRUISE_SPEED_MIN/MAX, MAX_ACCELERATION, MAX_JERK (the planner's knobs; defaults 0.45-0.8 m/s, 0.7, 2.0)."""
    import hashlib
    import viobench.tools.datasets.generate.simulation as simulation
    stock = Path(simulation.__file__).with_name("hyperdrone_world.h.in")
    if not overrides:
        simulation.TEMPLATE = stock; return
    anchor = "        static constexpr TI INITIALIZATION_HOLD_STEPS"
    text = stock.read_text()
    assert anchor in text
    lines = "".join(f"        static constexpr T {k} = {float(v)!r};\n" for k, v in sorted(overrides.items()))
    text = text.replace(anchor, lines + anchor, 1)
    path = Path(os.environ.get("TMPDIR", "/tmp"))/f"hyperdrone_world_{hashlib.sha256(text.encode()).hexdigest()[:10]}.h.in"
    if not path.exists():
        tmp = path.with_suffix(f".{os.getpid()}"); tmp.write_text(text); tmp.replace(path)
    simulation.TEMPLATE = path


def crop_episode(e, start):
    """Fresh-recording crop of an in-memory episode: keep frames from the first one at or after `start` s, shift times so
    that frame is the recording's first, keep one frame interval of IMU before it. The drone is already in motion there
    (same construction as wasm_eval.crop)."""
    from viobench.tools.datasets.episode import Episode
    k = int(np.searchsorted(e.frame_times, e.frame_times[0] + start - 1e-9))
    shift = e.frame_times[k] - e.frame_times[0]
    t0 = e.frame_times[k] - e.frame_interval - 1e-6
    imu = e.imu[e.imu[:, 0] > t0].copy(); imu[:, 0] -= shift
    gt = e.ground_truth[e.ground_truth[:, 0] >= t0 - 0.02].copy(); gt[:, 0] -= shift
    config = json.loads(json.dumps(e.config))
    config["episode"]["num_frames"] = int(e.num_frames - k)
    cropped = Episode(name=e.name, config=config, frame_times=e.frame_times[k:] - shift, frames=np.asarray(e.frames)[k:],
                      imu=imu, ground_truth=gt, T_body_camera=e.T_body_camera,
                      meta={k2: v for k2, v in e.meta.items() if k2 not in ("hash", "path")} | {"crop_start_s": start})
    cropped.check_consistency()
    return cropped


def generate(args):
    from viobench.tools.datasets.generate.simulation import SimConfig, scene_references, simulate, hssd_scenes
    from viobench.tools.datasets.storage import write_episode
    from robust_sim import IndependentYaw
    from common import Flight
    from pairs import digest
    RAW = Path(args.gen_raw)
    roster = json.loads(Path(args.gen_roster).read_text())["flights"]
    mine = [f for i, f in enumerate(roster) if i % args.workers == args.worker
            and (not args.split or f["split"] in args.split) and (not args.ids or f["id"] in args.ids)][:args.limit]
    log_path = RAW/"generated.jsonl"
    hssd_val = None
    for f in mine:
        target = RAW/f["split"]/f"{f['id']}.zip"
        if target.exists():
            continue
        if shutil.disk_usage(RAW).free < args.min_free_gb*2**30:
            print("disk below threshold; stopping", flush=True); return
        started, status, record = time.time(), "ok", None
        try:
            klass = IndependentYaw if f["regime"] == "independent-yaw" else SimConfig
            apply_task_overrides(f.get("task_overrides"))
            sim = klass(instances=1, duration_seconds=f["seconds"], hold_seconds=f["hold_seconds"],
                        waypoints=max(8, round(f["seconds"]*f["waypoints_per_second"])))
            if f["catalog"] == "hssd-val":
                hssd_val = hssd_val or hssd_scenes("val")
                refs = {f["scene"]: hssd_val[f["scene"]]}
            else:
                refs = scene_references([f["scene"]])
            episode, = simulate(sim, refs, 1, seed=f["seed"], name="native-campaign", log=lambda m: None)
            episode.check_consistency()
            if f.get("crop_start_s"):
                episode = crop_episode(episode, f["crop_start_s"])
            partial = RAW/"partial"; partial.mkdir(parents=True, exist_ok=True)
            write_episode(episode, partial/target.name)
            flight = Flight(partial/target.name)
            report = audit(flight)
            finite = all(np.isfinite(a).all() for a in (flight.v_body, flight.cam_gt, flight.imu))
            if not finite: raise ValueError("non-finite truth or IMU")
            if report["truth_integration_rms_m"] > .05: raise ValueError(f"truth does not integrate: {report['truth_integration_rms_m']} m")
            target.parent.mkdir(parents=True, exist_ok=True)
            record = {**f, "file": target.name, "sha256": digest(partial/target.name), "audit": report,
                      "simulator": asdict(sim), "simulator_class": klass.__name__,
                      "bytes": (partial/target.name).stat().st_size}
            (RAW/f["split"]/f"{f['id']}.json").write_text(json.dumps(record, indent=1))
            (partial/target.name).rename(target)
        except Exception as error:
            status = f"failed: {error!r}"[:300]
            traceback.print_exc()
        with log_path.open("a") as fh:
            fh.write(json.dumps({"id": f["id"], "status": status, "seconds": round(time.time()-started, 1),
                                 "worker": args.worker}) + "\n")
        print(time.strftime("%H:%M"), f["id"], status, round(time.time()-started), "s",
              (record or {}).get("audit", {}).get("flags"), flush=True)


def upload(args):
    """Roster and per-flight audits to the private campaign repo; with --raw also the archives
    (about 130 MB per flight; reserved test archives included, archived but not used). Raw data
    is generated on the GPU box itself, so the training path never needs the Hub copy."""
    from huggingface_hub import HfApi
    api = HfApi()
    api.create_repo(RAW_REPO, repo_type="dataset", private=True, exist_ok=True)
    if not api.repo_info(RAW_REPO, repo_type="dataset").private:
        raise RuntimeError(f"{RAW_REPO} is public")
    have = set(api.list_repo_files(RAW_REPO, repo_type="dataset"))
    shutil.copy(ROSTER, RAW/"roster.json")
    suffixes = (".zip", ".json") if args.raw else (".json",)
    files = [p for p in sorted(RAW.glob("*/*")) if p.suffix in suffixes and p.parent.name != "partial"
             and f"{p.parent.name}/{p.name}" not in have]
    for b in range(0, len(files), args.batch):
        batch = files[b:b+args.batch]
        patterns = [f"{p.parent.name}/{p.name}" for p in batch]
        api.upload_folder(repo_id=RAW_REPO, repo_type="dataset", folder_path=str(RAW), allow_patterns=patterns,
                          commit_message=f"native campaign: +{len(batch)} files")
        print(time.strftime("%H:%M"), f"uploaded {b+len(batch)}/{len(files)}", flush=True)
    api.upload_file(path_or_fileobj=str(RAW/"roster.json"), path_in_repo="roster.json", repo_id=RAW_REPO,
                    repo_type="dataset", commit_message="native campaign roster")


def prepare(args):
    """Training-format shards (the exact preprocessing of every earlier shard) for train or dev
    flights. Workers share one content-addressed staging folder and write their own record files;
    `publish` pushes them. The reserved test split is refused."""
    from odometry_pool import prepare as prepare_flight
    if "test" in (args.split or []):
        raise ValueError("the reserved test split is never prepared before a final candidate is frozen")
    base = json.loads((ROOT/"configs/odometry.json").read_text())
    sensor = json.loads((ROOT/"configs/sensor.json").read_text())
    sensor.update(width=base["model"]["width"], height=base["model"]["height"],
                  portable_pixels="remap", ordered_packet=True)
    staging = Path(args.staging); shards = staging/"shards"; shards.mkdir(parents=True, exist_ok=True)
    metas = sorted(p for s in args.split for p in (RAW/s).glob("*.json"))[args.worker::args.workers]
    for meta_path in metas:
        meta = json.loads(meta_path.read_text())
        done = staging/"records"/f"{meta['id']}.json"
        if done.exists() or not (RAW/meta["split"]/meta["file"]).exists(): continue
        records, _ = prepare_flight(RAW/meta["split"]/meta["file"],
                                    {"scene": meta["scene"], "domain": "native-campaign", "tier": meta["regime"],
                                     "regime": meta["regime"]},
                                    sensor, base["data"]["crops_s"], base["seed"], shards, gate_flights=False)
        for r in records:
            r.update(parent_file=meta["file"], parent_sha256=meta["sha256"], split=meta["split"], catalog=meta["catalog"],
                     flight_id=meta["id"], seconds=meta["seconds"], flags=meta["audit"]["flags"])
        done.parent.mkdir(exist_ok=True)
        done.write_text(json.dumps(records, indent=1))
        print(time.strftime("%H:%M"), meta["id"], len(records), "shards", flush=True)


def publish(args):
    """Push prepared shards (large batches, to stay clear of the Hub commit rate limit) and write
    data/native-campaign/<split>-records.json plus an immutable copy on the data repo."""
    from huggingface_hub import HfApi
    from odometry_store import push_shards, DATA_REPO
    staging = Path(args.staging)
    split, = args.split
    records = [r for p in sorted((staging/"records").glob(f"{split}-*.json")) for r in json.loads(p.read_text())]
    have = {f[len("shards/"):] for f in HfApi().list_repo_files(DATA_REPO, repo_type="dataset") if f.startswith("shards/")}
    todo = sorted({r["file"] for r in records} - have)
    for b in range(0, len(todo), args.batch):
        push_shards(staging/"shards", todo[b:b+args.batch], DATA_REPO, f"native campaign {split}: +{len(todo[b:b+args.batch])} shards")
        print(time.strftime("%H:%M"), f"pushed {b+len(todo[b:b+args.batch])}/{len(todo)}", flush=True)
    listed = {f[len("shards/"):] for f in HfApi().list_repo_files(DATA_REPO, repo_type="dataset") if f.startswith("shards/")}
    if {r["file"] for r in records} - listed: raise RuntimeError("some shards are not visible on the Hub")
    out = staging/f"{split}-records.json"
    out.write_text(json.dumps({"records": records, "flights": len({r["flight_id"] for r in records})}, indent=1))
    name = f"manifests/native-campaign-{split}-records-{len(records)}.json"
    if name not in listed:
        HfApi().upload_file(path_or_fileobj=str(out), path_in_repo=name, repo_id=DATA_REPO, repo_type="dataset",
                            commit_message=f"native campaign {split} records ({len(records)})")
    print("records:", out, "and", name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("roster", "generate", "upload", "prepare", "publish"))
    parser.add_argument("--worker", type=int, default=0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--split", nargs="*")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", nargs="*", help="generate: only these flights (one process per flight isolates native crashes)")
    parser.add_argument("--min-free-gb", type=float, default=200)
    parser.add_argument("--batch", type=int, default=400)
    parser.add_argument("--raw", action="store_true", help="upload: include the raw archives")
    parser.add_argument("--staging", default=str(ROOT/"data"/"native-campaign"))
    parser.add_argument("--gen-roster", default=str(ROSTER), help="generate: roster file (default: the native campaign)")
    parser.add_argument("--gen-raw", default=str(RAW), help="generate: output directory (default: the native campaign's)")
    args = parser.parse_args()
    if args.action == "roster":
        from viobench.tools.datasets.generate.simulation import hssd_scenes
        roster = build_roster(list(hssd_scenes("train")), list(hssd_scenes("val")))
        ROSTER.write_text(json.dumps(roster, indent=1) + "\n")
        from collections import Counter
        print(Counter(f["split"] for f in roster["flights"]), "flights;",
              Counter((f["split"], f["catalog"]) for f in roster["flights"]))
    else:
        {"generate": generate, "upload": upload, "prepare": prepare, "publish": publish}[args.action](args)


if __name__ == "__main__":
    main()
