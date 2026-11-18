"""Hand-built-feature ablation: gyro-derotated LK flow statistics (features.py) vs IMU window, fit with ridge / RFF-GP / MLP.

This is the 'flow statistics in a hand-built pipeline' side of the decision; the learned CNN side is learned_probe.py.

    python probes.py [tier-glob]      e.g. python probes.py "base-*"
"""
import glob
import sys

import numpy as np
import torch
import torch.nn as nn

from common import Flight, ate, integrate_body_velocity
from features import extract
from pairs import config, digest
from learned_probe import open_run, write
from probes_util import rff_gp_fit, ridge_fit


def load(pattern):
    out = []
    for p in sorted(glob.glob(pattern)):
        with np.load(extract(p)) as cached:
            out.append((p, dict(cached)))
    return out


def group(d, name):
    return {"imu_1s": d["imu"], "flow": d["flow"], "flow+imu_1s": np.concatenate([d["flow"], d["imu"]], 1)}[name]


def mlp_fit(X, Y, epochs=20, seed=0):
    torch.manual_seed(seed)
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Xt, Yt = torch.tensor((X - mu) / sd, dtype=torch.float32), torch.tensor(Y, dtype=torch.float32)
    net = nn.Sequential(nn.Linear(X.shape[1], 128), nn.ReLU(), nn.Linear(128, 128), nn.ReLU(), nn.Linear(128, 3))
    opt = torch.optim.AdamW(net.parameters(), 1e-3, weight_decay=1e-3)
    for _ in range(epochs):
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), 512):
            b = perm[i:i + 512]
            loss = nn.functional.smooth_l1_loss(net(Xt[b]), Yt[b], beta=0.05)
            opt.zero_grad(); loss.backward(); opt.step()
    net.eval()
    return lambda Xn: net(torch.tensor((Xn - mu) / sd, dtype=torch.float32)).detach().numpy()


def score(fn, val, g):
    out = []
    for p, d in val:
        f = Flight(p)
        vb = fn(group(d, g))
        e = f.camera_positions(f.p[0] + integrate_body_velocity(f.R, vb, times=f.ft), f.R)
        out.append(ate(e, f.cam_gt))
    return float(np.mean(out))


def main():
    tg = sys.argv[1] if len(sys.argv) > 1 else "*"
    train, val = load(f"data/train/{tg}.npz"), load(f"data/val/{tg}.npz")
    print(f"{len(train)} train / {len(val)} val flights ({tg}); truth-R unaligned ATE")
    print(f"  zero output {score(lambda X: np.zeros((len(X), 3)), val, 'imu_1s'):.3f}")
    res = {}
    for g in ["imu_1s", "flow", "flow+imu_1s"]:
        X = np.concatenate([group(d, g)[5::2] for _, d in train]); Y = np.concatenate([d["v_body"][5::2] for _, d in train])
        for m, fit in [("ridge", lambda X, Y: ridge_fit(X, Y, 1e-3)), ("gp-rff", lambda X, Y: rff_gp_fit(X, Y, 1.0)),
                       ("mlp", mlp_fit)]:
            r = score(fit(X, Y), val, g)
            res[f"{g}/{m}"] = r
            print(f"  {g:12s} {m:7s} {r:.3f}", flush=True)
    data = {key:[{"path":path,"sha256":digest(path),"scene":str(row["scene"])} for path,row in group]
            for key,group in (("train",train),("development",val))}
    directory, manifest = open_run("handbuilt",config(),data)
    write(directory/"scores.json",{"truth_attitude_only":res})
    manifest["status"]="completed"
    write(directory/"manifest.json",manifest)
    print(directory)


if __name__ == "__main__":
    main()
