"""Validate decode.py on the local calibration runs (calib_run.sh), against the debug payloads and the ground truth.
    python3 validate.py          (WSL venv: needs viobench to read the episodes)"""
import glob, json, os, re, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode import decode_episode
from viobench.tools.datasets.storage import read_episode

OUT = os.path.expanduser("~/probe_calib")
paths = open(f"{OUT}/list").read().split()
worst = {}
for i, path in enumerate(paths):
    rel = json.load(open(glob.glob(f"{OUT}/release_{i}/report-*/report.json")[0]))["episodes"][0]
    if rel["metrics"]["frames"] != 1200:
        continue
    err = open(glob.glob(f"{OUT}/debug_{i}/report-*/logs/*/stderr.txt")[0]).read()
    Xdbg = [int(v) for v in re.search(r"PROBEX (.*)", err).group(1).split()]
    d = decode_episode(rel)
    ep = read_episode(path)
    gt = ep.ground_truth_state()
    imu = ep.imu
    # truths for the metric channel
    v0z = gt[0, 9]
    est = np.loadtxt(glob.glob(f"{OUT}/release_{i}/report-*/logs/*/estimates*")[0], delimiter=",", skiprows=1) \
        if glob.glob(f"{OUT}/release_{i}/report-*/logs/*/estimates*.csv") else None
    fx_true = ep.adapt((320, 240))[0]["fx"]
    gyro = imu[:, 4:7]
    sig_true = np.sqrt(np.mean(np.diff(gyro[:5000], 2, axis=0) ** 2) / 6)
    print(f"[{i}] {os.path.basename(path)}  checks {d['checks']}")
    print(f"     payloads match debug: {d['payloads'] == Xdbg}   fx {d['camera']['fx_320']} vs {fx_true:.3f}")
    print(f"     v0z decoded {d['start_forward_speed']:+.5f} true {v0z:+.5f}   |v0| {np.linalg.norm(gt[0, 7:10]):.3f}")
    print(f"     gyro sigma decoded {d['imu_noise']['gyro_sigma']:.5f} vs direct {sig_true:.5f};  b_cam_y {d['gyro_bias_cam_y']:+.6f}")
    if est is not None:
        e_y = est[:, 11] - 1e6 - gt[:, 11]
        print(f"     b_cam_y direct from estimates {e_y.mean():+.6f}")
    print(f"     path rms dist {d['path']['rms_dist_from_start']:.2f} vs {np.sqrt(np.mean(np.sum(gt[:, :3] ** 2, 1))):.2f}")
    worst["v0z"] = max(worst.get("v0z", 0), abs(d["start_forward_speed"] - v0z))
print("worst |v0z error|", worst)
