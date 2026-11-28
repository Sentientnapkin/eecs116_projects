"""Stage-3 experiment: heading-independent "physics" velocity features vs the camera-frame gyro features, fitted with the
same trajectory least squares (unaligned ATE), scored on val / test / the hidden-episode neighbours.

    ~/.venv_gru/bin/python s3phys.py

Physics features, per frame k (all in camera-0 axes, from the same attitude R_k the guest integrates):
  w_k   = R_k f_k                    specific force (mean of AROWS accel rows, camera axes) rotated into camera 0
  g_k   = EMA_tg(w)                  gravity + slow biases: the drone's mean acceleration over tg seconds is ~0
  a_k   = w_k - g_k                  acceleration estimate
  u_t,k = leaky integral of a with time constant t  (t in TAUS)  -> recent velocity change
Velocity model:  v_k = R_k (Wcam x_k) + sum_t alpha_t u_t,k   (alpha: one scalar per tau, so it does not care about heading)
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("AROWS", "0123456789")
import fit_cheap as fc  # noqa: E402

DT = fc.DT
TAUS = [float(x) for x in os.environ.get("TAUS", "1,3,10").split(",")]
TG = float(os.environ.get("TG", "15"))
LAM = float(os.environ.get("LAM", "10"))


def phys(f, R):
    Rbc = f["Tbc"][:3, :3]
    a = f["imu"][:, fc.AROWS, 1:4].mean(1) @ Rbc
    w = np.einsum("kij,kj->ki", R, a)
    g = w[0].copy(); al = DT / TG
    U = np.zeros((len(w), len(TAUS), 3)); u = np.zeros((len(TAUS), 3))
    for k in range(len(w)):
        g += al * (w[k] - g)
        acc = w[k] - g
        for j, t in enumerate(TAUS):
            u[j] = u[j] * (1 - DT / t) + DT * acc
        U[k] = u
    return U


TB = [float(x) for x in os.environ.get("TB", "1,3,10,30").split(",")]


def time_basis(n):
    """(n, 3, 3*len(TB)+3): start-frame velocity basis per axis, exp(-t/tau) and a constant -> learned mean drift."""
    t = np.arange(n) * DT
    phi = np.stack([np.exp(-t / tau) for tau in TB] + [np.ones(n)], 1)          # (n, J)
    B = np.zeros((n, 3, 3 * phi.shape[1]))
    for ax in range(3):
        B[:, ax, ax * phi.shape[1]:(ax + 1) * phi.shape[1]] = phi
    return np.cumsum(DT * B, 0)


def design(f, use_cam=True, use_phys=True, use_tb=False):
    R, X = fc.prep(f)
    cols = []
    if use_tb:
        cols.append(time_basis(len(X)))
    if use_cam:
        cols.append(fc.design(R, X))                              # (n, 3, 30)
    if use_phys:
        U = phys(f, R)                                            # (n, T, 3)
        cols.append(np.cumsum(DT * np.transpose(U, (0, 2, 1)), 0))  # (n, 3, T): scalar alpha per tau
    return np.concatenate(cols, 2)


def fit(S, **kw):
    Zs = [design(f, **kw) for f in S]
    m = Zs[0].shape[2]; A = np.zeros((m, m)); b = np.zeros(m)
    for f, Z in zip(S, Zs):
        Z2 = Z.reshape(-1, m); y = f["cam"][1:len(Z) + 1].reshape(-1)
        wt = 1 / max(np.sqrt((f["cam"] ** 2).sum(1).mean()), 1)
        A += wt * Z2.T @ Z2; b += wt * Z2.T @ y
    return np.linalg.solve(A + LAM * np.eye(m), b)


def score(S, w, **kw):
    out = []
    for f in S:
        Z = design(f, **kw)
        p = np.vstack([np.zeros(3), Z @ w])
        out.append(np.sqrt(((p - f["cam"][:len(p)]) ** 2).sum(1).mean()))
    return np.array(out)


def main():
    ntr = int(os.environ.get("NTR", "1200"))
    ex = {x.strip() for x in open(os.path.join(HERE, "..", "stage3", "ids_s3nb.txt"))}
    va, te, nb = (fc.load(f"~/data/imucache/{n}") for n in ("s3va", "s3te", "s3nb"))
    if os.environ.get("QUICK"):   # before s3tr is downloaded: train on part of val, validate on the rest
        rng = np.random.default_rng(0); idx = rng.permutation(len(va))
        tr, va = [va[i] for i in idx[:400]], [va[i] for i in idx[400:]]
    else:
        tr = [f for f in fc.load("~/data/imucache/s3tr") if f["name"] not in ex][:ntr]
    te = te or va
    zero = lambda S: np.array([np.sqrt((f["cam"] ** 2).sum(1).mean()) for f in S])
    print(f"train {len(tr)}  val {len(va)}  test {len(te)}  nbr {len(nb)} | TAUS {TAUS} TG {TG} AROWS {fc.AROWS}")
    print(f"{'model':12s} {'val':>7s} {'test':>7s} {'nbr':>7s}  worse-than-zero(val)")
    zv = zero(va)
    print(f"{'zero':12s} {zv.mean():7.3f} {zero(te).mean():7.3f} {zero(nb).mean():7.3f}")
    for name, kw in (("cam", dict(use_phys=False)), ("cam+phys", {}), ("tb", dict(use_cam=False, use_phys=False, use_tb=True)),
                     ("cam+tb", dict(use_phys=False, use_tb=True))):
        w = fit(tr, **kw)
        v, t, n = score(va, w, **kw), score(te, w, **kw), score(nb, w, **kw)
        print(f"{name:12s} {v.mean():7.3f} {t.mean():7.3f} {n.mean():7.3f}  {np.mean(v > zv):.1%}"
              + (f"   alpha {np.round(w[-len(TAUS):], 3).tolist()}" if name == "cam+phys" else ""))


if __name__ == "__main__":
    main()
