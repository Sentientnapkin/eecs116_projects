"""Experiment: do a few pixels help the cheap guest? Visual features on a sparse grid, added to fit_cheap's linear model.

  python vis_feats.py         (needs ~/data/imucache/{hf,ho} and ~/data/pixcache/{hf,ho}; trains on hf, tests on ho)

Per frame k (pixels of frames k-1, k on a grid of every STRIDE-th pixel of the 320x240 image, green channel):
  global flow fit  It + Ix u + Iy v + (x Ix + y Iy) d + (x Iy - y Ix) r = 0  (ridge least squares, 4 params)
  diff energy      sum|It| / (sum|Ix| + |Iy| + eps)
Features = these raw + EMAs (0.25 s, 1 s), appended to the gyro features; fitted to unaligned ATE like fit_cheap.
"""
import glob, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fit_cheap as fc


def vis_raw(pix, stride, ridge=1.0):
    """(F-1, 5): [u, v, d, r, energy] per frame k>=1, in units of full-res (320) pixels per frame."""
    s = stride // 4
    I = pix[:, ::s, ::s].astype(np.float64)
    H, W = I.shape[1:]
    Ix = 0.5 * (I[:, 1:-1, 2:] - I[:, 1:-1, :-2]); Iy = 0.5 * (I[:, 2:, 1:-1] - I[:, :-2, 1:-1])
    Ix = 0.5 * (Ix[1:] + Ix[:-1]); Iy = 0.5 * (Iy[1:] + Iy[:-1])          # gradient of the average of k-1, k
    It = I[1:, 1:-1, 1:-1] - I[:-1, 1:-1, 1:-1]
    yy, xx = np.mgrid[1:H - 1, 1:W - 1].astype(np.float64)
    xx -= (W - 1) / 2; yy -= (H - 1) / 2
    xx /= W / 2; yy /= W / 2                                               # normalised image coordinates
    G = np.stack([Ix, Iy, xx * Ix + yy * Iy, xx * Iy - yy * Ix], -1).reshape(len(It), -1, 4)
    b = It.reshape(len(It), -1)
    A = np.einsum("fni,fnj->fij", G, G) + ridge * np.eye(4) * G.shape[1]
    p = -np.linalg.solve(A, np.einsum("fni,fn->fi", G, b)[..., None])[..., 0]
    p[:, :2] *= stride                                                     # grid px -> 320-px units
    en = np.abs(b).sum(1) / (np.abs(Ix).sum((1, 2)) + np.abs(Iy).sum((1, 2)) + 1e-6)
    return np.c_[p, en * stride], G.shape[1]


def ema_cols(x, taus):
    out = [x]
    for tau in taus:
        e = np.zeros_like(x); s = np.zeros(x.shape[1]); al = fc.DT / tau
        for k in range(len(x)): s = s + al * (x[k] - s); e[k] = s
        out.append(e)
    return np.concatenate(out, 1)


DEROT = None  # (4, 4) linear map [1, gyro_cam] -> rotational part of [u, v, d, r], fitted on the training flights


def gyro_cam(f):
    return f["imu"][:, fc.GROWS, 4:7].mean(1) @ f["Tbc"][:3, :3]


def fit_derot(S, pixdir, stride):
    A = []; B = []
    for f in S:
        V, _ = vis_raw(np.load(os.path.join(pixdir, f["name"] + ".npz"))["pix"], stride)
        A.append(np.c_[np.ones(len(V)), gyro_cam(f)]); B.append(V[:, :4])
    A = np.concatenate(A); B = np.concatenate(B)
    return np.linalg.lstsq(A, B, rcond=None)[0]


def build(S, pixdir, stride, which, mode="lin"):
    out = {}
    for f in S:
        R, X = fc.prep(f)
        if stride:
            pix = np.load(os.path.join(pixdir, f["name"] + ".npz"))["pix"]
            V, n = vis_raw(pix, stride)
            cols = [V[:, which]]
            if mode in ("dir", "dirabs"):
                T = V[:, :3] - (np.c_[np.ones(len(V)), gyro_cam(f)] @ DEROT)[:, :3]   # translational flow
                Te = ema_cols(T, (0.5,))[:, 3:]                                       # smoothed, then normalised
                dirn = Te / (np.linalg.norm(Te, axis=1, keepdims=True) + 1e-3)
                spd = np.abs(X[:, 7:10]).sum(1, keepdims=True)                         # gyro activity (|e1|) as speed cue
                cols += [T, dirn, dirn * spd]
                if mode == "dirabs": cols += [np.abs(T), np.abs(Te)]
            X = np.concatenate([X, ema_cols(np.concatenate(cols, 1), (0.25, 1.0))], 1)
        out[id(f)] = fc.design(R, X)
    return out


def fit_eval(train, tests, Z, lam=10.0):
    nw = Z[id(train[0])].shape[-1]; A = np.zeros((nw, nw)); b = np.zeros(nw)
    for f in train:
        Zf = Z[id(f)].reshape(-1, nw); y = f["cam"][1:].reshape(-1)
        wt = 1 / max(np.sqrt((f["cam"] ** 2).sum(1).mean()), 1); A += wt * Zf.T @ Zf; b += wt * Zf.T @ y
    w = np.linalg.solve(A + lam * np.eye(nw), b)
    res = []
    for S in tests:
        r = np.array([np.sqrt(((np.vstack([np.zeros(3), Z[id(f)] @ w]) - f["cam"]) ** 2).sum(1).mean()) for f in S])
        res.append(r)
    return w, res


def main():
    home = os.path.expanduser("~/data")
    hf = [f for f in fc.load(f"{home}/imucache/hf") if os.path.exists(f"{home}/pixcache/hf/{f['name']}.npz")]
    ho = [f for f in fc.load(f"{home}/imucache/ho") if os.path.exists(f"{home}/pixcache/ho/{f['name']}.npz")]
    print(f"train hf n={len(hf)}, test ho n={len(ho)}, zero ho {np.mean([np.sqrt((f['cam']**2).sum(1).mean()) for f in ho]):.3f}")
    global DEROT
    runs = [(0, None, "lin", "gyro only"), (16, [0, 1, 2, 3, 4], "lin", "flow4+energy, 20x15")]
    if os.environ.get("ALL"):
        runs += [(16, [4], "lin", "energy, 20x15"), (16, [0, 1, 2, 3], "lin", "flow4, 20x15"),
                 (8, [0, 1, 2, 3, 4], "lin", "flow4+energy, 40x30"), (4, [0, 1, 2, 3, 4], "lin", "flow4+energy, 80x60")]
    runs += [(16, [0, 1, 2, 3, 4], "dir", "+derotated dir, 20x15"), (16, [0, 1, 2, 3, 4], "dirabs", "+dir+|flow|, 20x15"),
             (8, [0, 1, 2, 3, 4], "dirabs", "+dir+|flow|, 40x30")]
    for stride, which, mode, label in runs:
        if mode != "lin": DEROT = fit_derot(hf, f"{home}/pixcache/hf", stride)
        Z = build(hf, f"{home}/pixcache/hf", stride, which, mode); Z.update(build(ho, f"{home}/pixcache/ho", stride, which, mode))
        _, (rh, ro) = fit_eval(hf, [hf, ho], Z)
        print(f"  {label:22s} hf {rh.mean():.3f}  ho {ro.mean():.3f} (median {np.median(ro):.3f}, worst {ro.max():.2f})", flush=True)


if __name__ == "__main__":
    main()
