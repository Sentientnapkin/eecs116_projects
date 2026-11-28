"""Stage-3 feature set for the cheap MLP guest (mlp_fit.py FEAT=s3b). Every feature is causal and cheap in C.

Per frame k (fit_cheap.prep conventions: gyro mean of rows GROWS in camera axes, attitude R_k = camera k in camera 0):
  x[0:10]   fit_cheap gabs2 features: 1, EMA_0.25s(g), EMA_1s(g), |EMA_1s(g)|
  f_k       mean of accel rows AROWS in camera axes (specific force)
  gc        = -f_0                         gravity in camera-0 axes, assuming frame 0 is unaccelerated
  a_k       = R_k f_k + gc                 acceleration in camera-0 axes (no drag: tilt -> acceleration)
  x[10:13]  R_k^T gc / 9.81                tilt: gravity direction in camera-k axes
  x[13:16]  R_k^T u_1,  x[16:19] R_k^T u_4 u_t = leaky integral of a, time constant t s (recent velocity change)
  x[19]     hover-start flag: 1 from frame 20 on if the first 20 frames had gyro RMS < HOVER_G and
            specific-force RMS deviation < HOVER_A, else 0
"""
import os

import numpy as np

import fit_cheap as fc

DT = fc.DT
AROWS = [int(c) for c in os.environ.get("S3_AROWS", "27")]
TAUS = (1.0, 4.0)
HOVER_G, HOVER_A, HOVER_N = 0.15, 0.3, 20
NF = 20


def prep(f):
    R, X0 = fc.prep(f)
    Rbc = f["Tbc"][:3, :3]
    fs = f["imu"][:, AROWS, 1:4].mean(1) @ Rbc
    gc = -fs[0]
    n = len(X0)
    X = np.zeros((n, NF))
    X[:, :10] = X0
    u = np.zeros((len(TAUS), 3))
    g = f["imu"][:, fc.GROWS, 4:7].mean(1) @ Rbc
    gs = np.sqrt((g[:HOVER_N] ** 2).sum(1).mean())
    asd = np.sqrt(((fs[:HOVER_N] - fs[:HOVER_N].mean(0)) ** 2).sum(1).mean())
    hover = float(gs < HOVER_G and asd < HOVER_A)
    for k in range(n):
        a = R[k] @ fs[k] + gc
        for j, t in enumerate(TAUS):
            u[j] = u[j] * (1 - DT / t) + DT * a
        X[k, 10:13] = R[k].T @ gc / 9.81
        X[k, 13:16] = R[k].T @ u[0]
        X[k, 16:19] = R[k].T @ u[1]
        X[k, 19] = hover if k >= HOVER_N else 0.0
    return R, X
