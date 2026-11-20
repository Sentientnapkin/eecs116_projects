"""Package the calibrated server benchmark and upload it as a PRIVATE Hugging Face dataset.

    python release_benchmark.py --calibration results/eval/server-benchmark/calibration.json \\
        --scores /data/backups/rganapa/Sebastian/baselines/bench-pool --stage <dir> [--repo SentientNapkin/viobench-server-calibrated] [--no-upload]

The dataset contains the selected episodes unchanged (official archive format, so `viobench evaluate x.wasm <dir>` runs
them), a manifest with each episode's hash and truth statistics, every measured guest's per-episode result, the
calibration, and the code that produced them. The repository is created private and this script never makes it public.
"""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CODE = ["server_benchmark.py", "bench_eval.py", "failure_analysis.py", "wasm_eval.py", "release_benchmark.py", "native_campaign.py"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration", required=True)
    parser.add_argument("--scores", required=True, help="bench_eval.py output directory")
    parser.add_argument("--raw", default="/data/backups/rganapa/Sebastian/gen/raw-bench")
    parser.add_argument("--stage", required=True)
    parser.add_argument("--repo", default="SentientNapkin/viobench-server-calibrated")
    parser.add_argument("--no-upload", action="store_true")
    parser.add_argument("--all", action="store_true", help="include every generated flight, not only the calibrated selection")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    from server_benchmark import SERVER
    calibration = json.loads(Path(args.calibration).read_text())
    selected = calibration["selected"]
    stage = Path(args.stage); (stage/"episodes").mkdir(parents=True, exist_ok=True); (stage/"code").mkdir(exist_ok=True)
    manifest = []
    everything = sorted(p.stem for p in (Path(args.raw)/"bench").glob("*.json")) if args.all else selected
    draws = calibration.get("selection_weights", {})
    for name in everything:
        meta = json.loads((Path(args.raw)/"bench"/f"{name}.json").read_text()); a = meta["audit"]
        src, dst = Path(args.raw)/"bench"/f"{name}.zip", stage/"episodes"/f"{name}.zip"
        if not dst.exists():
            try: os.link(src, dst)
            except OSError: shutil.copy2(src, dst)
        manifest.append({"in_benchmark": name in draws or not draws, "draws": draws.get(name, 0 if args.all else 1), "start_offset_s": float(meta.get("crop_start_s", 0) or 0), "planner_setting": meta.get("setting"), "id": name, "file": f"episodes/{name}.zip", "sha256": meta["sha256"], "scene": meta["scene"],
                         "catalog": meta["catalog"], "group": meta["group"], "seed": meta["seed"], "seconds": a["seconds"],
                         "frames": a["frames"], "zero_motion_ate_m": a["zero_motion_ate_m"], "travel_m": a["travel_m"],
                         "speed_p10_p50_p90": a["speed_p10_p50_p90"], "flags": a["flags"]})
    (stage/"manifest.json").write_text(json.dumps({"episodes": manifest}, indent=1))
    # per-guest results on the selected episodes (plus on the whole pool, for reference)
    results = {}
    for path in sorted(Path(args.scores).glob("*/scores.json")):
        d = json.loads(path.read_text()); name = d["guest"]["name"]
        rows = {r["episode"]: r for r in d["rows"] if r.get("ate_full") is not None}
        sel = [rows[n]["ate_full"] for n in selected if n in rows]
        wts = [calibration.get("selection_weights", {}).get(n, 1) for n in selected if n in rows]
        if len(sel) < 5: continue
        pool = [r["ate_full"] for r in rows.values()]
        results[name] = {"wasm_sha256": d["guest"]["sha256"], "selected_n": len(sel), "selected_mean_ate_m": float(np.average(sel, weights=wts)),
                         "selected_median_ate_m": float(np.median(sel)), "pool_mean_ate_m": float(np.mean(pool)),
                         "peak_fuel_per_frame": max(r["peak_fuel_per_frame"] for r in rows.values()),
                         "per_episode_ate_m": {n: rows[n]["ate_full"] for n in selected if n in rows}}
    (stage/"results.json").write_text(json.dumps({"server_scores_supplied_by_course_leaderboard": {k: v for k, v in SERVER.items() if "compact" not in k}, "guests": results,
                                                  "calibration": {k: v for k, v in calibration.items() if k != "selected"}}, indent=1))
    sel_rows = [m for m in manifest if m["in_benchmark"]]
    zero = np.average([m["zero_motion_ate_m"] for m in sel_rows], weights=[max(m["draws"], 1) for m in sel_rows])
    lines = ["| guest | benchmark mean ATE (m) | calibrated pool mean (m) | 90% range of a 12-episode draw | course server (m) |", "| --- | ---: | ---: | --- | ---: |"]
    lines.append(f"| identity pose (`cpp_minimal`) | {zero:.3f} | {SERVER['cpp_minimal']['mean_ate_m']:.3f} (matched by construction) | - | {SERVER['cpp_minimal']['mean_ate_m']:.3f} |")
    for name, info in sorted(calibration["guests"].items(), key=lambda kv: kv[1]["calibrated_mean"]):
        r = results.get(name, {})
        server = info.get("server")
        lines.append(f"| `{name}` | {r.get('selected_mean_ate_m', float('nan')):.3f} | {info['calibrated_mean']:.3f} | "
                     f"{info['p5_p95_of_12'][0]:.2f}-{info['p5_p95_of_12'][1]:.2f} | {'%.3f' % server if server else 'not on the server'} |")
    groups = {}
    for m in manifest: groups[m["group"]] = groups.get(m["group"], 0)+1
    card = f"""---
pretty_name: VIOBench server-calibrated benchmark
license: other
task_categories: [robotics]
---
# VIOBench server-calibrated benchmark (private draft)

{len(manifest)} raw VIOBench episodes ({len(sel_rows)} of them form the calibrated benchmark, weighted by `draws` in `manifest.json`; the rest are the unselected pool, released for further analysis; 60 s, 1200 frames, official archive format) whose flight-extent and flight-length
distribution is calibrated so that what the course server reveals about its own flights is reproduced. Episodes use the
upstream generator's defaults (60 s, 48 waypoints, 1 s hover, FOV 120 +/- 15 deg, nominal camera, upstream IMU noise)
**except for the planner's speed settings**: the server's 12 flights average 59.6 m of path (39-80 m) while the public set
averages 18 m and the default planner cannot exceed about 48 m, so cruise speed, acceleration, jerk, yaw rate and roadmap
spacing are raised (see `code/server_fast_pool.json`, field `task_overrides`). No guest, ours or anyone's, chose the flights.

Run any guest: `viobench evaluate guest.wasm <dir with the episode zips>` (mean unaligned ATE is the headline), or
`python code/bench_eval.py --guest name=guest.wasm --episodes episodes --out out` to run every guest on all cores.

## How it was calibrated
The server's `cpp_minimal` baseline outputs an identity pose, so its score (4.694 m) is the mean RMS distance of the truth
from its start: a pure flight-extent anchor. The selection weights come from two guest-independent numbers only: that extent and the
server's mean path length (scene-balanced base weights tilted exponentially in each flight's own extent and path length). Everything else below is a held-out check; it is not fitted.
The course server has 12 episodes, so its own numbers carry sampling noise; the interval column shows how much a 12-episode
draw from this benchmark varies.

{chr(10).join(lines)}

## Contents
- `episodes/` every generated episode, unchanged generator output. About half start from the usual seated hover; the other half start mid-flight (`start_offset_s` > 0 in the manifest): the flight is generated longer and its first 3-40 s cropped away, so the drone is already moving. `manifest.json`: hashes, scenes, truth statistics.
- `results.json`: per-episode ATE of every measured guest, the server scores, the calibration.
- `code/`: generator roster, calibration, evaluation and analysis scripts.

## Limitations (read before trusting a number)
- Calibrated on two scalars (extent, path length) from 12 server episodes; the speed settings are our inference of how the server's faster flights were made, not its actual spec. The server's scenes and any difference in its camera or start
  conditions are unknown; a guest that depends on those can still rank differently there.
- Scene groups: {groups}. `clean` scenes are in none of our models' training data; `dev` and `seen` scenes were used by our
  models, so learned-model results on them are optimistic. Large-extent flights come mostly from big HSSD houses.
- VIO guests fail in a heavy tail here: OpenVINS and VINS-Mono have medians of 0.58 and 0.62 m (server means 0.553 and 0.475 m) but means of 28.5 and 5.5 m, because of rare divergences. These concentrate in ProcTHOR scenes with textureless views and in runs that initialize late. A 12-episode draw from this benchmark reproduces the server's clean VIO scores only rarely, so the server's own flights are probably friendlier to VIO than this pool. Use the medians, not the means, of VIO guests here.
- `dead_reckoning` scores about 7.0 m here against 9.07 m on the server, so this benchmark is somewhat easier than the server for that guest. B-D0 (4.20 m calibrated, 90% range 3.46-5.06) is inside the range of the server's 4.55 m.
- Half of the flights start mid-route (see `start_offset_s`); whether the server's flights do is unknown. Learned guests do slightly worse on mid-flight starts (rank correlation 0.2-0.3 of error with start offset).
- The speed settings that make the flights as long as the server's are our inference, not the server's spec.
- The server's hidden episodes were never downloaded or used; only published scores were.
- Reserved-test scenes of our campaign are not used.
"""
    (stage/"README.md").write_text(card)
    for name in CODE:
        if (HERE/name).exists(): shutil.copy2(HERE/name, stage/"code"/name)
    for cfg in ("server_fast_pool.json", "server_benchmark_pool.json"):
        if (HERE/"configs"/cfg).exists(): shutil.copy2(HERE/"configs"/cfg, stage/"code"/cfg)
    shipped = stage/"code"/"server_benchmark.py"
    shipped.write_text("".join(l for l in shipped.read_text().splitlines(True) if "compact" not in l))
    (stage/"code"/"server_observed.json").unlink(missing_ok=True)
    print(f"staged {len(manifest)} episodes in {stage}")
    if args.no_upload:
        return
    from huggingface_hub import HfApi
    api = HfApi()
    api.create_repo(args.repo, repo_type="dataset", private=True, exist_ok=True)
    if args.all:  # hundreds of GB: resumable, parallel upload (rerun the command to continue after any failure)
        api.upload_large_folder(folder_path=str(stage), repo_id=args.repo, repo_type="dataset", num_workers=args.workers)
    else:
        api.upload_folder(folder_path=str(stage), repo_id=args.repo, repo_type="dataset", commit_message="Update server-calibrated benchmark")
    print("uploaded (private):", args.repo)


if __name__ == "__main__":
    main()
