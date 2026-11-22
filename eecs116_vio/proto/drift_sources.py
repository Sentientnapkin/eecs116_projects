"""Where does the position drift come from? Uses the cached runs of diag.py (~/ws_proto/cache/<lib>/*.npz).

Every frame-to-frame displacement error (estimate minus truth, in the first camera's axes) is assigned to the kind of
vision window that covers that frame:
  good     window used, drone judged moving
  still    window used, drone judged not moving (velocity held at zero)
  failed   window not used (too few points or bad geometry): the velocity coasts on the last measurement
  gap      not covered by any window
For each kind: share of frames, and the size of the summed error vector (the drift it leaves behind).
Also: drift split into "speed" (along the true motion) and "direction" (across it).
    python drift_sources.py [lib name] [name filter...]
"""
import glob
import os
import sys

import numpy as np

lib = sys.argv[1] if len(sys.argv) > 1 else "libvio_host"
filters = sys.argv[2:]
files = sorted(glob.glob(os.path.expanduser(f"~/ws_proto/cache/{lib}/*.npz")))
total = {}
for f in files:
    name = os.path.basename(f)
    if filters and not any(x in name for x in filters):
        continue
    d = np.load(f)
    est, gt, t, w = d["est"][:, :3], d["gt"][:, :3], d["t"], d["windows"]
    de, dg = np.diff(est, axis=0), np.diff(gt, axis=0)
    err = de - dg
    kind = np.full(len(err), "gap", dtype=object)
    for t0, t1, *_, used, moving in w:
        sel = (t[1:] > t0) & (t[1:] <= t1)
        kind[sel] = ("good" if moving else "still") if used else "failed"
    # along / across the true motion
    unit = dg / np.maximum(np.linalg.norm(dg, axis=1, keepdims=True), 1e-9)
    along = np.sum(err * unit, axis=1)[:, None] * unit
    across = err - along
    line = f"{name[:28]:28s} final drift {np.linalg.norm(err.sum(0)):5.2f} m  (along {np.linalg.norm(along.sum(0)):4.2f}, across {np.linalg.norm(across.sum(0)):4.2f}) |"
    for k in ("good", "still", "failed", "gap"):
        sel = kind == k
        line += f" {k} {sel.mean():4.0%} {np.linalg.norm(err[sel].sum(0)):4.2f}m |"
        total.setdefault(k, []).append((sel.mean(), np.linalg.norm(err[sel].sum(0))))
    print(line)
print("\nAVERAGE share of frames / drift left by that kind of window")
for k, v in total.items():
    v = np.array(v)
    print(f"  {k:7s} {v[:, 0].mean():4.0%}  {v[:, 1].mean():.2f} m")
