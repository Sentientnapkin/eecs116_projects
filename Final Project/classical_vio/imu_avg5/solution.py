"""One propagation per camera interval using the latest five IMU readings."""

import numpy as np

from batched import Solution as Batched


class Solution(Batched):
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
