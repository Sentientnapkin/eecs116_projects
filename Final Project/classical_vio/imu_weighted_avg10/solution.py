"""Stage 10: one timestamp-weighted inertial update per camera frame."""

import numpy as np

GRAVITY = 9.81


# Rotation helpers follow VIOBench's Python dead-reckoning example.
def matrix_to_quaternion(R):
    trace = np.trace(R)
    if trace > 0:
        s = np.sqrt(trace + 1.0) * 2
        return np.array([(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s])
    i = int(np.argmax(np.diag(R)))
    j, k = (i + 1) % 3, (i + 2) % 3
    s = np.sqrt(1.0 + R[i, i] - R[j, j] - R[k, k]) * 2
    q = np.empty(4)
    q[i] = 0.25 * s
    q[j] = (R[j, i] + R[i, j]) / s
    q[k] = (R[k, i] + R[i, k]) / s
    q[3] = (R[k, j] - R[j, k]) / s
    return q / np.linalg.norm(q)


def exp_so3(omega):
    angle = np.linalg.norm(omega)
    if angle < 1e-12:
        return np.eye(3)
    k = omega / angle
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * K @ K


class Solution:
    frame_width = 320

    def __init__(self, config):
        T_cam_imu = np.asarray(config["T_cam_imu"], dtype=float)
        self.R_cam_imu = T_cam_imu[:3, :3]
        self.camera_offset = -self.R_cam_imu.T @ T_cam_imu[:3, 3]

        # The integration frame is the IMU frame at the first image.
        self.R_world_imu = np.eye(3)
        self.position = np.zeros(3)
        self.velocity = np.zeros(3)
        self.gravity = np.array([0.0, 0.0, -GRAVITY])
        self.last_time = None
        self.accel = -self.gravity.copy()
        self.gyro = np.zeros(3)

    def _propagate(self, dt, accel, gyro):
        rotation_step = gyro * dt
        R_mid = self.R_world_imu @ exp_so3(0.5 * rotation_step)
        acceleration = R_mid @ accel + self.gravity
        self.position += self.velocity * dt + 0.5 * acceleration * dt**2
        self.velocity += acceleration * dt
        self.R_world_imu = self.R_world_imu @ exp_so3(rotation_step)

    def step(self, t, frame, imu):
        if self.last_time is None:
            # The first batch precedes the pose origin. Use it only to seed
            # gravity and rates. The gravity estimate assumes low acceleration.
            if len(imu):
                mean_accel = imu[:, 1:4].mean(axis=0)
                norm = np.linalg.norm(mean_accel)
                if norm > 1e-6:
                    self.gravity = -GRAVITY * mean_accel / norm
                self.accel, self.gyro = imu[-1, 1:4].copy(), imu[-1, 4:7].copy()
            self.last_time = t
        elif t > self.last_time:
            dt = t - self.last_time
            if len(imu):
                # Use Stage 1's sample intervals, including the final hold
                # from the last valid sample to the image timestamp.
                times = np.clip(imu[:, 0], self.last_time, t)
                durations = np.diff(times, prepend=self.last_time)
                valid = np.flatnonzero(durations > 0)
                if len(valid):
                    latest = valid[-1]
                    durations[latest] += t - times[latest]
                    accel, gyro = (durations @ imu[:, 1:] / dt).reshape(2, 3)
                    self.accel, self.gyro = imu[latest, 1:4].copy(), imu[latest, 4:7].copy()
                else:
                    accel, gyro = self.accel, self.gyro
            else:
                accel, gyro = self.accel, self.gyro
            self._propagate(dt, accel, gyro)
            self.last_time = t

        # The first camera center lies at camera_offset in the integration frame.
        R = self.R_world_imu
        R_c0_camera = self.R_cam_imu @ R @ self.R_cam_imu.T
        p_c0_camera = self.R_cam_imu @ (self.position + R @ self.camera_offset - self.camera_offset)
        q = matrix_to_quaternion(R_c0_camera)

        omega = self.gyro
        v_camera = self.R_cam_imu @ (R.T @ self.velocity + np.cross(omega, self.camera_offset))
        w_camera = self.R_cam_imu @ omega
        return np.concatenate([p_c0_camera, q / np.linalg.norm(q), v_camera, w_camera])
