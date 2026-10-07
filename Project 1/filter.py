"""Student exercise: connect prediction and updates in a single filter loop."""

import numpy as np
from numpy.typing import ArrayLike
from scipy.spatial.transform import Rotation

from support import Dataset, Estimate, FilterResult
from prediction import predict
from updates import update_pose, update_velocity


def noise_covariances(part: int) -> tuple[np.ndarray, np.ndarray]:
    """Choose Q (12, 12) and R (6, 6) for Part 1 or R (3, 3) for Part 2.

    See predict() for Q's noise ordering. R follows the measurement ordering.
    These are covariance matrices, not standard deviations. Use your chosen
    values for report runs; the checker supplies its own Q and R to run_filter().
    """

    Q = np.eye(12)

    Q[0, 0] *= 1 * 1e-4
    Q[1, 1] *= 1 * 1e-4
    Q[2, 2] *= 1 * 1e-4
    Q[3, 3] *= 1 * 1e-2
    Q[4, 4] *= 1 * 1e-2
    Q[5, 5] *= 2 * 1e-2
    Q[6, 6] *= 1 * 1e-6
    Q[7, 7] *= 1 * 1e-6
    Q[8, 8] *= 1 * 1e-6
    Q[9, 9] *= 1 * 1e-4
    Q[10, 10] *= 1 * 1e-4
    Q[11, 11] *= 1 * 1e-4
    
    if part == 1:
        R = np.eye(6) 
        R[0, 0] *= 1 * 1e-5
        R[1, 1] *= 1 * 1e-5
        R[2, 2] *= 1 * 1e-5

        R[3,3] *= 1.5 * 1e-3
        R[4,4] *= 1.5 * 1e-3
        R[5,5] *= 2.5 * 1e-5

    elif part == 2:
        R = np.eye(3)
        R[0, 0] *= 3 * 1e-2
        R[1, 1] *= 3 * 1e-2
        R[2, 2] *= 4 * 1e-3
    else:
        raise ValueError("part must be 1 or 2")

    return Q, R


def run_filter(
    dataset: Dataset, process_noise: ArrayLike, measurement_noise: ArrayLike,
    *, part: int = 1,
) -> FilterResult:
    """Run with the supplied Q and R; return the state history and final estimate."""
    measurements = dataset.vicon[:6] if part == 1 else dataset.vicon[6:9]
    update = update_pose if part == 1 else update_velocity
    estimate = Estimate(
        state=np.concatenate((dataset.vicon[:9, 0], np.zeros(6))),
        covariance=np.eye(15),
    )
    states = np.empty((15, dataset.time.size))
    states[:, 0] = estimate.state
    for index in range(1, dataset.time.size):
        # propagate from time[index - 1] to time[index] using IMU column
        # index - 1, update using measurements[:, index], and save the state.
        # Pass process_noise to predict and measurement_noise to update.

        prev_time = dataset.time[index - 1]
        time = dataset.time[index]
        angular_velo = dataset.angular_velocity[:, index - 1]
        accel = dataset.acceleration[:, index - 1]

        dt = time - prev_time

        measurement = measurements[:, index]

        # Kalman filter!!

        estimate = predict(estimate, angular_velo, accel, dt, process_noise)

        estimate = update(estimate, measurement, measurement_noise)

        states[:, index] = estimate.state

    return FilterResult(
        states=states, time=dataset.time, vicon=dataset.vicon,
        final_estimate=estimate, part=part, dataset_number=dataset.number,
    )
