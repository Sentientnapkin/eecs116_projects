"""Score prototype variants (and cheat/oracle variants) on episodes with viobench's own metric.

    python run.py ~/data/agile_a ~/data/public                 # all variants
    python run.py ~/data/agile_a --variants imu vision         # a subset

Unaligned ATE (the graded number) per episode and the mean; rotation RMSE shows whether heading drift was fixed.
"""
import argparse
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "solution"))

import solution as S  # noqa: E402
from viobench.tools.datasets.sources import episodes  # noqa: E402
from viobench.tools.geometry import poses_to_matrices  # noqa: E402
from viobench.tools.runner.metrics import evaluate_trajectory  # noqa: E402

VARIANTS = {
    "zeros": None,                                            # output "never moved"
    "final": S.FINAL,                                         # the chosen configuration
    "imu": dict(vision=False),                                # = the course's new dead-reckoning baseline
    "vision": dict(vision=True),                              # + gyro-bias / attitude correction from corners
    "vision+dir": dict(vision=True, use_direction=True),      # + visual direction of travel
    "cheat_rotation": dict(vision=False, oracle="rotation"),  # true attitude every frame (upper bound for vision)
    "cheat_rot+speed": dict(vision=False, oracle="rotation+speed"),
    "cheat_rot+dir": dict(vision=False, oracle="rotation+direction"),             # true rotation + direction of travel
    "cheat_rot+dir+0.35": dict(vision=False, oracle="rotation+direction+fixed_speed"),  # ... at a constant 0.35 m/s
    "cheat_velocity": dict(vision=False, oracle="rotation+velocity"),             # sanity check: should be ~0
    "cheat_kf_dir": dict(vision=False, velocity_mode="filter", oracle="kf_direction"),  # filter speed, true direction
}


def window_direction_quality(windows, episode, gt_state):
    """Share of moving windows whose measured direction of travel is within 30 degrees of the truth."""
    T = poses_to_matrices(gt_state[:, :7])
    times = episode.frame_times
    good = total = 0
    for row in windows:
        if not row[11] or not np.any(row[7:10]):
            continue
        i0, i1 = np.searchsorted(times, row[0] - 1e-6), np.searchsorted(times, row[1] - 1e-6)
        rel = T[i0, :3, :3].T @ (T[i1, :3, 3] - T[i0, :3, 3])
        if np.linalg.norm(rel) < 0.05:
            continue
        total += 1
        good += (rel / np.linalg.norm(rel)) @ row[7:10] > 0.866
    return f"{good}/{total}"


def run_variant(name, options, episode, gt_state):
    n = episode.num_frames
    if options is None:
        return np.tile([0, 0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 0, 0], (n, 1)), {}
    options = dict(options)
    oracle = options.pop("oracle", None)
    config, frames = episode.adapt((320, 240))
    if options.get("impl") == "c":  # the compiled C solution, driven exactly like the Python one
        from csolution import CSolution, LIBRARY
        library = LIBRARY.replace("libvio_host", f"libvio_{options['lib']}") if "lib" in options else LIBRARY
        solver = CSolution(config, library)
        estimates = np.empty((n, 13))
        for index, (t, frame, imu) in enumerate(episode.steps(frames)):
            estimates[index] = solver.step(float(t), frame, imu)
        w = solver.windows()
        stats = dict(windows=len(w), used=int(w[:, 10].sum()) if len(w) else 0)
        if len(w) and gt_state is not None:
            stats["direction_ok"] = window_direction_quality(w, episode, gt_state)
        return estimates, stats
    S.Solution.OPTIONS = options
    solver = S.Solution(config)
    if not options.get("vision", True):
        frames = [None] * n  # no image decoding for IMU-only variants
    R_ic = solver.R_ic
    T = poses_to_matrices(gt_state[:, :7])
    if oracle and "gravity" in oracle:
        # body attitude in the simulator's world (z up) at the first frame -> specific force at rest in IMU-0 axes
        from viobench.tools.geometry import interpolate_poses
        q = interpolate_poses(episode.ground_truth[:, 0], episode.ground_truth[:, 1:8], episode.frame_times[:1])[0, 3:7]
        R_sim_b0 = poses_to_matrices(np.r_[[0, 0, 0], q][None])[0, :3, :3]
        solver.oracle_gravity = R_sim_b0.T @ np.array([0, 0, 9.81])
        oracle = oracle.replace("+gravity", "").replace("gravity", "") or None
    estimates = np.empty((n, 13))
    for index, (t, frame, imu) in enumerate(episode.steps(frames)):
        if oracle and index > 0:
            R_c0_ck = T[index - 1, :3, :3]
            solver.oracle_R_wb = R_ic @ R_c0_ck @ R_ic.T
            # true velocity of the IMU in world (= IMU frame at frame 0) axes; the camera lever arm is ignored
            v_world = R_ic @ T[index, :3, :3] @ gt_state[index, 7:10]
            if oracle.startswith("kf_direction"):  # true direction/stop-go into the filter
                if oracle != "kf_direction+rotation":
                    solver.oracle_R_wb = None  # attitude stays estimated
                solver.oracle_dir_v = v_world
            elif oracle in ("moving", "direction_only"):  # one true ingredient, everything else estimated
                solver.oracle_R_wb = None
                speed = float(np.linalg.norm(v_world))
                if oracle == "moving":
                    solver.oracle_moving = speed > 0.05
                elif speed > 0.05:
                    solver.oracle_direction = v_world / speed
            elif oracle == "speed":  # true speed only; rotation and direction stay estimated
                solver.oracle_R_wb = None
                solver.oracle_speed = float(np.linalg.norm(gt_state[index, 7:10]))
            elif oracle == "rotation+speed":
                solver.oracle_speed = float(np.linalg.norm(gt_state[index, 7:10]))
            elif oracle != "rotation":
                solver.oracle_v = v_world
                solver.oracle_mode = oracle.removeprefix("rotation+")
        estimates[index] = solver.step(float(t), frame, imu)
    return estimates, solver.stats


def cropped(episode, seconds):
    """The same flight starting `seconds` later: the solution's first frame is then mid-flight (unknown velocity)."""
    if seconds <= 0:
        return episode
    from dataclasses import replace
    from viobench.tools.datasets.episode import FrameSequence

    k = int(np.searchsorted(episode.frame_times, episode.frame_times[0] + seconds))
    source = episode.frames
    frames = FrameSequence(lambda i: source[i + k], len(source) - k, source.frame_shape) \
        if isinstance(source, FrameSequence) else source[k:]
    return replace(episode, name=f"{episode.name}+{seconds:g}s", frame_times=episode.frame_times[k:], frames=frames)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sources", nargs="+", help="episode .zip files or directories of them")
    parser.add_argument("--variants", nargs="+", default=list(VARIANTS))
    parser.add_argument("--crops", nargs="+", type=float, default=[0.0],
                        help="also start each flight this many seconds in (mid-flight starts), e.g. --crops 0 7")
    parser.add_argument("--quiet", action="store_true", help="only the mean table")
    parser.add_argument("--try", dest="tries", action="append", default=[], metavar="NAME:key=value,key=value",
                        help="extra variant, e.g. --try nobias:vision=1,bias_gain=0")
    args = parser.parse_args()
    for spec in args.tries:
        name, _, settings = spec.partition(":")
        options = {}
        for item in filter(None, settings.split(",")):
            key, _, value = item.partition("=")
            if key in ("impl", "lib"):
                options[key] = value
            elif key in ("vision", "use_direction"):
                options[key] = bool(int(value))
            else:
                try:
                    options[key] = float(value)
                except ValueError:
                    options[key] = value
        VARIANTS[name] = options
        args.variants.append(name)
    table = {name: [] for name in args.variants}
    rotation = {name: [] for name in args.variants}
    names = []
    all_episodes = [cropped(e, c) for e in episodes(args.sources) for c in args.crops]
    for episode in all_episodes:
        gt = episode.ground_truth_state()
        names.append(episode.name)
        line = [f"{episode.name[:34]:34s} {episode.duration:5.0f}s"]
        for name in args.variants:
            started = time.time()
            est, stats = run_variant(name, VARIANTS[name], episode, gt)
            m = evaluate_trajectory(gt, est, episode.frame_times)
            table[name].append(m.ate_rmse)
            rotation[name].append(np.degrees(m.rotation_rmse))
            extra = ""
            if "direction_ok" in stats:
                extra = f" [{stats['used']}/{stats['windows']} win, dir ok {stats['direction_ok']}]"
            elif stats.get("windows"):
                extra = f" [{stats['used']}/{stats['windows']} win"
                reasons = {k: stats[k] for k in ("few_points", "short", "big_rotation", "no_corners") if stats.get(k)}
                extra += (" " + ",".join(f"{k}={v}" for k, v in reasons.items()) if reasons else "") + "]"
            line.append(f"{name}={m.ate_rmse:6.2f}m/{np.degrees(m.rotation_rmse):4.0f}deg{extra}")
        if not args.quiet:
            print("  ".join(line), flush=True)
    print("\nMEAN over", len(names), "episodes (unaligned ATE, the graded number; rotation RMSE)")
    for name in args.variants:
        print(f"  {name:18s} ATE {np.mean(table[name]):6.2f} m   rotation error {np.mean(rotation[name]):5.1f} deg")


if __name__ == "__main__":
    main()
