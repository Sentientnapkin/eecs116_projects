"""Stage A: rank the viobench-stage3 dataset flights (manifest.csv) by similarity to each hidden episode, using only
the probe's decoded statistics (no downloads).

    python stage_a.py MANIFEST.csv [K]      -> ../../stage3/match_stage_a.json (top K per hidden episode, default 40)

Feature mapping (probe -> manifest; both use frames 0-1129 where it matters):
  fov_deg                 = camera.hfov_deg                      (exact on both sides)
  path_m                  ~ path.distance                        (server: camera at 20 Hz; manifest: body at 200 Hz)
  rms_dist_from_start     ~ path.rms_dist_from_start
  rms_spread              ~ path.rms_spread
  start_fwd_speed         ~ start_forward_speed                  (server: +-5 ms central difference at frame 0)
  tilt/yaw/gyro rms       ~ dynamics (probe uses 10-row frame means, the manifest raw 200 Hz samples:
                            manifest^2 = probe^2 + axes * 0.9 * sigma_g^2, sigma_g = 0.070)
  jerk_rms                = sqrt(3) * probe jerk (probe: per-axis RMS; manifest: vector RMS)
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE3 = os.path.join(HERE, "..", "..", "stage3")
SIG_G2 = 0.9 * 0.070 ** 2
GROUP = ["room"] * 12 + ["warehouse"] * 6 + ["forest"] * 6

# (name, server value, manifest column, transform, sigma) ; transform 'log' compares log values
def server_features(d):
    dy = d["dynamics"]
    tilt2 = max(dy["gyro_rms"] ** 2 - dy["yaw_rms"] ** 2, 0)
    return {
        "fov_deg": d["camera"]["hfov_deg"],
        "path_m": d["path"]["distance"],
        "rms_dist_from_start": d["path"]["rms_dist_from_start"],
        "rms_spread": d["path"]["rms_spread"],
        "start_fwd_speed": d["start_forward_speed"],
        "tilt_rms": math.sqrt(tilt2 + 2 * SIG_G2),
        "yaw_rms": math.sqrt(dy["yaw_rms"] ** 2 + SIG_G2),
        "jerk_rms": math.sqrt(3) * dy["jerk_rms"],
    }


SPEC = [  # column, kind, sigma
    ("fov_deg", "lin", 1.0),
    ("path_m", "log", 0.05),
    ("rms_dist_from_start", "log", 0.08),
    ("rms_spread", "log", 0.08),
    ("start_fwd_speed", "lin", 0.15),
    ("tilt_rms", "log", 0.12),
    ("yaw_rms", "log", 0.15),
    ("jerk_rms", "log", 0.15),
]


def zscores(m, f):
    z = {}
    for col, kind, s in SPEC:
        a = m[col].to_numpy(float)
        z[col] = (np.log(np.maximum(a, 1e-6)) - math.log(max(f[col], 1e-6))) / s if kind == "log" else (a - f[col]) / s
    return pd.DataFrame(z, index=m.index)


def main():
    m = pd.read_csv(sys.argv[1])
    K = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    m = m[(m.frames == 1200) & (m.quality == "ok")].copy()
    server = json.load(open(os.path.join(STAGE3, "probe_decoded.json")))
    out = []
    print(f"{len(m)} usable flights")
    for i, d in enumerate(server):
        f = server_features(d)
        c = m[m.setting_class == GROUP[i]]
        z = zscores(c, f)
        hover = abs(f["start_fwd_speed"]) < 0.01 and d["start_1s"]["gyro_rms"] < 0.2
        pen = np.where((c.start == "hover") == hover, 0.0, 9.0)   # 3 sigma for a start-type mismatch
        dist = np.sqrt((z ** 2).sum(1) + pen)
        order = np.argsort(dist.to_numpy())[:K]
        top = c.iloc[order]
        within = int((np.abs(z) < 1).all(1).sum())
        print(f"{i + 1:2d} {d['hash'][:8]} {GROUP[i]:9s} best d={dist.iloc[order[0]]:.2f}  10th d={dist.iloc[order[9]]:.2f}  "
              f"flights within 1 sigma on all 8: {within:3d}   best {top.id.iloc[0]} ({top.split.iloc[0]})")
        out.append({"index": i + 1, "hash": d["hash"], "group": GROUP[i], "server_features": f, "hover": hover,
                    "candidates": [{"id": r.id, "d": float(dist.loc[idx]), "split": r.split, "path": r.path,
                                    "z": {k: round(float(v), 2) for k, v in z.loc[idx].items()}}
                                   for idx, r in top.iterrows()]})
    json.dump(out, open(os.path.join(STAGE3, "match_stage_a.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
