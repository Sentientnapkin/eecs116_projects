"""Stats of rendered flights, one tab-separated line per flight:
STAT  name  duration_s  avg_speed_m_per_s  rms_distance_from_start_m  max_distance_from_start_m  p90_speed
    python flight_stats.py DIR...
"""
import sys

import numpy as np
from viobench.tools.datasets.sources import episodes

for e in episodes(sys.argv[1:]):
    s = e.ground_truth_state()
    p = s[:, :3]
    speed = np.linalg.norm(s[:, 7:10], axis=1)
    path = float(np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1)))
    r = np.linalg.norm(p, axis=1)
    print(f"STAT\t{e.name}\t{e.duration:.1f}\t{path / e.duration:.3f}\t{np.sqrt(np.mean(r ** 2)):.2f}\t{r.max():.2f}"
          f"\t{np.percentile(speed, 90):.2f}", flush=True)
