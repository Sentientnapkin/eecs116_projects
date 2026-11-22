"""Does the estimate undershoot more when the drone is faster? From diag.py caches.

For frames grouped by true speed: median of (estimated speed / true speed) for
  output   the speed of the position we output (0.5 s finite difference)
  camera   the camera's own speed measurement (debug_flow_speed, after the accelerometer scale if enabled)
  blend    what the speed blend makes of a PERFECT camera measurement: FIXED_SPEED^(1-w) * true^w
    python speed_bins.py libvio_sc20 [w=0.6]
"""
import glob
import os
import sys

import numpy as np

lib = sys.argv[1]
w = float(next((a[2:] for a in sys.argv[2:] if a.startswith("w=")), 0.6))
bins = [0.1, 0.4, 0.7, 1.0, 1.4, 2.0, 5.0]
out = {b: [] for b in range(len(bins) - 1)}
cam = {b: [] for b in range(len(bins) - 1)}
for f in glob.glob(os.path.expanduser(f"~/ws_proto/cache/{lib}/*.npz")):
    d = np.load(f)
    est, gt, t, flow = d["est"][:, :3], d["gt"], d["t"], d["flow"]
    true_speed = np.linalg.norm(gt[:, 7:10], axis=1)
    k = 5  # +-5 frames = 0.5 s
    v_out = np.full(len(t), np.nan)
    v_out[k:-k] = np.linalg.norm(est[2 * k:] - est[:-2 * k], axis=1) / (t[2 * k:] - t[:-2 * k])
    for b in range(len(bins) - 1):
        sel = (true_speed >= bins[b]) & (true_speed < bins[b + 1]) & np.isfinite(v_out)
        out[b] += list(v_out[sel] / true_speed[sel])
        cam[b] += list(flow[sel] / true_speed[sel])
print(f"{lib}: estimated / true speed (median), by true speed")
print(f"{'true speed m/s':16s} {'frames':>7s} {'output':>7s} {'camera':>7s} {'blend of a perfect camera':>26s}")
for b in range(len(bins) - 1):
    if not out[b]:
        continue
    mid = np.sqrt(bins[b] * bins[b + 1])
    print(f"{bins[b]:4.1f} - {bins[b + 1]:3.1f}       {len(out[b]):7d} {np.median(out[b]):7.2f} {np.median(cam[b]):7.2f} "
          f"{0.35 ** (1 - w) * mid ** w / mid:26.2f}")
