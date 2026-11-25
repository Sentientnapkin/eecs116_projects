"""Compare probe statistics of local flights against the 24 hidden stage-3 episodes.

    python compare.py FLIGHT_DIR [FLIGHT_DIR ...]    # after run_local.sh FLIGHT_DIR
    python compare.py                                # just print the server targets

For each statistic: the server's min / median / max per scene group (rooms = episodes 1-12, warehouse 13-18,
forest 19-24) and over the local flights. A local set is a good stand-in when its ranges cover the server's.
Plain python (no viobench needed).
"""
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from decode import decode_episode  # noqa: E402

FIELDS = [  # (label, getter)
    ("hfov deg", lambda d: d["camera"]["hfov_deg"]),
    ("path length m", lambda d: d["path"]["distance"]),
    ("mean speed m/s", lambda d: d["path"]["mean_speed"]),
    ("rms 1 s move m", lambda d: d["path"]["rms_1s_displacement"]),
    ("rms dist from start m", lambda d: d["path"]["rms_dist_from_start"]),
    ("rms spread m", lambda d: d["path"]["rms_spread"]),
    ("start fwd speed m/s", lambda d: d["start_forward_speed"]),
    ("|start fwd speed| m/s", lambda d: abs(d["start_forward_speed"])),
    ("start 1 s gyro rms", lambda d: d["start_1s"]["gyro_rms"]),
    ("gyro rms rad/s", lambda d: d["dynamics"]["gyro_rms"]),
    ("yaw rms rad/s", lambda d: d["dynamics"]["yaw_rms"]),
    ("roll+pitch rms rad/s", lambda d: np.sqrt(max(d["dynamics"]["gyro_rms"] ** 2 - d["dynamics"]["yaw_rms"] ** 2, 0))),
    ("jerk rms m/s3", lambda d: d["dynamics"]["jerk_rms"]),
    ("accel xy rms m/s2", lambda d: d["dynamics"]["accel_xy_rms"]),
    ("gyro sigma", lambda d: d["imu_noise"]["gyro_sigma"]),
    ("accel sigma", lambda d: d["imu_noise"]["accel_sigma"]),
    ("Y mean", lambda d: d["image"]["Y_mean"]),
    ("chroma g", lambda d: d["image"]["chroma_g"]),
    ("chroma b", lambda d: d["image"]["chroma_b"]),
    ("gradient energy", lambda d: d["image"]["grad2_mean"]),
    ("blur x <60 px/s", lambda d: d["blur_ratio_x_by_px_speed"][0]),
    ("blur x 60-200 px/s", lambda d: d["blur_ratio_x_by_px_speed"][1]),
    ("gyro drift deg rms", lambda d: d["gyro_drift"]["rot_rmse_deg"]),
]


def stats(decoded, get):
    v = [get(d) for d in decoded]
    v = np.array([x for x in v if x is not None], float)
    return "        -          " if v.size == 0 else f"{v.min():7.2f} {np.median(v):7.2f} {v.max():7.2f}"


def main():
    server = json.load(open(os.path.join(HERE, "..", "stage3", "probe_decoded.json")))
    groups = {"rooms": server[:12], "warehouse": server[12:18], "forest": server[18:]}
    local = {}
    for d in sys.argv[1:]:
        reps = glob.glob(os.path.join(d, "probe_reports", "*", "report-*", "report.json")) or \
               glob.glob(os.path.join(d, "**", "report.json"), recursive=True)
        eps = [decode_episode(e) for r in reps for e in json.load(open(r))["episodes"]]
        ok = [e for e in eps if "camera" in e]
        print(f"{d}: {len(ok)} of {len(eps)} flights decoded (others are not 1200 frames)")
        local[os.path.basename(os.path.normpath(d))] = ok
    cols = list(groups) + list(local)
    print(f"{'(min median max)':22s}" + "".join(f"{c[:23]:>24s}" for c in cols))
    for label, get in FIELDS:
        print(f"{label:22s}" + "".join(f"{stats(g, get):>24s}" for g in list(groups.values()) + list(local.values())))


if __name__ == "__main__":
    main()
