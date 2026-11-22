"""How good is each speed guess? Compares, frame by frame while the drone truly moves, the true speed with
  fixed: 0.35 m/s,  camera: the C solution's flow speed,  blend: sqrt(0.35 x camera).
Errors are ratios (estimate / truth): 1.0 is perfect, and "within 30%" counts frames with 0.77 < ratio < 1.3."""
import sys

import numpy as np

from csolution import CSolution
from viobench.tools.datasets.sources import episodes

rows = []
for episode in episodes(sys.argv[1:]):
    gt = episode.ground_truth_state()
    true_speed = np.linalg.norm(gt[:, 7:10], axis=1)
    config, frames = episode.adapt((320, 240))
    solver = CSolution(config)
    camera = np.empty(episode.num_frames)
    for i, (t, frame, imu) in enumerate(episode.steps(frames)):
        solver.step(float(t), frame, imu)
        camera[i] = solver.lib.debug_flow_speed()
    moving = true_speed > 0.1
    guesses = {"fixed": np.full(moving.sum(), 0.35), "camera": camera[moving], "blend": np.sqrt(0.35 * camera[moving])}
    s = true_speed[moving]
    line = f"{episode.name[:28]:28s} true speed median {np.median(s):.2f} m/s |"
    for name, g in guesses.items():
        ratio = g / s
        line += f" {name}: median ratio {np.median(ratio):.2f}, within 30% {np.mean((ratio > 0.77) & (ratio < 1.3)):.0%} |"
        rows.append((name, np.log(ratio)))
    print(line, flush=True)
print("\nALL FLIGHTS (typical size of the speed error, as a factor; 1.00 would be perfect)")
for name in ("fixed", "camera", "blend"):
    logs = np.concatenate([r for n, r in rows if n == name])
    print(f"  {name:7s} typical error factor {np.exp(np.sqrt(np.mean(logs ** 2))):.2f}   bias (median ratio) {np.exp(np.median(logs)):.2f}"
          f"   within 30% of the truth: {np.mean(np.abs(logs) < np.log(1.3)):.0%}")
