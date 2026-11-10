"""Direct IMU and visual displacement combination over a keyframe interval."""

import numpy as np


def skew(v):
    x, y, z = v
    return np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])


def combine_displacement(position, velocity, key_position, camera_offset_change,
                         direction_world, elapsed):
    """Replace the camera displacement direction and blend its average velocity."""
    imu_displacement = position - key_position
    camera_distance = np.linalg.norm(imu_displacement + camera_offset_change)
    # Convert the corrected camera displacement back to IMU-centre displacement
    # before using it to update position or velocity.
    displacement = camera_distance * direction_world - camera_offset_change
    corrected_velocity = 0.5 * (velocity + displacement / elapsed)
    return key_position + displacement, corrected_velocity
