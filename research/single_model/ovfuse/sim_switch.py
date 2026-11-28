"""Offline B16/OpenVINS switching rules on saved trajectories (tuning flights only: HF visible folds 0-3 + proxy).

  python -I sim_switch.py [--b16 b16 px_b16] [--ov ov_plain px_ov_plain]
Inputs: estimate.tum of B16 and of plain OpenVINS per flight (work/evals/<name>/<ep>/estimate.tum) and truth
(work/epdump or work/proxydump). OpenVINS reports position exactly 0 before it initializes, so its init frame is the
first frame with a non-zero position. A rule decides per frame which estimate is reported, using only past/current
values of the two estimates (causal), exactly as fuse.cpp would; the result is that rule's unaligned ATE.
"""
import argparse, json
from pathlib import Path
import numpy as np

W = Path("C:/Users/alexa/vio_data/work")


def gt_cam(z):
    R, p, T = z["R"], z["p"], z["T_bc"]
    Rc = R @ T[:3, :3]; pc = p + R @ T[:3, 3]
    return np.einsum("ji,nj->ni", Rc[0], pc - pc[0])


def load(b16, ov):
    out = []
    for bname, oname, gt in ((b16[0], ov[0], "epdump"), (b16[1], ov[1], "proxydump")):
        for tb in sorted((W / "evals" / bname).glob("*/estimate.tum")):
            ep = tb.parent.name
            to = W / "evals" / oname / ep / "estimate.tum"
            zf = W / gt / f"{ep}.npz"
            if not (to.exists() and zf.exists()):
                continue
            z = np.load(zf); g = gt_cam(z)
            pb = np.loadtxt(tb)[:, 1:4]; po = np.loadtxt(to)[:, 1:4]
            n = min(len(pb), len(po), len(g))
            row = json.loads((tb.parent / "row.json").read_text())
            out.append(dict(ep=ep, set="hf" if gt == "epdump" else "px", scene=row.get("scene", ep), start=row.get("start"),
                            fold=row.get("fold", -1), g=g[:n], b=pb[:n], o=po[:n]))
    return out


def rule(f, warm=20, vmax=12.0, dmax=1e9, dframes=40, late=1e9, blend=0, tmax=1e9, anchor=False):
    """anchor: after the switch report B16's position at the switch plus OpenVINS's motion since then
    (keeps OpenVINS's tracking, drops its startup offset); dmax then compares that anchored position with B16."""
    b, o = f["b"], f["o"]; n = len(b)
    nz = np.nonzero(np.abs(o).sum(1) > 0)[0]
    out = b.copy()
    if not len(nz):
        return out, -1
    i0 = nz[0]
    if i0 > late:
        return out, -1
    v = np.r_[0, np.linalg.norm(np.diff(o, axis=0), axis=1) * 20.0]
    use, sw, far = False, -1, 0
    off = np.zeros(3)
    for k in range(i0, n):
        ok = o[k] + off
        dk = np.linalg.norm(ok - b[k])
        far = far + 1 if dk > dmax else 0
        if use and (v[k] > vmax or far >= dframes):
            out[k:] = b[k:]; return out, sw
        if not use and k - i0 >= warm and v[k] <= vmax and k <= tmax:
            use, sw = True, k
            if anchor:
                off = b[k] - o[k]; ok = o[k] + off
        if use:
            w = min(1.0, (k - sw) / blend) if blend else 1.0
            out[k] = (1 - w) * b[k] + w * ok
    return out, sw


def ate(p, g):
    return float(np.sqrt((np.linalg.norm(p - g, axis=1) ** 2).mean()))


def boot(d, scenes, n=4000, seed=1):
    rng = np.random.default_rng(seed); u = sorted(set(scenes))
    idx = {s: [i for i, x in enumerate(scenes) if x == s] for s in u}
    bs = [d[[i for p in rng.integers(0, len(u), len(u)) for i in idx[u[p]]]].mean() for _ in range(n)]
    return np.percentile(bs, [2.5, 97.5])


def report(fl, name, **kw):
    res = []
    for f in fl:
        p, sw = rule(f, **kw)
        res.append((ate(p, f["g"]), ate(f["b"], f["g"]), sw))
    a = np.array([r[0] for r in res]); b = np.array([r[1] for r in res]); d = a - b
    out = [f"{name:34s}"]
    for s in ("hf", "px"):
        m = np.array([f["set"] == s for f in fl])
        if m.any():
            lo, hi = boot(d[m], [f["scene"] for f, k in zip(fl, m) if k])
            out.append(f"{s} n={m.sum()} {a[m].mean():.3f} (B16 {b[m].mean():.3f}) d {d[m].mean():+.3f} [{lo:+.3f},{hi:+.3f}] >1m {(a[m] > 1).sum()}/{(b[m] > 1).sum()}")
    out.append(f"switched {np.mean([r[2] >= 0 for r in res]):.0%}")
    print(" | ".join(out))
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--b16", nargs=2, default=["b16", "px_b16"]); ap.add_argument("--ov", nargs=2, default=["ov_plain", "px_ov_plain"])
    a = ap.parse_args()
    fl = load(a.b16, a.ov)
    print(f"{len(fl)} flights ({sum(f['set'] == 'hf' for f in fl)} HF, {sum(f['set'] == 'px' for f in fl)} proxy)")
    init = [np.nonzero(np.abs(f["o"]).sum(1) > 0)[0] for f in fl]
    i0 = np.array([x[0] / 20 if len(x) else np.inf for x in init])
    print(f"OpenVINS init time: median {np.median(i0[np.isfinite(i0)]):.2f} s, never {np.isinf(i0).sum()}, >5 s {(i0 > 5).sum()}")
    ov_only = [ate(f["o"], f["g"]) for f in fl]; b16 = [ate(f["b"], f["g"]) for f in fl]
    pf = [ate(np.where((np.linalg.norm(f["o"] - f["g"], axis=1) < np.linalg.norm(f["b"] - f["g"], axis=1))[:, None], f["o"], f["b"]), f["g"]) for f in fl]
    for st in ("hf", "px"):
        m = np.array([f["set"] == st for f in fl])
        if m.any():
            print(f"[{st}] plain OpenVINS mean {np.mean(np.array(ov_only)[m]):.3f} median {np.median(np.array(ov_only)[m]):.3f} | B16 {np.mean(np.array(b16)[m]):.3f} | "
                  f"oracle per-flight {np.mean(np.minimum(ov_only, b16)[m]):.3f} | oracle per-frame {np.mean(np.array(pf)[m]):.3f} | OV better on {(np.array(ov_only) < np.array(b16))[m].sum()}/{m.sum()}")
    report(fl, "always B16 (sanity)", warm=10 ** 9)
    for warm in (0, 20, 60):
        report(fl, f"switch warm={warm}", warm=warm)
    for vmax in (6, 9):
        report(fl, f"warm=20 vmax={vmax}", warm=20, vmax=vmax)
    for dmax in (1, 2, 4):
        for df in (20, 60):
            report(fl, f"warm=20 dmax={dmax} dframes={df}", warm=20, dmax=dmax, dframes=df)
    for late in (40, 100):
        report(fl, f"warm=20 late<{late}fr", warm=20, late=late)
    report(fl, "warm=20 blend=40", warm=20, blend=40)
    for vmax in (5, 12):
        for late in (40, 1e9):
            report(fl, f"ANCHOR warm=20 vmax={vmax} late<{late}", warm=20, vmax=vmax, late=late, anchor=True)
            for dmax in (1, 2):
                report(fl, f"ANCHOR vmax={vmax} late<{late} dmax={dmax}", warm=20, vmax=vmax, late=late, anchor=True, dmax=dmax, dframes=20)
    for vmax in (5,):
        for late in (40, 100):
            for dmax in (1, 2):
                report(fl, f"SWITCH vmax={vmax} late<{late} dmax={dmax}", warm=20, vmax=vmax, late=late, dmax=dmax, dframes=20)


if __name__ == "__main__":
    main()
