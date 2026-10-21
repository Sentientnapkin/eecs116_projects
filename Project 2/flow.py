"""Part 2: feature tracking, optical-flow velocity, and three-point RANSAC."""

import cv2
import numpy as np

from support import BODY_TO_CAMERA, CAMERA_MATRIX, Frame, Pose

def create_A_B(points, depth):
    """ 
    Create helper function that, from a set of points, 
    generates out A(p) and B(p) matrices for optical flow
    """

    # Our A(p)/Z matrix
    A_p = np.zeros((len(points) * 2, 3))

    # Our B(p) matrix
    B_p = np.zeros((len(points) * 2, 3))


    for i, point in enumerate(points):
        x = point[0]
        y = point[1]

        Z = depth[i]

        A_p[2 * i, 0] = -1.0 / Z
        A_p[2 * i + 1, 1] = -1.0 / Z

        A_p[2 * i, 2] = x / Z
        A_p[2 * i + 1, 2] = y / Z


        B_p[2 * i, 0] = x * y
        B_p[2 * i, 1] = -(1 + x**2)
        B_p[2 * i, 2] = y
        B_p[2 * i + 1, 0] = 1 + y**2
        B_p[2 * i + 1, 1] = - x * y
        B_p[2 * i + 1, 2] = -x

    return A_p, B_p

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

    # Fit all points
    A_p, B_p = create_A_B(points, depth)

    H = np.concatenate((A_p, B_p), axis=1)

    if ransac == False:
        # Fit with least squares using the pseudo inverse
        return np.linalg.pinv(H) @ flow.reshape(-1)
    
    else:
        # RANSAC
        rng = np.random.default_rng()

        best_inliers = None
        best_count = -1
        for i in range(iterations):
            # take subset of 3 points and calculate H for them
            indices = rng.choice(len(points), size=3, replace=False)
            H_subset = np.vstack([H[2*i:2*i+2] for i in indices])

            # eliminate rank defficient matrices
            if np.linalg.matrix_rank(H_subset) < 6:
                continue

            # fit velocities to our subset
            velocities_subset = np.linalg.pinv(H_subset) @ flow[indices].reshape(-1)

            # calculate the loss
            count_inliers = 0
            inliers = []
            for i in range(len(points)):
                flow_i = flow[i]
                A_p_i = A_p[2*i : 2*i + 2, :]
                B_p_i = B_p[2*i : 2*i + 2, :]

                H_i = np.concatenate((A_p_i, B_p_i), axis = 1)

                loss = np.linalg.norm(H_i @ velocities_subset - flow_i)

                if loss < threshold:
                    count_inliers += 1
                    inliers.append(i)

            # keep best option
            if count_inliers > best_count:
                best_count = count_inliers
                best_inliers = inliers

        # Refit using all inliers in the best consensus.
        if best_inliers:
            H_inliers = np.vstack([H[2*i:2*i+2] for i in best_inliers])
            return np.linalg.pinv(H_inliers) @ flow[best_inliers].reshape(-1)
        
        return np.linalg.pinv(H) @ flow.reshape(-1)

        

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

    # Find features on image
    prev_features = cv2.goodFeaturesToTrack(image=previous.image, maxCorners=100, qualityLevel=0.5, minDistance=10)

    if prev_features is None or len(prev_features) < 3:
        return None

    next_features, status, _ = cv2.calcOpticalFlowPyrLK(prevImg=previous.image, nextImg=current.image, prevPts=prev_features, nextPts=None)

    if next_features is None or status is None:
        return None

    valid = status.reshape(-1) == 1
    prev_features = prev_features.reshape(-1, 2)[valid]
    next_features = next_features.reshape(-1, 2)[valid]
    dt = current.time - previous.time
    if len(prev_features) < 3 or not np.isfinite(dt) or dt <= 0:
        return None

    # Normalize homogeneous pixels before calculating flow.
    previous_pixels = np.column_stack((prev_features, np.ones(len(prev_features))))
    next_pixels = np.column_stack((next_features, np.ones(len(next_features))))
    points_ray = np.linalg.inv(CAMERA_MATRIX) @ previous_pixels.T
    next_rays = np.linalg.inv(CAMERA_MATRIX) @ next_pixels.T
    points = points_ray[:2].T
    flow = (next_rays[:2].T - points) / dt

    # Create out R_WB & p_WB
    BODY_TO_WORLD = np.eye(4)
    BODY_TO_WORLD[:3, :3] = pose.rotation
    BODY_TO_WORLD[:3, 3] = pose.position

    # Create a ray from our point features on previous image
    CAMERA_TO_WORLD = BODY_TO_WORLD @ np.linalg.inv(BODY_TO_CAMERA)

    # Isolate rotation and translation for camera to world transform
    R_WC = CAMERA_TO_WORLD[:3, :3]
    p_WC = CAMERA_TO_WORLD[:3, 3]

    # Calculate our image feature depths
    points_rotated = R_WC @ points_ray
    with np.errstate(divide="ignore", invalid="ignore"):
        depths = -p_WC[2] / points_rotated[2, :]

    valid = (np.isfinite(depths) & (depths > 0)
             & np.all(np.isfinite(points), axis=1)
             & np.all(np.isfinite(flow), axis=1))
    points, flow, depths = points[valid], flow[valid], depths[valid]
    if len(points) < 3:
        return None


    # RANSAC
    threshold = 0.1
    iterations = 15
    velocity = velocity_ransac(points, flow, depths, ransac=ransac, threshold=threshold, iterations=iterations)


    # Check if we have enough usable points
    if velocity is None:
        return None

    # Convert velocity into world frame
    R_BC = BODY_TO_CAMERA[:3, :3].T
    angular_velocity_body = R_BC @ velocity[3:]
    body_origin_camera = R_BC @ BODY_TO_CAMERA[:3, 3]
    linear_velocity_world = (R_WC @ velocity[:3]
                             + pose.rotation @ np.cross(angular_velocity_body, body_origin_camera))
    world_velocity = np.concatenate((linear_velocity_world, angular_velocity_body))

    return world_velocity


    




    
