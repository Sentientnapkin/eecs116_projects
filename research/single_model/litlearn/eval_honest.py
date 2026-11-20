"""Evaluate trained imuvel_B net on fold-3 with gravity-in-body taken from the FILTER attitude (estimate.tum) + per-flight gravity direction estimated as mean cam0-frame specific force over the first 20 s (causal after 20 s; uses no truth).
Then fusion test as in fuse.py. usage: python eval_honest.py WL SUF"""
import sys, glob, json, numpy as np, torch
WL = float(sys.argv[1]); SUF = sys.argv[2] if len(sys.argv) > 2 else ''
sys.argv = ['x', 'B', '1', str(WL)]
sys.path.insert(0, "/dev/shm/sebastian-vio/viobench")
import importlib; T = importlib.import_module('research.single_model.litlearn.train_imuvel')
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
from viobench.tools.geometry import poses_to_matrices
dev = 'cuda'; W = T.W; n = int(WL * 20)
net = T.Net(9).to(dev); net.load_state_dict(torch.load(T.HERE / f'imuvel_B_{WL}{SUF}.pt')); net.eval()
sc = torch.tensor([0.1] * 3 + [0.3] * 3 + [1.0] * 3, device=dev).view(1, -1, 1)
Dev, offe = T.load(T.F3)
EV = 'research/results/single_model/lc_b11_r0/eval_f3'
def ate(a, b): return float(np.sqrt(np.mean(np.sum((a - b) ** 2, 1))))
Wl = [1.0, 0.8, 0.7, 0.6, 0.5, 0.0]; res = {w: [] for w in Wl}; gate = {}; MON = []; base = []; tilt = []; ne = []; netrms = []
for i, ep in enumerate(T.F3):
    p = glob.glob(f'{EV}/*/{ep}/report/logs/*/estimate.tum')
    if not p: continue
    e = read_episode(f'/data/backups/rganapa/Sebastian/tmp/lc_fold3_pool/{ep}.zip', frames='none')
    t = np.asarray(e.frame_times); S = np.asarray(e.ground_truth_state()); G = S[:, :3]; Es = fill_missing_states(load_estimates(p[0], t)); E = Es[:, :3]
    Rbc = np.asarray(e.T_body_camera)[:3, :3]; RE = poses_to_matrices(Es)[:, :3, :3]; RG = poses_to_matrices(S)[:, :3, :3]
    z = np.load(T.CACHE / f'{ep}.npz'); ti = z['ti']; a = z['a']
    k20 = np.searchsorted(ti, t[:400]); 
    # cam0-frame mean specific force over first 20 s using FILTER attitude
    idx = np.clip(np.searchsorted(t, ti[:4000]) , 0, len(t) - 1)
    up = np.einsum('nij,nj->ni', RE[idx] @ Rbc.T, a[:4000]).mean(0); up /= np.linalg.norm(up)
    js = np.arange(n, len(t), n); ends = np.searchsorted(ti, t[js] + 1e-6, side='right') - 1 + offe[i]
    ix = torch.from_numpy(ends).to(dev)
    x, y = T.batch(Dev, ix)
    gf = np.einsum('ij,nkj,k->ni', Rbc, RE, up)  # per frame: Rbc R_e^T up
    gs = np.stack([np.interp(ti, t, gf[:, c]) for c in range(3)], 1); gs /= np.linalg.norm(gs, axis=1, keepdims=True)
    ar = np.arange(-W + 1, 1); gwin = gs[(ends - offe[i])[:, None] + ar[None]]  # (B,W,3)
    gt = x[:, 6:9, :].transpose(1, 2).cpu().numpy() if False else x[:, 6:9, :].cpu().numpy().transpose(0, 2, 1)
    tilt.append(np.degrees(np.arccos(np.clip((gwin[:, -1] * gt[:, -1]).sum(1), -1, 1))))
    x = torch.cat([x[:, :6], torch.from_numpy(gwin.transpose(0, 2, 1).astype(np.float32)).to(dev)], 1)
    with torch.no_grad(): o = net(x * sc)
    mu = o[:, :3].cpu().numpy()
    dnet = np.einsum('nij,nj->ni', RE[js] @ Rbc.T, mu); de = E[js] - E[js - n]; dg = G[js] - G[js - n]
    netrms.append(np.linalg.norm(dnet - dg, axis=1)); ne.append(np.linalg.norm(de - dg, axis=1))
    k0 = js[0] - n; ref = G[np.r_[k0, js]]; base.append(ate(E[np.r_[k0, js]] - E[k0] + G[k0], ref))
    for w in Wl: res[w].append(ate(G[k0] + np.vstack([np.zeros(3), np.cumsum(w * de + (1 - w) * dnet, 0)]), ref))
    dis = np.linalg.norm(de - dnet, axis=1); MON.append((ep, ate(E, G), t[js], dis, np.linalg.norm(E[js] - G[js], axis=1)))
    for thr in (0.6, 1.0):
        ww = np.where(dis > thr, 0.0, 0.8)[:, None]; gate.setdefault(thr, []).append(ate(G[k0] + np.vstack([np.zeros(3), np.cumsum(ww * de + (1 - ww) * dnet, 0)]), ref))
print('tilt error of gravity-in-body (filter attitude, no truth): rms %.2f deg  median %.2f' % (np.sqrt(np.mean(np.concatenate(tilt) ** 2)), np.median(np.concatenate(tilt))))
print('window-disp err rms: filter %.3f  net %.3f' % tuple(np.sqrt(np.mean(np.concatenate(v) ** 2)) for v in (ne, netrms)))
print('filter sampled ATE %.4f' % np.mean(base))
for w in Wl:
    r = np.array(res[w]); print('w_filter=%.1f fused %.4f median %.4f >3m %d better %d/%d' % (w, r.mean(), np.median(r), (r > 3).sum(), (r < np.array(base)).sum(), len(r)))
for thr in gate: r = np.array(gate[thr]); print('gate>%.1f (w .8 else net only) fused %.4f median %.4f >3m %d better %d/%d' % (thr, r.mean(), np.median(r), (r > 3).sum(), (r < np.array(base)).sum(), len(r)))

ates = np.array([m[1] for m in MON])
def auc(sc_, y):
    o = np.argsort(sc_); rk = np.empty(len(sc_)); rk[o] = np.arange(len(sc_)); pos = y.astype(bool)
    return (rk[pos].mean() - (pos.sum() - 1) / 2) / (len(sc_) - pos.sum())
for T_ in (6, 10, 20):
    sm = np.array([np.mean(m[3][m[2] <= T_]) for m in MON]); print('MONITOR first %ds AUC(mean dis) ate>1 (n=%d): %.2f ; ate>0.7: %.2f' % (T_, (ates > 1).sum(), auc(sm, ates > 1), auc(sm, ates > .7)))
for c in (1.0, 1.5):
    hit = [(m[0][-14:], float(m[2][np.argmax(m[3] > c)]), round(float(m[4][np.argmax(m[3] > c)]), 2)) for m in MON if m[1] > 1 and (m[3] > c).any()]
    fa = sum(1 for m in MON if m[1] <= 1 and (m[3] > c).any()); print('thr %.1f flagged bad %d/%d, false alarms %d/%d, (ep,t,err) %s' % (c, len(hit), (ates > 1).sum(), fa, (ates <= 1).sum(), hit))
