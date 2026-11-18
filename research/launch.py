"""Resolve experiments from configs/experiments.json and start (or print) their training runs.

    python launch.py D0-ssm D1-ssm D2-ssm [--seed 218] [--gpu 0] [--tag gpu] [--dry-run]

Runs go to results/loop/<name>[-s<seed>] with logs alongside, and sync to the private lab
repo each epoch. A run directory that already has a completed checkpoint is resumed.
On the Mac the course environment wrapper (odometry_env.sh) is used; elsewhere the current
Python runs odometry_train.py directly. --gpu pins each launched run to one CUDA device,
consecutive runs taking consecutive devices (e.g. --gpu 0 with three names uses 0, 1, 2).
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB_REPO = "SentientNapkin/viobench-teacher-lab"


def resolve(name, seed=None, tag=None):
    spec = json.loads((ROOT/"configs/experiments.json").read_text())
    exp = spec["experiments"][name]
    args = [a for block in exp.get("use", []) for a in spec["blocks"][block]] + exp.get("args", [])
    if seed is not None:
        args += ["--seed", str(seed)]
    run = name + (f"-s{seed}" if seed is not None else "") + (f"-{tag}" if tag else "")
    return run, exp["data"], args


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="+")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--gpu", type=int, help="First CUDA device; each further run takes the next one")
    parser.add_argument("--tag", help="Suffix for run names (e.g. the machine), so runs never share a Hub folder")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    runs = ROOT/"results"/"loop"; runs.mkdir(parents=True, exist_ok=True)
    mac = sys.platform == "darwin" and (ROOT/"odometry_env.sh").exists() and Path("/opt/miniconda3/bin/python").exists()
    python = [str(ROOT/"odometry_env.sh")] if mac else [sys.executable, "-B"]
    for index, name in enumerate(args.names):
        run, data, extra = resolve(name, args.seed, args.tag)
        out = runs/run
        cmd = [*python, "odometry_train.py", "--config", str(ROOT/"configs/odometry.json"),
               "--data", data, "--output", str(out), "--hub-repo", LAB_REPO,
               # One cache per run: concurrent runs must never evict or rewrite each other's shards.
               "--cache-dir", str(ROOT/"data"/"hub-cache"/run), *extra]
        done = sorted(out.glob("checkpoints/epoch-*/complete.json"))
        if done:
            cmd += ["--resume", str(done[-1].parent)]
        env = dict(os.environ)
        if args.gpu is not None:
            env["CUDA_VISIBLE_DEVICES"] = str(args.gpu + index)
        print(("CUDA_VISIBLE_DEVICES=" + env["CUDA_VISIBLE_DEVICES"] + " " if args.gpu is not None else "") + " ".join(cmd))
        if not args.dry_run:
            log = open(runs/f"{run}.log", "a")
            prefix = ["caffeinate", "-i"] if sys.platform == "darwin" else []
            subprocess.Popen([*prefix, *cmd], stdout=log, stderr=subprocess.STDOUT, cwd=ROOT, env=env,
                             start_new_session=True)


if __name__ == "__main__":
    main()
