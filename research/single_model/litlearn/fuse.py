"""Post-hoc fusion test: replace filter 1 s increments by w*filter + (1-w)*net (variant B body-frame displacement rotated with the FILTER's own attitude). No truth used except for scoring
and for the net input (gravity direction from truth, optimistic). Samples at 1 s grid. PYTHONPATH=. python litlearn/fuse.py B 1.0 [lc_b11_r0]"""
import sys, glob, json, numpy as np
sys.path.insert(0, "/dev/shm/sebastian-vio/viobench")
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
from viobench.tools.geometry import poses_to_matrices
var, WL = sys.argv[1], float(sys.argv[2]); run = sys.argv[3] if len(sys.argv) > 3 else 'lc_b11_r0'; n = int(WL * 20)
P = json.load(open(f'research/single_model/litlearn/imuvel_pred_{var}_{WL}{__import__('os').environ.get('SUF','')}.json'))
EV = f'research/results/single_model/{run}/eval_f3'
def ate(a, b): return float(np.sqrt(np.mean(np.sum((a - b) ** 2, 1))))
W = [1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2, 0.0]
res = {w: [] for w in W}; base = []; names = []; rotchk = []
for ep, v in P.items():
    p = glob.glob(f'{EV}/*/{ep}/report/logs/*/estimate.tum')
    if not p: continue
    e = read_episode(f'/data/backups/rganapa/Sebastian/tmp/lc_fold3_pool/{ep}.zip', frames='none')
    t = np.asarray(e.frame_times); S = np.asarray(e.ground_truth_state()); G = S[:, :3]; Es = fill_missing_states(load_estimates(p[0], t)); E = Es[:, :3]
    Rbc = np.asarray(e.T_body_camera)[:3, :3]
    RG = poses_to_matrices(S)[:, :3, :3]; RE = poses_to_matrices(Es)[:, :3, :3]
    j = np.array(v['j']); mu = np.array(v['mu']); y = np.array(v['y'])
    sel = (j % n == 0); js = j[sel]; mu = mu[sel]; y = y[sel]
    # convention check: truth rotation applied to true body-frame displacement vs true cam0 displacement
    dtrue = np.einsum('nij,nj->ni', RG[js] @ Rbc.T, y); rotchk.append(np.linalg.norm(dtrue - (G[js] - G[js - n]), axis=1).mean())
    dnet = np.einsum('nij,nj->ni', RE[js] @ Rbc.T, mu)
    de = E[js] - E[js - n]
    k0 = js[0] - n  # start of the first window
    ref = G[np.r_[k0, js]]; names.append(ep)
    base.append(ate(E[np.r_[k0, js]] - E[k0] + G[k0], ref))
    for w in W:
        inc = w * de + (1 - w) * dnet
        path = G[k0] + np.vstack([np.zeros(3), np.cumsum(inc, 0)])
        res[w].append(ate(path, ref))
    dis = np.linalg.norm(de - dnet, axis=1)
    for thr in (0.6, 1.0):
        for wlo in (0.8, 0.7):
            ww = np.where(dis > thr, 0.0, wlo)[:, None]; inc = ww * de + (1 - ww) * dnet
            res.setdefault(('gate', thr, wlo), []).append(ate(G[k0] + np.vstack([np.zeros(3), np.cumsum(inc, 0)]), ref))
print('rot-convention check (mean |d|, m):', np.mean(rotchk))
print('flights', len(names), 'sampled-ATE filter %.4f' % np.mean(base))
ate_f = np.array(base)
for w in list(res):
    r = np.array(res[w]); print('w_filter=%s fused sampled-ATE mean %.4f median %.4f  >3m %d  (filter >3m %d)  better in %d/%d flights' % (str(w), r.mean(), np.median(r), (r > 3).sum(), (ate_f > 3).sum(), (r < ate_f).sum(), len(r)))
