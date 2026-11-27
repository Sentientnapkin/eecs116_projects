"""r6 init solvers on preintegrated IMU + KLT tracks (all in the b0 = body-at-frame-0 frame).
Unknown x = [v0 (3), g (3), ba (3)] (subsets selectable); camera centre c_k(x) = F_k x + e_k,
F_k = [t I, .5 t^2 I, -Bp_k], e_k = alpha_k + R_k p_bc (+ fixed parts of x).
  MV : multi-view, landmark eliminated (Schur):  min_x,P  sum_k || Q_k (P - c_k(x)) ||^2 / (sig * |P - c_k|)^2   (Q = I - d d^T)
  PW : pairwise epipolar (r3-style):            sum_{i<j} ( nh_ij^T (c_j(x) - c_i(x)) )^2 / (sig^2 (z_i^2 + z_j^2))
  DIR: translation direction (r2-style):          sum_k || (I - t_k t_k^T)(c_k(x) - c_0(x)) ||^2 / (sig_k |c_k - c_0|)^2
IRLS (depth weights + Huber), linear in x for fixed weights; gravity magnitude optionally enforced by GN on the sphere."""
import numpy as np

SIG = 1.5 / 116.0  # ~1.5 px at 320x240 (fx ~116) in radians


def bearings(fl, tr, pi, N):
    """tracks restricted to frames <= N: list of (ks, D (m,3) unit bearings in b0)"""
    out = []
    RcK = fl.R_bc @ fl.Kinv
    for o in tr.values():
        o = o[o[:, 0] <= N]
        if len(o) < 2: continue
        ks = o[:, 0].astype(int)
        h = np.c_[o[:, 1:3], np.ones(len(o))] @ RcK.T  # body-frame rays
        d = np.einsum('nij,nj->ni', pi['R'][ks], h)
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        out.append((ks, d))
    return out


class Model:
    """which unknowns are free; fixed values for the rest"""
    def __init__(self, pi, free=('v0', 'g', 'ba'), fixed=None, p_bc=np.zeros(3)):
        self.free = list(free); fixed = fixed or {}
        self.fixed = {k: np.asarray(fixed.get(k, np.zeros(3)), float) for k in ('v0', 'g', 'ba')}
        t = pi['dt']; n = len(t)
        blk = {'v0': t[:, None, None] * np.eye(3), 'g': 0.5 * (t ** 2)[:, None, None] * np.eye(3), 'ba': -pi['Bp']}
        self.F = np.concatenate([blk[k] for k in self.free], axis=2) if self.free else np.zeros((n, 3, 0))
        e = pi['al'] + np.einsum('nij,j->ni', pi['R'], p_bc)
        for k in ('v0', 'g', 'ba'):
            if k not in self.free: e = e + np.einsum('nij,j->ni', blk[k], self.fixed[k])
        self.e = e; self.n = 3 * len(self.free); self.pi = pi

    def unpack(self, x):
        d = dict(self.fixed); i = 0
        for k in self.free: d[k] = x[i:i + 3]; i += 3
        return d

    def centres(self, x):
        return np.einsum('nij,j->ni', self.F, x) + self.e


def _tri(ks, D, C, w=None):
    """LS landmark from rays (C[ks], D) with weights w"""
    w = np.ones(len(ks)) if w is None else w
    Q = np.eye(3)[None] - D[:, :, None] * D[:, None, :]
    A = np.einsum('n,nij->ij', w, Q); b = np.einsum('n,nij,nj->i', w, Q, C[ks])
    ev, U = np.linalg.eigh(A)
    if ev[0] < 1e-6 * ev[2]: return None, ev
    return U @ ((U.T @ b) / ev), ev


def mv_normal(M, obs, x, it0, huber=2.5, sig=SIG):
    """reduced normal equations of the multi-view problem at weights from x (it0: first iteration -> unit metric weights)"""
    n = M.n; H = np.zeros((n, n)); b = np.zeros(n); C = M.centres(x); chi = 0.0; m = 0; nl = 0
    for ks, D in obs:
        P, ev = _tri(ks, D, C)
        if P is None: continue
        r = P[None] - C[ks]; dist = np.linalg.norm(r, axis=1); z = np.einsum('ni,ni->n', r, D)
        if it0:
            w = np.ones(len(ks))
        else:
            if np.any(z < 0.05) or np.any(dist > 300): continue
            w = 1.0 / (sig * dist) ** 2
            Q = np.eye(3)[None] - D[:, :, None] * D[:, None, :]
            P, ev = _tri(ks, D, C, w)
            if P is None: continue
            res = np.linalg.norm(np.einsum('nij,nj->ni', Q, P[None] - C[ks]), axis=1) * np.sqrt(w)
            hw = np.where(res > huber, huber / np.maximum(res, 1e-12), 1.0); w = w * hw
            chi += np.sum(np.minimum(res, huber) ** 2); m += 2 * len(ks)
        Q = np.eye(3)[None] - D[:, :, None] * D[:, None, :]
        A = w[:, None, None] * Q                                   # (m,3,3)
        Fk = M.F[ks]; ek = M.e[ks]
        Hpp = A.sum(0); Hpx = -np.einsum('nij,njk->ik', A, Fk); Hxx = np.einsum('nji,njk,nkl->il', Fk, A, Fk)
        bp = np.einsum('nij,nj->i', A, ek); bx = -np.einsum('nji,njk,nk->i', Fk, A, ek)
        ev, U = np.linalg.eigh(Hpp); keep = ev > 1e-6 * ev[-1]
        Hinv = (U[:, keep] / ev[keep]) @ U[:, keep].T
        # cost = [P;x]^T [[Hpp,Hpx],[Hxp,Hxx]] [P;x] - 2 [bp;bx]^T [P;x] + ...  -> eliminate P
        H += Hxx - Hpx.T @ Hinv @ Hpx; b += bx - Hpx.T @ Hinv @ bp; nl += 1
    return H, b, chi, m, nl


def pw_normal(M, obs, x, it0, huber=2.5, sig=SIG, maxpairs=None):
    n = M.n; H = np.zeros((n, n)); b = np.zeros(n); C = M.centres(x); chi = 0.0; m = 0; nl = 0
    for ks, D in obs:
        mm = len(ks)
        I, J = np.triu_indices(mm, 1)
        if not it0:
            P, ev = _tri(ks, D, C)
            if P is None: continue
            r = P[None] - C[ks]; z = np.linalg.norm(r, axis=1); zz = np.einsum('ni,ni->n', r, D)
            if np.any(zz < 0.05) or np.any(z > 300): continue
        nv = np.cross(D[I], D[J]); nn = np.linalg.norm(nv, axis=1); ok = nn > 1e-4
        I, J, nv, nn = I[ok], J[ok], nv[ok], nn[ok]
        if len(I) == 0: continue
        nh = nv / nn[:, None]
        a = np.einsum('pi,pij->pj', nh, M.F[ks[J]] - M.F[ks[I]]); c = -np.einsum('pi,pi->p', nh, M.e[ks[J]] - M.e[ks[I]])
        if it0:
            w = np.ones(len(I))
        else:
            w = 1.0 / (sig ** 2 * (z[I] ** 2 + z[J] ** 2))
            res = (a @ x - c) * np.sqrt(w)
            hw = np.where(np.abs(res) > huber, huber / np.maximum(np.abs(res), 1e-12), 1.0); w = w * hw
            chi += np.sum(np.minimum(np.abs(res), huber) ** 2); m += len(I)
        w = w * (2.0 / mm)  # all-pairs over-counting: a track of m obs contributes ~ (m-1) pair-equivalents
        H += (a * w[:, None]).T @ a; b += (a * w[:, None]).T @ c; nl += 1
    return H, b, chi, m, nl


def dir_normal(M, obs, x, it0, sig=SIG, N=None):
    """r2-style: per frame k, translation direction c_0 -> c_k from the tracks seen in 0 and k (smallest eigvec of sum n n^T,
    sign from positive depth), then (I - t t^T)(c_k - c_0) = 0."""
    n = M.n; H = np.zeros((n, n)); b = np.zeros(n); C = M.centres(x); nl = 0
    K = max(int(ks.max()) for ks, _ in obs) if N is None else N
    for k in range(1, K + 1):
        d0 = []; dk = []
        for ks, D in obs:
            if ks[0] == 0 and k in ks: d0.append(D[0]); dk.append(D[list(ks).index(k)])
        if len(d0) < 8: continue
        d0 = np.array(d0); dk = np.array(dk); nv = np.cross(d0, dk); nn = np.linalg.norm(nv, axis=1)
        okm = nn > 1e-4
        if okm.sum() < 8: continue
        nh = nv[okm] / nn[okm, None]
        S = nh.T @ nh; ev, U = np.linalg.eigh(S); t = U[:, 0]
        # sign: depth along d0 of the triangulated points must be positive for c_k - c_0 = s t, s>0
        z0 = np.einsum('ni,ni->n', np.cross(t[None], dk[okm]), np.cross(d0[okm], dk[okm])) / np.maximum(nn[okm] ** 2, 1e-12)
        if np.median(z0) < 0: t = -t
        sd = np.sqrt(max(ev[0], 1e-12) / max(ev[1], 1e-12)) + 0.02  # rough direction sd (rad)
        Pp = np.eye(3) - np.outer(t, t)
        A = Pp @ (M.F[k] - M.F[0]); c = -Pp @ (M.e[k] - M.e[0])
        base = max(np.linalg.norm(C[k] - C[0]), 0.05) if not it0 else 1.0
        w = 1.0 / (sd * base) ** 2
        H += w * A.T @ A; b += w * A.T @ c; nl += 1
    return H, b, 0.0, 0, nl


def solve(M, obs, kind='mv', iters=5, prior=None, gnorm=False, x0=None):
    """prior: (mean (n,), info (n,n)) on the free vector. gnorm: enforce |g| = 9.81 (GN on the sphere) when g is free."""
    fn = {'mv': mv_normal, 'pw': pw_normal, 'dir': dir_normal}[kind]
    x = np.zeros(M.n) if x0 is None else x0.copy(); info = None
    for it in range(iters):
        H, b, chi, m, nl = fn(M, obs, x, it == 0 and x0 is None)
        if it == 0 and x0 is None:  # unit-weight scale: normalise so the prior does not dominate the first pass
            s = np.trace(H) / max(M.n, 1); H = H / max(s, 1e-12); b = b / max(s, 1e-12)
        if prior is not None and (it > 0 or x0 is not None):
            H = H + prior[1]; b = b + prior[1] @ prior[0]
        elif prior is not None:
            H = H + 1e-6 * prior[1]; b = b + 1e-6 * prior[1] @ prior[0]
        try:
            x = np.linalg.solve(H + 1e-12 * np.eye(M.n), b)
        except np.linalg.LinAlgError:
            return None
        if gnorm and 'g' in M.free:
            x = _gsphere(M, H, b, x)
        info = (H, chi, m, nl)
    return x, info


def _gsphere(M, H, b, x):
    """min x^T H x - 2 b^T x s.t. |g| = 9.81 (g block of x): GN on g = 9.81 * normalize(g0 + T delta), other blocks closed form."""
    gi = 3 * M.free.index('g'); idx = np.r_[gi:gi + 3]; oth = np.setdiff1d(np.arange(M.n), idx)
    g = x[idx]; g = 9.81 * g / max(np.linalg.norm(g), 1e-9)
    def reduced(g):
        if len(oth):
            Hoo = H[np.ix_(oth, oth)]; y = np.linalg.solve(Hoo, b[oth] - H[np.ix_(oth, idx)] @ g)
        else: y = np.zeros(0)
        xx = np.zeros(M.n); xx[idx] = g; xx[oth] = y
        return xx, xx @ H @ xx - 2 * b @ xx
    xx, f = reduced(g)
    for _ in range(20):
        u = g / 9.81; a = np.cross(u, [1, 0, 0] if abs(u[0]) < .9 else [0, 1, 0]); a /= np.linalg.norm(a); c = np.cross(u, a)
        best = None
        for s in (0.05, 0.02, 0.005, 0.001):
            for e in (a, -a, c, -c, (a + c) / 1.414, -(a + c) / 1.414, (a - c) / 1.414, (c - a) / 1.414):
                g2 = 9.81 * (u + s * e) / np.linalg.norm(u + s * e); x2, f2 = reduced(g2)
                if f2 < f - 1e-12 and (best is None or f2 < best[1]): best = (g2, f2, x2)
            if best: break
        if not best: break
        g, f, xx = best
    return xx
