"""Student exercise: implement the IMU prediction shared by both parts."""

import numpy as np
from numpy.typing import ArrayLike
from scipy.spatial.transform import Rotation

from support import Estimate


def predict(
    estimate: Estimate,
    angular_velocity: ArrayLike,
    acceleration: ArrayLike,
    dt: float,
    process_noise: ArrayLike,
) -> Estimate:
    """Return an Estimate with the propagated state (15,) and covariance (15, 15).

    IMU vectors have shape (3,) and dt is seconds. process_noise is the (12, 12)
    continuous-time noise intensity Q, ordered as gyroscope noise, accelerometer
    noise, gyroscope bias drift, accelerometer bias drift (three axes each).
    For gravity use 9.8 m/s^2.
    """

    x, y, z, roll, pitch, yaw, vx, vy, vz, gxb, gyb, gzb, axb, ayb, azb= estimate.state
   
    G = np.array([
        [1, 0, -np.sin(pitch)],
        [0, np.cos(roll), np.sin(roll) * np.cos(pitch)],
        [0, -np.sin(roll), np.cos(roll) * np.cos(pitch)]
    ])

    G_dot_roll = np.array([
        [0, 0, 0],
        [0, -np.sin(roll), np.cos(roll) * np.cos(pitch)],
        [0, -np.cos(roll), -np.sin(roll) * np.cos(pitch)],
    ])

    G_dot_pitch = np.array([
        [0, 0, -np.cos(pitch)],
        [0, 0, -np.sin(roll) * np.sin(pitch)],
        [0, 0, -np.cos(roll) * np.sin(pitch)]
    ])

    G_inv = np.linalg.inv(G)

    g_dot_roll_inv = -G_inv @ G_dot_roll @ G_inv

    g_dot_pitch_inv = -G_inv @ G_dot_pitch @ G_inv

    w_bar = np.asarray(angular_velocity) - np.array([gxb, gyb, gzb])

    rpy_model = G_inv @ w_bar

    R = Rotation.from_euler("ZYX", [yaw, pitch, roll]).as_matrix()

    a_bar = np.asarray(acceleration) - np.array([axb, ayb, azb])

    world_accel_model = np.array([0, 0, -9.8]) + R @ a_bar

    R_yaw = Rotation.from_euler("ZYX", [yaw, 0, 0]).as_matrix()

    R_yaw_dot = np.array([
        [-np.sin(yaw), -np.cos(yaw), 0],
        [np.cos(yaw), -np.sin(yaw), 0],
        [0, 0, 0]
    ])

    R_pitch = Rotation.from_euler("ZYX", [0, pitch, 0]).as_matrix()

    R_pitch_dot = np.array([
        [-np.sin(pitch), 0, np.cos(pitch)],
        [0, 0, 0],
        [-np.cos(pitch), 0, -np.sin(pitch)]
    ])

    R_roll = Rotation.from_euler("ZYX", [0, 0, roll]).as_matrix()

    R_roll_dot = np.array([
        [0, 0, 0],
        [0, -np.sin(roll), -np.cos(roll)],
        [0, np.cos(roll), -np.sin(roll)]
    ])

    Jacob_yaw = R_yaw_dot @ R_pitch @ R_roll
    Jacob_pitch = R_yaw @ R_pitch_dot @ R_roll
    Jacob_roll = R_yaw @ R_pitch @ R_roll_dot

    f = np.array([
            vx,
            vy,
            vz,
            rpy_model[0],
            rpy_model[1],
            rpy_model[2],
            world_accel_model[0],
            world_accel_model[1],
            world_accel_model[2],
            0,
            0,
            0,
            0,
            0,
            0
        ])

    A = np.zeros((15, 15))

    A[0:3, 6:9] = np.eye(3)

    A[3:6, 3] = g_dot_roll_inv @ w_bar
    A[3:6, 4] = g_dot_pitch_inv @ w_bar

    A[3:6, 9:12] = -G_inv

    A[6:9, 3] = Jacob_roll @ a_bar
    A[6:9, 4] = Jacob_pitch @ a_bar
    A[6:9, 5] = Jacob_yaw @ a_bar

    A[6:9, 12:15] = -R


    U = np.zeros((15, 12))

    U[3:6, 0:3] = -G_inv
    U[6:9, 3:6] = -R

    U[9:12, 6:9] = np.eye(3)
    U[12:15, 9:12] = np.eye(3)

    new_mean = np.array([
        x + vx * dt,
        y + vy * dt,
        z + vz * dt,
        roll + rpy_model[0] * dt,
        pitch + rpy_model[1] * dt,
        yaw + rpy_model[2] * dt,
        vx + world_accel_model[0] * dt,
        vy + world_accel_model[1] * dt,
        vz + world_accel_model[2] * dt,
        gxb,
        gyb,
        gzb,
        axb,
        ayb,
        azb
    ])

    F = np.eye(15) + dt * A

    Q_d = np.asarray(process_noise) * dt

    new_covariance = F @ estimate.covariance @ F.T + U @ Q_d @ U.T
    return Estimate(new_mean, new_covariance)
