"""Shared helpers for the research probes: loading gen.py flights, scoring, integrating velocity sources.

Scoring follows docs/TASK.md: the headline is UNALIGNED position RMSE in camera-frame-0 coordinates.
Sim(3) ATE is kept as a diagnostic (stage-1 slides quoted it).
"""
import glob
import json

import numpy as np

G = np.array([0.0, 0.0, -9.81])  # world z-up (checked: accel residual vs GT is pure sensor noise)
FRAME_DT = 0.05


from orientation import Orientation, exp_so3


class Flight:
    """One gen.py flight resampled to frame rate. World = simulator world; body = IMU/body axes."""

    def __init__(self, path, crop=0.0, stop=None):
        if str(path).endswith(".zip"):
            self._native(path, crop, stop)
            return
        d = np.load(path, allow_pickle=False)
        self.path = path
        self.tier = str(d["tier"])
        self.scene = str(d["scene"])
        self.imu = d["imu"]  # (N, 7) t, acc, gyro at 200 Hz, stamped at step end
        self.frames = d["frames"]  # (F, H, W) uint8, frame k at t = 0.05 k
        self.ft = d["frame_times"]
        start = int(np.searchsorted(self.ft, self.ft[0] + crop - 1e-8))
        indices = np.arange(start, len(self.ft))[:stop]
        if len(indices) < 2:
            raise ValueError("flight requires at least two frames")
        origin = self.ft[start]
        stamps = self.ft[indices]
        self.frames = self.frames[indices]
        self.ft = stamps - origin
        self.F = len(stamps)
        self.realized_crop = float(origin)
        gt_times = d["gt_t"] if "gt_t" in d else np.arange(len(d["gt_p"])) * .005
        idx = np.searchsorted(gt_times, stamps - 1e-7)
        self.p = d["gt_p"][idx].astype(np.float64)
        self.R = d["gt_R"][idx].astype(np.float64)
        self.v = d["gt_v"][idx].astype(np.float64)
        self.w = d["gt_w"][idx].astype(np.float64)
        self.T_bc = d["T_body_camera"]
        self.fov = float(d["fov"])
        self.K = json.loads(str(d["K"]))
        self.params = json.loads(str(d["params"]))
        self.seed = int(d["seed"]) if "seed" in d else None
        self.v_body = np.einsum("nji,nj->ni", self.R, self.v)
        cuts = np.searchsorted(self.imu[:, 0], stamps + 1e-7, side="right")
        self.imu = self.imu[cuts[0]:cuts[-1]].copy()
        self.imu[:, 0] -= origin
        cuts -= cuts[0]
        self.win = [np.empty((0, 7))] + [self.imu[a:b] for a, b in zip(cuts[:-1], cuts[1:])]
        self.cam_gt = self.camera_positions(self.p, self.R)

    def _native(self, path, crop, stop):
        from viobench.tools.datasets.storage import read_episode
        from viobench.tools.geometry import interpolate_poses, poses_to_matrices
        ep = read_episode(path)
        first = int(np.searchsorted(ep.frame_times, ep.frame_times[0]+crop-1e-8))
        selection = np.arange(first, ep.num_frames)[:stop]
        if len(selection) < 2:
            raise ValueError("native crop too short")
        times = ep.frame_times[selection]
        self.realized_crop = float(times[0]-ep.frame_times[0])
        self.ft = times-times[0]
        self.F, self.path = len(times), path
        camera, frames = ep.adapt((320,240))
        self.frames = frames[int(selection[0]):int(selection[-1])+1]
        truth = ep.ground_truth
        matrices = poses_to_matrices(interpolate_poses(truth[:,0],truth[:,1:8],times))
        self.p,self.R = matrices[:,:3,3], matrices[:,:3,:3]
        self.T_bc = ep.T_body_camera
        self.K = camera
        self.scene = str(ep.meta.get("scene", ep.name))
        self.tier, self.fov, self.params, self.seed = "benchmark", None, ep.meta, None
        camera_twist = ep.ground_truth_state()[selection,7:]
        self.w = camera_twist[:,3:] @ self.T_bc[:3,:3].T
        self.v_body = camera_twist[:,:3] @ self.T_bc[:3,:3].T - np.cross(self.w,self.T_bc[:3,3])
        self.v = (self.R @ self.v_body[...,None]).squeeze(-1)
        self.cam_gt = self.camera_positions(self.p,self.R)
        self.win = [np.empty((0,7))]
        for i in selection[1:]:
            packet = ep.imu_window(i).copy()
            packet[:,0] -= times[0]
            self.win.append(packet)
        self.imu = np.concatenate(self.win)

    def camera_positions(self, p_world_body, R_world_body):
        """Camera centres in camera-frame-0 axes, origin at camera 0 (what the scorer compares)."""
        R_bc, t_bc = self.T_bc[:3, :3], self.T_bc[:3, 3]
        pc = p_world_body + np.einsum("nij,j->ni", R_world_body, t_bc)
        R_wc0 = R_world_body[0] @ R_bc
        return (pc - pc[0]) @ R_wc0  # == R_wc0^T (pc - pc0)

    def gyro_attitude(self, bias=None, R0=None):
        """Fixed supplied bias is privileged when estimated from future or truth."""
        state = Orientation({"policy": "none", "startup_seconds": 1.0}, R0)
        if bias is not None:
            state.bias = np.asarray(bias)
        return np.stack([state.step(t, packet, 0) for t, packet in zip(self.ft, self.win)])


def integrate_body_velocity(R, v_body, p0=None, times=None):
    """Trapezoidal integration in a common frame using observation times."""
    vw = np.einsum("nij,nj->ni", R, v_body)
    dt = np.diff(times) if times is not None else np.full(len(vw) - 1, FRAME_DT)
    p = np.zeros_like(vw)
    p[1:] = np.cumsum(0.5 * (vw[1:] + vw[:-1]) * dt[:, None], axis=0)
    return p if p0 is None else p + p0


def ate(est, gt):
    return float(np.sqrt(((est - gt) ** 2).sum(1).mean()))


def sim3_ate(est, gt):
    mu_e, mu_g = est.mean(0), gt.mean(0)
    E, Gm = est - mu_e, gt - mu_g
    var = (E ** 2).sum() / len(E)
    if var < 1e-12:
        return float(np.sqrt((Gm ** 2).sum(1).mean()))
    U, S, Vt = np.linalg.svd(Gm.T @ E / len(E))
    D = np.eye(3)
    if np.linalg.det(U @ Vt) < 0:
        D[2, 2] = -1
    Rm = U @ D @ Vt
    s = np.trace(np.diag(S) @ D) / var
    return float(np.sqrt(((gt - (s * E @ Rm.T + mu_g)) ** 2).sum(1).mean()))


def load(pattern):
    return [Flight(p) for p in sorted(glob.glob(pattern))]


# --- area score (docs/STUDENT_GUIDE.md); frontier read off the stage-2 server plot of 2026-11-17 (approximate)
STAGE2_BASELINES = [(80, 5.1), (110, 4.7), (40e3, 4.4), (2.0e6, 4.1), (50e6, 3.7), (3.0e9, 0.52)]
STEP_FUEL = 2e10


def frontier(points):
    pts = sorted(points)
    out, best = [], np.inf
    for f, e in pts:
        if e < best:
            out.append((f, e)); best = e
    return out


def _area_under(points, f_hi, e_ref):
    """log-area of the region {fuel in [f_min, f_hi], ate in [frontier(fuel), e_ref]} ... computed as area ABOVE frontier
    is unnecessary; we only need the dominated region's complement. Returns integral of log(e_ref/frontier(f)) dlog f."""
    fr = frontier(points)
    total = 0.0
    for i, (f, e) in enumerate(fr):
        f_next = fr[i + 1][0] if i + 1 < len(fr) else f_hi
        if f >= f_hi:
            break
        total += np.log(min(f_next, f_hi) / f) * max(0.0, np.log(e_ref / e))
    return total


def area_gain(point, baselines=STAGE2_BASELINES):
    """Percentage of the log-space reference rectangle that `point` (fuel, ate) adds beyond the baselines."""
    fastest = min(baselines, key=lambda x: (x[0], x[1]))
    e_ref = 1.2 * max(fastest[1], 0.001)
    f_hi = 1.2 * STEP_FUEL
    rect = np.log(f_hi / 1.0) * np.log(e_ref / 0.001)
    gain = _area_under(baselines + [point], f_hi, e_ref) - _area_under(baselines, f_hi, e_ref)
    return 100.0 * gain / rect
