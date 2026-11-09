"""Consecutive-frame camera motion from sparse optical flow."""

from dataclasses import dataclass

import cv2
import numpy as np


MIN_TRACKS = 15
MIN_INLIER_FRACTION = 0.5
MIN_PARALLAX_DEGREES = 0.5


@dataclass(frozen=True)
class VisualMotion:
    """Current camera rotation and unit displacement in previous camera axes."""

    rotation: np.ndarray
    direction: np.ndarray
    track_count: int
    inlier_count: int
    parallax_degrees: float


class VisualOdometry:
    def __init__(self, config):
        self.K = np.array([
            [config["fx"], 0, config["cx"]],
            [0, config["fy"], config["cy"]],
            [0, 0, 1],
        ], dtype=float)
        self.K_inv = np.linalg.inv(self.K)
        self.previous_gray = None

    def step(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        previous_gray = self.previous_gray
        self.previous_gray = gray
        if previous_gray is None:
            return None

        points = cv2.goodFeaturesToTrack(previous_gray, maxCorners=100, qualityLevel=0.01, minDistance=8)
        if points is None or len(points) < MIN_TRACKS:
            return None

        tracked, status, _ = cv2.calcOpticalFlowPyrLK(previous_gray, gray, points, None)
        if tracked is None or status is None:
            return None
        points = points[status.ravel() != 0]
        tracked = tracked[status.ravel() != 0]
        height, width = gray.shape
        pixels = tracked.reshape(-1, 2)
        inside = ((pixels[:, 0] >= 0) & (pixels[:, 0] < width)
                  & (pixels[:, 1] >= 0) & (pixels[:, 1] < height))
        points, tracked = points[inside], tracked[inside]
        if len(points) < MIN_TRACKS:
            return None

        returned, status, _ = cv2.calcOpticalFlowPyrLK(gray, previous_gray, tracked, None)
        if returned is None or status is None:
            return None
        error = np.linalg.norm((returned - points).reshape(-1, 2), axis=1)
        valid = (status.ravel() != 0) & (error <= 1.0)
        return self._relative_motion(points[valid].reshape(-1, 2), tracked[valid].reshape(-1, 2))

    def _relative_motion(self, previous, current):
        if len(previous) < MIN_TRACKS:
            return None

        essential, mask = cv2.findEssentialMat(
            previous, current, self.K, method=cv2.RANSAC, prob=0.999,
            threshold=1.0, maxIters=200,
        )
        if essential is None or essential.shape != (3, 3) or mask is None:
            return None
        count, rotation, translation, mask = cv2.recoverPose(
            essential, previous, current, self.K, mask=mask,
        )
        if count < MIN_TRACKS or count < MIN_INLIER_FRACTION * len(previous):
            return None

        # OpenCV maps points from the previous camera to the current camera.
        # Invert that transform to describe the motion of the camera itself.
        rotation = rotation.T
        direction = -rotation @ translation.ravel()

        # Measure parallax after removing the recovered camera rotation.
        inliers = mask.ravel() != 0
        previous_rays = self._rays(previous[inliers])
        current_rays = self._rays(current[inliers]) @ rotation.T
        dot = np.sum(previous_rays * current_rays, axis=1)
        parallax = float(np.degrees(np.median(np.arccos(np.clip(dot, -1.0, 1.0)))))
        if not np.isfinite(parallax) or parallax < MIN_PARALLAX_DEGREES:
            return None
        return VisualMotion(rotation, direction, len(previous), count, parallax)

    def _rays(self, pixels):
        rays = np.column_stack((pixels, np.ones(len(pixels)))) @ self.K_inv.T
        return rays / np.linalg.norm(rays, axis=1, keepdims=True)
