"""Gate, prepare and upload spooled flights into the Hub shard pool (training env).

For each simulated flight in the spool:
  1. Quality gates, so the pool stays learnable and representative (lessons from other
     teams' generated data): at least 2 m of camera travel (no zero-velocity flights),
     no stall (the autopilot can park forever near the start), finite truth. Hover, dark
     and low-texture stretches are legitimate conditions and are only audited (2026-11-18).
  2. Prepare crops at 0 s and 5 s with the same causal sensor pipeline and settings as
     the base teacher dataset, written content-addressed (<sha256>.npz).
  3. Every --batch shards, upload them plus the growing pool manifest
     (manifests/<pool>.json) to the private data repo, move them into the local shard
     cache (so training never re-downloads them), and delete the raw flight.
Rejected flights are logged with their reason in the pool manifest.
"""
import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

import numpy as np

from common import Flight
from pairs import digest, variant_rows
from streaming import Inputs
from teacher_store import push_shards, push_manifest, DATA_REPO

ROOT = Path(__file__).resolve().parent


def gate(f):
    speed = np.linalg.norm(f.v_body, axis=1)
    travel = float(np.sum(np.linalg.norm(np.diff(f.cam_gt, axis=0), axis=1)))
    moving = float(np.mean(speed > .1))
    # Stall: the last 40% of the flight stays within 0.5 m of where that stretch began.
    tail = f.cam_gt[int(.6*len(f.cam_gt)):]
    stalled = float(np.max(np.linalg.norm(tail-tail[0], axis=1))) < .5
    sample = np.asarray(f.frames[::20], dtype=np.float32)
    gray = sample.mean(-1) if sample.ndim == 4 else sample
    dark = float(np.mean(gray.mean((1, 2)) < 15))
    flat = float(np.mean(gray.std((1, 2)) < 6))
    audit = {"travel_m": round(travel, 2), "moving_fraction": round(moving, 3), "stalled": stalled,
             "dark_fraction": round(dark, 3), "flat_fraction": round(flat, 3),
             "speed_p50_p90": [round(float(np.percentile(speed, q)), 3) for q in (50, 90)],
             "backward_fraction": round(float(np.mean(f.v_body[:, 0] < -.2)), 3),
             "lateral_fraction": round(float(np.mean(np.abs(f.v_body[:, 1]) > .2)), 3)}
    # Reject only simulator failures (corrupt truth, no motion, stall). Hover, darkness and low
    # texture are legitimate conditions: they stay in the audit for sampling/reporting, not gating.
    finite = all(np.isfinite(np.asarray(a, np.float64)).all() for a in (f.v_body, f.cam_gt, f.imu))
    reasons = [r for r, bad in (("nonfinite", not finite), ("travel<2m", travel < 2), ("stalled", stalled)) if bad]
    return reasons, audit


def prepare(zip_path, meta, sensor, crops, seed, out_dir, gate_flights=True):
    records = []
    parent = digest(zip_path)
    for crop in crops:
        f = Flight(zip_path, crop=crop)
        if crop == crops[0]:
            reasons, audit = gate(f)
            if reasons and gate_flights:
                return None, {"rejected": reasons, **audit}
        h, w = f.frames[0].shape[:2]
        state = Inputs(sensor, f.K, (h, w), f.T_bc[:3, :3])
        images, imu, rotation = [], [], []
        for t, frame, packet in variant_rows(f, "clean", seed):
            im, u, rot, _ = state.step(t, frame, packet, "triple_derot")
            images.append(im); imu.append(u); rotation.append(rot.copy())
        tmp = out_dir/f"tmp-{parent[:12]}-{crop}.npz"
        np.savez_compressed(tmp, images=np.stack(images), imu=np.stack(imu), R=np.stack(rotation),
                            v=f.v_body, times=f.ft, cam_gt=f.cam_gt, T_bc=f.T_bc)
        sha = digest(tmp)
        final = out_dir/f"{sha}.npz"
        tmp.replace(final)
        v = f.v_body
        records.append({"file": final.name, "sha256": sha, "scene": meta["scene"], "parent_sha256": parent,
                        "crop_s": crop, "frames": len(v), "regime": meta.get("regime"), "pass": meta.get("pass"),
                        "domain": meta.get("domain", "native-generated"), "tier": meta.get("tier"),
                        "backward_fraction": float(np.mean(v[:, 0] < -.2)),
                        "lateral_fraction": float(np.mean(np.abs(v[:, 1]) > .2))})
    return records, audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spool", default="data/gen-spool")
    parser.add_argument("--pool", default="gen-pool-v1")
    parser.add_argument("--cache-dir", default="data/hub-cache")
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--repo", default=DATA_REPO)
    parser.add_argument("--idle-exit-minutes", type=float, default=90)
    args = parser.parse_args()
    teachers = json.loads((ROOT/"configs/teachers.json").read_text())
    sensor = json.loads((ROOT/"configs/sensor.json").read_text())
    sensor.update(width=teachers["model"]["width"], height=teachers["model"]["height"],
                  portable_pixels="remap", ordered_packet=True)
    crops, seed = teachers["data"]["crops_s"], teachers["seed"]
    spool = Path(args.spool); staging = spool/"staging"; staging.mkdir(parents=True, exist_ok=True)
    shards = Path(args.cache_dir)/"shards"; shards.mkdir(parents=True, exist_ok=True)
    state_path = spool/f"{args.pool}.json"
    pool = json.loads(state_path.read_text()) if state_path.exists() else {
        "status": "growing", "pool": args.pool, "sensor_config": sensor, "crops_s": crops,
        "sources": {n: digest(ROOT/n) for n in ("teacher_pool.py", "streaming.py", "common.py", "pairs.py")},
        "datasets": {"train": []}, "rejected": []}
    pending, done_zips, last_work = [], [], time.time()

    def flush():
        nonlocal pending, done_zips
        if not pending:
            return
        names = {r["file"] for r in pending}
        for attempt in range(5):
            try:
                push_shards(staging, names, args.repo, f"{args.pool}: +{len(names)} shards")
                pool["datasets"]["train"] += pending
                push_manifest(pool, args.pool, args.repo)
                break
            except Exception as error:
                print("upload retry", attempt, repr(error)[:200], flush=True); time.sleep(60*(attempt+1))
        else:
            raise RuntimeError("Hub upload failed repeatedly")
        state_path.write_text(json.dumps(pool, indent=1))
        for name in names:
            shutil.move(str(staging/name), str(shards/name))
        for z in done_zips:
            z.unlink(missing_ok=True); z.with_suffix("").with_suffix(".json").unlink(missing_ok=True)
        print(time.strftime("%H:%M"), f"uploaded {len(names)} shards; pool train={len(pool['datasets']['train'])}"
              f" rejected={len(pool['rejected'])}", flush=True)
        pending, done_zips = [], []

    while True:
        zips = sorted(spool.glob("*.zip"), key=lambda p: p.stat().st_mtime)
        zips = [z for z in zips if z not in done_zips]
        if not zips:
            flush()
            if time.time()-last_work > args.idle_exit_minutes*60:
                print("spool idle; exiting", flush=True); return
            time.sleep(20); continue
        z = zips[0]
        meta = json.loads(z.with_suffix("").with_suffix(".json").read_text())
        started = time.time()
        try:
            records, audit = prepare(z, meta, sensor, crops, seed, staging)
        except Exception as error:
            records, audit = None, {"rejected": [f"error: {error!r}"[:200]]}
        if records:
            pending += records
            print(time.strftime("%H:%M"), meta["key"], "ok", audit, round(time.time()-started), "s", flush=True)
        else:
            pool["rejected"].append({"key": meta["key"], "scene": meta["scene"], **audit})
            state_path.write_text(json.dumps(pool, indent=1))
            print(time.strftime("%H:%M"), meta["key"], "REJECTED", audit, flush=True)
            z.unlink(missing_ok=True); z.with_suffix("").with_suffix(".json").unlink(missing_ok=True)
            continue
        done_zips.append(z)
        last_work = time.time()
        if len(pending) >= args.batch:
            flush()


def expand(args_list=None):
    """Prepare ledger parents into content-addressed shards in bounded, verified batches.

    ./teacher_env.sh -c 'from teacher_pool import expand; expand()' --select proxy-train --worker 0 --workers 2
    Writes data/expand/<selection>-<worker>.json (records so far); upload happens per batch and
    a shard is moved into the local cache only after the Hub lists it.
    """
    from huggingface_hub import HfApi
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default="data/ledger/ledger.json")
    parser.add_argument("--select", default="proxy-train")
    parser.add_argument("--exclude-manifest", default="data/hub-cache/manifests/teacher-full.json")
    parser.add_argument("--worker", type=int, default=0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--batch", type=int, default=20)
    parser.add_argument("--cache-dir", default="data/hub-cache")
    parser.add_argument("--repo", default=DATA_REPO)
    args = parser.parse_args(args_list)
    teachers = json.loads((ROOT/"configs/teachers.json").read_text())
    sensor = json.loads((ROOT/"configs/sensor.json").read_text())
    sensor.update(width=teachers["model"]["width"], height=teachers["model"]["height"],
                  portable_pixels="remap", ordered_packet=True)
    ledger = json.loads(Path(args.ledger).read_text())
    domain, split = args.select.split("-")
    have = {r["parent_sha256"] for r in json.loads(Path(args.exclude_manifest).read_text())["datasets"]["train"]
            if "parent_sha256" in r}
    parents = [r for r in ledger["rows"] if r["domain"] == domain and r["split"] == split and r["eligible"]
               and r["sha256"] not in have]
    parents = parents[args.worker::args.workers]
    out = Path("data/expand"); staging = out/f"staging-{args.worker}"; staging.mkdir(parents=True, exist_ok=True)
    shards = Path(args.cache_dir)/"shards"; shards.mkdir(parents=True, exist_ok=True)
    state_path = out/f"{args.select}-{args.worker}.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"records": [], "done": []}
    pending, api = [], HfApi()

    def flush():
        nonlocal pending
        if not pending: return
        names = {r["file"] for r in pending}
        push_shards(staging, names, args.repo, f"{args.select}: +{len(names)} shards")
        listed = set(api.list_repo_files(args.repo, repo_type="dataset"))
        missing = [n for n in names if f"shards/{n}" not in listed]
        if missing: raise RuntimeError(f"Upload not visible on the Hub: {missing[:3]}")
        for n in names: shutil.move(str(staging/n), str(shards/n))
        state["records"] += pending; state_path.write_text(json.dumps(state, indent=1))
        print(time.strftime("%H:%M"), f"worker {args.worker}: {len(state['records'])} shards verified", flush=True)
        pending = []

    for row in parents:
        if row["sha256"] in state["done"]: continue
        meta = {"scene": row["scene"], "domain": row["domain"], "tier": row["tier"], "seed": row.get("seed")}
        records, _ = prepare(row["path"], meta, sensor, teachers["data"]["crops_s"], teachers["seed"], staging,
                             gate_flights=False)
        for r in records: r["parent_file"] = row["file"]
        pending += records; state["done"].append(row["sha256"])
        if len(pending) >= args.batch: flush()
    flush()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "expand":
        expand(sys.argv[2:])
    else:
        main()
