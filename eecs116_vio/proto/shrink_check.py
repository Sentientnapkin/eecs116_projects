"""Does pulling the output toward the start help the (unaligned) ATE?

Runs the C solution once per episode, then scores post-processed positions:
  constant:   p_out = a * p
  growing:    p_out = p / (1 + (k * d)^2), d = path length estimated so far (causal), i.e. the estimate is trusted less
              the farther the drone has flown, the way a Bayesian estimate with a "stays near the start" prior behaves.
"""
import sys

import numpy as np

from csolution import CSolution
from viobench.tools.datasets.sources import episodes
from viobench.tools.runner.metrics import evaluate_trajectory

A = [0.6, 0.7, 0.8, 0.9, 1.0]
K = [0.0, 0.01, 0.02, 0.03, 0.05, 0.08]
table_a, table_k, zeros = {a: [] for a in A}, {k: [] for k in K}, []
for episode in episodes(sys.argv[1:]):
    gt = episode.ground_truth_state()
    config, frames = episode.adapt((320, 240))
    solver = CSolution(config)
    est = np.array([solver.step(float(t), f, imu) for t, f, imu in episode.steps(frames)])
    path = np.r_[0, np.cumsum(np.linalg.norm(np.diff(est[:, :3], axis=0), axis=1))]
    ate = lambda positions: evaluate_trajectory(gt, np.c_[positions, est[:, 3:]], episode.frame_times).ate_rmse
    zeros.append(ate(np.zeros((len(est), 3))))
    for a in A:
        table_a[a].append(ate(est[:, :3] * a))
    for k in K:
        table_k[k].append(ate(est[:, :3] / (1 + (k * path) ** 2)[:, None]))
    print(f"{episode.name[:30]:30s} zeros {zeros[-1]:.2f}  as is {table_a[1.0][-1]:.2f}  "
          f"best constant {min(table_a, key=lambda a: table_a[a][-1])}  best growing {min(table_k, key=lambda k: table_k[k][-1])}", flush=True)
print(f"\nMEAN over {len(zeros)}: zeros {np.mean(zeros):.2f} m")
print("  constant a: " + "  ".join(f"{a}: {np.mean(v):.2f}" for a, v in table_a.items()))
print("  growing  k: " + "  ".join(f"{k}: {np.mean(v):.2f}" for k, v in table_k.items()))
