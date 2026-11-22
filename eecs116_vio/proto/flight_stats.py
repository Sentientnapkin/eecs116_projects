"""Speed / turn statistics of episodes (ground truth), to see what kind of flights a folder holds."""
import sys
import numpy as np
from viobench.tools.datasets.sources import episodes

for e in episodes(sys.argv[1:]):
    s = e.ground_truth_state()
    speed = np.linalg.norm(s[:, 7:10], axis=1)
    yaw_rate = np.abs(s[:, 10:13]).max(axis=1)
    dist = np.linalg.norm(s[:, :3], axis=1)
    print(f"{e.name[:30]:30s} {e.duration:4.0f}s  speed p50 {np.median(speed):.2f} p90 {np.percentile(speed, 90):.2f} max {speed.max():.2f} m/s"
          f" | turn rate p90 {np.percentile(yaw_rate, 90):.2f} rad/s | still {np.mean(speed < 0.05) * 100:3.0f}% | path {np.sum(speed) / 20:5.1f} m, max from start {dist.max():.1f} m")
