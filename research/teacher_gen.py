"""Continuously simulate new training flights into a spool directory (simulator env, CPU).

Scenes: unused ProcTHOR-Train scenes (never the training, development, reserved or
confirmation scenes of earlier work) interleaved with HSSD-Train scenes for visual
diversity. Each pass over the scene list uses a new seed, so later passes add new
routes in the same rooms. Flights follow the benchmark defaults (60 s, 1 s hover,
FOV 120 +/- 15 deg); a fraction use the independent-yaw autopilot for backward and
lateral motion. teacher_pool.py gates, prepares and uploads what lands in the spool.
"""
import argparse
import json
import random
import shutil
import time
from dataclasses import asdict
from pathlib import Path

from viobench.tools.datasets.generate.simulation import SimConfig, procthor_scenes, hssd_scenes, simulate
from viobench.tools.datasets.storage import write_episode

from robust_sim import IndependentYaw

USED = set(range(10, 46)) | set(range(162, 180))  # train roster, reserved, development, confirmation


CACHE_CUTOFF = time.mktime(time.strptime("2026-11-17 23:40", "%Y-%m-%d %H:%M"))


def prune_scene_cache():
    """Delete scene models downloaded by this generator (newer than the cutoff); earlier
    sessions' cache entries are kept. A later pass re-downloads a scene if it needs it."""
    import os
    cache = Path(os.environ["CONTA_CACHE"])
    for entry in cache.iterdir():
        try:
            if entry.is_file() and entry.stat().st_mtime > CACHE_CUTOFF:
                entry.unlink()
        except OSError:
            pass


def scene_list(seed):
    procthor = [n for n in procthor_scenes() if int(n.rsplit("-", 1)[1]) not in USED]
    hssd = list(hssd_scenes("train"))
    rng = random.Random(seed)
    rng.shuffle(procthor); rng.shuffle(hssd)
    # About three ProcTHOR flights per HSSD flight: ProcTHOR matches the benchmark scenes.
    out, h = [], iter(hssd)
    for i, name in enumerate(procthor):
        out.append(name)
        if i % 3 == 2:
            nxt = next(h, None)
            if nxt: out.append(nxt)
    return out + list(h)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spool", default="data/gen-spool")
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--yaw-fraction", type=float, default=0.15)
    parser.add_argument("--max-pending", type=int, default=6, help="Pause while this many zips await preparation")
    parser.add_argument("--min-free-gb", type=float, default=8)
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--worker", type=int, default=0)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    spool = Path(args.spool); spool.mkdir(parents=True, exist_ok=True)
    done_path = spool/"generated.jsonl"
    done = {json.loads(l)["key"] for l in done_path.read_text().splitlines()} if done_path.exists() else set()
    from viobench.tools.datasets.generate.simulation import scene_references
    for p in range(args.passes):
        scenes = scene_list(1000+p)
        for index, scene in enumerate(scenes):
            if index % args.workers != args.worker:
                continue
            key = f"p{p}-{scene}"
            if key in done:
                continue
            while (len(list(spool.glob("*.zip"))) >= args.max_pending
                   or shutil.disk_usage(spool).free < args.min_free_gb*2**30):
                time.sleep(20)
            seed = 90000 + 1000*p + index
            yaw = random.Random(seed).random() < args.yaw_fraction
            klass = IndependentYaw if yaw else SimConfig
            options = klass(instances=1, duration_seconds=args.seconds, spool=str(spool.resolve()))
            started = time.time()
            (spool/"current.json").write_text(json.dumps({"key": key}))  # read by gen_supervisor.sh after a native crash
            try:
                refs = scene_references([scene])
                episode, = simulate(options, refs, 1, seed=seed, name=f"gen{p}", log=lambda m: None)
                episode.check_consistency()
                partial = spool/"partial"; partial.mkdir(exist_ok=True)
                write_episode(episode, partial/f"{key}.zip")
                (partial/f"{key}.zip").rename(spool/f"{key}.zip")
                (spool/f"{key}.json").write_text(json.dumps(
                    {"key": key, "scene": scene, "seed": seed, "pass": p,
                     "regime": "independent-yaw" if yaw else "benchmark",
                     "simulator": asdict(options), "seconds": round(time.time()-started, 1)}))
                status = "ok"
            except Exception as error:
                status = f"failed: {error!r}"[:300]
            prune_scene_cache()
            with done_path.open("a") as f:
                f.write(json.dumps({"key": key, "status": status}) + "\n")
            print(time.strftime("%H:%M"), key, status, round(time.time()-started), "s", flush=True)


if __name__ == "__main__":
    main()
