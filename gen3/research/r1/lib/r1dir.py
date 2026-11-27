"""r1 translation-direction estimators from bearing correspondences + known relative rotation.

Conventions
  b_i, b_j : (N,3) unit bearings in camera i / camera j.
  R        : R_ji, maps camera-i coordinates to camera-j coordinates (X_j = R X_i + t).
  t        : t_ji (unit). The camera MOTION direction expressed in camera j is d = -t.
  m        : m = (R b_i) x b_j ; epipolar constraint m . t = 0  (the r1 brief's n).
  residual : angle of b_j from the epipolar plane span(t, R b_i):  r = (t . m) / |t x R b_i|  [rad]
All estimators are sign-free; the sign is fixed afterwards by cheirality (positive depths).
"""
import numpy as np


def unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def bearings(uv, fx, fy, cx, cy):
    x = np.stack([(uv[:, 0] - cx) / fx, (uv[:, 1] - cy) / fy, np.ones(len(uv))], 1)
    return unit(x)


def residuals(t, Rbi, m):
    den = np.linalg.norm(np.cross(t[None, :], Rbi), axis=1) + 1e-12
    return (m @ t) / den, den


def min_eig(M):
    w, V = np.linalg.eigh(M)
    return V[:, 0], w


def est_eig(Rbi, bj, m, normalize=False):
    mm = unit(m) if normalize else m
    t, w = min_eig(mm.T @ mm)
    return t


def est_irls(Rbi, bj, m, t0, sig, iters=6, mask=None):
    """weighted eigen with weights 1/|t x Rb_i|^2 * Cauchy(r/sig): minimises the true angular residual robustly"""
    t = t0.copy(); keep = np.ones(len(m), bool) if mask is None else mask
    for _ in range(iters):
        r, den = residuals(t, Rbi, m)
        w = keep / (den ** 2) / (1.0 + (r / sig) ** 2)
        tn, _ = min_eig((m * w[:, None]).T @ m)
        if tn @ t < 0: tn = -tn
        if np.linalg.norm(tn - t) < 1e-7: t = tn; break
        t = tn
    return t


def est_ransac(Rbi, bj, m, thr, iters=64, rng=None, min_par=None):
    """2-point RANSAC: t = m_a x m_b; inliers |r| < thr (rad). Samples drawn from pairs with parallax."""
    rng = np.random.default_rng(0) if rng is None else rng
    n = len(m)
    if n < 2: return None, np.zeros(n, bool)
    par = np.linalg.norm(m, axis=1)
    pool = np.flatnonzero(par > (min_par if min_par is not None else 0))
    if len(pool) < 2: pool = np.arange(n)
    a = rng.choice(pool, iters); b = rng.choice(pool, iters)
    T = np.cross(m[a], m[b]); nt = np.linalg.norm(T, axis=1); ok = nt > 1e-12
    if not ok.any(): return None, np.zeros(n, bool)
    T = T[ok] / nt[ok, None]
    # residual matrix (H, N)
    num = T @ m.T
    den = np.linalg.norm(np.cross(T[:, None, :], Rbi[None, :, :]), axis=2) + 1e-12
    inl = np.abs(num / den) < thr
    # score: inlier count weighted by parallax (low-parallax points agree with everything)
    sc = (inl * np.minimum(par / (thr + 1e-12), 4.0)[None, :]).sum(1)
    k = int(np.argmax(sc))
    return T[k], inl[k]


def cheirality(t, Rbi, bj):
    """depths for t = t_ji: X_j = lam_j b_j = lam_i R b_i + t. returns (lam_i, lam_j)"""
    m = np.cross(Rbi, bj)
    mm = (m * m).sum(1) + 1e-15
    lam_i = -(np.cross(t[None, :], bj) * m).sum(1) / mm
    lam_j = -(np.cross(t[None, :], Rbi) * m).sum(1) / mm
    return lam_i, lam_j


def sign_fix(t, Rbi, bj, w=None):
    li, lj = cheirality(t, Rbi, bj)
    par = np.linalg.norm(np.cross(Rbi, bj), axis=1)
    w = par if w is None else w * par
    vote = (w * (np.sign(li) + np.sign(lj))).sum() / (2 * w.sum() + 1e-15)  # +1: all positive
    return (t if vote >= 0 else -t), abs(vote)


def info_sigma(t, Rbi, m, sig_px, f, w=None):
    """predicted 1-sigma angular error (rad) of t from the Fisher information of the angular residuals"""
    r, den = residuals(t, Rbi, m)
    s = sig_px / f
    w = np.ones(len(m)) if w is None else w
    J = m / den[:, None]  # d r / d t (ignoring den's dependence, exact at r=0 up to scale)
    I = (J * (w / s ** 2)[:, None]).T @ J
    # tangent basis
    a = np.array([1.0, 0, 0]) if abs(t[0]) < 0.9 else np.array([0, 1.0, 0])
    e1 = unit(np.cross(t, a)); e2 = np.cross(t, e1); E = np.stack([e1, e2], 1)
    It = E.T @ I @ E
    try:
        C = np.linalg.inv(It + 1e-12 * np.eye(2))
        return float(np.sqrt(max(np.trace(C), 0)))
    except np.linalg.LinAlgError:
        return float('inf')


def so3_exp(w):
    th = np.linalg.norm(w)
    K = np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]])
    if th < 1e-9: return np.eye(3) + K
    return np.eye(3) + np.sin(th) / th * K + (1 - np.cos(th)) / th ** 2 * K @ K


def est_joint_rot(bi, bj, R, t0, sig, rot_sd, iters=5, mask=None):
    """Gauss-Newton on (t on S^2, dtheta) with R' = Exp(dtheta) R, prior dtheta ~ N(0, rot_sd^2); robust Cauchy weights.
    Returns (t, R')."""
    t = t0.copy(); dth = np.zeros(3); keep = np.ones(len(bi), bool) if mask is None else mask
    for _ in range(iters):
        Rc = so3_exp(dth) @ R; Rbi = bi @ Rc.T; m = np.cross(Rbi, bj)
        r, den = residuals(t, Rbi, m)
        w = keep / (1.0 + (r / sig) ** 2)
        a = np.array([1.0, 0, 0]) if abs(t[0]) < 0.9 else np.array([0, 1.0, 0])
        e1 = unit(np.cross(t, a)); e2 = np.cross(t, e1)
        # numeric jacobian (5 params)
        J = np.zeros((len(bi), 5)); h = 1e-6
        for k, (dt_, dr) in enumerate([(e1, None), (e2, None), (None, 0), (None, 1), (None, 2)]):
            if dt_ is not None:
                tt = unit(t + h * dt_); rr, _ = residuals(tt, Rbi, m)
            else:
                d = np.zeros(3); d[dr] = h; R2 = so3_exp(dth + d) @ R; Rb2 = bi @ R2.T
                rr, _ = residuals(t, Rb2, np.cross(Rb2, bj))
            J[:, k] = (rr - r) / h
        A = (J * w[:, None]).T @ J; g = (J * w[:, None]).T @ r
        A[2:, 2:] += np.eye(3) * (sig ** 2) / rot_sd ** 2 * 1.0
        g[2:] += dth * (sig ** 2) / rot_sd ** 2
        try:
            dx = -np.linalg.solve(A + 1e-12 * np.eye(5), g)
        except np.linalg.LinAlgError:
            break
        t = unit(t + dx[0] * e1 + dx[1] * e2); dth = dth + dx[2:]
        if np.linalg.norm(dx) < 1e-8: break
    return t, so3_exp(dth) @ R


def estimate(bi, bj, R, f, method, sig_px=1.0, thr_px=1.5, rot_sd=None, rng=None):
    """Return dict(d=motion direction in cam j (unit), conf metrics) or None. method in
    eig | eign | irls | ransac | ransac_irls | joint"""
    n = len(bi)
    if n < 5: return None
    Rbi = bi @ R.T; m = np.cross(Rbi, bj)
    sig = sig_px / f; thr = thr_px / f
    inl = np.ones(n, bool)
    if method == 'eig':
        t = est_eig(Rbi, bj, m)
    elif method == 'eign':
        t = est_eig(Rbi, bj, m, normalize=True)
    elif method == 'irls':
        t = est_irls(Rbi, bj, m, est_eig(Rbi, bj, m), sig)
    elif method in ('ransac', 'ransac_irls', 'joint'):
        t, inl = est_ransac(Rbi, bj, m, thr, rng=rng)
        if t is None: return None
        if method != 'ransac':
            t = est_irls(Rbi, bj, m, t, sig, mask=None)
        if method == 'joint':
            t, R = est_joint_rot(bi, bj, R, t, sig, rot_sd if rot_sd else 2e-3)
            Rbi = bi @ R.T; m = np.cross(Rbi, bj)
        r, _ = residuals(t, Rbi, m); inl = np.abs(r) < thr
    else:
        raise ValueError(method)
    r, den = residuals(t, Rbi, m)
    inl2 = np.abs(r) < thr
    t, vote = sign_fix(t, Rbi[inl2] if inl2.sum() >= 3 else Rbi, bj[inl2] if inl2.sum() >= 3 else bj)
    par = np.linalg.norm(m, axis=1)
    w = 1.0 / (1.0 + (r / sig) ** 2)
    M = (m / den[:, None] * w[:, None]).T @ (m / den[:, None])
    ev = np.linalg.eigvalsh(M)
    return dict(d=-t, vote=vote, ninl=int(inl2.sum()), n=n, par_med=float(np.median(par)), par_p90=float(np.quantile(par, 0.9)),
                rrms=float(np.sqrt(np.mean(np.minimum(r[inl2] ** 2, thr ** 2)))) * f if inl2.any() else 99.0,
                evr=float(ev[0] / (ev[1] + 1e-15)), ev1=float(ev[1]),
                sig_pred=info_sigma(t, Rbi, m, sig_px, f, w=w * inl2))
