"""Error-state EKF for inertial propagation and two-view camera motion."""

import cv2
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


def camera_innovation(position, rotation, previous_position, previous_rotation,
                      R_cam_imu, camera_offset, motion):
    """Residual and Jacobian for the current state and a six-error pose clone."""
    C = R_cam_imu
    world_to_previous = C @ previous_rotation.T
    relative_rotation = world_to_previous @ rotation @ C.T
    delta_world = position - previous_position + rotation @ camera_offset
    delta_previous_imu = previous_rotation.T @ delta_world
    displacement = C @ (delta_previous_imu - camera_offset)

    # Left rotation residual in previous camera axes.
    rotation_error = cv2.Rodrigues(motion.rotation @ relative_rotation.T)[0].ravel()
    H = np.zeros((5, 21))
    H[:3, 3:6] = relative_rotation @ C
    H[:3, 18:21] = -C

    # Two perpendicular components constrain the direction of travel.
    # Distance along the bearing does not appear in the measurement.
    direction = motion.direction
    normal = skew(direction)[:, np.argmin(np.abs(direction))]
    normal /= np.linalg.norm(normal)
    tangent = np.stack((normal, np.cross(direction, normal)))
    H[3:, 0:3] = tangent @ world_to_previous
    H[3:, 3:6] = -tangent @ world_to_previous @ rotation @ skew(camera_offset)
    H[3:, 15:18] = -H[3:, 0:3]
    H[3:, 18:21] = tangent @ C @ skew(delta_previous_imu)

    residual = np.concatenate((rotation_error, -tangent @ displacement))
    # Heuristic noise for two-view geometry, with a floor near zero baseline.
    lateral_std = 0.01 + 0.15 * np.linalg.norm(displacement)
    noise = np.diag(np.repeat(np.square([0.035, lateral_std]), [3, 2]))
    return residual, H, noise


def correct_covariance(covariance, cross, previous_covariance, residual, H, noise):
    joint = np.block([[covariance, cross], [cross.T, previous_covariance]])
    HP = H @ joint
    innovation_covariance = HP @ H.T + noise
    weighted = np.linalg.solve(innovation_covariance, residual)
    if not np.isfinite(weighted).all() or residual @ weighted > 20.5:
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
