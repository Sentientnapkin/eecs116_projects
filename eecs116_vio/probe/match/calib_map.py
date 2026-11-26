"""Calibrate the probe -> manifest feature mapping on dataset flights the probe was run on locally.

    python3 calib_map.py MANIFEST.csv REPORT_DIR      (REPORT_DIR = ~/data/s3match/probe_reports)

For each stage-A feature: the probe-derived value (stage_a.server_features) against the manifest value, as
median log-ratio (or median difference) and its scatter. stage_a.py uses these as offsets and sigmas.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import decode_episode  # noqa: E402
from stage_a import SPEC, server_features  # noqa: E402

m = pd.read_csv(sys.argv[1]).set_index("id")
rows = []
for rep in glob.glob(os.path.join(sys.argv[2], "*", "report-*", "report.json")):
    fid = rep.split(os.sep)[-3]
    d = decode_episode(json.load(open(rep))["episodes"][0])
    if "camera" not in d:
        continue
    f = server_features(d)
    rows.append({"id": fid, **{f"p_{k}": v for k, v in f.items()}, **{f"m_{k}": m.loc[fid, k] for k in f}})
r = pd.DataFrame(rows)
print(f"{len(r)} flights")
cal = {}
for col, kind, _ in SPEC:
    p, q = r[f"p_{col}"].to_numpy(float), r[f"m_{col}"].to_numpy(float)
    e = np.log(q / p) if kind == "log" else q - p
    cal[col] = {"offset": float(np.median(e)), "scatter": float(1.4826 * np.median(np.abs(e - np.median(e))))}
    print(f"{col:22s} manifest vs probe: median {'log-ratio' if kind == 'log' else 'diff'} {np.median(e):+.4f}  "
          f"robust scatter {cal[col]['scatter']:.4f}  max |dev| {np.max(np.abs(e - np.median(e))):.4f}")
json.dump(cal, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "feature_calibration.json"), "w"), indent=1)
