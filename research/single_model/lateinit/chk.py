"""Check LI preintegration/model against truth for a dumped flight.  python chk.py RUN POOL EP"""
import sys, glob
import numpy as np
sys.path.insert(0, '.')
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
run, pool, ep = sys.argv[1:4]
L = 'research/single_model/lateinit'
f = glob.glob(f'research/results/single_model/{run}/eval_{pool}/*/{ep}/report/logs/*/stderr.txt')[0]
F, O = {}, []
for l in open(f):
    x = l.split()
    if x[0] == 'LF': F[int(x[1])] = np.array(list(map(float, x[2:])))
    elif x[0] == 'LO': O.append((int(x[1]), int(x[2]), float(x[3]), float(x[4])))
    elif x[0] == 'LX': X = np.array(list(map(float, x[1:])))
Rbc = X[:9].reshape(3, 3); pbc = X[9:12]
e = read_episode(f'{L}/pool_{pool}/{ep}.zip', frames='none')
gt = np.asarray(e.ground_truth); t = np.asarray(e.frame_times)
print('gt cols', gt.shape)
from viobench.tools.geometry import interpolate_poses
Tb = poses_to_matrices(interpolate_poses(gt[:, 0], gt[:, 1:8], t))
Tbc = np.asarray(e.T_body_camera)
print('T_body_camera\n', Tbc.round(4), '\nRbc\n', Rbc.round(4), pbc.round(4))
R0 = Tb[0, :3, :3]; p0 = Tb[0, :3, 3]
g0 = R0.T @ np.array([0, 0, -9.81])
dt = 1e-3
def vel(k):
    Ta = poses_to_matrices(interpolate_poses(gt[:, 0], gt[:, 1:8], np.array([t[k] - dt, t[k] + dt])))
    return (Ta[1, :3, 3] - Ta[0, :3, 3]) / (2 * dt)
v0 = R0.T @ vel(0)
print('truth v0 body0', v0.round(3), 'g0', g0.round(3))
for k in sorted(F)[:40:4]:
    a = F[k]; tk = a[0]; Rk = a[1:10].reshape(3, 3); al = a[10:13]; be = a[13:16]
    pt = R0.T @ (Tb[k, :3, 3] - p0); Rt = R0.T @ Tb[k, :3, :3]
    pm = v0 * tk + 0.5 * g0 * tk * tk + al
    vm = v0 + g0 * tk + be; vt = R0.T @ vel(k)
    ang = np.degrees(np.linalg.norm(np.array([1, 1, 1]) * 0) + np.arccos(np.clip((np.trace(Rk.T @ Rt) - 1) / 2, -1, 1)))
    print(f'k {k} t {tk:.3f} (frame t {t[k]-t[0]:.3f}) pos truth {pt.round(3)} model {pm.round(3)} | vel truth {vt.round(3)} model {vm.round(3)} | rot err {ang:.2f} deg')

# ---- python LS (same model) ----
N = max(k for k in F if F[k][0] <= 1.5 + 1e-6)
obs = {}
for k, g, x, y in O:
    if k <= N: obs.setdefault(g, []).append((k, x, y))
def bearing(k, x, y):
    r = np.array([x, y, 1.0]); r /= np.linalg.norm(r); return F[k][1:10].reshape(3, 3) @ (Rbc @ r)
def skew(v): return np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
def build(wdepth=None, extra_ba=False):
    rows_A, rows_b, cols = [], [], []
    feats = [g for g, o in obs.items() if len(o) >= 6]
    nf = len(feats); nx = 9 if extra_ba else 6
    A = []; B = []
    for j, g in enumerate(feats):
        o = obs[g]; k = o[0][0]; dk = bearing(*o[0]); ak = F[k][10:13]; tk = F[k][0]; pk = F[k][1:10].reshape(3, 3) @ pbc
        w = 1.0 if wdepth is None else wdepth.get(g, 1.0)
        for (i, x, y) in o[1:]:
            d = bearing(i, x, y); K = skew(d); ti = F[i][0]; ai = F[i][10:13]; pi = F[i][1:10].reshape(3, 3) @ pbc
            row = np.zeros((3, nx + nf))
            row[:, 0:3] = K * (tk - ti); row[:, 3:6] = K * 0.5 * (tk * tk - ti * ti)
            row[:, nx + j] = K @ dk
            if extra_ba:  # alpha depends on ba linearly ~ -0.5 R t^2 ba (approx with body-0 axes)
                row[:, 6:9] = -K * 0.5 * (tk * tk - ti * ti)
            A.append(w * row); B.append(w * (-K @ (ak - ai + pk - pi)))
    return np.vstack(A), np.concatenate(B), feats
A, b, feats = build()
xt = np.concatenate([v0, g0])
def cost_at(x6):
    Ax = A[:, :6] @ x6; Al = A[:, 6:]; lam, *_ = np.linalg.lstsq(Al, b - Ax, rcond=None)
    r = Ax + Al @ lam - b; return float(r @ r), lam
sol, *_ = np.linalg.lstsq(A, b, rcond=None)
print('features', len(feats), 'rows', A.shape)
print('free LS v0', sol[:3].round(3), 'g0', sol[3:6].round(3), '|g|', np.linalg.norm(sol[3:6]).round(3), 'cost', cost_at(sol[:6])[0])
c, lam = cost_at(xt); print('truth cost', c, 'depths', np.round(lam[:10], 2))
sv = np.linalg.svd(A, compute_uv=False); print('sing values tail', sv[-8:])
def tilt(g): return np.degrees(np.arccos(np.clip(g @ g0 / np.linalg.norm(g) / 9.81, -1, 1)))
def report(nm, x):
    print(f'{nm:24s} v0 err {np.linalg.norm(x[:3]-v0):.3f} tilt {tilt(x[3:6]):.2f} deg |g| {np.linalg.norm(x[3:6]):.2f}', ('ba ' + str(x[6:9].round(3))) if len(x) > 6 else '')
report('free', sol[:6])
for eb in (False, True):
    A, b, feats = build(extra_ba=eb); nx = 9 if eb else 6
    s1, *_ = np.linalg.lstsq(A, b, rcond=None)
    lam = s1[nx:]; wd = {g: 1 / max(l, 0.3) for g, l in zip(feats, lam)}
    good = {g for g, l in zip(feats, lam) if l > 0.2}
    obs_b = dict(obs); obs = {g: o for g, o in obs_b.items() if g in good or len(o) < 6}
    A2, b2, f2 = build(wd, extra_ba=eb); s2, *_ = np.linalg.lstsq(A2, b2, rcond=None)
    obs = obs_b
    report(f'ba={eb} unweighted', s1); report(f'ba={eb} depth-weighted', s2)
