"""Effect of time-sliced (lagged) secondary back ends on causal fusion. Primary member 0 is current; secondary members are
available only D frames late and are propagated to t with the primary's increment: s_k(t) ~ s_k(t-D) + p0(t) - p0(t-D).
python lag.py POOL -> lag_POOL.json"""
import sys, os, json
from multiprocessing import Pool
import numpy as np
import cons
from cons import load, gmed, RUNS, SETS, POOLS, episodes
import glob

USE = ['V1M1', 'V2M1', 'J2M1', 'V1J1M1', 'V3', 'V3M3']


def one(z):
    name = os.path.basename(z)[:-4]
    L = {r: load(r, name) for r in RUNS}
    if any(v is None for v in L.values()): return None
    gt = next(episodes([z])).ground_truth_state()[:, :3]
    n = min(len(gt), *(len(v[1]) for v in L.values())); gt = gt[:n]
    ate = lambda p: float(np.sqrt(((p - gt) ** 2).sum(1).mean()))
    out = {}
    for sn in USE:
        S = np.stack([L[r][1][:n] for r in SETS[sn]])
        for D in [0, 2, 5, 10, 20]:
            idx = np.maximum(np.arange(n) - D, 0)
            T = S.copy(); T[1:] = S[1:, idx] + (S[0] - S[0, idx])[None]
            out['%s_D%d_mean' % (sn, D)] = ate(T.mean(0)); out['%s_D%d_gm' % (sn, D)] = ate(gmed(T))
        out['%s_avg' % sn] = float(np.mean([ate(s) for s in S])); out['%s_p0' % sn] = ate(S[0])
    return name, out


if __name__ == '__main__':
    pool = sys.argv[1]; cons.pool = pool
    zs = sorted(glob.glob(POOLS[pool] + '/*.zip'))
    with Pool(48) as p: res = dict(r for r in p.map(one, zs) if r)
    json.dump(res, open(os.path.dirname(os.path.abspath(__file__)) + '/lag_%s.json' % pool, 'w'))
    names = sorted(res); print(pool, len(names))
    for sn in USE:
        avg = np.mean([res[k]['%s_avg' % sn] for k in names]); p0 = np.mean([res[k]['%s_p0' % sn] for k in names])
        print('%-7s avg %.4f p0 %.4f | ' % (sn, avg, p0) + ' '.join(
            'D%d mean %+.1f%% gm %+.1f%%' % (D, 100 * (np.mean([res[k]['%s_D%d_mean' % (sn, D)] for k in names]) / avg - 1),
                                            100 * (np.mean([res[k]['%s_D%d_gm' % (sn, D)] for k in names]) / avg - 1)) for D in [0, 2, 5, 10, 20]))
