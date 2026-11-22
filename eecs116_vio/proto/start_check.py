"""Window-by-window speed in the first seconds of a flight (from a diag.py cache):
true mean speed, the camera's smoothed speed (after scale), the accelerometer scale, and the speed of our output."""
import glob, os, sys
import numpy as np
lib, flight, until = sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 12
d = np.load(glob.glob(os.path.expanduser(f"~/ws_proto/cache/{lib}/{flight}_*.npz"))[0])
t = d["t"] - d["t"][0]
gt, est, flow, scale, w = d["gt"], d["est"][:, :3], d["flow"], d["scale"], d["windows"]
true_speed = np.linalg.norm(gt[:, 7:10], axis=1)
print(f"{lib}: {flight}")
print(" window (s)    true m/s  camera m/s  scale  output m/s  moving used  points  parallax")
for row in w:
    t0, t1 = row[0] - d["t"][0], row[1] - d["t"][0]
    if t0 > until:
        break
    sel = (t >= t0) & (t <= t1)
    i0, i1 = np.searchsorted(t, t0), np.searchsorted(t, t1)
    out = np.linalg.norm(est[i1] - est[i0]) / max(t1 - t0, 1e-3)
    print(f" {t0:5.1f}-{t1:5.1f}   {true_speed[sel].mean():6.2f}   {flow[i1]:8.2f}   {scale[i1]:5.2f}   {out:7.2f}      {int(row[11])}     {int(row[10])}   {int(row[2]):5d}   {row[3]:.3f}")
