"""Bundle and benchmark the IMU experiments using a common VIOBench runtime."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

VARIANTS = {
    "avg5": "RollingAverage",
    "avg15": "Average15",
    "avg20": "Average20",
    "previous": "PreviousReading",
    "hold109": "Hold109",
    "steps5": "FiveSteps",
    "steps20": "TwentySteps",
    "taylor10": "TaylorTen",
    "reuse_midpoint": "ReuseMidpoint",
}
HERE = Path(__file__).resolve().parent


def evaluate(variant, args, cli):
    with TemporaryDirectory(prefix="eecs116-imu-") as directory:
        source = Path(directory)
        shutil.copyfile(HERE / "models.py", source / "models.py")
        shutil.copyfile(HERE.parent / "dead_reckoning" / "solution.py", source / "batched.py")
        (source / "solution.py").write_text(f"from models import {VARIANTS[variant]} as Solution\n")
        wasm = args.output / f"imu_{variant}.wasm"
        with (args.output / f"imu_{variant}.log").open("w") as log:
            subprocess.run([cli, "bundle", str(source), "--runtime", str(args.runtime), "-o", str(wasm)],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
            command = [cli, "evaluate", str(wasm)]
            if args.max_episodes is not None:
                command += ["--max-episodes", str(args.max_episodes)]
            subprocess.run(command, cwd=args.output, stdout=log, stderr=subprocess.STDOUT, check=True)
    return variant


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-episodes", type=int)
    args = parser.parse_args()
    args.runtime = args.runtime.resolve()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    cli = shutil.which("viobench")
    if cli is None:
        parser.error("viobench must be on PATH")
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for variant in executor.map(lambda name: evaluate(name, args, cli), VARIANTS):
            print(f"Completed {variant}", flush=True)


if __name__ == "__main__":
    main()
