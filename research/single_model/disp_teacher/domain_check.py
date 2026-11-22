"""Offline check on SERVER flights: teacher 1 s displacement error vs B16's own 1 s displacement error, same windows.

  vio_env/Scripts/python domain_check.py --ckpt runs/t2/best.pt [--b16 b16]
Teacher inputs as deployed but from truth + training-matched noise (derotation 0.4 deg, tilt 1 deg, preintegration
noise); B16 displacement from its saved estimate.tum (camera poses in camera-0 frame) over the same 20-frame window.
"""
import argparse, glob, json, math
from pathlib import Path
import numpy as np
import torch

from model import arch_of
from train import exp_so3, prepare

DATA = Path("C:/Users/alexa/vio_data")


def quat_to_R(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def windows(z, rng, L=20, step=4):
    gray, R, p, v, ft, Tbc, K = z["gray"], z["R"], z["p"], z["v"], z["ft"], z["T_bc"], z["K"]
    Rbc = Tbc[:3, :3]; s = 128 / 320
    Km = np.array([[K[0] * s, 0, (K[2] + .5) * s - .5], [0, K[1] * s, (K[3] + .5) * s - .5], [0, 0, 1]]); Ki = np.linalg.inv(Km)
    out = []
    for t in range(L + 4, len(gray), step):
        Rc = [R[k] @ Rbc for k in (t, t - L // 2, t - L)]
        Hs = []
        for j in (1, 2):
            Rcc = exp_so3(rng.normal(0, math.radians(0.4) * (j / 2) ** .5, 3)) @ (Rc[0].T @ Rc[j])
            Hs.append(Km @ Rcc.T @ Ki)
        d = Rc[0].T @ (p[t] - p[t - L])
        tn = math.radians(1.0)
        g = exp_so3(rng.normal(0, tn, 3)) @ (Rc[0].T @ np.array([0, 0, -1.0]))
        b = rng.normal(0, 9.81 * tn, 3) + rng.normal(0, 0.05, 3)
        af = Rc[0].T @ (p[t] - p[t - L] - v[t - L] * (ft[t] - ft[t - L])) + 0.5 * b + rng.normal(0, .012, 3)
        am = Rc[0].T @ (p[t] - p[t - L // 2] - v[t - L // 2] * (ft[t] - ft[t - L // 2])) + 0.125 * b + rng.normal(0, .004, 3)
        aux = np.r_[g, Km[0, 0] / 128, af, am].astype(np.float32)
        out.append((t, np.stack([gray[t], gray[t - L // 2], gray[t - L]]), np.stack(Hs).astype(np.float32), aux, d))
    return out


def b16_disp(name, ep, L=20):
    f = glob.glob(str(DATA / f"work/evals/{name}/{ep}/estimate.tum"))
    if not f:
        return None
    a = np.loadtxt(f[0])
    c = a[:, 1:4]; Rs = [quat_to_R(q) for q in a[:, 4:8]]
    return lambda t: Rs[t].T @ (c[t] - c[t - L])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--ckpt", required=True); ap.add_argument("--b16", default="b16")
    ap.add_argument("--folds", type=int, nargs="*", default=[2, 3])
    a = ap.parse_args()
    sd = torch.load(a.ckpt, map_location="cpu")["model"]; m = arch_of(sd); m.load_state_dict(sd); m.eval()
    dev = "cuda" if torch.cuda.is_available() else "cpu"; m.to(dev)
    rng = np.random.default_rng(0)
    E_t, E_b, Z, MAG, SP = [], [], [], [], []
    for f in sorted(glob.glob(str(DATA / "work/epdump/*.npz"))):
        ep = Path(f).stem; z = np.load(f)
        if int(z["fold"]) not in a.folds:
            continue
        W = windows(z, rng); bd = b16_disp(a.b16, ep)
        if not W:
            continue
        ims = torch.tensor(np.stack([w[1] for w in W])); Hs = torch.tensor(np.stack([w[2] for w in W]))
        aux = torch.tensor(np.stack([w[3] for w in W])); tgt = torch.zeros(len(W), 6)
        outs = []
        with torch.no_grad():
            for s in range(0, len(W), 128):
                img, mask, ax, _ = prepare(ims[s:s + 128], Hs[s:s + 128], aux[s:s + 128], tgt[s:s + 128], dev, False)
                outs.append(m(img, mask, ax).float().cpu().numpy())
        o = np.concatenate(outs); d = np.stack([w[4] for w in W])
        et = np.linalg.norm(o[:, :3] - d, axis=1)
        E_t.append(et); MAG.append(np.linalg.norm(d, axis=1))
        Z.append(np.abs(o[:, :3] - d) / np.exp(o[:, 3:6]))
        if bd is not None:
            E_b.append(np.array([np.linalg.norm(bd(w[0]) - w[4]) for w in W]))
        if False: print(f"{ep:40s} n={len(W)} teacher {et.mean():.3f}  b16 {E_b[-1].mean() if bd is not None else float('nan'):.3f}  |d| {MAG[-1].mean():.2f}", flush=True)
    et = np.concatenate(E_t); mg = np.concatenate(MAG); z = np.concatenate(Z)
    print(f"ALL teacher mean {et.mean():.3f} median {np.median(et):.3f}; |d| mean {mg.mean():.3f}; laplace z mean per axis {z.mean(0).round(2)} (1.0 = calibrated)")
    if E_b:
        eb = np.concatenate(E_b); print(f"ALL b16 mean {eb.mean():.3f} median {np.median(eb):.3f}")
        for lo, hi in ((0, .5), (.5, 1), (1, 2), (2, 9)):
            s = (mg >= lo) & (mg < hi)
            print(f"  |d| {lo}-{hi}: n={s.sum()} teacher {et[s].mean():.3f} b16 {eb[s].mean():.3f}")


if __name__ == "__main__":
    main()
