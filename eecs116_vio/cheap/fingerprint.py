"""Exact server metrics of a cheap-model numpy replica on local flights (viobench's own evaluate_trajectory), for
matching local flights to the hidden server episodes.

  ~/.venv/bin/python fingerprint.py MODEL.npz OUT.json SET=ZIPGLOB ...
MODEL.npz: Wv (3,10), W1 (H,9), B1 (H,), W2 (3,H), act, grows (gyro rows) -- the cheap_mlp.c layout (W2 = 0 for linear).
Each SET=ZIPGLOB names a pool, e.g. ho='~/data/ho240/*.zip' tune_fconf='~/data/tune/fconf/*.zip'.
States match cheap_mlp.c: frame 0 identity, then gyro-quaternion pose, twist = (v_cam, gyro mean in camera axes).
"""
import glob, json, os, sys
from multiprocessing import Pool
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.metrics import evaluate_trajectory

DT = 0.05
M = None


def qmul(a, b):
    w1, x1, y1, z1 = a; w2, x2, y2, z2 = b
    return np.array([w1*w2-x1*x2-y1*y2-z1*z2, w1*x2+x1*w2+y1*z2-z1*y2, w1*y2-x1*z2+y1*w2+z1*x2, w1*z2+x1*y2-y1*x2+z1*w2])


def rot(q, v):
    w, x, y, z = q
    R = np.array([[1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y)], [2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x)], [2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)]])
    return R @ v


def states(ep, m):
    t = ep.frame_times; F = len(t); Rbc = ep.T_body_camera[:3, :3]; rows = list(m["grows"])
    S = np.zeros((F, 13)); S[0, 6] = 1
    q = np.array([1.0, 0, 0, 0]); p = np.zeros(3); e0 = np.zeros(3); e1 = np.zeros(3)
    act = str(m["act"])
    for k in range(1, F):
        g = ep.imu_window(k)[rows, 4:7].mean(0) @ Rbc
        h = 0.5 * DT * g; q = qmul(q, np.array([1 - 0.5 * h @ h, *h])); q /= np.linalg.norm(q)
        e0 += (DT / 0.25) * (g - e0); e1 += (DT / 1.0) * (g - e1)
        x = np.r_[1.0, e0, e1, np.abs(e1)]
        z = m["W1"] @ x[1:] + m["B1"]
        z = np.maximum(z, 0) if act == "relu" else np.tanh(z) if act == "tanh" else z / (1 + np.abs(z))
        v = m["Wv"] @ x + m["W2"] @ z
        p = p + DT * rot(q, v)
        S[k] = np.r_[p, q[1:], q[0], v, g]
    return S


def one(job):
    pool, path = job
    try:
        ep = read_episode(path, frames="none")
        met = evaluate_trajectory(ep.ground_truth_state(), states(ep, M), ep.frame_times).as_dict()
        gt = ep.ground_truth_state()
        met["zero_ate"] = float(np.sqrt((gt[:, :3] ** 2).sum(1).mean()))
        met["truth_speed_rms"] = float(np.sqrt((gt[:, 7:10] ** 2).sum(1).mean()))
        met["truth_rate_rms"] = float(np.sqrt((gt[:, 10:13] ** 2).sum(1).mean()))
        side = path[:-4] + ".json"
        info = json.load(open(side)) if os.path.exists(side) else {}
        return {"pool": pool, "name": os.path.basename(path)[:-4], "metrics": met, "setting": info.get("setting"),
                "scene": info.get("scene"), "audit": info.get("audit")}
    except Exception as e:
        return {"pool": pool, "name": os.path.basename(path)[:-4], "error": f"{type(e).__name__}: {e}"}


def init(path):
    global M
    M = dict(np.load(path))


if __name__ == "__main__":
    model, out = sys.argv[1], sys.argv[2]
    jobs = [(a.split("=", 1)[0], p) for a in sys.argv[3:] for p in sorted(glob.glob(os.path.expanduser(a.split("=", 1)[1])))]
    print(f"{len(jobs)} flights", flush=True)
    with Pool(int(os.environ.get("J", 12)), initializer=init, initargs=(model,)) as P:
        res = list(P.imap_unordered(one, jobs, chunksize=4))
    print(f"errors: {sum('error' in r for r in res)}", [r for r in res if "error" in r][:3])
    json.dump(res, open(os.path.expanduser(out), "w"))
