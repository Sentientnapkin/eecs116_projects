"""Hyperparameter search for the D0-ssm recipe: trial definitions, a GPU-slot scheduler and a summary.

    python hp_search.py run --trials base lr1e-4 ... --seeds 217 218 [--epochs 12] [--slots 1,1,2,2,3,3,7,7]
                           [--extra training.foo=json ...] [--hub]
    python hp_search.py summary [--epochs 12]
    python hp_search.py promote [--slots 4,4,4,4]  # completed 12-epoch screen -> 36 epochs, 3 seeds

Every trial is D0-ssm (configs/experiments.json: recipe + original_sampler, --head ssm, hf:teacher-full)
plus the trial's --set overrides plus any global --extra overrides (e.g. a faster training path).
Runs go to results/loop/HP-<trial>-e<epochs>-s<seed>-hp<k>, one shard cache each (as launch.py does).
The scheduler keeps at most one run per listed slot and launches in the order given (priority order).
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from launch import resolve, ROOT, LAB_REPO

SAMPLER = 'training.sampler={{"mode":"original","windows_per_epoch":{}}}'
# Trial -> overrides on top of D0-ssm. Base: lr 3e-4, warmup 0.5 epoch, EMA 0.995, 64 scored + 32 burn-in
# frames, horizons [0.25,1,3] s, channels [24,48,96,128] / embedding 128, weight decay 0.01, clip 1.
TRIALS = {
    "base": [],
    "lr1e-4": ["training.learning_rate=0.0001"],
    "lr6e-4": ["training.learning_rate=0.0006"],
    "lr1e-3": ["training.learning_rate=0.001"],
    "ema99": ["training.weight_ema=0.99"],
    "ema999": ["training.weight_ema=0.999"],
    # A 64-frame scored window spans about 3.15 s. Only the w128 variant can use 6 s.
    "h-long": ["training.horizons=[0.5,2,3]"],
    "h4": ["training.horizons=[0.25,1,2,3]"],
    # Equal scored frames per epoch: 244x64 = 15,616; 162x96 = 15,552 (sampler needs an even count); 122x128.
    "w96": ["training.window_frames=96", SAMPLER.format(162)],
    "w128": ["training.window_frames=128", SAMPLER.format(122)],
    "w128-h4": ["training.window_frames=128", SAMPLER.format(122), "training.horizons=[0.25,1,3,6]"],
    "cnn-narrow": ["model.channels=[16,32,64,96]", "model.embedding=96"],
    "cnn-wide": ["model.channels=[32,64,128,192]", "model.embedding=192"],
    "warm0": ["training.warmup_epochs=0"],
    "warm2": ["training.warmup_epochs=2"],
    "burn16": ["training.burn_in=16"],
    "burn48": ["training.burn_in=48"],
    "wd0": ["training.weight_decay=0"],
    "wd1e-1": ["training.weight_decay=0.1"],
    "clip03": ["training.grad_clip=0.3"],
    "clip5": ["training.grad_clip=5"],
}
DEFAULT_SLOTS = "1,1,2,2,3,3,7,7"
RUNS = ROOT/"results"/"loop"


def run_name(trial, epochs, seed, tag):
    return f"HP-{trial}-e{epochs}-s{seed}-{tag}"


def command(trial, epochs, seed, tag, extra, hub, overrides=None):
    _, data, args = resolve("D0-ssm", seed)
    run = run_name(trial, epochs, seed, tag)
    sets = (TRIALS[trial] if overrides is None else overrides) + list(extra)
    cmd = [sys.executable, "-B", "odometry_train.py", "--config", str(ROOT/"configs/odometry.json"),
           "--data", data, "--output", str(RUNS/run), "--cache-dir", str(ROOT/"data"/"hub-cache"/run),
           *args, "--epochs", str(epochs)]
    for item in sets: cmd += ["--set", item]
    if hub: cmd += ["--hub-repo", LAB_REPO]
    done = sorted((RUNS/run).glob("checkpoints/epoch-*/complete.json"))
    if done: cmd += ["--resume", str(done[-1].parent)]
    return run, cmd


def status(run):
    path = RUNS/run/"manifest.json"
    return json.loads(path.read_text()).get("status") if path.exists() else None


def schedule(args):
    queue = [(t, s) for t in args.trials for s in args.seeds]
    queue = [(t, s) for t, s in queue if status(run_name(t, args.epochs, s, args.tag)) != "completed"]
    slots = {i: (int(g), None) for i, g in enumerate(args.slots.split(","))}
    failed = False
    while queue or any(p is not None for _, p in slots.values()):
        for i, (gpu, proc) in slots.items():
            if proc is not None and proc.poll() is not None:
                print(time.strftime("%H:%M:%S"), "finished", proc.run, "exit", proc.returncode, flush=True)
                failed |= proc.returncode != 0
                slots[i] = (gpu, proc := None)
            if proc is None and queue:
                trial, seed = queue.pop(0)
                run, cmd = command(trial, args.epochs, seed, args.tag, args.extra or [], args.hub)
                env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu))
                log = open(RUNS/f"{run}.log", "a")
                proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT, env=env,
                                        start_new_session=True)
                proc.run = run
                print(time.strftime("%H:%M:%S"), "launched", run, "gpu", gpu, "pid", proc.pid, flush=True)
                slots[i] = (gpu, proc)
        if queue or any(p is not None for _, p in slots.values()):
            time.sleep(30)
    return int(failed)


def promote(args):
    scores = {}
    for trial in args.trials:
        scores[trial] = []
        for seed in (217, 218):
            name = run_name(trial, 12, seed, args.tag)
            if status(name) != "completed":
                raise SystemExit(f"Cannot advance an incomplete screen: {name}")
            history = json.loads((RUNS/name/"metrics.json").read_text())
            scores[trial].append(min(row["selection_score"] for row in history))
    means = {trial: sum(values)/len(values) for trial, values in scores.items()}
    if "base" not in means:
        raise SystemExit("The screen requires the paired base trial.")
    contenders = [trial for trial, score in means.items() if score < means["base"]]
    args.trials = sorted(contenders, key=lambda trial: (means[trial], trial))[:2]
    print(f"12-epoch screening means: {json.dumps(means, sort_keys=True)}", flush=True)
    print(f"Advancing {args.trials} to 36 epochs on seeds 217, 218, 219.", flush=True)
    args.epochs = 36
    args.seeds = [217, 218, 219]
    return schedule(args)


def summary(args):
    rows = []
    for path in sorted(RUNS.glob(f"HP-*-e{args.epochs}-s*")):
        if not path.is_dir() or not (path/"metrics.json").exists(): continue
        trial, seed = path.name[3:].rsplit(f"-e{args.epochs}-s", 1)
        history = json.loads((path/"metrics.json").read_text())
        best = min(history, key=lambda h: h["selection_score"])
        rows.append((trial, seed.split("-")[0], len(history), best["selection_score"], best["epoch"], status(path.name)))
    by = {}
    for trial, seed, n, score, epoch, st in rows:
        by.setdefault(trial, []).append((seed, n, score, epoch, st))
    for trial, items in sorted(by.items(), key=lambda kv: sum(x[2] for x in kv[1])/len(kv[1])):
        mean = sum(x[2] for x in items)/len(items)
        print(f"{trial:12s} mean {mean:.3f}  " + "  ".join(f"s{s}:{v:.3f}@{e}/{n}{'' if st == 'completed' else ' ' + str(st)}"
                                                       for s, n, v, e, st in sorted(items)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("run", "summary", "print", "promote"))
    parser.add_argument("--trials", nargs="+", default=list(TRIALS))
    parser.add_argument("--seeds", nargs="+", type=int, default=[217, 218])
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--slots", default=DEFAULT_SLOTS, help="Comma-separated GPU ids, one entry per concurrent run")
    parser.add_argument("--tag", default="hp1")
    parser.add_argument("--extra", nargs="*", help="Overrides added to every trial (KEY=JSON)")
    parser.add_argument("--hub", action="store_true", help="Sync runs to the lab repo (off: it rate-limits commits)")
    args = parser.parse_args()
    if args.mode == "summary": return summary(args)
    if args.mode == "promote": return promote(args)
    if args.mode == "print":
        for t in args.trials:
            for s in args.seeds: print(" ".join(command(t, args.epochs, s, args.tag, args.extra or [], args.hub)[1]))
        return
    return schedule(args)


if __name__ == "__main__":
    sys.exit(main())
