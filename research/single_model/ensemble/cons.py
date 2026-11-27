"""T1: replay of the course OpenVINS-baseline consensus (geometric median + causal 2 s observer) and variants
on stored multi-run outputs. Causal per-frame rules only (each output frame uses members' frames <= t).
python cons.py POOL           -> cons_POOL.json  (per-flight ATE for every member set x rule)
Members: estimate.tum (camera-0 frame positions, quaternion) + twist.txt (camera-k axes velocity -> rotated to world)."""
import sys, glob, os, json
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.datasets.sources import episodes

R = '/data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model/'
POOLS = {'st2conf': '/data/backups/rganapa/Sebastian/tmp/st_pools/st2conf', 'fconf': '/data/backups/rganapa/Sebastian/tmp/lv_pools/fconf'}
RUNS = ['lv_glNP', 'lv_glNP_r1', 'lv_glNP_r2', 'lj_ajc', 'lj_ajc_r1', 'lj_ajc_r2', 'lv_gl', 'lv_gl_r1', 'lv_gl_r2']
V3, J3, M3 = RUNS[0:3], RUNS[3:6], RUNS[6:9]
SETS = {'V3': V3, 'J3': J3, 'M3': M3, 'V3M3': V3 + M3, 'V1M1': [V3[0], M3[0]], 'V2M1': [V3[0], V3[1], M3[0]],
        'V1M2': [V3[0], M3[0], M3[1]], 'V1J1M1': [V3[0], J3[0], M3[0]], 'J2M1': [J3[0], J3[1], M3[0]], 'VJ6': V3 + J3}
pool = sys.argv[1] if len(sys.argv) > 1 else 'st2conf'


def qrot(q):  # q = (qx,qy,qz,qw) -> n x 3 x 3
    x, y, z, w = q.T
    return np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], -1),
                     np.stack([2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], -1),
                     np.stack([2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)], -1)], 1)


def load(run, name):
    f = glob.glob(R + '%s/%s/*/%s/report/logs/*/estimate.tum' % (run, pool, name))
    if not f: return None
    e = np.loadtxt(f[0]); tw = np.loadtxt(os.path.dirname(f[0]) + '/twist.txt')
    n = min(len(e), len(tw))
    v = np.einsum('nij,nj->ni', qrot(e[:n, 4:8]), tw[:n, 1:4])
    return e[:n, 0], e[:n, 1:4], v


def gmed(X, w=None, it=60):
    """Weighted geometric median over axis 0 of K x n x 3, per frame. Weiszfeld + vertex optimality test (exact for K=3:
    a vertex with angle >= 120 deg is returned; otherwise converges to the Fermat point)."""
    K = X.shape[0]
    w = np.ones(X.shape[:2]) if w is None else w
    if K == 1: return X[0]
    if K == 2: return (w[0, :, None] * X[0] + w[1, :, None] * X[1]) / (w[0] + w[1])[:, None]
    y = (w[..., None] * X).sum(0) / w.sum(0)[:, None]
    for _ in range(it):
        d = np.maximum(np.linalg.norm(X - y, axis=2), 1e-9)
        a = w / d
        y = (a[..., None] * X).sum(0) / a.sum(0)[:, None]
    for k in range(K):  # vertex test: |sum_{j!=k} w_j u_kj| <= w_k  -> vertex k is the median
        g = np.zeros_like(y)
        for j in range(K):
            if j == k: continue
            dv = X[j] - X[k]; g += w[j][:, None] * dv / np.maximum(np.linalg.norm(dv, axis=1), 1e-12)[:, None]
        m = np.linalg.norm(g, axis=1) <= w[k]
        y[m] = X[k][m]
    return y


def observer(P, V, t, tau, trap=True):
    """Baseline anti-jump observer: predict with trapezoidal median velocity, bleed toward median position."""
    out = np.empty_like(P); out[0] = P[0]
    for i in range(1, len(P)):
        dt = t[i] - t[i - 1]
        pred = out[i - 1] + (0.5 * (V[i - 1] + V[i]) if trap else V[i]) * dt
        a = 1.0 if tau == 0 else (0.0 if tau == np.inf else 1 - np.exp(-dt / tau))
        out[i] = pred + a * (P[i] - pred)
    return out


def ema_w(X, C, t, tau=5.0):
    """Causal weight per member: 1/(eps + EMA of squared distance to consensus C), using frames < i (strictly causal)."""
    K, n = X.shape[:2]; d2 = ((X - C) ** 2).sum(2); w = np.ones((K, n)); e = np.zeros(K)
    for i in range(n):
        w[:, i] = 1.0 / (0.01 + e)
        a = 1 - np.exp(-0.05 / tau); e = (1 - a) * e + a * d2[:, i]
    return w


def reanchor_proxy(X, t, period):
    """Proxy for position-only feedback: every `period` s each member is shifted onto the consensus; members keep their own
    increments in between (assumes reset does not change their future increments - true only for position-only feedback)."""
    K, n = X.shape[:2]; off = np.zeros((K, 3)); out = np.empty((n, 3)); last = 0.0
    for i in range(n):
        Y = X[:, i] + off
        c = gmed(Y[:, None])[0]
        out[i] = c
        if t[i] - last >= period - 1e-9:
            off += c - Y; last = t[i]
    return out


def rules(S, Vw, t):
    K = S.shape[0]; out = {}
    gm = gmed(S); vgm = gmed(Vw)
    out['mean'] = S.mean(0); out['cmed'] = np.median(S, 0); out['gm'] = gm
    for tau in [0.5, 1, 2, 4, 8]: out['gm_obs%g' % tau] = observer(gm, vgm, t, tau)
    out['vint'] = observer(gm, vgm, t, np.inf)       # integrate consensus velocity only (measurement-level velocity proxy)
    out['mean_obs2'] = observer(S.mean(0), Vw.mean(0), t, 2)
    # causal backward-difference member velocities (include the filters' position corrections, unlike twist)
    dt = np.diff(t, prepend=t[0] - 0.05); Vb = np.diff(S, axis=1, prepend=S[:, :1]) / dt[None, :, None]
    vb = gmed(Vb)
    for tau in [0.5, 2, 8]: out['ginc_obs%g' % tau] = observer(gm, vb, t, tau, False)
    out['ginc_inf'] = observer(gm, vb, t, np.inf, False)
    if K >= 3:
        far = np.argmax(np.linalg.norm(S - gm, axis=2), 0)
        keep = np.ones(S.shape[:2], bool); keep[far, np.arange(S.shape[1])] = False
        tm = (S * keep[..., None]).sum(0) / keep.sum(0)[:, None]; tv = (Vw * keep[..., None]).sum(0) / keep.sum(0)[:, None]
        out['trim'] = tm; out['trim_obs2'] = observer(tm, tv, t, 2)
    w = ema_w(S, gm, t)
    wm = (w[..., None] * S).sum(0) / w.sum(0)[:, None]; wv = (w[..., None] * Vw).sum(0) / w.sum(0)[:, None]
    out['wdis'] = wm; out['wdis_obs2'] = observer(wm, wv, t, 2)
    wg = gmed(S, w); out['wgm_obs2'] = observer(wg, gmed(Vw, w), t, 2)
    wvel = ema_w(Vw, vgm, t, 2.0)                      # weight by causal velocity disagreement
    wvm = (wvel[..., None] * S).sum(0) / wvel.sum(0)[:, None]; wvv = (wvel[..., None] * Vw).sum(0) / wvel.sum(0)[:, None]
    out['wvel_obs2'] = observer(wvm, wvv, t, 2)
    for p in [1, 5]: out['reanch%d' % p] = reanchor_proxy(S, t, p)
    d = np.linalg.norm(S[:, None] - S[None, :], axis=3).sum(1); out['medoid'] = S[np.argmin(d, 0), np.arange(S.shape[1])]
    return out, vgm


def one(z):
    name = os.path.basename(z)[:-4]
    L = {r: load(r, name) for r in RUNS}
    if any(v is None for v in L.values()): return None
    gt = next(episodes([z])).ground_truth_state()[:, :3]
    n = min(len(gt), *(len(v[1]) for v in L.values())); gt = gt[:n]
    t = L[RUNS[0]][0][:n]
    gv = np.gradient(gt, t, axis=0)
    ate = lambda p: float(np.sqrt(((p - gt) ** 2).sum(1).mean()))
    vrms = lambda v: float(np.sqrt(((v - gv) ** 2).sum(1).mean()))
    res = {'single': {r: ate(L[r][1][:n]) for r in RUNS}, 'vsingle': {r: vrms(L[r][2][:n]) for r in RUNS},
           'vfd_check': float(np.sqrt(((np.gradient(L[RUNS[0]][1][:n], t, axis=0) - L[RUNS[0]][2][:n]) ** 2).sum(1).mean())), 'sets': {}}
    for sn, members in SETS.items():
        S = np.stack([L[r][1][:n] for r in members]); Vw = np.stack([L[r][2][:n] for r in members])
        o, vgm = rules(S, Vw, t)
        res['sets'][sn] = {k: ate(v) for k, v in o.items()}
        res['sets'][sn]['_vgm_rms'] = vrms(vgm)
    return name, res


if __name__ == '__main__':
    zs = sorted(glob.glob(POOLS[pool] + '/*.zip'))
    with Pool(48) as p: res = [r for r in p.map(one, zs) if r]
    json.dump(dict(res), open(os.path.dirname(os.path.abspath(__file__)) + '/cons_%s.json' % pool, 'w'))
    print(pool, len(res), 'flights')
