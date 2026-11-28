"""Summarise an eval_twin120.sh run: python twin_summary.py OUTDIR TAG WASM (run in the WSL ~/.venv)."""
import glob
import hashlib
import json
import os
import sys

import numpy as np
from viobench.tools.datasets.storage import archive_hash

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import area_gain  # noqa: E402

out, tag, wasm = sys.argv[1:4]
names = {archive_hash(p): os.path.basename(p)[:-4] for p in open(os.path.join(out, "list")).read().split()}
eps = [e for f in sorted(glob.glob(os.path.join(out, "r_*", "*", "report.json"))) for e in json.load(open(f))["episodes"]]
by_name = {names.get(e.get("hash"), "?"): e for e in eps}
ate = {n: (e.get("metrics") or {}).get("ate_rmse", np.nan) for n, e in by_name.items()}
fuel = [e.get("fuel_per_frame_max") or (e.get("fuel") or {}).get("max", np.nan) for e in eps]


def rows(fname):
    path = os.path.join(HERE, "..", "stage3", "twin", fname)
    return [l.split("\t")[:2] for l in open(path).read().splitlines() if l.strip()]


def episode_means(fname):
    per = {}
    for ep, n in rows(fname):
        per.setdefault(int(ep), []).append(ate.get(n, np.nan))
    return {ep: float(np.nanmean(v)) if np.isfinite(v).any() else np.nan for ep, v in sorted(per.items())}


t120, t24 = episode_means("twin120.txt"), episode_means("twin24.txt")
missing = sorted(set(n for _, n in rows("twin120.txt")) - set(k for k, v in ate.items() if np.isfinite(v)))
m120, m24, fmax = float(np.nanmean(list(t120.values()))), float(np.nanmean(list(t24.values()))), float(np.nanmax(fuel))
# Calibration (2026-11-26, IMU-only models and zero output): twin120 is within ~3% of the server in both directions
# (zero 7.76 vs 7.55; MLPs 11.96 vs 12.20 and 9.95 vs 9.99). Not yet checked for vision solutions.
est_server = m120
g = area_gain.gain(fmax, est_server)
claimed, best = area_gain.best()
res = {"tag": tag, "wasm": wasm, "wasm_sha256": hashlib.sha256(open(wasm, "rb").read()).hexdigest(),
       "flights_scored": len(ate) - len(missing), "flights_missing": missing,
       "twin120_ate": m120, "twin24_ate": m24, "est_server_ate": est_server, "fuel_per_frame_max": fmax,
       "est_area_gain": g, "current_claimed_area": claimed, "beats_best": g > claimed,
       "twin120_per_episode": t120}
json.dump(res, open(os.path.join(HERE, "results", f"{tag}.json"), "w"), indent=1)
print(f"== {tag}  sha256 {res['wasm_sha256'][:12]}  flights {res['flights_scored']}/120"
      f"{'  MISSING ' + str(len(missing)) if missing else ''}")
print(f"twin120 {m120:.3f} m  twin24 {m24:.3f} m  -> est. server {est_server:.3f} m @ max fuel {fmax:,.0f}")
print(f"est. area gain {g:.3f} vs current best {claimed:.3f} ({best['label'] if best else '?'}): "
      f"{'BEATS' if g > claimed else 'does not beat'}")
print("worst episodes:", ", ".join(f"ep{ep} {v:.2f}" for ep, v in sorted(t120.items(), key=lambda kv: -kv[1])[:4]))
