"""Distance covered vs ground gained, over 2 s stretches grouped by the true average speed of the stretch.
  path    estimated path length / true path length            (is the speed right?)
  net     estimated straight-line progress / true progress    (does it get as far?)
    python progress_bins.py libvio_sc20
"""
import glob, os, sys
import numpy as np
lib = sys.argv[1]
bins = [0.1, 0.4, 0.7, 1.0, 1.4, 5.0]
rows = {b: [] for b in range(len(bins) - 1)}
for f in glob.glob(os.path.expanduser(f"~/ws_proto/cache/{lib}/*.npz")):
    d = np.load(f)
    p, q = d["est"][:, :3], d["gt"][:, :3]
    step_p = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    step_q = np.r_[0, np.cumsum(np.linalg.norm(np.diff(q, axis=0), axis=1))]
    n = 40  # 2 s
    for i in range(0, len(p) - n, 10):
        true_path = step_q[i + n] - step_q[i]
        true_net = np.linalg.norm(q[i + n] - q[i])
        v = true_path / 2.0
        if true_net < 0.3:
            continue
        b = np.searchsorted(bins, v) - 1
        if 0 <= b < len(bins) - 1:
            rows[b].append(((step_p[i + n] - step_p[i]) / true_path, np.linalg.norm(p[i + n] - p[i]) / true_net))
print(f"{lib}: over 2 s stretches (median ratios, estimate / truth)")
print(f"{'true speed m/s':16s} {'stretches':>9s} {'path':>6s} {'net':>6s}")
for b, r in rows.items():
    if r:
        r = np.array(r)
        print(f"{bins[b]:4.1f} - {bins[b + 1]:3.1f}       {len(r):9d} {np.median(r[:, 0]):6.2f} {np.median(r[:, 1]):6.2f}")
