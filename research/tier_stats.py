"""Per-tier motion statistics and zero-output unaligned ATE (the frontier's ~5 m reference)."""
import sys
import numpy as np
from common import load, ate
fl = load(sys.argv[1])
by = {}
for f in fl:
    sp = np.linalg.norm(f.v, axis=1); tilt = np.degrees(np.arccos(np.clip(f.R[:, 2, 2], -1, 1)))
    yawr = np.abs(f.w[:, 2])
    by.setdefault(f.tier, []).append((sp.mean(), np.percentile(sp, 99), np.percentile(tilt, 99), np.percentile(yawr, 99),
                                     ate(np.zeros_like(f.cam_gt), f.cam_gt), f.cam_gt[-1].__abs__().max()))
for t, r in by.items():
    r = np.array(r)
    print(f"{t:16s} n={len(r)} speed mean {r[:,0].mean():.2f} p99 {r[:,1].mean():.2f} m/s | tilt p99 {r[:,2].mean():.1f} deg | yaw-rate p99 {r[:,3].mean():.2f} | zero-output ATE {r[:,4].mean():.2f} m (range {r[:,4].min():.2f}-{r[:,4].max():.2f})")
