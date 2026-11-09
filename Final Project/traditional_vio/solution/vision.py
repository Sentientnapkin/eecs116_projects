"""Known-rotation translation from keyframe feature tracks."""

from dataclasses import dataclass

import cv2
import numpy as np


MIN_TRACKS = 15
MIN_KEYFRAME_AGE = 4
MAX_KEYFRAME_AGE = 10
MIN_PARALLAX = np.radians(0.5)


@dataclass(frozen=True)
class VisualMotion:
    """Unsigned translation axis in keyframe camera coordinates."""

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
        self.gray = None
        self.points = np.empty((0, 1, 2), dtype=np.float32)
        self.keyframe_points = self.points
        self.age = 0

    def reset_keyframe(self):
        points = cv2.goodFeaturesToTrack(self.gray, maxCorners=100, qualityLevel=0.01, minDistance=8)
        self.points = points if points is not None else np.empty((0, 1, 2), dtype=np.float32)
        self.keyframe_points = self.points
        self.age = 0

    @property
    def needs_keyframe(self):
        return len(self.points) < MIN_TRACKS or self.age >= MAX_KEYFRAME_AGE

    def step(self, frame, rotation):
        """Track one image hop. Rotation maps current bearings into the keyframe."""
        previous_gray = self.gray
        self.gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        if rotation is None or self.needs_keyframe:
            return None

        self.age += 1
        tracked, status, _ = cv2.calcOpticalFlowPyrLK(previous_gray, self.gray, self.points, None)
        if tracked is None or status is None:
            self.points = self.points[:0]
            return None
        pixels = tracked.reshape(-1, 2)
        height, width = self.gray.shape
        valid = ((status.ravel() != 0) & (pixels[:, 0] >= 0) & (pixels[:, 0] < width)
                 & (pixels[:, 1] >= 0) & (pixels[:, 1] < height))
        tracked, previous = tracked[valid], self.points[valid]
        self.keyframe_points = self.keyframe_points[valid]
        self.points = tracked
        if len(tracked) < MIN_TRACKS:
            return None

        returned, status, _ = cv2.calcOpticalFlowPyrLK(self.gray, previous_gray, tracked, None)
        if returned is None or status is None:
            self.points = self.points[:0]
            return None
        error = np.linalg.norm((returned - previous).reshape(-1, 2), axis=1)
        valid = (status.ravel() != 0) & (error <= 1.0)
        self.keyframe_points = self.keyframe_points[valid]
        self.points = tracked[valid]
        if self.age < MIN_KEYFRAME_AGE or len(self.points) < MIN_TRACKS:
            return None
        return self._fit_axis(self.keyframe_points.reshape(-1, 2), self.points.reshape(-1, 2), rotation)

    def _rays(self, pixels):
        rays = np.column_stack(((pixels - self.center) / self.focal, np.ones(len(pixels))))
        return rays / np.linalg.norm(rays, axis=1, keepdims=True)

    def _fit_axis(self, keyframe, current, rotation):
        key_rays = self._rays(keyframe)
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
        return VisualMotion(direction, len(normals), count, median_parallax, float(geometry_ratio))

    @staticmethod
    def _epipolar_error(normals, rays, axes):
        cosine = np.clip(rays @ axes.T, -1.0, 1.0)
        plane_norm = np.sqrt(np.maximum(1.0 - cosine**2, 1e-8))
        return np.abs(normals @ axes.T) / plane_norm
