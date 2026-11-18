"""Causal orientation shared by proxy preprocessing and guest replay."""
from collections import deque
from math import sqrt, sin, cos

import cv2
import numpy as np


def exp_so3(w):
    x, y, z = w
    a = sqrt(x*x+y*y+z*z)
    cross = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    if a < 1e-8:
        return np.eye(3) + cross + 0.5 * cross @ cross
    return np.eye(3) + (sin(a) / a) * cross + ((1 - cos(a)) / a**2) * cross @ cross


def window_quantile(values, fraction):
    """Linear quantile on a short rolling calibration window."""
    ordered=np.sort(values,axis=0)
    rank=fraction*(len(ordered)-1)
    left=int(rank)
    fraction=rank-left
    return ordered[left] if fraction==0 else ordered[left]*(1-fraction)+ordered[left+1]*fraction


class Orientation:
    def __init__(self, cfg, initial=None):
        self.cfg = cfg
        self.R = np.eye(3) if initial is None else initial.copy()
        self.bias = np.zeros(3)
        self.learned_bias = np.zeros(3)
        self.rolling = deque()
        self.accepted_at = None
        self.last_rolling_check = 0.
        self.elapsed = 0.0
        self.previous = None
        self.origin = None
        self.total = np.zeros(3)
        self.weight = 0.0
        self.evidence = True
        self.done = False
        self.activated = False
        self.checked_windows = self.rejected_windows = 0

    @property
    def total_bias(self):
        return self.bias + self.learned_bias

    def update_feedback(self, correction, dt, available):
        if available and np.isfinite(correction).all():
            weight = -np.expm1(-max(dt,0.) / .8)
            self.learned_bias += weight*(np.clip(correction,-.12,.12)-self.learned_bias)

    def rolling_update(self, t, packet, image_difference):
        if len(packet):
            self.rolling.append((t, packet[:,4:7].mean(0),
                                 window_quantile(np.abs(np.linalg.norm(packet[:,1:4],axis=1)-9.81),.5),
                                 image_difference))
        window = self.cfg["startup_seconds"]
        while self.rolling and self.rolling[0][0] < t-window:
            self.rolling.popleft()
        if t-self.last_rolling_check < .2 or len(self.rolling)<8:
            return
        self.last_rolling_check = t
        if t-self.rolling[0][0] < .8*window:
            return
        _, gyro, accel, image = zip(*self.rolling)
        rates = np.asarray(gyro)
        center = window_quantile(rates,.5)
        calm = (np.linalg.norm(center)<.10 and
                window_quantile(np.linalg.norm(rates-center,axis=1),.8)<.055 and
                window_quantile(accel,.5)<.45 and window_quantile(image,.8)<.018)
        self.checked_windows += 1
        self.rejected_windows += not calm
        if calm:
            self.bias = center if not self.activated else .9*self.bias+.1*center
            if not self.activated:
                self.accepted_at = t-self.origin
            self.activated = True

    def step(self, t, packet, image_difference):
        if self.origin is None:
            self.origin = self.previous = t
            return self.R.copy()
        duration = t - self.previous
        self.elapsed = t - self.origin
        if not self.done and self.cfg["policy"] in ("startup","evidence"):
            if len(packet):
                gyro = packet[:, 4:7].mean(0)
                accel_norm = np.linalg.norm(packet[:, 1:4], axis=1)
                self.total += gyro * duration
                self.weight += duration
                self.evidence &= (np.linalg.norm(gyro) < self.cfg["still_gyro"]
                                  and np.max(np.abs(accel_norm - 9.81)) < self.cfg["still_accel"]
                                  and image_difference < self.cfg["still_image_difference"])
            else:
                self.evidence = False
        if len(packet):
            last_rate = packet[0, 4:7]
            bias = self.total_bias
            for row in packet:
                row_time = max(self.previous,min(float(row[0]),t))
                self.R = self.R @ exp_so3((row[4:7] - bias) * (row_time - self.previous))
                self.previous = row_time
                last_rate = row[4:7]
            self.R = self.R @ exp_so3((last_rate - bias) * (t - self.previous))
        self.previous = t
        if not self.done and self.elapsed + 1e-8 >= self.cfg["startup_seconds"]:
            self.done = True
            if self.cfg["policy"] in ("startup", "evidence"):
                self.checked_windows += 1
            if self.weight and (self.cfg["policy"] == "startup" or
                                (self.cfg["policy"] == "evidence" and self.evidence)):
                self.bias = self.total / self.weight
                self.activated = True
                self.accepted_at = self.elapsed
            elif self.cfg["policy"] in ("startup", "evidence"):
                self.rejected_windows += 1
        if self.cfg["policy"] == "rolling":
            self.rolling_update(t,packet,image_difference)
        return self.R.copy()


def visual_rotation(first, last, K, camera_rotation):
    p = cv2.goodFeaturesToTrack(first, 100, .015, 4)
    if p is None or len(p) < 12:
        return None
    q, status, _ = cv2.calcOpticalFlowPyrLK(first, last, p, None)
    if q is None:
        return None
    back, valid, _ = cv2.calcOpticalFlowPyrLK(last, first, q, None)
    if back is None:
        return None
    good = (status.ravel() > 0) & (valid.ravel() > 0) & (np.linalg.norm((back-p)[:,0], axis=1) < .8)
    a, b = p[good,0], q[good,0]
    if len(a) < 12:
        return None
    inverse = np.linalg.inv(K)
    old = (inverse @ np.c_[a, np.ones(len(a))].T).T
    new = (inverse @ np.c_[b, np.ones(len(b))].T).T
    predicted = old @ camera_rotation
    z = predicted[:, 2]
    if np.any(z < .1):
        return None
    xy = predicted[:, :2] / z[:, None]
    residual = new[:, :2] - xy
    x, y = xy.T
    X = np.stack((np.column_stack((-x*y, 1+x*x, -y)),
                  np.column_stack((-1-y*y, x*y, x))), axis=1)
    # Only the rotation-focused gate uses this fit. Broad parallax or large post-fit
    # residuals suppress updates. Spatially varying translation remains a confound.
    weight = np.ones(len(x))
    delta = np.zeros(3)
    for _ in range(3):
        A = (X*weight[:,None,None]).reshape(-1, 3)
        delta = np.linalg.lstsq(A, (weight[:,None]*residual).ravel(), rcond=None)[0]
        error = np.linalg.norm(residual - X @ delta, axis=1)
        weight = np.sqrt(np.minimum(1, .012 / np.maximum(error, 1e-8)))
    err = float(np.median(error))
    spread = np.linalg.svd(A, compute_uv=False)
    return -delta, err, len(a), float(spread[-1]/spread[0]), np.median(residual, axis=0)


def rotation_proposal(first, last, K, R_bc, relative, bias, duration, method, coefficients):
    visual = visual_rotation(first, last, K, R_bc.T @ relative @ R_bc)
    if visual is None:
        return None, False, np.zeros(3)
    correction, error, support, conditioning, median = visual
    body = R_bc @ correction
    feat = np.r_[body, error, support/100, conditioning, median,
                 cv2.Rodrigues(relative)[0].ravel(), bias, duration]
    gated = error < .018 and conditioning > .10 and np.linalg.norm(body) < .12
    update = np.zeros(3)
    if gated and method == "geometry":
        update = .35*body
    if gated and method == "learned":
        update = np.r_[feat, 1.] @ coefficients
        norm = np.linalg.norm(update)
        update *= min(1., .04/max(norm, 1e-10))
    return feat, bool(gated), update
