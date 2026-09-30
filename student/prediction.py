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
    # TODO: derive the dynamics and Jacobians, then propagate mean and covariance.
    raise NotImplementedError("Complete prediction.py: predict")
