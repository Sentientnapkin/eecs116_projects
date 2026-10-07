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

    mean, cov = estimate.state, estimate.covariance

    # Our update model g
    z_t = np.asarray(measurement)

    # Jacobian of our process model wrt our state
    Ct = np.zeros((6, 15))
    Ct[:, :6] = np.eye(6)
    
    Wt = np.eye(6)

    # Our Kalman Gain
    Kt = cov @ Ct.T @ np.linalg.inv(Ct @ cov @ Ct.T + Wt @ measurement_noise @ Wt.T)

    innovation = z_t - np.array(mean[:6])

    # Wrap orientations to [-pi, pi)
    innovation[3:6] = (innovation[3:6] + np.pi) % (2 * np.pi) - np.pi

    new_mean = mean + Kt @ (innovation)

    new_cov = cov - Kt @ Ct @ cov

    return Estimate(new_mean, new_cov)


def update_velocity(
    estimate: Estimate, measurement: ArrayLike, measurement_noise: ArrayLike
) -> Estimate:
    """Part 2: world-frame velocity measurement (3,) and its covariance R (3, 3)."""

    mean, cov = estimate.state, estimate.covariance

    # Our update process model
    z_t = np.asarray(measurement)

    # Jacobian of our process model wrt our state
    Ct = np.zeros((3, 15))
    Ct[:, 6:9] = np.eye(3)
    
    Wt = np.eye(3)

    # Kalman Gain
    Kt = cov @ Ct.T @ np.linalg.inv(Ct @ cov @ Ct.T + Wt @ measurement_noise @ Wt.T)

    innovation = z_t - np.array(mean[6:9])

    new_mean = mean + Kt @ (innovation)

    new_cov = cov - Kt @ Ct @ cov

    return Estimate(new_mean, new_cov)
