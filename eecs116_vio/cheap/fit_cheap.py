"""Fit the cheap IMU-only guest (cheap.c): gyro attitude + linear camera-frame velocity from gyro/accel EMAs.

Weights are fitted to minimise UNALIGNED position error directly: position is linear in the weights once the
attitude (gyro integration, no vision) is fixed, so the whole-trajectory least squares is a ridge regression.

  python fit_cheap.py TRAIN_CACHE_DIR [TEST_CACHE_DIR ...]   -> weights.h (+ prints ATE per set)

Cache dirs hold <episode>.npz from cache_imu.py: imu (F-1,10,7) body axes, cam (F,3) truth in camera-0 axes, Tbc.
Must match cheap.c exactly: per-frame mean of the IMU rows GROWS (default rows 2 and 7 of 10), camera axes,
EMA alpha = 0.05/tau, updated before use. Defaults (SPEC=gabs2, GROWS=27) are the submitted configuration; cheap.c
hard-codes that feature layout, so another SPEC needs a matching cheap.c.
"""
import glob, os, sys
import numpy as np

DT = 0.05
SPECS = {"ga": [("g", 0.25), ("g", 1.0), ("gabs", 1.0), ("a", 0.25), ("a", 1.0)],
         "ga1": [("g", 0.25), ("g", 1.0), ("gabs", 1.0), ("a", 1.0)],
         "gabs": [("g", 1.0), ("gabs", 1.0)],
         "gabs2": [("g", 0.25), ("g", 1.0), ("gabs", 1.0)]}
SPEC = SPECS[os.environ.get("SPEC", "gabs2")]  # order = feature order in cheap.c
GROWS = [int(c) for c in os.environ.get("GROWS", "27")]  # which of the 10 IMU rows feed the gyro mean
AROWS = [int(c) for c in os.environ.get("AROWS", "0")]  # ... and the accel mean
LAM = 10.0


def load(d):
    out = []
    for p in sorted(glob.glob(os.path.join(os.path.expanduser(d), "*.npz"))):
        if ".tmp." in p:  # remote_cache.py writes <id>.npz.tmp.npz while a download is in progress
            continue
        z = np.load(p)
        out.append({k: z[k] for k in z.files} | {"name": os.path.basename(p)[:-4]})
    return out


def quat_mul(a, b):
    w1, x1, y1, z1 = a; w2, x2, y2, z2 = b
    return np.array([w1*w2-x1*x2-y1*y2-z1*z2, w1*x2+x1*w2+y1*z2-z1*y2, w1*y2-x1*z2+y1*w2+z1*x2, w1*z2+x1*y2-y1*x2+z1*w2])


def quat_R(q):
    w, x, y, z = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y)], [2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x)],
                     [2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)]])


def prep(f):
    """Camera-axis frame means, attitude (same small-angle quaternion step as cheap.c), features."""
    Rbc = f["Tbc"][:3, :3]
    g = f["imu"][:, GROWS, 4:7].mean(1) @ Rbc
    a = f["imu"][:, AROWS, 1:4].mean(1) @ Rbc
    q = np.array([1.0, 0, 0, 0]); Rs = []
    for k in range(len(g)):
        h = 0.5 * DT * g[k]
        dq = np.array([1.0 - 0.5 * (h @ h), *h])
        q = quat_mul(q, dq); q /= np.linalg.norm(q); Rs.append(quat_R(q))
    cols = [np.ones(len(g))]
    for kind, tau in SPEC:
        src = g if kind[0] == "g" else a
        e = np.zeros_like(src); s = np.zeros(3); al = DT / tau
        for k in range(len(src)):
            s = s + al * (src[k] - s); e[k] = s
        cols += [np.abs(e[:, i]) if kind.endswith("abs") else e[:, i] for i in range(3)]
    return np.array(Rs), np.stack(cols, 1)


def design(R, X):
    """p_{k+1}[d] = Z[k, d, :] @ w with w[m*nf+n] the weight of feature n for camera axis m."""
    M = np.einsum("kdm,kn->kdmn", R, X).reshape(len(X), 3, -1) * DT
    return np.cumsum(M, 0)


def ate(f, R, X, w):
    p = np.vstack([np.zeros(3), design(R, X) @ w])
    return float(np.sqrt(((p - f["cam"]) ** 2).sum(1).mean()))


def main():
    sets = [(d, load(d)) for d in sys.argv[1:]]
    train = sets[0][1]
    P = {id(f): prep(f) for _, S in sets for f in S}
    nw = 3 * (1 + 3 * len(SPEC)); A = np.zeros((nw, nw)); b = np.zeros(nw)
    for f in train:
        R, X = P[id(f)]; Z = design(R, X).reshape(-1, nw); y = f["cam"][1:].reshape(-1)
        wt = 1.0 / max(np.sqrt((f["cam"] ** 2).sum(1).mean()), 1.0)  # flights count about equally, not by extent
        A += wt * Z.T @ Z; b += wt * Z.T @ y
    w = np.linalg.solve(A + LAM * np.eye(nw), b)
    for d, S in sets:
        r = np.array([ate(f, *P[id(f)], w) for f in S]); z = np.array([np.sqrt((f["cam"] ** 2).sum(1).mean()) for f in S])
        print(f"{d}: n={len(S)} ATE mean {r.mean():.3f} median {np.median(r):.3f} | zero {z.mean():.3f} | wins {np.mean(r < z):.0%}")
    nf = 1 + 3 * len(SPEC)
    if os.environ.get("NOWRITE"): return
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights.h"), "w") as fh:
        fh.write(f"/* fit_cheap.py: trained on {len(train)} flights ({sets[0][0]}), SPEC={SPEC}, GROWS={GROWS}, lambda={LAM} */\n")
        assert len(GROWS) == 2 and SPEC == SPECS["gabs2"], "cheap.c hard-codes 2 gyro rows and the gabs2 feature layout"
        fh.write(f"#define GROW_A {GROWS[0]}\n#define GROW_B {GROWS[1]}\n")
        fh.write(f"#define NF {nf}\nstatic const double Wv[3][NF] = {{\n")
        for m in range(3):
            fh.write("  {" + ", ".join(f"{w[m*nf+n]:.10g}" for n in range(nf)) + "},\n")
        fh.write("};\n")
    np.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights.npy"), w)


if __name__ == "__main__":
    main()
