"""tilt (gravity-direction) and yaw error over time from estimate.tum vs truth; truth world assumed z-up."""
import sys, glob, numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import poses_to_matrices
def series(est_path, zipp):
    S = np.asarray(read_episode(zipp, frames='none').ground_truth_state()); Tt = poses_to_matrices(S[:, :7])
    E = np.loadtxt(est_path); Te = poses_to_matrices(E[:, 1:8])
    n = min(len(Tt), len(Te)); Rt0 = Tt[0, :3, :3]
    g0 = Rt0.T @ np.array([0, 0, -1.0])
    out = []
    for k in range(n):
        Rr = Rt0.T @ Tt[k, :3, :3]; Re = Te[k, :3, :3]
        a, b = Re.T @ g0, Rr.T @ g0
        tilt = np.degrees(np.arccos(np.clip(a @ b, -1, 1)))
        dR = Re @ Rr.T; ang = np.degrees(np.arccos(np.clip((np.trace(dR) - 1) / 2, -1, 1)))
        out.append((k * 0.05, tilt, ang, np.linalg.norm(Te[k, :3, 3] - (Rt0.T @ (Tt[k, :3, 3] - Tt[0, :3, 3])))))
    return np.array(out)
if __name__ == '__main__':
    o = series(sys.argv[1], sys.argv[2]); step = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    for r in o[::step]: print('t %5.1f tilt %5.1f deg  rot %5.1f deg  pos %.2f' % tuple(r))
