"""Compare the committed IMU baseline and current VIO on the same episodes.

Run with VIOBench installed: python benchmark.py --max-episodes 1
Reports are JSON lines. Host timing is separate from WebAssembly fuel.
"""

import argparse
from itertools import islice
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter

import numpy as np
from viobench.tools.datasets import sources
from viobench.tools.runner.direct import PythonSolution
from viobench.tools.runner.metrics import evaluate_trajectory, valid_states


WORKSPACE = Path(__file__).resolve().parent
BASELINE = "8fe28cd"
BASELINE_FILE = "Final Project/traditional_vio/solution/solution.py"


def compare(episode, baseline, fused):
    config, frames = episode.adapt(fused.resolution)
    estimators = (baseline.create(config), fused.create(config))
    states = np.empty((2, episode.num_frames, 13))
    timings = np.empty((2, episode.num_frames))
    available = accepted = 0
    for index, (timestamp, frame, imu) in enumerate(episode.steps(frames)):
        for mode, estimator in enumerate(estimators):
            start = perf_counter()
            states[mode, index] = estimator.step(float(timestamp), frame, imu)
            timings[mode, index] = perf_counter() - start
        available += estimators[1].visual_motion is not None
        accepted += estimators[1].visual_update_applied

    truth = episode.ground_truth_state()
    report = {"episode": episode.key, "visual_pairs": available, "ekf_updates": accepted}
    for mode, name in enumerate(("imu_only", "fused")):
        if not valid_states(states[mode]).all():
            raise ValueError(f"{episode.key}: {name} returned an invalid state")
        metrics = evaluate_trajectory(truth, states[mode], episode.frame_times).as_dict()
        metrics["host_median_ms_per_frame"] = float(np.median(timings[mode]) * 1000)
        report[name] = metrics
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sources.add_argument(parser)
    parser.add_argument("--max-episodes", type=int, help="limit the number of episodes")
    args = parser.parse_args()
    if args.max_episodes is not None and args.max_episodes < 1:
        parser.error("--max-episodes must be positive")

    with TemporaryDirectory(prefix="traditional-vio-imu-") as directory:
        baseline_source = subprocess.check_output(
            ["git", "show", f"{BASELINE}:{BASELINE_FILE}"], cwd=WORKSPACE,
        )
        (Path(directory) / "solution.py").write_bytes(baseline_source)
        baseline = PythonSolution(directory)
        fused = PythonSolution(WORKSPACE / "solution")
        for episode in islice(sources.from_arguments(args.episodes), args.max_episodes):
            print(json.dumps(compare(episode, baseline, fused)), flush=True)


if __name__ == "__main__":
    main()
