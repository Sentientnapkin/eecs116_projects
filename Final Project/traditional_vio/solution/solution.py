"""116_traditional_combination: inertial prediction and keyframe translation updates."""

import numpy as np

from traditional_combination import (
    INITIAL_VARIANCE, camera_innovation, correct_covariance, predict_covariance, skew,
)
from vision import VisualOdometry

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
    K = skew(omega / angle)
    return np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * K @ K


class Solution:
    frame_width = 320

    def __init__(self, config):
        self.vision = VisualOdometry(config)
        self.visual_motion = None
        self.visual_update_applied = False
        self.covariance = np.diag(INITIAL_VARIANCE)
        self.key_position = None
        self.key_rotation = None
        self.key_covariance = None
        self.key_cross = None
        T_cam_imu = np.asarray(config["T_cam_imu"], dtype=float)
        self.R_cam_imu = T_cam_imu[:3, :3]
        self.camera_offset = -self.R_cam_imu.T @ T_cam_imu[:3, 3]

        # The integration frame is the IMU frame at the first image.
        self.R_world_imu = np.eye(3)
        self.position = np.zeros(3)
        self.velocity = np.zeros(3)
        self.gyro_bias = np.zeros(3)
        self.accel_bias = np.zeros(3)
        self.gravity = np.array([0.0, 0.0, -GRAVITY])
        self.last_time = None
        self.accel = -self.gravity.copy()
        self.gyro = np.zeros(3)

    def _propagate(self, dt):
        # Project 1's bias-corrected inertial model, with rotation increments
        # applied directly and acceleration evaluated at the midpoint attitude.
        rotation_step = (self.gyro - self.gyro_bias) * dt
        R_mid = self.R_world_imu @ exp_so3(0.5 * rotation_step)
        R_step = exp_so3(rotation_step)
        specific_force = self.accel - self.accel_bias
        acceleration = R_mid @ specific_force + self.gravity
        self.position += self.velocity * dt + 0.5 * acceleration * dt**2
        self.velocity += acceleration * dt
        self.R_world_imu = self.R_world_imu @ R_step
        self.covariance, self.key_cross = predict_covariance(
            self.covariance, self.key_cross, R_mid, R_step, specific_force, dt,
        )

    def _correct(self):
        residual, H, noise = camera_innovation(
            self.position, self.R_world_imu, self.key_position, self.key_rotation,
            self.R_cam_imu, self.camera_offset, self.visual_motion, min(self.vision.focal),
        )
        result = correct_covariance(
            self.covariance, self.key_cross, self.key_covariance, residual, H, noise,
        )
        if result is None:
            return

        correction, self.covariance = result
        self.position += correction[:3]
        self.R_world_imu = self.R_world_imu @ exp_so3(correction[3:6])
        self.velocity += correction[6:9]
        self.gyro_bias += correction[9:12]
        self.accel_bias += correction[12:15]
        self.visual_update_applied = True

    def _reset_keyframe(self):
        self.vision.reset_keyframe()
        self.key_position = self.position.copy()
        self.key_rotation = self.R_world_imu
        self.key_covariance = self.covariance[:6, :6]
        self.key_cross = self.covariance[:, :6]

    def step(self, t, frame, imu):
        self.visual_update_applied = False
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
        else:
            for sample_time, ax, ay, az, gx, gy, gz in imu:
                # The ABI allows a floating-point tolerance at the frame boundary.
                sample_time = min(sample_time, t)
                if sample_time > self.last_time:
                    self.accel = np.array([ax, ay, az])
                    self.gyro = np.array([gx, gy, gz])
                    self._propagate(sample_time - self.last_time)
                    self.last_time = sample_time
            if t > self.last_time:
                self._propagate(t - self.last_time)
                self.last_time = t
        C = self.R_cam_imu
        # No visual correction occurs within a keyframe interval. This relative
        # orientation therefore comes from the bias-corrected gyro integration.
        relative_rotation = None
        if self.key_rotation is not None:
            relative_rotation = C @ self.key_rotation.T @ self.R_world_imu @ C.T
        self.visual_motion = self.vision.step(frame, relative_rotation)
        if self.visual_motion is not None:
            self._correct()
        # Use a track set for at most one EKF update. Clone the corrected pose
        # when starting fresh so the filter does not reuse correlated tracks.
        if self.key_rotation is None or self.visual_motion is not None or self.vision.needs_keyframe:
            self._reset_keyframe()

        # The first camera center lies at camera_offset in the integration frame.
        R = self.R_world_imu
        R_c0_camera = self.R_cam_imu @ R @ self.R_cam_imu.T
        p_c0_camera = self.R_cam_imu @ (self.position + R @ self.camera_offset - self.camera_offset)
        q = matrix_to_quaternion(R_c0_camera)

        omega = self.gyro - self.gyro_bias
        v_camera = self.R_cam_imu @ (R.T @ self.velocity + np.cross(omega, self.camera_offset))
        w_camera = self.R_cam_imu @ omega
        return np.concatenate([p_c0_camera, q / np.linalg.norm(q), v_camera, w_camera])
