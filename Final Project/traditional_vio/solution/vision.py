"""Known-rotation translation from consecutive-frame feature tracks."""

from dataclasses import dataclass

import cv2
import numpy as np


MIN_TRACKS = 15
MIN_PARALLAX = np.radians(0.5)


@dataclass(frozen=True)
class VisualMotion:
    """Signed translation direction in previous camera coordinates."""

    direction: np.ndarray
    track_count: int
    inlier_count: int
    parallax_radians: float
    geometry_ratio: float


class VisualOdometry:
    def __init__(self, config):
        self.center = np.array([config["cx"], config["cy"]])
        self.focal = np.array([config["fx"], config["fy"]])
        self.epipolar_threshold = 1.0 / min(self.focal)
        self.rng = np.random.default_rng(116)
        self.previous_gray = None

    def step(self, frame, rotation):
        """Match fresh corners. Rotation maps current bearings into previous axes."""
        previous_gray = self.previous_gray
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        self.previous_gray = gray
        if previous_gray is None or rotation is None:
            return None

        points = cv2.goodFeaturesToTrack(previous_gray, maxCorners=100, qualityLevel=0.01, minDistance=8)
        if points is None or len(points) < MIN_TRACKS:
            return None

        tracked, status, _ = cv2.calcOpticalFlowPyrLK(previous_gray, gray, points, None)
        if tracked is None or status is None:
            return None
        pixels = tracked.reshape(-1, 2)
        height, width = gray.shape
        valid = ((status.ravel() != 0) & (pixels[:, 0] >= 0) & (pixels[:, 0] < width)
                 & (pixels[:, 1] >= 0) & (pixels[:, 1] < height))
        tracked, previous = tracked[valid], points[valid]
        if len(tracked) < MIN_TRACKS:
            return None

        returned, status, _ = cv2.calcOpticalFlowPyrLK(gray, previous_gray, tracked, None)
        if returned is None or status is None:
            return None
        error = np.linalg.norm((returned - previous).reshape(-1, 2), axis=1)
        valid = (status.ravel() != 0) & (error <= 1.0)
        if np.count_nonzero(valid) < MIN_TRACKS:
            return None
        return self._fit_axis(previous[valid].reshape(-1, 2), tracked[valid].reshape(-1, 2), rotation)

    def _rays(self, pixels):
        rays = np.column_stack(((pixels - self.center) / self.focal, np.ones(len(pixels))))
        return rays / np.linalg.norm(rays, axis=1, keepdims=True)

    def _fit_axis(self, previous, current, rotation):
        key_rays = self._rays(previous)
        current_rays = self._rays(current) @ rotation.T
        normals = np.cross(key_rays, current_rays)
        parallax = np.arcsin(np.clip(np.linalg.norm(normals, axis=1), 0.0, 1.0))
        if np.median(parallax) < MIN_PARALLAX:
            return None

        # Two epipolar planes intersect along the translation axis. Score
        # hypotheses by angular distance to the corresponding epipolar plane.
        pairs = self.rng.integers(len(normals), size=(48, 2))
        axes = np.cross(normals[pairs[:, 0]], normals[pairs[:, 1]])
        lengths = np.linalg.norm(axes, axis=1)
        axes = axes[lengths > 1e-7]
        if len(axes) == 0:
            return None
        axes /= np.linalg.norm(axes, axis=1, keepdims=True)
        errors = self._epipolar_error(normals, key_rays, axes)
        support = errors <= self.epipolar_threshold
        best = int(np.argmax(support.sum(axis=0)))
        inliers = support[:, best]
        minimum = max(MIN_TRACKS, 0.6 * len(normals))
        if inliers.sum() < minimum:
            return None

        _, singular, basis = np.linalg.svd(normals[inliers], full_matrices=False)
        geometry_ratio = singular[1] / singular[0]
        if geometry_ratio < 0.12 or singular[2] > 0.4 * singular[1]:
            return None
        direction = basis[-1]
        inliers = self._epipolar_error(normals, key_rays, direction[None])[:, 0] <= self.epipolar_threshold
        count = int(inliers.sum())
        if count < minimum:
            return None
        median_parallax = float(np.median(parallax[inliers]))
        if median_parallax < MIN_PARALLAX:
            return None
        sign = self._translation_sign(key_rays[inliers], current_rays[inliers], direction)
        if sign is None:
            return None
        return VisualMotion(sign * direction, len(normals), count, median_parallax, float(geometry_ratio))

    @staticmethod
    def _translation_sign(key_rays, current_rays, direction):
        # Triangulate the two depths up to a common positive denominator.
        # Reversing the translation reverses both depths (cheirality test).
        cosine = np.sum(key_rays * current_rays, axis=1)
        key_projection = key_rays @ direction
        current_projection = current_rays @ direction
        key_depth = key_projection - cosine * current_projection
        current_depth = cosine * key_projection - current_projection
        positive = np.count_nonzero((key_depth > 0) & (current_depth > 0))
        negative = np.count_nonzero((key_depth < 0) & (current_depth < 0))
        if max(positive, negative) < 0.7 * len(key_rays):
            return None
        return 1 if positive > negative else -1

    @staticmethod
    def _epipolar_error(normals, rays, axes):
        cosine = np.clip(rays @ axes.T, -1.0, 1.0)
        plane_norm = np.sqrt(np.maximum(1.0 - cosine**2, 1e-8))
        return np.abs(normals @ axes.T) / plane_norm
