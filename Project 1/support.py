"""Provided data loading, containers, and plotting for the EKF exercise."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.io import loadmat


@dataclass
class Dataset:
    time: np.ndarray                 # (N,)
    angular_velocity: np.ndarray     # (3, N), body frame
    acceleration: np.ndarray         # (3, N), body frame
    vicon: np.ndarray                # (12, N), mocap system observations
    number: int


@dataclass
class Estimate:
    """State slices and frames (body and IMU frames coincide):

    0:3   position in the world frame (m)
    3:6   roll/pitch/yaw defining the body-to-world rotation (rad)
    6:9   velocity in the world frame (m/s)
    9:12  gyroscope bias in the body frame (rad/s)
    12:15 accelerometer bias in the body frame (m/s^2)
    """

    state: np.ndarray                # (15,)
    covariance: np.ndarray           # (15, 15)


@dataclass
class FilterResult:
    states: np.ndarray               # (15, N)
    time: np.ndarray
    vicon: np.ndarray
    final_estimate: Estimate
    part: int
    dataset_number: int


def load_dataset(number):
    """Load one of the supplied recordings and align IMU and mocap timestamps."""
    path = Path(__file__).parent / "data" / f"studentdata{number}.mat"
    contents = loadmat(path, struct_as_record=False, variable_names=("data", "time", "vicon"))
    packets = contents["data"].reshape(-1)
    time = contents["time"].reshape(-1)
    packet_times = np.array([packet.t.item() for packet in packets])
    aligned = np.isin(time, packet_times)
    return Dataset(
        time=time[aligned],
        angular_velocity=np.column_stack([packet.omg.reshape(3) for packet in packets]),
        acceleration=np.column_stack([packet.acc.reshape(3) for packet in packets]),
        vicon=contents["vicon"][:, aligned],
        number=number,
    )


def plot_result(result: FilterResult):
    """Return a Matplotlib figure; callers decide whether to save or show it."""
    import matplotlib.pyplot as plt

    title = f"Part {result.part} - Dataset {result.dataset_number}"
    fig, axes = plt.subplots(5, 3, figsize=(13, 11), sharex=True, layout="constrained")
    fig.canvas.manager.set_window_title(title)
    fig.suptitle(title)
    groups = (
        ("Position", "m"),
        ("Orientation", "rad"),
        ("Velocity", "m/s"),
        ("Bias Gyroscope", "rad/s"),
        ("Bias Accelerometer", "m/s²"),
    )
    for row, (group, unit) in enumerate(groups):
        components = ("Roll", "Pitch", "Yaw") if row == 1 else ("X", "Y", "Z")
        for col, component in enumerate(components):
            ax = axes[row, col]
            index = 3 * row + col
            ax.plot(result.time, result.states[index], "r", label="EKF estimate", linewidth=1)
            if row < 3:
                ax.plot(result.time, result.vicon[index], "b", label="Mocap measurement", linewidth=1)
            ax.set_title(f"{group} {component}")
            if col == 0:
                ax.set_ylabel(unit)
            if row == 4:
                ax.set_xlabel("Time (s)")
    axes[0, 0].legend()
    return fig
