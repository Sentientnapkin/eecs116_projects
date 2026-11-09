"""Error-state EKF for inertial propagation and keyframe translation measurements."""

import numpy as np


# Error state: world position, IMU-local attitude, world velocity, gyro bias,
# accelerometer bias. The first IMU pose fixes the origin and orientation gauge.
INITIAL_VARIANCE = np.repeat(np.square([0.0, 0.0, 0.5, 0.05, 0.3]), 3)
# Continuous-time noise intensities, in Project 1's gyro/accel/bias order.
IMU_NOISE = np.repeat([1e-4, 1e-2, 1e-6, 1e-4], 3)


def skew(v):
    x, y, z = v
    return np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])


def predict_covariance(covariance, cross, R_mid, R_step, specific_force, dt):
    identity = np.eye(3)
    F = np.eye(15)
    F[0:3, 6:9] = dt * identity
    F[3:6, 3:6] = R_step.T
    F[3:6, 9:12] = -dt * identity
    F[6:9, 3:6] = -dt * R_mid @ skew(specific_force)
    F[6:9, 12:15] = -dt * R_mid
    F[0:3, 3:6] = 0.5 * dt * F[6:9, 3:6]
    F[0:3, 12:15] = 0.5 * dt * F[6:9, 12:15]

    G = np.zeros((15, 12))
    G[3:6, 0:3] = identity
    G[6:9, 3:6] = R_mid
    G[0:3, 3:6] = 0.5 * dt * R_mid
    G[9:15, 6:12] = np.eye(6)
    predicted = F @ covariance @ F.T + (G * (dt * IMU_NOISE)) @ G.T
    return predicted, None if cross is None else F @ cross


def camera_innovation(position, rotation, key_position, key_rotation,
                      R_cam_imu, camera_offset, motion, focal_length):
    """Translation residual and Jacobian for the live state and keyframe clone."""
    C = R_cam_imu
    world_to_key = C @ key_rotation.T
    delta_world = position - key_position + rotation @ camera_offset
    delta_key_imu = key_rotation.T @ delta_world
    displacement = C @ (delta_key_imu - camera_offset)

    direction = motion.direction
    normal = skew(direction)[:, np.argmin(np.abs(direction))]
    normal /= np.linalg.norm(normal)
    tangent = np.stack((normal, np.cross(direction, normal)))
    H = np.zeros((2, 21))
    H[:, 0:3] = tangent @ world_to_key
    H[:, 3:6] = -tangent @ world_to_key @ rotation @ skew(camera_offset)
    H[:, 15:18] = -H[:, 0:3]
    H[:, 18:21] = tangent @ C @ skew(delta_key_imu)

    # Weaker parallax and poorer plane spread make a pixel of angular
    # uncertainty correspond to a larger error in the fitted translation axis.
    axis_std = np.clip(
        1.0 / (focal_length * motion.parallax_radians * motion.geometry_ratio),
        0.10, 0.60,
    )
    lateral_std = 0.01 + axis_std * np.linalg.norm(displacement)
    return -tangent @ displacement, H, np.eye(2) * lateral_std**2


def correct_covariance(covariance, cross, previous_covariance, residual, H, noise):
    joint = np.block([[covariance, cross], [cross.T, previous_covariance]])
    HP = H @ joint
    innovation_covariance = HP @ H.T + noise
    weighted = np.linalg.solve(innovation_covariance, residual)
    if not np.isfinite(weighted).all() or residual @ weighted > 13.82:
        return None

    # Only the current state survives this step. Keep the clone in the Joseph
    # update so shared uncertainty cancels in the relative measurement.
    gain = np.linalg.solve(innovation_covariance, HP[:, :15]).T
    correction = gain @ residual
    joseph = np.eye(21)[:15] - gain @ H
    posterior = joseph @ joint @ joseph.T + gain @ noise @ gain.T

    # Reset the attitude error into the corrected IMU tangent frame.
    reset = np.eye(15)
    reset[3:6, 3:6] -= 0.5 * skew(correction[3:6])
    posterior = reset @ posterior @ reset.T
    return correction, 0.5 * (posterior + posterior.T)
