"""learned_sel.py: offline feasibility checks for using learned models as ensemble members / a learned selector.
Analysis only (truth used for labels/scoring). Inputs are existing tables; no holdout, no fold 4.
  A: learnvel/tables/diag_lcJ_st2dev.json (lcJ net vs HM40 filter velocity error at every stride-5 anchor, + TC_LOG signals)
     -> error correlation, autocorrelation, and a tiny per-anchor selector (logistic / boosted stumps), scene-grouped CV.
  B: stlong/tables/{teacher4,v700b}_{st2dev,st3}_pred.npz -> teacher vs deployed-net error correlation and fusion.
Run: venv-teacher python -I learned_sel.py"""
import json, re, hashlib
import numpy as np

SM = '/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/'
out = {}

def auc(s, y):
    o = np.argsort(s); r = np.empty(len(s)); r[o] = np.arange(1, len(s) + 1)
    n1 = y.sum(); n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))

def logreg(X, y, l2=1e-3, it=300):
    w = np.zeros(X.shape[1])
    for _ in range(it):                      # Newton
        p = 1 / (1 + np.exp(-X @ w)); g = X.T @ (p - y) / len(y) + l2 * w
        H = (X * (p * (1 - p))[:, None]).T @ X / len(y) + l2 * np.eye(len(w)); w -= np.linalg.solve(H, g)
    return w

def stumps(X, y, n=60, lr=0.2, nq=16):
    """gradient-boosted depth-1 trees on logistic loss (each stump = 1 compare + 1 add at inference)."""
    F = np.zeros(len(y)); model = []
    qs = [np.unique(np.quantile(X[:, j], np.linspace(0.05, 0.95, nq))) for j in range(X.shape[1])]
    for _ in range(n):
        p = 1 / (1 + np.exp(-F)); g = y - p; h = p * (1 - p) + 1e-9
        best = None
        for j in range(X.shape[1]):
            for t in qs[j]:
                m = X[:, j] <= t
                gl, hl, gr, hr = g[m].sum(), h[m].sum(), g[~m].sum(), h[~m].sum()
                gain = gl * gl / (hl + 1) + gr * gr / (hr + 1)
                if best is None or gain > best[0]: best = (gain, j, t, gl / (hl + 1), gr / (hr + 1))
        _, j, t, a, b = best; model.append((j, t, lr * a, lr * b)); F += np.where(X[:, j] <= t, lr * a, lr * b)
    return model

def stump_pred(model, X):
    F = np.zeros(len(X))
    for j, t, a, b in model: F += np.where(X[:, j] <= t, a, b)
    return F

# ---------------- A: lcJ net vs HM40 filter ----------------
R = json.load(open(SM + 'learnvel/tables/diag_lcJ_st2dev.json'))
ep = np.array([r['ep'] for r in R]); f = np.array([r['f'] for r in R])
nerr = np.array([r['nerr'] for r in R]); ferr = np.array([r['ferr'] for r in R], float)
sig = np.array([r['sig'] for r in R]); live = np.array([r['live'] for r in R]); pv = np.array([r['pv'] for r in R])
tex = np.array([r['tex'] for r in R]); nsp = np.linalg.norm(np.array([r['mu'] for r in R]), axis=1); spd = np.array([r['spd'] for r in R])
ok = np.isfinite(ferr) & np.isfinite(live) & np.isfinite(pv)
scene = np.array([re.sub(r'-\d+$', '', e.split('-', 1)[1]) for e in ep])
A = dict(n_anchors=int(ok.sum()), n_flights=int(len(set(ep[ok]))), n_scenes=int(len(set(scene[ok]))))
e_n, e_f = nerr[ok], ferr[ok]
A['mean_err'] = dict(net=float(e_n.mean()), filt=float(e_f.mean()), oracle_min=float(np.minimum(e_n, e_f).mean()))
rk = lambda x: np.argsort(np.argsort(x))
A['spearman_net_vs_filter_err'] = float(np.corrcoef(rk(e_n), rk(e_f))[0, 1])
A['frac_net_better'] = float((e_n < e_f).mean())
for thr in (0.3, 0.5, 1.0):
    m = e_f > thr; A['filter_err_gt_%.1f' % thr] = dict(frac=float(m.mean()), net=float(e_n[m].mean()), filt=float(e_f[m].mean()))
# within-flight autocorrelation of error magnitudes at lags of 1,2,4,8 anchors (0.25 s per anchor)
ac = {}
for name, e in (('net', nerr), ('filt', ferr)):
    for lag in (1, 2, 4, 8, 20):
        a, b = [], []
        for E in set(ep[ok]):
            idx = np.where((ep == E) & ok)[0]; idx = idx[np.argsort(f[idx])]
            x = e[idx]; x = x - x.mean()
            if len(x) > lag: a.append(x[:-lag]); b.append(x[lag:])
        a, b = np.concatenate(a), np.concatenate(b); ac['%s_lag%d' % (name, lag)] = float((a * b).mean() / np.sqrt((a * a).mean() * (b * b).mean()))
A['autocorr_err_within_flight_demeaned'] = ac
# selector: label = net better than filter by a margin that matters (> 0.1 m/s); features causal
X = np.stack([np.log1p(live), np.log(pv + 1e-3), np.log(sig), nsp, tex, np.log(sig) - np.log(pv + 1e-3)], 1)[ok]
y = (e_f - e_n > 0.1).astype(float)
fold = np.array([int(hashlib.sha256(s.encode()).hexdigest(), 16) % 5 for s in scene[ok]])
pl, ps = np.zeros(len(y)), np.zeros(len(y))
mu_, sd_ = X.mean(0), X.std(0) + 1e-9
Xs = (X - mu_) / sd_; X1 = np.c_[np.ones(len(Xs)), Xs]
for k in range(5):
    tr, te = fold != k, fold == k
    pl[te] = X1[te] @ logreg(X1[tr], y[tr]); ps[te] = stump_pred(stumps(Xs[tr], y[tr]), Xs[te])
A['selector_label'] = 'filter err - net err > 0.1 m/s (positive rate %.3f)' % y.mean()
A['selector_auc_scene5fold'] = dict(logistic=auc(pl, y), stumps60=auc(ps, y),
                                    single_pv=auc(X[:, 1], y), single_live=auc(-X[:, 0], y), single_netspeed=auc(-X[:, 3], y))
for nm, s in (('logistic', pl), ('stumps60', ps)):
    for q in (0.5, 0.8, 0.9, 0.95):
        t = np.quantile(s, q); use = s > t
        A['select_%s_top%d%%' % (nm, round(100 * (1 - q)))] = float(np.where(use, e_n, e_f).mean())
# continuous soft weighting oracle bound: best fixed convex weight is not computable from norms; report per-flight effect proxy
A['per_flight_time_frac_net_better_by_0.1'] = dict(
    median=float(np.median([y[ep[ok] == E].mean() for E in set(ep[ok])])),
    p90=float(np.quantile([y[ep[ok] == E].mean() for E in set(ep[ok])], 0.9)))
out['A_lcJ_vs_HM40'] = A

# ---------------- B: stlong teacher4 vs v700b (deployed GSLV net) ----------------
B = {}
for pool in ('st2dev', 'st3'):
    T = np.load(SM + 'stlong/tables/teacher4_%s_pred.npz' % pool); V = np.load(SM + 'stlong/tables/v700b_%s_pred.npz' % pool)
    key = lambda y: [tuple(r) for r in np.round(y.astype(np.float64), 6)]
    vi = {}
    for i, k in enumerate(key(V['y'])): vi.setdefault(k, i)
    pairs = [(i, vi[k]) for i, k in enumerate(key(T['y'])) if k in vi]
    ti, vj = np.array(pairs).T
    yt = T['y'][ti]; et = T['mu'][ti] - yt; ev = V['mu'][vj] - yt
    nt, nv = np.linalg.norm(et, axis=1), np.linalg.norm(ev, axis=1)
    vt, vv = np.exp(T['lv'][ti]), np.exp(V['lv'][vj])
    fused = (T['mu'][ti] / vt + V['mu'][vj] / vv) / (1 / vt + 1 / vv); avg = (T['mu'][ti] + V['mu'][vj]) / 2
    sp = np.linalg.norm(yt, axis=1)
    b = dict(n_matched=int(len(ti)), n_teacher=int(len(T['y'])), teacher=float(nt.mean()), v700b=float(nv.mean()),
             invvar_fused=float(np.linalg.norm(fused - yt, axis=1).mean()), mean2=float(np.linalg.norm(avg - yt, axis=1).mean()),
             corr_err_components=float(np.corrcoef(et.ravel(), ev.ravel())[0, 1]),
             spearman_err_norm=float(np.corrcoef(rk(nt), rk(nv))[0, 1]),
             frac_teacher_better=float((nt < nv).mean()))
    for lo, hi in ((0, 1), (1, 2), (2, 99)):
        m = (sp >= lo) & (sp < hi); b['speed_%g_%g' % (lo, hi)] = dict(n=int(m.sum()), teacher=float(nt[m].mean()), v700b=float(nv[m].mean()))
    m = nv > 0.5; b['where_v700b_err_gt_0.5'] = dict(frac=float(m.mean()), teacher=float(nt[m].mean()), v700b=float(nv[m].mean()))
    B[pool] = b
out['B_teacher4_vs_v700b'] = B
json.dump(out, open(SM + 'ensemble/learned_sel.json', 'w'), indent=1)
print(json.dumps(out, indent=1))
