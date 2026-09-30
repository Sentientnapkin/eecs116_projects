"""Student exercises: the two observation models share the prediction step."""

import numpy as np
from numpy.typing import ArrayLike
from scipy.spatial.transform import Rotation

from support import Estimate


def update_pose(
    estimate: Estimate, measurement: ArrayLike, measurement_noise: ArrayLike
) -> Estimate:
    """Part 1: position/orientation measurement (6,) and its covariance R (6, 6).

    Wrap orientation innovations to [-pi, pi); leave state angles unwrapped.
    """
    # TODO: build the observation model and apply the Kalman update.
    raise NotImplementedError("Complete updates.py: update_pose")


def update_velocity(
    estimate: Estimate, measurement: ArrayLike, measurement_noise: ArrayLike
) -> Estimate:
    """Part 2: world-frame velocity measurement (3,) and its covariance R (3, 3)."""
    # TODO: build the observation model and apply the Kalman update.
    raise NotImplementedError("Complete updates.py: update_velocity")
