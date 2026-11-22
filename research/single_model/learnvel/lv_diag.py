"""lv_diag.py PRED.npz RUNDIR POOLDIR OUT.json : per-anchor comparison of the net's velocity error vs the filter's (twist) error, with TC_LOG signals.
Analysis only (truth used for scoring)."""
import sys, glob, json, os, re
import numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.datasets.storage import read_episode
RX = re.compile(r'D f=(\d+) t=([\d.]+) live=(\d+) used=(\d+) u20=(\d+) att=(\d+) gate=(\d+) tri=(\d+) nis=([\d.]+) sp=([\d.]+) psp=([-\d.]+) nanch=(\d+) fire=(\d+) Pv=([\d.]+)')
P = np.load(sys.argv[1]); run, pool, out = sys.argv[2], sys.argv[3], sys.argv[4]
rows = []
for i, ep in enumerate(P['names']):
    m = P['fid'] == i
    d = glob.glob(f'{run}/*/{ep}/report/logs/*/twist.txt')
    if not d: continue
    tw = np.loadtxt(d[0]); se = d[0].replace('twist.txt', 'stderr.txt')
    e = read_episode(f'{pool}/{ep}.zip', frames='none'); S = np.asarray(e.ground_truth_state()); n = len(S)
    Rbc = np.asarray(e.T_body_camera)[:3, :3]
    ferr = np.linalg.norm(tw[:n, 1:4] - S[:len(tw), 7:10], axis=1) if len(tw) == n else None
    L = np.full((n, 4), np.nan)
    for line in open(se):
        g = RX.match(line)
        if g:
            f = int(g.group(1))
            if 0 <= f < n: L[f] = [int(g.group(3)), int(g.group(4)), float(g.group(14)), int(g.group(13))]
    for a, mu, y, lv, tex in zip(P['anchor'][m], P['mu'][m], P['y'][m], P['lv'][m], P['tex'][m]):
        fK = 5 * (a + 1)
        if fK >= n: continue
        vt = S[fK, 7:10]; vnet = Rbc.T @ mu   # body -> camera axes (lever arm ignored)
        u20 = np.nansum(L[max(0, fK - 20):fK + 1, 1])
        rows.append(dict(ep=ep, f=int(fK), spd=float(np.linalg.norm(y)), nerr=float(np.linalg.norm(mu - y)), nerr_cam=float(np.linalg.norm(vnet - vt)),
                         ferr=float(ferr[fK]) if ferr is not None else None, sig=float(np.sqrt(np.exp(lv).sum())), z=((mu - y) / np.exp(0.5 * lv)).tolist(),
                         live=float(L[fK, 0]), u20=float(u20), pv=float(L[fK, 2]), tex=float(tex), mu=mu.tolist(), y=y.tolist()))
json.dump(rows, open(out, 'w'))
print(len(rows))
