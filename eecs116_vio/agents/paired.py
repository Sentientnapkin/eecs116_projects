"""Paired comparison of two eval_set.sh runs on the same flights, priced on the server.

    python paired.py CAND_TAG BASE_TAG [SET]      (default SET heldout_s3, default BASE_TAG base_gslv)

The server estimate is relative: est. ATE = server ATE of the base x (candidate mean / base mean), and est. fuel =
server fuel of the base x (candidate peak / base peak). The base is "GSLV smaller net" (0.4444 m @ 4,032,692 on
the server). Absolute local numbers are not calibrated for vision models; the ratios are what to trust.
"""
import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import area_gain  # noqa: E402

BASE_SERVER = {"base_gslv": (0.4443728206485426, 4032692)}


def load(tag, s):
    return json.loads((HERE / "results" / f"{tag}__{s}.json").read_text())


def main():
    cand_tag = sys.argv[1]
    base_tag = sys.argv[2] if len(sys.argv) > 2 else "base_gslv"
    s = sys.argv[3] if len(sys.argv) > 3 else "heldout_s3"
    c, b = load(cand_tag, s), load(base_tag, s)
    names = sorted(n for n in b["flights"] if b["flights"][n]["ate"] is not None)
    missing = [n for n in names if (c["flights"].get(n) or {}).get("ate") is None]
    if missing:
        print(f"WARNING: candidate is missing {len(missing)} flights: {missing[:5]}")
    names = [n for n in names if n not in missing]
    ca = np.array([c["flights"][n]["ate"] for n in names])
    ba = np.array([b["flights"][n]["ate"] for n in names])
    d = ca - ba
    rng = np.random.default_rng(0)
    boot = np.array([d[i].mean() for i in rng.integers(0, len(d), (10000, len(d)))])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    cpk = max(c["flights"][n]["fuel_max"] for n in names)
    bpk = max(b["flights"][n]["fuel_max"] for n in names)
    print(f"{cand_tag} vs {base_tag} on {s}, n={len(names)} flights")
    print(f"  ATE mean {ca.mean():.4f} vs {ba.mean():.4f}  d {d.mean():+.4f} m  95% CI [{lo:+.4f}, {hi:+.4f}]  "
          f"ratio {ca.mean() / ba.mean():.4f}  better on {np.mean(d < 0):.0%} of flights")
    print(f"  peak fuel {cpk:,.0f} vs {bpk:,.0f} (ratio {cpk / bpk:.3f})")
    for cls in ("ro", "wa", "fo"):
        m = np.array([f"-{cls}-" in n for n in names])
        if m.any():
            print(f"  {cls}: n={m.sum():2d}  {ca[m].mean():.3f} vs {ba[m].mean():.3f}  d {d[m].mean():+.4f}")
    worst = np.argsort(-d)[:3]
    print("  biggest losses:", ", ".join(f"{names[i]} {d[i]:+.3f}" for i in worst))
    if base_tag in BASE_SERVER:
        sa, sf = BASE_SERVER[base_tag]
        ea, ef = sa * ca.mean() / ba.mean(), sf * cpk / bpk
        g = area_gain.gain(ef, ea)
        claimed, _ = area_gain.best()
        print(f"  est. server {ea:.4f} m @ {ef:,.0f} -> gain {g:.3f} vs claimed {claimed:.3f}: "
              f"{'BEATS' if g > claimed else 'does not beat'}"
              f"{'  (bit-identical ATE)' if lo == hi == 0 else '' if hi < 0 else '  (ATE CI includes no improvement)'}")


if __name__ == "__main__":
    main()
