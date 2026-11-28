"""Fit the cheap vision guest's velocity model by trajectory least squares (unaligned ATE), score it.

    ~/.venv_gru/bin/python s3vis_fit.py            (TRAIN=s3vtr VAL=s3vva; NBR=s3nb)

v_cam,k = Wcam x_k                       (fit_cheap gabs2 IMU features, camera axes; optional: IMU=0 drops it)
        + (sum_j w_j phi_j,k) d_k        (speed linear in cues phi, times the vision direction d_k)
phi = [1, q/Q0, (q/Q0)^2, nv/16, [nv >= 4]]   q = flow magnitude (rad/frame), nv = valid points (vis3.features_for)
"""
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fit_cheap as fc  # noqa: E402

DT = fc.DT
Q0 = 0.02
LAM = float(os.environ.get("LAM", 10))
USE_IMU = os.environ.get("IMU", "1") == "1"
BASE = os.environ.get("BASE")          # an mlp_fit checkpoint: its velocity (times a fitted scale) replaces the linear IMU part
if BASE:
    import export_mlp as em
    BASE_M = em.load(os.path.expanduser(BASE))


EXCL = {x.strip() for x in open(os.path.expanduser(os.environ["EXCLUDE"]))} if os.environ.get("EXCLUDE") else set()


def load(name):
    out = []
    for p in sorted(glob.glob(os.path.expanduser(f"~/data/viscache/{name}/*.npz"))):
        fid = os.path.basename(p)[:-4]
        if fid in EXCL and name not in ("twin", "s3nb"):
            continue
        c = os.path.expanduser(f"~/data/imucache/{name}/{fid}.npz")
        if not os.path.exists(c):
            continue
        z = np.load(c); f = {k: z[k] for k in z.files}; f["name"] = fid
        f["vis"] = np.load(p)["vis"]
        out.append(f)
    return out


def phi(V):
    q = V[:, 3] / Q0; nv = V[:, 4]
    return np.stack([np.ones(len(V)), q, q * q, nv / 16, (nv >= 4).astype(float)], 1)


def design(f):
    R, X = fc.prep(f)
    V = f["vis"][:len(R)]
    P = phi(V)
    if BASE:
        m = BASE_M
        vb = X @ m["Wv"].T + em.act(X[:, 1:] @ m["W1"].T + m["B1"], m["act"]) @ m["W2"].T
        cols = [np.cumsum(DT * np.einsum("kij,kj->ki", R, vb), 0)[:, :, None]]   # one column: the MLP's scale
    else:
        cols = [fc.design(R, X)] if USE_IMU else []
    if not os.environ.get("VISOFF"):
        dv = np.einsum("kij,kj->ki", R, V[:, :3])                     # direction in camera-0 axes
        cols.append(np.cumsum(DT * dv[:, :, None] * P[:, None, :], 0))  # (n, 3, J)
    return np.concatenate(cols, 2)


def fit(S):
    Zs = [design(f) for f in S]; m = Zs[0].shape[2]
    A = np.zeros((m, m)); b = np.zeros(m)
    for f, Z in zip(S, Zs):
        Z2 = Z.reshape(-1, m); y = f["cam"][1:len(Z) + 1].reshape(-1)
        wt = 1 / max(np.sqrt((f["cam"] ** 2).sum(1).mean()), 1)
        A += wt * Z2.T @ Z2; b += wt * Z2.T @ y
    return np.linalg.solve(A + LAM * np.eye(m), b)


def score(S, w):
    out = []
    for f in S:
        Z = design(f); p = np.vstack([np.zeros(3), Z @ w])
        out.append(np.sqrt(((p - f["cam"][:len(p)]) ** 2).sum(1).mean()))
    return np.array(out)


def main():
    tr, va, nb = load(os.environ.get("TRAIN", "s3vtr")), load(os.environ.get("VAL", "s3vva")), load(os.environ.get("NBR", "s3nb"))
    zero = lambda S: np.array([np.sqrt((f["cam"] ** 2).sum(1).mean()) for f in S])
    print(f"train {len(tr)} val {len(va)} nbr {len(nb)} | IMU features {USE_IMU}")
    w = fit(tr)
    v, n = score(va, w), score(nb, w)
    print(f"zero   val {zero(va).mean():.3f}  nbr {zero(nb).mean():.3f}")
    print(f"model  val {v.mean():.3f}  nbr {n.mean():.3f}   last weights {np.round(w[-5:], 3).tolist()}")
    if os.environ.get("NBR") == "twin":   # per-episode twin120 means (the friend's server-twin sets)
        S3 = os.path.join(HERE, "..", "stage3", "twin")
        t120 = [l.split(chr(9))[:2] for l in open(os.path.join(S3, "twin120.txt")).read().splitlines() if l.strip()]
        by = dict(zip([f["name"] for f in nb], n)); bz = dict(zip([f["name"] for f in nb], zero(nb)))
        ep = lambda d: np.mean([np.mean([d[x] for i, x in t120 if int(i) == e and x in d]) for e in range(1, 25)])
        print(f"twin120 per-episode: zero {ep(bz):.3f}  model {ep(by):.3f}")
    np.save(os.path.expanduser("~/data/s3vis_w.npy"), w)
    if USE_IMU:
        export(w, f"train {len(tr)}: val {v.mean():.3f} nbr {n.mean():.3f}")


def export(w, note):
    """vis_weights.h for cheap_vis.c: Wv[3][10] (fit_cheap.design order: w[m*10+n]) and WS[5]."""
    fmt = lambda r: "{" + ", ".join(f"{x:.17g}" for x in r) + "}"
    lines = [f"/* s3vis_fit.py ({note}), GROWS={fc.GROWS} */",
             f"#define GROW_A {fc.GROWS[0]}", f"#define GROW_B {fc.GROWS[1]}", "#define NF 10",
             "static const double Wv[3][NF] = {" + ", ".join(fmt(w[m * 10:(m + 1) * 10]) for m in range(3)) + "};",
             f"static const double WS[5] = {fmt(w[30:35])};"]
    with open(os.path.join(HERE, "vis_weights.h"), "w") as fh:
        fh.write(chr(10).join(lines) + chr(10))


if __name__ == "__main__":
    main()
