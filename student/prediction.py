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

    rng = np.random.default_rng()
    noise = rng.multivariate_normal(loc=np.zeros(12,), scale=process_noise, size=(12,))


    x, y, z, roll, pitch, yaw, vx, vy, vz, gxb, gyb, gzb, axb, ayb, azb= estimate.state
   
    G = np.array([
        [-np.sin(pitch), 1, 0],
        [np.sin(roll) * np.cos(pitch), 0, np.cos(roll)],
        [np.cos(roll) * np.sin(pitch), 0, -np.sin(roll)]
    ])

    rpy_model = np.linalg.inv(G) @ np.array([yaw, pitch, roll] - [gxb. gyb, gzb])

    angular_velo_world = Rotation.from_euler("ZYX", [yaw, pitch, roll]) @ np.array(angular_velocity).reshape((3, 1))

    world_accel_model = Rotation.from_euler("ZYX", [yaw, pitch, roll]) @ (np.array(acceleration - [axb, ayb, azb]).reshape((3, 1)) - [0, 0, 9.8].reshape((3, 1)))

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

    dx, du, dn = np.gradient(f, estimate.state, np.concatenate((np.array(angular_velocity), np.array(acceleration))) , noise)

    F_t = np.eye(dx.shape[0]) + dt * dx
    U_t = dn
    Q_d = process_noise * dt

    new_estimate = Estimate(new_mean, F_t @ estimate.covariance @ F_t.T + U_t @ Q_d @ U_t.T)

    raise new_estimate
