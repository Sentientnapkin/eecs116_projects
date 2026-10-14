"""Part 1: AprilTag map geometry and pose from a planar homography."""

import numpy as np
from scipy.spatial.transform import Rotation

from support import BODY_TO_CAMERA, CAMERA_MATRIX, Frame, Pose


def get_corners(ids: np.ndarray) -> np.ndarray:
    """Return (N, 4, 3) world coordinates in metres for the given tag IDs.

    Preserve ID order. Each tag's corners are bottom left, bottom right,
    top right, top left (p1, p2, p3, p4); the mat is the world z=0 plane.
    """

    corners = []

    for id in ids:
        row = id % 12
        col = id // 12

        p1_x = 2 * row * 0.152 + 0.152
        p1_y = 2 * col * 0.152

        if col > 2:
            p1_y += 0.026
        if col > 5:
            p1_y += 0.026

        corners.append([[p1_x, p1_y, 0], [p1_x, p1_y + 0.152, 0], [p1_x - 0.152, p1_y + 0.152, 0], [p1_x - 0.152, p1_y, 0]])

    return np.array(corners)


def estimate_pose(frame: Frame) -> Pose | None:
    """Estimate the body origin and body-to-world rotation from tag corners.

    Use get_corners(), the calibrated camera, and a homography estimated by
    SVD. Choose the sign giving positive camera depths and a proper rotation.
    Apply BODY_TO_CAMERA to recover the body pose. Return None if no tags
    are visible. Pixel coordinates are zero-based (u right, v down).
    """

    # Check if any tags are visible
    if len(frame.ids) == 0:
        return None
    
    # Grab our image coordinates from camera frame of tag
    camera_img_corners = frame.corners.reshape(-1, 2)

    # Grab our image coordinates from world frame of tags
    world_corners = get_corners(frame.ids).reshape(-1, 3)

    # define number of points were going to use
    num_points = len(frame.ids) * 4

    # Create our A matrix
    A = np.zeros((2 * num_points, 9))

    for i, point_pair in enumerate(zip(world_corners, camera_img_corners)):
        world_p = point_pair[0]
        camera_p = point_pair[1]

        A[2 * i, 0] = world_p[0]
        A[2 * i, 1] = world_p[1]
        A[2 * i, 2] = 1

        A[2 * i, 6] = -world_p[0] * camera_p[0]
        A[2 * i, 7] = -world_p[1] * camera_p[0]
        A[2 * i, 8] = -camera_p[0]

        A[2 * i + 1, 3] = world_p[0]
        A[2 * i + 1, 4] = world_p[1]
        A[2 * i + 1, 5] = 1

        A[2 * i + 1, 6] = -world_p[0] * camera_p[1]
        A[2 * i + 1, 7] = -world_p[1] * camera_p[1]
        A[2 * i + 1, 8] = -camera_p[1]

    # Calculate h as last column of V in SVD
    U, S, V_t = np.linalg.svd(A)

    h = V_t.T[:, 8]

    H = h.reshape(3, 3)

    # Testing sign convention of H
    test_point_world = np.array([world_corners[0][0], world_corners[0][1], 1])
    test_point_camera = H @ test_point_world

    if test_point_camera[2] < 0:
        H = -H

    # Find our first two columns of rotation and our position
    G_temp = np.linalg.inv(CAMERA_MATRIX) @ H

    # Create homogenous transform from G_temp
    WORLD_TO_CAMERA = np.zeros((4, 4))

    WORLD_TO_CAMERA[:3, 0] = G_temp[:, 0]
    WORLD_TO_CAMERA[:3, 1] = G_temp[:, 1]
    WORLD_TO_CAMERA[:3, 2] = np.cross(G_temp[:, 0].reshape((-1,)), G_temp[:, 1].reshape((-1,))).reshape((3,))

    WORLD_TO_CAMERA[:3, 3] = G_temp[:, 2] / np.linalg.norm(G_temp[:, 0])

    WORLD_TO_CAMERA[3, 3] = 1

    WORLD_TO_CAMERA[:3, :3] = Rotation.from_matrix(WORLD_TO_CAMERA[:3, :3]).as_matrix()

    # Create our final body to world transformation matrix
    BODY_TO_WORLD = np.linalg.inv(WORLD_TO_CAMERA) @ BODY_TO_CAMERA

    return Pose(BODY_TO_WORLD[:3, 3].reshape((-1,)), BODY_TO_WORLD[:3, :3])



