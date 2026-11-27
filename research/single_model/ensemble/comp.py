"""Complementarity analysis of existing estimator builds (read-only on logged estimate.tum; no new estimator runs).
python comp.py POOL   -> comp_POOL.pkl (per-flight metrics) ; summarize with comp_report.py
Families = mechanism-distinct builds; each has up to 3 chaos replicas (r0, r1, r2: PIXEL_STD/DETECT_MIN_SCORE nudges).
For every subset (size 2..4) of families and every replica index i (family uses its r_i, or r0 if it has fewer reps) we compute:
  hindsight best-of-K per flight, segment oracle (best member per 1 s / 5 s window, per-frame), causal per-frame mean/median/medoid,
  fixed-weight pair blends (w=0..1). Plus pairwise per-flight error-vector correlation for ALL runs (incl. replicas)."""
import sys, glob, os, pickle, itertools
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.datasets.sources import episodes

R = '/data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model/'
SL = '/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/stlong/results/'
ST, LV = '/data/backups/rganapa/Sebastian/tmp/st_pools/', '/data/backups/rganapa/Sebastian/tmp/lv_pools/'
POOLDIR = {p: ST + p for p in ['st2dev', 'st2conf', 'st1dev', 'st1conf', 'probe']}
POOLDIR.update({p: LV + p for p in ['fdev', 'fconf', 'st3']})
r3 = lambda r: [r, r + '_r1', r + '_r2']
ST2 = [('GSLV', r3('lv_glNP')), ('LJA', r3('lj_ajc')), ('LJB4', r3('lj_ajgb4')), ('GSLM', r3('lv_gl')),
       ('LGVHY', r3('gs_lgVHY')), ('RSOFT', r3('fc_rsoft1t0')), ('HM40', r3('st_hm40')), ('HFG', r3('st_hfg')),
       ('B17X', ['st_b17x', 'fc_b17x_r1', 'fc_b17x_r2']), ('BM40', r3('fc_Bm40s1')), ('EDGE', r3('gs_eB')),
       ('KV1', r3('gs_kv1')), ('G24M', r3('st_G24m')), ('C30M', r3('st_C30m')), ('L8', r3('fc_L8'))]
FAM = {
    'st2dev': ST2 + [('SLBASE', ['sl:baseline']), ('SLPILOT', ['sl:pilot']), ('SLPMM', ['sl:pilot_mm'])],
    'st2conf': ST2 + [('OVINS', ['lv_ovins'])],
    'st3': [('GSLV', r3('lv_glNP')), ('LJA', r3('lj_ajc')), ('LJB4', r3('lj_ajgb4')), ('GSLM', r3('lv_gl')),
            ('RSOFT', r3('lv_rs')), ('RSLV', r3('lv_rsNP10B')), ('HM40', r3('lv_hm40')), ('HM40P', r3('lv_P10S2')),
            ('SLBASE', ['sl:baseline']), ('SLPILOT', ['sl:pilot']), ('SLPMM', ['sl:pilot_mm'])],
    'st1dev': [('GSLV', r3('lv_glNP')), ('LJA', r3('lj_ajc')), ('LJB4', r3('lj_ajgb4')), ('GSLM', r3('lv_gl')),
               ('LYPK', ['gs_lYpK']), ('LGVHY', ['gs_lgVHY']), ('RSOFT', ['fc_rsoft1t0s']), ('HM40', ['fc_hm40', 'gs_hm40b', 'gs_hm40b_r1']),
               ('HFG', r3('st_hfg')), ('C30', r3('st_C30')), ('B17X', ['st_b17x']), ('GB6', ['st_GB6'])],
    'probe': [('HFG', r3('st_hfg')), ('C30', r3('st_C30')), ('B17X', ['st_b17x']), ('GB6', ['st_GB6']), ('C30M', ['st_C30m']),
              ('K30', ['st_K30']), ('C34', ['st_C34'])],
    'fdev': [('GSLV', r3('lv_glNP')), ('LJA', r3('lj_ajc')), ('LJB4', r3('lj_ajgb4')), ('GSLM', r3('lv_gl'))],
}
FAM['st1conf'] = FAM['st1dev']; FAM['fconf'] = FAM['fdev']
pool = sys.argv[1]; fams = FAM[pool]
WIN = {'w1s': 20, 'w5s': 100, 'frame': 1}

def path(run, name):
    if run.startswith('sl:'): g = glob.glob(SL + '%s/%s/%s/report/logs/*/estimate.tum' % (run[3:], pool, name))
    else: g = glob.glob(R + '%s/%s/*/%s/report/logs/*/estimate.tum' % (run, pool, name))
    return g[0] if g else None

def seg_oracle(E2, w):            # E2: K x n per-frame squared errors -> RMSE choosing best member per window
    K, n = E2.shape; m = (n + w - 1) // w; pad = np.zeros((K, m * w)); pad[:, :n] = E2
    return float(np.sqrt(pad.reshape(K, m, w).sum(2).min(0).sum() / n))

def one(z):
    name = os.path.basename(z)[:-4]
    runs = {r: path(r, name) for _, rs in fams for r in rs}
    if any(v is None for v in runs.values()): return name, None, sorted(k for k, v in runs.items() if v is None)
    gt = next(episodes([z])).ground_truth_state()[:, :3]
    P = {r: np.loadtxt(f)[:, 1:4] for r, f in runs.items()}
    n = min(len(gt), *(len(p) for p in P.values())); gt = gt[:n]
    P = {r: p[:n] for r, p in P.items()}
    ate = lambda p: float(np.sqrt(((p - gt) ** 2).sum(1).mean()))
    out = {'n': n, 'ate': {r: ate(p) for r, p in P.items()}, 'evc': {}, 'sets': {}, 'blend': {}}
    rl = list(P)
    for a, b in itertools.combinations(rl, 2):    # error-vector correlation (how much averaging cancels)
        ea, eb = P[a] - gt, P[b] - gt
        out['evc'][(a, b)] = float((ea * eb).sum() / np.sqrt((ea ** 2).sum() * (eb ** 2).sum() + 1e-30))
    F = [f for f, _ in fams]; fr = dict(fams)
    for i in range(3):
        mem = {f: fr[f][i] if len(fr[f]) > i else fr[f][0] for f in F}
        for K in (2, 3, 4):
            for S in itertools.combinations(F, K):
                if i > 0 and all(len(fr[f]) == 1 for f in S): continue
                X = np.stack([P[mem[f]] for f in S]); E2 = ((X - gt) ** 2).sum(2)
                d = np.linalg.norm(X[:, None] - X[None, :], axis=3).sum(1)
                r = {'mean': ate(X.mean(0)), 'median': ate(np.median(X, 0)),
                     'medoid': ate(X[np.argmin(d, 0), np.arange(n)])}
                for k, w in WIN.items(): r[k] = seg_oracle(E2, w)
                out['sets'][(i, S)] = r
                if K == 2:
                    out['blend'][(i, S)] = [ate(w * X[0] + (1 - w) * X[1]) for w in np.linspace(0, 1, 11)]
    # replicate (chaos) ensembles within a family
    out['rep'] = {}
    for f, rs in fams:
        if len(rs) < 3: continue
        X = np.stack([P[r] for r in rs]); E2 = ((X - gt) ** 2).sum(2)
        d = np.linalg.norm(X[:, None] - X[None, :], axis=3).sum(1)
        r = {'mean': ate(X.mean(0)), 'median': ate(np.median(X, 0)), 'medoid': ate(X[np.argmin(d, 0), np.arange(n)]),
             'mean2': ate(X[:2].mean(0))}
        for k, w in WIN.items(): r[k] = seg_oracle(E2, w)
        r['w1s_2'] = seg_oracle(E2[:2], 20)
        out['rep'][f] = r
    return name, out, None

if __name__ == '__main__':
    zs = sorted(glob.glob(POOLDIR[pool] + '/*.zip'))
    with Pool(int(os.environ.get('W', 48))) as p: res = p.map(one, zs, chunksize=1)
    miss = [(n, m) for n, o, m in res if o is None]
    res = {n: o for n, o, m in res if o is not None}
    print(pool, 'flights', len(res), 'missing', len(miss), miss[:3])
    pickle.dump({'pool': pool, 'fams': fams, 'res': res, 'miss': miss},
                open(os.path.dirname(os.path.abspath(__file__)) + '/comp_%s.pkl' % pool, 'wb'))
