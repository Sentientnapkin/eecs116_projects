"""K=2 same-family pairs (mean fusion = 2-point geometric median), with lag D for the secondary. python pairs.py POOL"""
import sys, os, json, glob
from multiprocessing import Pool
import numpy as np
import cons
from cons import load, RUNS, POOLS, episodes
PAIRS = [('lv_glNP', 'lv_glNP_r1'), ('lv_glNP', 'lv_glNP_r2'), ('lv_glNP_r1', 'lv_glNP_r2'), ('lj_ajc', 'lj_ajc_r1'), ('lj_ajc', 'lj_ajc_r2'), ('lj_ajc_r1', 'lj_ajc_r2')]
def one(z):
    name = os.path.basename(z)[:-4]; L = {r: load(r, name) for r in RUNS}
    if any(v is None for v in L.values()): return None
    gt = next(episodes([z])).ground_truth_state()[:, :3]; n = min(len(gt), *(len(v[1]) for v in L.values())); gt = gt[:n]
    ate = lambda p: float(np.sqrt(((p - gt) ** 2).sum(1).mean())); o = {}
    for a, b in PAIRS:
        A, B = L[a][1][:n], L[b][1][:n]
        for D in [0, 5]:
            i = np.maximum(np.arange(n) - D, 0); Bl = B[i] + A - A[i]
            o['%s+%s_D%d' % (a, b, D)] = ate(0.5 * (A + Bl))
        o['%s+%s_avg' % (a, b)] = 0.5 * (ate(A) + ate(B))
    return name, o
if __name__ == '__main__':
    pool = sys.argv[1]; zs = sorted(glob.glob(POOLS[pool] + '/*.zip'))
    with Pool(48) as p: res = dict(r for r in p.map(one, zs) if r)
    json.dump(res, open('pairs_%s.json' % pool, 'w')); names = sorted(res)
    for a, b in PAIRS:
        k = '%s+%s' % (a, b); av = np.mean([res[n][k + '_avg'] for n in names])
        print(pool, k, 'avg %.4f D0 %+.1f%% D5 %+.1f%%' % (av, 100 * (np.mean([res[n][k + '_D0'] for n in names]) / av - 1), 100 * (np.mean([res[n][k + '_D5'] for n in names]) / av - 1)))
