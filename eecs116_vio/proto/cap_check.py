"""Would a "the drone stays inside the house" safety net help? Post-hoc, on cached runs (~/ws_proto/cache/<lib>/*.npz).

Replays each run's frame-to-frame displacements through a causal filter (what the C code would do to its own
position each frame) and scores the result:
  cap R      soft radius: beyond R metres from the start, the excess is pulled back by a factor `pull` per second
  leak tau   position decays toward the start with time constant tau seconds
    python cap_check.py [lib] [group: night|old|all]
"""
import glob
import os
import sys

import numpy as np

lib = sys.argv[1] if len(sys.argv) > 1 else "libvio_host"
files = sorted(glob.glob(os.path.expanduser(f"~/ws_proto/cache/{lib}/*.npz")))


def ate(q, p):
    return float(np.sqrt(np.mean(np.sum((p - q) ** 2, axis=1))))


def replay(est, t, radius=np.inf, rate=0.0, tau=np.inf):
    d = np.diff(est, axis=0)
    dt = np.diff(t)
    p = np.zeros(3)
    out = [p.copy()]
    for k in range(len(d)):
        p = p + d[k]
        if np.isfinite(tau):
            p *= np.exp(-dt[k] / tau)
        r = np.linalg.norm(p)
        if r > radius:
            p *= (radius + (r - radius) * np.exp(-rate * dt[k])) / r
        out.append(p.copy())
    return np.array(out)


configs = [("as is", {})]
for R in (3, 4, 5, 6, 8, 10):
    for rate in (0.5, 2.0, 1e9):
        configs.append((f"cap {R} pull {rate:g}/s", dict(radius=R, rate=rate)))
for tau in (20, 40, 80):
    configs.append((f"leak {tau}s", dict(tau=tau)))
table = {name: [] for name, _ in configs}
zeros = []
for f in files:
    d = np.load(f)
    est, gt, t = d["est"][:, :3], d["gt"][:, :3], d["t"]
    zeros.append(ate(gt, 0 * gt))
    for name, kw in configs:
        table[name].append(ate(gt, replay(est, t, **kw)))
z = np.array(zeros)
print(f"{len(files)} runs; zeros mean {z.mean():.2f}")
base = np.array(table["as is"])
for name, v in table.items():
    v = np.array(v)
    print(f"  {name:22s} mean {v.mean():.3f}  worst {v.max():5.2f}  flights better/worse than as-is by >0.1 m: "
          f"{np.sum(v < base - 0.1):2d}/{np.sum(v > base + 0.1):2d}   on flights far from start (zeros>2.5): {v[z > 2.5].mean():.3f}")
