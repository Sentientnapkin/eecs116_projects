"""tsd.py RUNDIR POOL EP T0 T1 [step]: frame-level D/G lines with truth velocity (analysis only)"""
import sys, glob, re, numpy as np
from viobench.tools.datasets.storage import read_episode
RUN, POOL, ep, T0, T1 = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5]); st = int(sys.argv[6]) if len(sys.argv) > 6 else 5
d = f'{RUN}/{ep}'; se = glob.glob(f'{d}/report/logs/*/stderr.txt')[0]
e = read_episode(f'{POOL}/{ep}.zip', frames='none'); t = np.asarray(e.frame_times); S = np.asarray(e.ground_truth_state())
vt = np.gradient(S[:, :3], t, axis=0)
G = {}
for line in open(se):
    if line.startswith('G '): G[int(line.split()[1][2:])] = line.strip()
for line in open(se):
    if not line.startswith('D '): continue
    f = int(line.split()[1][2:]); tt = t[f - 1] - t[0] if f - 1 < len(t) else -1
    if T0 <= tt <= T1 and f % st == 0:
        m = re.search(r'v=([-\d.]+),([-\d.]+),([-\d.]+)', line); v = np.array([float(x) for x in m.groups()])
        g = G.get(f, ''); gl = re.search(r'live=\d+ lo=\d+', g); bl = re.search(r'black=[\d.]+', g)
        print('%5.2f vtrue %5.2f %5.2f %5.2f verr %5.2f %5.2f %5.2f | %s | %s %s' % (tt, *vt[f - 1], *(v - vt[f - 1]), ' '.join(x for x in line.split()[3:15] if not x.startswith(('t=', 'used', 'u20', 'v=', 'p='))), gl.group(0) if gl else '', bl.group(0) if bl else ''))
