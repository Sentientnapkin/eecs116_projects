"""Ensemble feasibility: hindsight best-of-K vs causal per-frame fusion of several estimator runs on the same flights.
python ens.py POOLNAME RUN1 RUN2 ...   (RUN = results/single_model/<dir>, e.g. lv_glNP)"""
import sys, glob, os, json
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.datasets.sources import episodes

R = '/data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model/'
POOLS = {'st2conf': '/data/backups/rganapa/Sebastian/tmp/st_pools/st2conf', 'fconf': '/data/backups/rganapa/Sebastian/tmp/lv_pools/fconf',
         'st2dev': '/data/backups/rganapa/Sebastian/tmp/st_pools/st2dev'}
pool, runs = sys.argv[1], sys.argv[2:]

def est(run, name):
    f = glob.glob(R + '%s/%s/*/%s/report/logs/*/estimate.tum' % (run, pool, name))
    return np.loadtxt(f[0])[:, 1:4] if f else None

def one(z):
    name = os.path.basename(z)[:-4]
    E = [est(r, name) for r in runs]
    if any(e is None for e in E): return None
    gt = next(episodes([z])).ground_truth_state()[:, :3]
    n = min(len(gt), *(len(e) for e in E)); gt = gt[:n]; S = np.stack([e[:n] for e in E])   # K x n x 3
    ate = lambda p: float(np.sqrt(((p - gt) ** 2).sum(1).mean()))
    single = [ate(s) for s in S]
    med = np.median(S, axis=0)
    # causal medoid: at each frame use the run closest to the others (smallest summed distance)
    d = np.linalg.norm(S[:, None] - S[None, :], axis=3).sum(1)            # K x n
    medoid = S[np.argmin(d, axis=0), np.arange(n)]
    return name, single, ate(med), ate(medoid), ate(S.mean(0))

if __name__ == '__main__':
    zs = sorted(glob.glob(POOLS[pool] + '/*.zip'))
    with Pool(48) as p: res = [r for r in p.map(one, zs) if r]
    S = np.array([r[1] for r in res]); med = np.array([r[2] for r in res]); mdd = np.array([r[3] for r in res]); mn = np.array([r[4] for r in res])
    print('pool', pool, 'flights', len(res), 'runs', runs)
    for i, r in enumerate(runs): print('  single %-14s %.4f  >3m %d' % (r, S[:, i].mean(), (S[:, i] > 3).sum()))
    print('  hindsight best-of-K   %.4f' % S.min(1).mean())
    print('  causal median         %.4f  >3m %d' % (med.mean(), (med > 3).sum()))
    print('  causal medoid select  %.4f  >3m %d' % (mdd.mean(), (mdd > 3).sum()))
    print('  causal mean           %.4f' % mn.mean())
    json.dump(res, open(os.path.dirname(__file__) + '/ens_%s_%s.json' % (pool, '+'.join(runs)), 'w'))
