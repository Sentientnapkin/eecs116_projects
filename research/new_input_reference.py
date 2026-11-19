"""Sensor-only causal Python reference for the newly trained kf_grid_native input policy.

The original rolling preprocessing remains an explicit parallel path because training
re-derived its float32 feature tensors and its stored rotation increments. No ground
truth is accepted by either streaming class. This reproduces that transformation,
including its documented noncommuting-rate approximation for startup history.
"""
from collections import deque

import cv2
import numpy as np

from attitude_bias import GYRO_INIT, GYRO_WALK, GYRO_WHITE, grid_rotation, gray, integrate_packet
from input_attitude import counts, still_window
from orientation import exp_so3
from streaming import Inputs, portable_warp


class NativeGridAttitude:
    """Streaming transcription of attitude_bias.attitudes(..., 'kf_grid')."""

    def __init__(self, camera, R_bc):
        cv2.setRNGSeed(217)
        self.K = np.array([[camera['fx'], 0, camera['cx']], [0, camera['fy'], camera['cy']], [0, 0, 1.0]])
        self.R_bc = np.asarray(R_bc, dtype=np.float64)
        self.R = np.eye(3)
        self.bias = np.zeros(3)
        self.P = np.full(3, GYRO_INIT ** 2)
        self.previous = self.previous_t = None
        self.anchor_t = None
        self.anchor_R = np.eye(3)
        self.anchor_image = None
        self.startup = []
        self.decided = False
        self.accepted = self.rejected = 0
        self.last_window = None

    def step(self, t, image, packet):
        if self.previous is None:
            self.previous = self.previous_t = self.anchor_t = float(t)
            self.anchor_image = gray(image).copy()
            return self.R.copy(), self.bias.copy()
        if not self.decided and (not len(packet) or packet[0, 0] >= 0.8):
            self.decided = True
            still = np.concatenate([x[1] for x in self.startup if len(x[1])]) if self.startup else np.empty((0, 7))
            if len(still) > 40:
                rates, accel = still[:, 4:7], np.linalg.norm(still[:, 1:4], axis=1)
                if (np.linalg.norm(rates.mean(0)) < .1 and rates.std(0).max() < .12
                        and abs(accel.mean() - 9.81) < .3 and accel.std() < .5):
                    self.bias = rates.mean(0)
                    self.P = np.full(3, GYRO_WHITE ** 2 / len(rates) + 1e-8)
                    self.R, self.previous = np.eye(3), 0.0
                    for tj, pj in self.startup:
                        self.R, self.previous = integrate_packet(self.R, self.previous, tj, pj, self.bias)
            self.startup.clear()
        if not self.decided:
            self.startup.append((float(t), packet.copy()))
        self.R, self.previous = integrate_packet(self.R, self.previous, t, packet, self.bias)
        self.P += GYRO_WALK ** 2 * (t - self.previous_t)
        self.previous_t = float(t)
        if t - self.anchor_t >= .5 - 1e-8:
            dt = t - self.anchor_t
            relative = self.R_bc.T @ (self.anchor_R.T @ self.R) @ self.R_bc
            delta, sigma = grid_rotation(self.anchor_image, gray(image), self.K, relative)
            accepted = delta is not None and np.linalg.norm(delta) <= .05
            self.last_window = dict(t=float(t), accepted=bool(accepted),
                                    delta=None if delta is None else np.asarray(delta).tolist(),
                                    reason=None if delta is not None else sigma)
            if accepted:
                residual = self.R_bc @ delta
                variance = (sigma / dt) ** 2
                gain = self.P / (self.P + variance)
                self.bias += gain * (-residual / dt)
                self.P = (1 - gain) * self.P
                self.accepted += 1
            else:
                self.rejected += 1
            self.anchor_t = float(t)
            self.anchor_R = self.R.copy()
            self.anchor_image = gray(image).copy()
        return self.R.copy(), self.bias.copy()


class NewInputReference:
    """Faithful incremental version of derive(rolling_row, kf_grid, raw_external).

    Input packets/timestamps are relative to the first camera, and its packet is
    deliberately discarded. A changed activation state never rewrites emitted data.
    """

    def __init__(self, sensor, camera, shape, R_bc, native_attitude=None):
        cfg = dict(sensor, policy='rolling')
        self.base = Inputs(cfg, camera, shape, R_bc)
        self.attitude = native_attitude or NativeGridAttitude(camera, R_bc)
        self.R_bc = np.asarray(R_bc, dtype=np.float64)
        self.history = deque()
        self.original_imu = []
        self.original_R = []
        self.original_steps = []
        self.previous = None
        self.before_bias = np.zeros(3)
        self.decided = False
        self.static_bias = np.zeros(3)
        self.rewarp_K = self.rewarp_inverse = None
        self.trace = None

    def step(self, t, image, packet):
        first = self.previous is None
        packet = np.asarray(packet, dtype=np.float64)
        if first:
            packet = np.empty((0, 7), dtype=np.float64)
        original_images, original_imu, rolling_R, _ = self.base.step(t, image, packet, 'triple_derot')
        old_imu = original_imu.astype(np.float64)
        original_bias = old_imu[43:46] + old_imu[46:49]
        dt = 0.0 if first else float(t - self.previous)
        dR = np.eye(3) if first else self.original_R[-1].T @ rolling_R
        self.original_steps.append((dR, self.before_bias.copy(), dt, bool(old_imu[12] > 0)))
        self.original_imu.append(original_imu.copy())
        self.original_R.append(rolling_R.copy())
        self.before_bias = original_bias.copy()
        if first:
            h, w = original_images.shape[-2:]
            fx = float(old_imu[14]) * w
            self.rewarp_K = np.array([[fx, 0, (w - 1) / 2], [0, fx, (h - 1) / 2], [0, 0, 1.]])
            self.rewarp_inverse = np.linalg.inv(self.rewarp_K)
        if not first and not self.decided and (not old_imu[12] or self.previous >= .8 - 1e-6):
            self.decided = True
            u = np.stack(self.original_imu)
            b = still_window(u.astype(np.float64), counts(u.astype(np.float64)), len(u) - 1)
            if b is not None:
                self.static_bias = b
                reconstructed = np.eye(3)
                rotations = {0: reconstructed.copy()}
                for j in range(1, len(self.original_steps) - 1):
                    delta, old_bias, step_dt, has = self.original_steps[j]
                    reconstructed = reconstructed @ (delta @ exp_so3((old_bias - b) * step_dt) if has else delta)
                    rotations[j] = reconstructed.copy()
                self.history = deque((tj, index, frame, rotations[index])
                                     for tj, index, frame, old_R in self.history)
        R, bias = self.attitude.step(t, image, packet)
        imu = original_imu.copy()
        shift = original_bias - bias
        imu[3:6] = (old_imu[3:6] + shift * old_imu[12]).astype(np.float32)
        for i in range(4):
            cols = slice(18 + 7 * i, 21 + 7 * i)
            imu[cols] = (old_imu[cols] + shift * float(old_imu[21 + 7 * i] > 0)).astype(np.float32)
        imu[43:46] = bias.astype(np.float32)
        imu[49] = float(self.decided and np.any(bias != 0))
        images = original_images.copy()
        images[1:] = 0
        for index, age in enumerate((.25, 1.0)):
            match = next((row for row in reversed(self.history) if row[0] <= t - age + 1e-8), None)
            if match is None:
                continue
            _, _, frame, previous_R = match
            rotation = self.R_bc.T @ R.T @ previous_R @ self.R_bc
            inverse = self.rewarp_K @ rotation.T @ self.rewarp_inverse
            images[1 + index], images[3 + index] = portable_warp(frame, inverse, self.base.pixels, True)
        k = len(self.original_imu) - 1
        if old_imu[50] > 0:
            self.history.append((float(t), k, original_images[0].copy(), R.copy()))
        while len(self.history) > 2 and self.history[1][0] <= t - 1.0 + 1e-8:
            self.history.popleft()
        self.previous = float(t)
        if self.trace is not None:
            self.trace.update(bias=bias.copy(), decided=self.decided, rolling_imu=original_imu.copy(),
                              rolling_R=rolling_R.copy(), raw_decided=self.attitude.decided)
        return images, imu, R, (imu[3:6].astype(np.float64) if len(packet) else np.zeros(3))


def replay_inputs(sensor, camera, frames, times, packets, R_bc):
    state = NewInputReference(sensor, camera, frames[0].shape[:2], R_bc)
    images, imu, rotations = [], [], []
    for t, frame, packet in zip(times, frames, packets):
        im, u, R, _ = state.step(float(t), frame, packet)
        images.append(im); imu.append(u); rotations.append(R)
    return {'images': np.stack(images), 'imu': np.stack(imu), 'R': np.stack(rotations)}, state
