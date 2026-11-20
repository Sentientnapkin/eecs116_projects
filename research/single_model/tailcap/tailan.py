"""For flights of a run with ATE>thr: estimated vs truth extent/speed (open-loop clamps would bind?).  python tailan.py NAME_rK [thr]"""
import sys, glob, json, os
import numpy as np
sys.path.insert(0, '.'); sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from research.guard_fusion import traj as T
HERE = 'research/single_model/tailcap'
POOLS = {'fresh': '/data/backups/rganapa/Sebastian/tmp/fresh_pool', 'sel': HERE + '/pool_sel144'}
nm = sys.argv[1]; thr = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
tab = json.load(open(f'{HERE}/tables/{nm.rsplit("_r",1)[0]}_r{nm.rsplit("_r",1)[1]}.json'))
def stats(p, t):
    dt = float(np.median(np.diff(t))); n3 = int(round(3 / dt))
    d = np.linalg.norm(p, axis=1); r3 = np.linalg.norm(p[n3:] - p[:-n3], axis=1) / (n3 * dt)
    return d.max(), np.abs(p[:, 2]).max(), r3.max(), float(np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1)))
rows = []
for r in tab:
    if r['ate'] is None or (r['ate'] <= thr): continue
    ep, st = r['episode'], r['set']
    t, s, meta = T.load_truth(POOLS[st], ep)
    est = glob.glob(f'research/results/single_model/tc_{nm}/eval_{st}/*/{ep}/report/logs/*/estimate.tum')
    tum = np.loadtxt(est[0]); idx = np.searchsorted(t, tum[:, 0]).clip(0, len(t) - 1)
    pe = tum[:, 1:4]; pt = s[idx, :3]
    # estimates are in start-camera frame like truth; z not vertical -> use distance and 3-s rate only
    de, _, re_, le = stats(pe - pe[0], tum[:, 0]); dt_, _, rt, lt = stats(pt - pt[0], tum[:, 0])
    err = np.linalg.norm(pe - pt, axis=1); tt = tum[:, 0] - tum[0, 0]
    print(f'{st:5s} {ep:34s} ate {r["ate"]:6.2f} err@2s {err[tt>2][0]:5.2f} @5s {err[tt>5][0]:5.2f} | est maxd {de:5.1f} truth {dt_:5.1f} | est max3s-rate {re_:4.2f} truth {rt:4.2f} | path est {le:5.1f} truth {lt:5.1f} ratio {le/lt:4.2f}')
