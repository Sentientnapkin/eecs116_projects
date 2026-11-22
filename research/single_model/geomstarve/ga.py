"""ga.py RUNDIR POOL OUT.json : per-flight starvation diagnosis from a GS_DIAG=1 TC_LOG=1 run (analysis only; truth used for scoring).
Run with: PYTHONPATH=/dev/shm/sebastian-vio/viobench venv-viobench python ga.py ..."""
import sys, glob, json, os, re
import numpy as np
from concurrent.futures import ProcessPoolExecutor
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
RUN, POOL = sys.argv[1], sys.argv[2]
RG = re.compile(r'G f=(\d+) live=(\d+) lo=(\d+) mean=([\d.]+) black=([\d.]+) g8=([\d.]+) g20=([\d.]+) edges=(\d+) rows=(\d+) used=(\d+) cl=(\d)')
RD = re.compile(r'D f=(\d+) t=([\d.]+) live=(\d+) used=\d+ u20=\d+ att=(\d+) gate=(\d+) tri=(\d+) nis=([\d.]+) .* fire=(\d+) Pv=([\d.]+)')

def one(d):
    ep = os.path.basename(d)
    try:
        est = glob.glob(f'{d}/report/logs/*/estimate.tum')[0]; se = est.replace('estimate.tum', 'stderr.txt')
        e = read_episode(f'{POOL}/{ep}.zip', frames='none')
        t = np.asarray(e.frame_times); S = np.asarray(e.ground_truth_state()); n = len(t)
        E = fill_missing_states(load_estimates(est, t))
        Tg, Te = poses_to_matrices(S), poses_to_matrices(E)
        err = Te[:, :3, 3] - Tg[:, :3, 3]
        rms = lambda x: float(np.sqrt(np.mean(np.sum(x ** 2, 1))))
        G = np.full((n, 10), np.nan); acc = np.zeros(n); pv = np.zeros(n); fire = np.zeros(n)
        for line in open(se):
            m = RG.match(line)
            if m:
                f = int(m.group(1)) - 1
                if 0 <= f < n: G[f] = [float(m.group(k)) for k in range(2, 12)]
                continue
            m = RD.match(line)
            if m:
                f = int(m.group(1)) - 1
                if 0 <= f < n: acc[f] = int(m.group(4)) - int(m.group(5)) - int(m.group(6)); pv[f] = float(m.group(9)); fire[f] = int(m.group(8))
        live, lo, mean, black, g8, g20 = G[:, 0], G[:, 1], G[:, 2], G[:, 3], G[:, 4], G[:, 5]
        ok = ~np.isnan(live)
        live = np.where(ok, live, 0); lo = np.where(ok, lo, 0)
        inc = np.diff(err, axis=0, prepend=err[:1])
        vtrue = np.gradient(S[:, :3], t, axis=0); sp = np.linalg.norm(vtrue, axis=1)
        verr = np.linalg.norm(np.gradient(err, t, axis=0), axis=1)
        def cf(mask): r = np.cumsum(np.where(mask[:, None], 0, inc), 0); return rms(r)
        cls = dict(black=np.nan_to_num(black) > 0.97, live0=live == 0, live5=live < 5, live10=live < 10, live20=live < 20,
                   nb_live10=(np.nan_to_num(black) <= 0.97) & (live < 10), fast=sp > 2.0)
        out = dict(ep=ep, ate=rms(err), ate_mt=rms(err - err.mean(0)), sp_mean=float(sp.mean()), path=float(np.sum(np.linalg.norm(np.diff(S[:, :3], axis=0), axis=1))),
                   nfire=int((fire > 0).sum()), live_med=float(np.median(live)), black_mean=float(np.nanmean(black)),
                   g20_nb=float(np.nanmean(np.where(np.nan_to_num(black) <= 0.97, g20, np.nan))) if np.any(np.nan_to_num(black) <= 0.97) else 0.0)
        for k, msk in cls.items():
            out['f_' + k] = float(msk.mean()); out['cf_' + k] = cf(msk)
            out['verr_' + k] = float(verr[msk].mean()) if msk.any() else None
        out['verr_all'] = float(verr.mean())
        # error growth: fraction of total |increment| in class frames
        a = np.linalg.norm(inc, axis=1)
        for k, msk in cls.items(): out['incfrac_' + k] = float(a[msk].sum() / max(a.sum(), 1e-9))
        return out
    except Exception as ex:
        return dict(ep=ep, error=repr(ex))

if __name__ == '__main__':
    ds = sorted(d for d in glob.glob(f'{RUN}/*') if os.path.isdir(d) and os.path.exists(f'{d}/report'))
    with ProcessPoolExecutor(16) as ex: rows = list(ex.map(one, ds))
    json.dump(rows, open(sys.argv[3], 'w'))
    R = [r for r in rows if 'error' not in r]; print(len(R), 'ok', len(rows) - len(R), 'err', [r['error'] for r in rows if 'error' in r][:2])
    A = np.array([r['ate'] for r in R])
    print('mean ATE %.3f  rigid-removed %.3f' % (A.mean(), np.mean([r['ate_mt'] for r in R])))
    for k in ['black', 'live0', 'live5', 'live10', 'live20', 'nb_live10', 'fast']:
        print('%-10s frac %.3f  cf %.3f  incfrac %.3f  verr %.3f (all %.3f)' % (k, np.mean([r['f_' + k] for r in R]), np.mean([r['cf_' + k] for r in R]),
              np.mean([r['incfrac_' + k] for r in R]), np.nanmean([r['verr_' + k] if r['verr_' + k] is not None else np.nan for r in R]), np.mean([r['verr_all'] for r in R])))
    R.sort(key=lambda r: -r['ate'])
    print('ep ate live_med f_black f_live10 f_nb_live10 g20_nb incfrac_black incfrac_nbl10 sp path')
    for r in R[:20]:
        print('%-36s %.2f %4.0f %.2f %.2f %.2f %.3f %.2f %.2f %.2f %.0f' % (r['ep'], r['ate'], r['live_med'], r['f_black'], r['f_live10'], r['f_nb_live10'], r['g20_nb'], r['incfrac_black'], r['incfrac_nb_live10'], r['sp_mean'], r['path']))
    hi = [r for r in R if r['ate'] > 1]; lo = [r for r in R if r['ate'] < 0.5]
    for nm, S in (('ate>1', hi), ('ate<0.5', lo)):
        print(nm, len(S), ' '.join('%s %.3f' % (k, np.mean([r[k] for r in S])) for k in ['f_black', 'f_live10', 'f_nb_live10', 'live_med', 'g20_nb', 'sp_mean', 'path']))
