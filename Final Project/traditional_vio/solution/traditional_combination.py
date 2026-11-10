"""Direct position redirection and a velocity-only Kalman correction."""

import numpy as np


# Project 1's accelerometer process-noise intensity, in (m/s²)² per Hz.
ACCEL_NOISE = 0.01
INITIAL_VELOCITY_VARIANCE = 0.5**2


def skew(v):
    x, y, z = v
    return np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])


def correct_velocity(velocity, previous_covariance, camera_displacement, direction,
                     elapsed, axis_std):
    """Use zero average camera velocity perpendicular to the visual axis."""
    normal = skew(direction)[:, np.argmin(np.abs(direction))]
    normal /= np.linalg.norm(normal)
    tangent = np.stack((normal, np.cross(direction, normal)))
    mean_camera_velocity = camera_displacement / elapsed
    residual = -tangent @ mean_camera_velocity

    # Under white acceleration noise, end velocity and interval-average
    # velocity share the previous velocity uncertainty and part of the process noise.
    process = ACCEL_NOISE * elapsed * np.eye(3)
    end_covariance = previous_covariance + process
    average_covariance = previous_covariance + process / 3.0
    cross_covariance = (previous_covariance + process / 2.0) @ tangent.T

    lateral_std = 0.05 + axis_std * np.linalg.norm(mean_camera_velocity)
    innovation_covariance = tangent @ average_covariance @ tangent.T + lateral_std**2 * np.eye(2)
    gain = np.linalg.solve(innovation_covariance, cross_covariance.T).T
    posterior = end_covariance - gain @ cross_covariance.T
    return velocity + gain @ residual, 0.5 * (posterior + posterior.T)
