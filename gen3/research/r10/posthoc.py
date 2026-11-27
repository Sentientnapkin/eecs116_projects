"""r10 post-hoc oracle analysis of unaligned ATE on existing eval trajectories.
usage: python posthoc.py OUT.json EVALDIR1 [EVALDIR2 ...]   (EVALDIR = evals/NAME/v3val/NAME-sha)
For each flight: e(t)=p_est-p_gt (world). Counterfactual corrections (oracle, GT-based):
 off_T   : subtract e(T) from all frames t>=T (embedded early position error removed at time T)
 offv_T  : subtract e(T)+(t-T)*de(T) (also remove velocity error at T, de from 0.5 s finite diff) for t>=T
 const   : best constant offset over whole flight (non-causal upper bound for any origin translation fix)
 lin     : best a+b t ; quad: best a+bt+ct^2 (upper bound for δp0, δv0, δg-type corrections)
 yaw     : best rotation about z through origin (initial-heading oracle); yawc: yaw+const
Also stores ATE windows, path length, duration, early error at horizons."""
import sys, json, glob, os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
POOLS = [Path('/data/backups/rganapa/Sebastian/gen3/pools/v3val'), Path('/data/backups/rganapa/Sebastian/gen3/pools/v1val')]
TS = [0.5, 1, 2, 3, 5, 10]
rms = lambda e: float(np.sqrt(np.mean(np.sum(e ** 2, 1))))

def one(work):
    work = Path(work); ep = work.name
    arch = next((p / (ep + '.zip') for p in POOLS if (p / (ep + '.zip')).exists()), None)
    logs = list((work / 'report/logs').glob('*/estimate.tum'))
    if arch is None or not logs: return None
    e = read_episode(arch, frames='none'); t = e.frame_times - e.frame_times[0]
    gt = e.ground_truth_state()[:, :3]; est = fill_missing_states(load_estimates(logs[0], e.frame_times))[:, :3]
    E = est - gt; n = len(t); r = {'id': ep, 'n': n, 'dur': float(t[-1]), 'path': float(np.linalg.norm(np.diff(gt, axis=0), axis=1).sum()),
                                  'ate': rms(E)}
    for T in TS:
        k = int(np.searchsorted(t, T))
        if k >= n - 1: continue
        r[f'err_{T}'] = float(np.linalg.norm(E[k]))
        F = E.copy(); F[k:] -= E[k]; r[f'off_{T}'] = rms(F)
        k2 = max(0, int(np.searchsorted(t, T - 0.5)))
        dv = (E[k] - E[k2]) / max(t[k] - t[k2], 1e-3)
        G = E.copy(); G[k:] -= E[k] + (t[k:, None] - t[k]) * dv; r[f'offv_{T}'] = rms(G)
    r['const'] = rms(E - E.mean(0))
    for name, deg in (('lin', 1), ('quad', 2)):
        A = np.vander(t, deg + 1); c = np.linalg.lstsq(A, E, rcond=None)[0]; r[name] = rms(E - A @ c)
    # best yaw about origin: est rotated by Rz(a) about p0_est
    best = (r['ate'], 0.0, r['const'])
    for a in np.radians(np.arange(-20, 20.01, 0.25)):
        c, s = np.cos(a), np.sin(a); R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        er = (est - est[0]) @ R.T + est[0] - gt; v = rms(er)
        if v < best[0]: best = (v, float(np.degrees(a)), rms(er - er.mean(0)))
    r['yaw'], r['yaw_deg'], r['yawc'] = best
    # error growth profile (for late-vs-early decomposition)
    r['prof'] = [float(np.linalg.norm(E[min(int(np.searchsorted(t, s)), n - 1)])) for s in range(0, 61, 5)]
    return r

if __name__ == '__main__':
    out = sys.argv[1]; works = []
    for d in sys.argv[2:]: works += sorted(glob.glob(d + '/*/report'))
    works = [str(Path(w).parent) for w in works]
    with ProcessPoolExecutor(8) as ex: res = [r for r in ex.map(one, works, chunksize=4) if r]
    json.dump(res, open(out, 'w')); print(len(res), 'flights ->', out)
