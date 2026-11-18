"""Resolve experiments from configs/experiments.json and start (or print) their training runs.

    ./teacher_env.sh launch.py D0-ssm D1-ssm D2-ssm [--seed 218] [--dry-run]

Runs go to results/loop/<name>[-s<seed>] with logs alongside, and sync to the private lab
repo each epoch. A run directory that already has a completed checkpoint is resumed.
"""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB_REPO = "SentientNapkin/viobench-teacher-lab"


def resolve(name, seed=None):
    spec = json.loads((ROOT/"configs/experiments.json").read_text())
    exp = spec["experiments"][name]
    args = [a for block in exp.get("use", []) for a in spec["blocks"][block]] + exp.get("args", [])
    if seed is not None:
        args += ["--seed", str(seed)]
    run = name + (f"-s{seed}" if seed is not None else "")
    return run, exp["data"], args


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="+")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    runs = ROOT/"results"/"loop"; runs.mkdir(parents=True, exist_ok=True)
    for name in args.names:
        run, data, extra = resolve(name, args.seed)
        out = runs/run
        cmd = [str(ROOT/"teacher_env.sh"), "teacher_train.py", "--config", str(ROOT/"configs/teachers.json"),
               "--data", data, "--output", str(out), "--hub-repo", LAB_REPO, *extra]
        done = sorted(out.glob("checkpoints/epoch-*/complete.json"))
        if done:
            cmd += ["--resume", str(done[-1].parent)]
        print(" ".join(cmd))
        if not args.dry_run:
            log = open(runs/f"{run}.log", "a")
            subprocess.Popen(["caffeinate", "-i", *cmd], stdout=log, stderr=subprocess.STDOUT, cwd=ROOT,
                             start_new_session=True)


if __name__ == "__main__":
    main()
