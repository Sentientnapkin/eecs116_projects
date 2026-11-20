"""Evaluate many Wasm guests on many episodes in one parallel pass over all CPU cores.

    python bench_eval.py --guest vins_mono=/path/vins_mono.wasm --guest openvins=/path/openvins.wasm \\
        --episodes /path/to/episodes --out results/bench/pool [--workers 180] [--limit N]

Run with the pinned viobench venv (research/baselines/openvins-9b1b079.md), like wasm_eval.py. Guests are fuel-metered
Wasmtime modules, so this is CPU work: every (guest, episode) pair is an independent task, scheduled most expensive
guest first so the slowest episodes start earliest and the pass ends when the last one does. Results are cached by the
guest's SHA-256 and the episode file name, so a repeated or interrupted pass only runs what is missing.

Writes <out>/<guest>-<sha8>/scores.json (per-episode rows, same fields as wasm_eval.py) and <out>/matrix.json
(episode x guest ATE), and prints per-guest mean/median/p90 and the course-server score where one is known.
"""
import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

import wasm_eval

# Relative cost per episode of the provided/our guests (seconds, measured); unknown guests are assumed expensive.
COST = {"vins_mono": 200, "openvins": 150, "b_d0": 100, "n2_kfgrid": 150, "dead_reckoning": 5, "cpp_minimal": 2}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--guest", action="append", default=[], metavar="NAME=WASM")
    parser.add_argument("--episodes", required=True, help="directory of episode .zip archives (or one archive)")
    parser.add_argument("--out", required=True)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 8) - 12))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--score-only", action="store_true")
    args = parser.parse_args()
    source = Path(args.episodes)
    archives = sorted(source.glob("*.zip")) if source.is_dir() else [source]
    archives = archives[:args.limit]
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    guests = {}
    for spec in args.guest:
        name, path = spec.split("=", 1)
        sha = wasm_eval.sha256(path)
        guests[name] = (Path(path), out/f"{name}-{sha[:8]}", sha)
        guests[name][1].mkdir(parents=True, exist_ok=True)
    tasks = [(name, wasm, folder, a) for name, (wasm, folder, _) in sorted(guests.items(), key=lambda kv: -COST.get(kv[0], 300))
             for a in archives]
    started = time.time()
    if not args.score_only:
        todo = [t for t in tasks if not (t[2]/t[3].stem/"report"/"report.json").exists()]
        print(f"{len(tasks)} tasks, {len(tasks)-len(todo)} cached, {len(todo)} to run on {args.workers} workers", flush=True)
        done = 0
        with ThreadPoolExecutor(args.workers) as pool:
            for future in as_completed([pool.submit(wasm_eval.run_one, w, a, f) for _, w, f, a in todo]):
                future.result(); done += 1
                if done % 25 == 0 or done == len(todo):
                    print(f"  {done}/{len(todo)} done, {time.time()-started:.0f}s", flush=True)
    matrix = {a.stem: {} for a in archives}
    for name, (wasm, folder, sha) in guests.items():
        with ThreadPoolExecutor(min(args.workers, 64)) as pool:
            rows = list(pool.map(lambda a: wasm_eval.score_one(a, folder/a.stem), archives))
        (folder/"scores.json").write_text(json.dumps({"guest": {"name": name, "wasm": str(wasm), "sha256": sha,
                                                               "archives": [str(a) for a in archives]}, "rows": rows}, indent=1))
        for row in rows:
            matrix[row["episode"]][name] = row.get("ate_full")
        ok = [r for r in rows if r.get("ate_full") is not None]
        if not ok:
            print(f"{name}: no scored episodes"); continue
        ates = np.array([r["ate_full"] for r in ok])
        server = None
        try:
            from server_benchmark import SERVER
            server = SERVER.get(name, {}).get("mean_ate_m")
        except Exception:
            pass
        print(f"{name:16s} n={len(ok):4d}/{len(rows)} mean {ates.mean():7.3f} median {np.median(ates):6.3f} p90 {np.percentile(ates, 90):7.3f} "
              f"max {ates.max():8.2f} peak fuel {max(r['peak_fuel_per_frame'] for r in ok):,}"
              + (f"   [server {server:.3f}]" if server else ""))
    (out/"matrix.json").write_text(json.dumps({"guests": {n: g[2] for n, g in guests.items()}, "ate_full": matrix}, indent=1))
    print(f"total {time.time()-started:.0f}s")


if __name__ == "__main__":
    main()
