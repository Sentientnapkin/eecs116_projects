"""Rest-start flights only (like the server): mean, median, p90, and per-flight changes vs a base.  python rest_cmp.py BASE V..."""
import os, sys
import numpy as np
sys.path.insert(0, "/mnt/c/Users/alexa/Projects/eecs116_vio/proto/night/hf")
from hf_sum import man, load
names = sys.argv[1:]
base = load(names[0])
fl = sorted(f for f in base if man[f]["start_offset_s"] == 0)
print(f"{len(fl)} rest-start flights")
print(f"{'variant':12s} {'mean':>6s} {'median':>6s} {'p90':>6s} {'max':>6s}  {'better>0.2':>10s} {'worse>0.2':>9s}")
for n in names:
    r = load(n)
    a = np.array([r[f][0] for f in fl]); b = np.array([base[f][0] for f in fl])
    print(f"{n:12s} {a.mean():6.3f} {np.median(a):6.3f} {np.percentile(a, 90):6.3f} {a.max():6.2f}  {np.sum(a < b - 0.2):10d} {np.sum(a > b + 0.2):9d}")
