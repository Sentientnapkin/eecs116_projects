"""Part 2: feature tracking, optical-flow velocity, and three-point RANSAC."""

import cv2
import numpy as np

from support import BODY_TO_CAMERA, CAMERA_MATRIX, Frame, Pose


def velocity_ransac(points: np.ndarray, flow: np.ndarray, depth: np.ndarray, *,
                    ransac: bool, threshold: float, iterations: int) -> np.ndarray:
    """Return camera-frame [vx, vy, vz, wx, wy, wz] (6,).

    points and flow are (N, 2) normalized image coordinates and their rates
    (1/s); depth is (N,) positive camera-z depth in metres, with N >= 3.
    With ransac=False, fit all points by least squares. Otherwise sample
    three distinct points per trial, reject rank-deficient systems, score
    each point by its 2D flow residual norm (< threshold, in 1/s), keep the
    best consensus, and refit using all its inliers.
    """

    if ransac == False:
        # Our A(p)/Z matrix
        A_p = np.zeros((len(points) * 2, 3))

        # Our B(p) matrix
        B_p = np.zeros((len(points), 3))
        for i, point in enumerate(points):
            x = point[0]
            y = point[1]

            Z = depth[i]

            A_p[2 * i, 0] = -1.0 / Z
            A_p[2 * i + 1, 0] = -1.0 / Z

            A_p[2 * i, 2] = x / Z
            A_p[2 * i + 1, 2] = y / Z


            B_p[2 * i, 0] = x * y
            B_p[2 * i, 1] = -(1 + x**2)
            B_p[2 * i, 2] = y
            B_p[2 * i + 1, 0] = 1 + y**2
            B_p[2 * i + 1, 1] = - x * y
            B_p[2 * i + 1, 2] = -x

        # Fit with least squares using the pseudo inverse
        return np.linalg.pinv(np.concat(A_p, B_p, axis=1)) @ flow
    
    else:
        # RANSAC
        ...


def estimate_velocity(previous: Frame, current: Frame, pose: Pose, *,
                      ransac: bool) -> np.ndarray | None:
    """Return [world linear velocity, body angular velocity] (6,).

    pose is the body pose at previous.time. Detect corners in previous.image
    (including scribble), track to current.image with KLT, and discard failed
    tracks. Normalize pixels with CAMERA_MATRIX; divide displacements by
    current.time - previous.time. Intersect previous-frame rays with world
    z=0 using the camera pose to obtain depth. Fit camera motion with
    velocity_ransac(), then account for the camera/body rotation AND offset.
    Choose detector/tracker and RANSAC parameters here. Return None when
    fewer than three usable tracks remain. The runner plots interval averages
    at midpoint timestamps; use the previous pose for frame transformations.
    """
    raise NotImplementedError("Complete flow.py: estimate_velocity")
