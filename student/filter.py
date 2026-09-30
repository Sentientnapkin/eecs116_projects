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
    # TODO: choose and tune the process and measurement noise covariances.
    raise NotImplementedError("Choose Q and R in filter.py: noise_covariances")


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
        # TODO: propagate from time[index - 1] to time[index] using IMU column
        # index - 1, update using measurements[:, index], and save the state.
        # Pass process_noise to predict and measurement_noise to update.
        raise NotImplementedError("Complete filter.py: run_filter loop")
    return FilterResult(
        states=states, time=dataset.time, vicon=dataset.vicon,
        final_estimate=estimate, part=part, dataset_number=dataset.number,
    )
