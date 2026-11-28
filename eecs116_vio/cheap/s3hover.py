"""Idea 3 check: gyro-bias removal after a quiet first second, applied to an existing MLP checkpoint (no retraining).

    ~/.venv_gru/bin/python s3hover.py CKPT.pt [THR]
prep_hb = fit_cheap.prep, except: if the RMS of the first N0 frame-mean gyro vectors (camera axes) is below THR rad/s,
their mean is taken as the gyro bias and subtracted from frame N0 on (causal: the guest knows it after N0 frames).
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import export_mlp as em  # noqa: E402
import fit_cheap as fc  # noqa: E402

DT = fc.DT
N0 = 20


def prep_hb(f, thr):
    Rbc = f["Tbc"][:3, :3]
    g = f["imu"][:, fc.GROWS, 4:7].mean(1) @ Rbc
    hover = np.sqrt((g[:N0] ** 2).sum(1).mean()) < thr
    if hover:
        g = g.copy(); g[N0:] -= g[:N0].mean(0)
    q = np.array([1.0, 0, 0, 0]); Rs = []
    for k in range(len(g)):
        h = 0.5 * DT * g[k]
        q = fc.quat_mul(q, np.array([1.0 - 0.5 * (h @ h), *h])); q /= np.linalg.norm(q); Rs.append(fc.quat_R(q))
    cols = [np.ones(len(g))]
    for kind, tau in fc.SPEC:
        e = np.zeros_like(g); s = np.zeros(3); al = DT / tau
        for k in range(len(g)):
            s = s + al * (g[k] - s); e[k] = s
        cols += [np.abs(e[:, i]) if kind.endswith("abs") else e[:, i] for i in range(3)]
    return np.array(Rs), np.stack(cols, 1), hover


def ate(f, m, R, X):
    v = X @ m["Wv"].T + em.act(X[:, 1:] @ m["W1"].T + m["B1"], m["act"]) @ m["W2"].T
    p = np.vstack([np.zeros(3), np.cumsum(DT * np.einsum("kij,kj->ki", R, v), 0)])
    return float(np.sqrt(((p - f["cam"]) ** 2).sum(1).mean()))


def main():
    m = em.load(sys.argv[1]); thr = float(sys.argv[2]) if len(sys.argv) > 2 else 0.1
    for name in ("s3va", "s3nb"):
        S = fc.load(f"~/data/imucache/{name}")
        base, hb, flags = [], [], []
        for f in S:
            R, X = fc.prep(f); base.append(ate(f, m, R, X))
            R2, X2, h = prep_hb(f, thr); hb.append(ate(f, m, R2, X2)); flags.append(h)
        base, hb, flags = map(np.array, (base, hb, flags))
        print(f"{name}: {flags.mean():.0%} flagged quiet | all: {base.mean():.3f} -> {hb.mean():.3f} | "
              f"flagged only: {base[flags].mean():.3f} -> {hb[flags].mean():.3f}")


if __name__ == "__main__":
    main()
