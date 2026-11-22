"""Is a candidate better on (nearly) every flight, or only on average?  python hf_robust.py BASE CAND [CAND ...]

Per candidate vs BASE, on all 171 HF flights:
  better / worse   flights that improve / get worse by more than 0.1 m
  biggest loss     the single flight that gets most worse (m)
  p90 / max        90th percentile and worst ATE (the tail)
  >nothing         flights worse than "never moved"
and the mean for each subgroup (scene catalog x start type, tune / check scenes).
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hf_sum import man, load, is_tune  # noqa: E402

names = sys.argv[1:]
base = load(names[0])
fl = sorted(base)
groups = {
    "procthor/rest": lambda f: man[f]["catalog"] == "procthor" and man[f]["start_offset_s"] == 0,
    "procthor/mid": lambda f: man[f]["catalog"] == "procthor" and man[f]["start_offset_s"] > 0,
    "hssd/rest": lambda f: man[f]["catalog"] != "procthor" and man[f]["start_offset_s"] == 0,
    "hssd/mid": lambda f: man[f]["catalog"] != "procthor" and man[f]["start_offset_s"] > 0,
    "tune": is_tune,
    "check": lambda f: not is_tune(f),
}
print(f"{'variant':16s} {'mean':>5s} {'better':>6s} {'worse':>5s} {'biggest loss':>12s} {'p90':>5s} {'max':>5s} {'>nothing':>8s} | "
      + " ".join(f"{g:>13s}" for g in groups))
for n in names:
    r = load(n)
    if r is None:
        print(f"{n:16s} (not finished)")
        continue
    a = np.array([r[f][0] for f in fl])
    b = np.array([base[f][0] for f in fl])
    d = a - b
    loss_f = fl[int(np.argmax(d))]
    print(f"{n:16s} {a.mean():5.2f} {np.sum(d < -0.1):6d} {np.sum(d > 0.1):5d} {d.max():+12.2f} {np.percentile(a, 90):5.2f} "
          f"{a.max():5.2f} {sum(r[f][0] > r[f][1] for f in fl):8d} | "
          + " ".join(f"{np.mean([r[f][0] for f in fl if g(f)]):13.2f}" for g in groups.values()))
    if n != names[0]:
        print(f"{'':16s} biggest loss on {loss_f} ({b[fl.index(loss_f)]:.2f} -> {a[fl.index(loss_f)]:.2f}, "
              f"nothing {r[loss_f][1]:.2f})")
