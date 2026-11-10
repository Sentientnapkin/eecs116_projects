"""Causal IMU integration experiments on the Stage 10 pose/output model."""

import numpy as np

from batched import Solution as Batched, exp_so3


class RollingAverage(Batched):
    sample_count = 5

    def __init__(self, config):
        super().__init__(config)
        self.history = np.empty((0, 6))

    def step(self, t, frame, imu):
        # Include the first packet in history while keeping the shared startup.
        if len(imu):
            self.history = np.concatenate((self.history, imu[:, 1:]))[-self.sample_count:].copy()
        return super().step(t, frame, imu)

    def _integrate_window(self, t, imu):
        if len(imu):
            self.accel, self.gyro = imu[-1, 1:4].copy(), imu[-1, 4:7].copy()
        accel, gyro = self.history.mean(axis=0).reshape(2, 3) if len(self.history) else (self.accel, self.gyro)
        self._propagate(t - self.last_time, accel, gyro)
        self.last_time = t


class Average15(RollingAverage):
    sample_count = 15


class Average20(RollingAverage):
    sample_count = 20


class PreviousReading(Batched):
    def _integrate_window(self, t, imu):
        self._propagate(t - self.last_time, self.accel, self.gyro)
        if len(imu):
            self.accel, self.gyro = imu[-1, 1:4].copy(), imu[-1, 4:7].copy()
        self.last_time = t


class Hold109(Batched):
    def __init__(self, config):
        super().__init__(config)
        self.held = None
        self.remaining = 109

    def _integrate_window(self, t, imu):
        if self.held is None:
            self.held = (self.accel, self.gyro)
        start = self.last_time
        first = 0
        while first + self.remaining <= len(imu):
            boundary = first + self.remaining - 1
            end = float(np.clip(imu[boundary, 0], start, t))
            self._propagate(end - start, *self.held)
            self.held = (imu[boundary, 1:4].copy(), imu[boundary, 4:7].copy())
            self.remaining = 109
            start, first = end, boundary + 1
        self.remaining -= len(imu) - first
        self._propagate(t - start, *self.held)
        if len(imu):
            self.accel, self.gyro = imu[-1, 1:4].copy(), imu[-1, 4:7].copy()
        self.last_time = t


class SampleSteps(Batched):
    group_size = 1
    subdivisions = 1

    def _integrate_window(self, t, imu):
        if not len(imu):
            self._propagate(t - self.last_time, self.accel, self.gyro)
            self.last_time = t
            return
        times = np.clip(imu[:, 0], self.last_time, t)
        durations = np.diff(times, prepend=self.last_time)
        durations[-1] += t - times[-1]
        for first in range(0, len(imu), self.group_size):
            last = first + self.group_size
            weights = durations[first:last]
            dt = float(weights.sum())
            if dt <= 0.0:
                continue
            values = imu[first:last, 1:]
            accel, gyro = (weights @ values / dt if len(values) > 1 else values[0]).reshape(2, 3)
            for _ in range(self.subdivisions):
                self._propagate(dt / self.subdivisions, accel, gyro)
        self.accel, self.gyro = imu[-1, 1:4].copy(), imu[-1, 4:7].copy()
        self.last_time = t


class FiveSteps(SampleSteps):
    group_size = 2


class TwentySteps(SampleSteps):
    subdivisions = 2


def taylor_rotation(vector):
    x, y, z = vector
    squared_angle = x*x + y*y + z*z
    if squared_angle > 0.04:
        return exp_so3(vector)
    cross = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    sinc = 1.0 + squared_angle * (-1.0/6.0 + squared_angle * (1.0/120.0 - squared_angle/5040.0))
    cosc = 0.5 + squared_angle * (-1.0/24.0 + squared_angle * (1.0/720.0 - squared_angle/40320.0))
    return np.eye(3) + sinc * cross + cosc * (cross @ cross)


class TaylorTen(SampleSteps):
    def _propagate(self, dt, accel, gyro):
        half = taylor_rotation(gyro * (0.5 * dt))
        midpoint = self.R_world_imu @ half
        acceleration = midpoint @ accel + self.gravity
        self.position += (self.velocity + 0.5 * acceleration * dt) * dt
        self.velocity += acceleration * dt
        self.R_world_imu = midpoint @ half


class ReuseMidpoint(Batched):
    def _propagate(self, dt, accel, gyro):
        half = exp_so3(gyro * (0.5 * dt))
        midpoint = self.R_world_imu @ half
        acceleration = midpoint @ accel + self.gravity
        self.position += (self.velocity + 0.5 * acceleration * dt) * dt
        self.velocity += acceleration * dt
        self.R_world_imu = midpoint @ half
