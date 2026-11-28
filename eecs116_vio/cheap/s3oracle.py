"""Upper bounds for a cheap vision add-on: what if the guest knew the direction of travel (camera axes) each frame?

    ~/.venv_gru/bin/python s3oracle.py [SET ...]       (default s3va s3nb)

All variants integrate with the guest's own gyro-only attitude R_k (fit_cheap.prep), so attitude drift is included:
  true velocity     v_cam = true camera-frame velocity            (attitude drift is the only error)
  dir + true speed  true direction with angular noise, true speed
  dir + const speed true direction (+ noise), one constant speed fitted per set (no speed information)
  dir + mean speed  true direction (+ noise), the flight's true mean speed (a perfect speed prior per flight)
"""
import sys

import numpy as np

import fit_cheap as fc

DT = fc.DT


def true_vcam(f):
    """camera-frame velocity over each frame step, from the cached camera centres and orientations (camera-0 axes)."""
    dp = np.diff(f["cam"], axis=0) / DT                     # (n, 3) in camera-0 axes, step k -> k+1
    R = f["Rc0c"][1:len(dp) + 1]                            # camera k+1 in camera 0
    return np.einsum("kji,kj->ki", R, dp)


def noisy(d, deg, rng):
    if deg == 0:
        return d
    n = rng.normal(size=d.shape) * np.radians(deg)
    n -= (n * d).sum(1, keepdims=True) * d                  # perpendicular perturbation
    out = d + n
    return out / np.linalg.norm(out, axis=1, keepdims=True)


def ate(f, R, v):
    p = np.vstack([np.zeros(3), np.cumsum(DT * np.einsum("kij,kj->ki", R, v), 0)])
    return float(np.sqrt(((p - f["cam"][:len(p)]) ** 2).sum(1).mean()))


def main():
    for name in sys.argv[1:] or ["s3va", "s3nb"]:
        S = fc.load(f"~/data/imucache/{name}")
        rng = np.random.default_rng(0)
        rows = {}
        for f in S:
            R, _ = fc.prep(f)
            vt = true_vcam(f)[:len(R)]
            sp = np.linalg.norm(vt, axis=1, keepdims=True)
            d = vt / np.maximum(sp, 1e-9)
            rows.setdefault("zero", []).append(float(np.sqrt((f["cam"] ** 2).sum(1).mean())))
            rows.setdefault("true velocity", []).append(ate(f, R, vt))
            for deg in (0, 10, 20, 40):
                dn = noisy(d, deg, rng)
                rows.setdefault(f"dir{deg:>2d}deg + true speed", []).append(ate(f, R, dn * sp))
                rows.setdefault(f"dir{deg:>2d}deg + mean speed", []).append(ate(f, R, dn * sp.mean()))
                for s in (0.6, 0.9, 1.2):
                    rows.setdefault(f"dir{deg:>2d}deg + const {s}", []).append(ate(f, R, dn * s))
        print(f"\n{name}: {len(S)} flights (mean ATE, m)")
        for k, v in rows.items():
            print(f"  {k:26s} {np.mean(v):7.3f}")


if __name__ == "__main__":
    main()
