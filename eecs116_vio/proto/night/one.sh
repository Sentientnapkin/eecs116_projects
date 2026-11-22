#!/bin/bash
# one.sh NAME FLIGHT.zip [-DFLAG=VAL ...]: quick single-flight try. Prints the diag line and the speed match by speed band.
NAME=$1; FLIGHT=$2; shift 2
source ~/.venv/bin/activate
gcc -O2 -shared -fPIC -I ~/ws_c/runtime/native "$@" -o ~/ws_c/libvio_$NAME.so /mnt/c/Users/alexa/Projects/eecs116_vio/csol/solution/solution.c -lm || exit 1
cd /mnt/c/Users/alexa/Projects/eecs116_vio/proto
python diag.py $FLIGHT lib=$HOME/ws_c/libvio_$NAME.so 2>&1 | grep -v '^conta:' | head -1
python - $NAME $FLIGHT <<'PY'
import glob, os, sys
import numpy as np
name, flight = sys.argv[1], os.path.basename(sys.argv[2])[:-4]
d = np.load(glob.glob(os.path.expanduser(f"~/ws_proto/cache/libvio_{name}/{flight}_*.npz"))[0])
p, q = d["est"][:, :3], d["gt"][:, :3]
sp = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
sq = np.r_[0, np.cumsum(np.linalg.norm(np.diff(q, axis=0), axis=1))]
bins, rows = [0.1, 0.5, 1.0, 5.0], {}
for i in range(0, len(p) - 40, 10):
    v = (sq[i + 40] - sq[i]) / 2
    b = np.searchsorted(bins, v) - 1
    if 0 <= b < 3 and np.linalg.norm(q[i + 40] - q[i]) > 0.3:
        rows.setdefault(b, []).append((sp[i + 40] - sp[i]) / (sq[i + 40] - sq[i]))
print("   distance covered / true, by true speed: " + "  ".join(f"{bins[b]}-{bins[b + 1]} m/s: {np.median(r):.2f}" for b, r in sorted(rows.items())))
PY
