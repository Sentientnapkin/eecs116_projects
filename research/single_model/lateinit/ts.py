"""Time series of one flight: est vs truth world velocity, error, yaw/tilt error.  python ts.py RUN SET EP [tmax]"""
import sys, glob
import numpy as np
sys.path.insert(0, '.')
from research.single_model.lateinit.diag import POOLS, rotvec
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
run, st, ep = sys.argv[1:4]; tmax = float(sys.argv[4]) if len(sys.argv) > 4 else 6
e = read_episode(f'{POOLS[st]}/{ep}.zip', frames='none')
t = np.asarray(e.frame_times); S = np.asarray(e.ground_truth_state())
Twc = poses_to_matrices(e.camera_poses_world()); up = Twc[0, :3, :3].T @ np.array([0, 0, 1.0])
est = glob.glob(f'research/results/single_model/{run}/eval_{st}/*/{ep}/report/logs/*/estimate.tum')
E = fill_missing_states(load_estimates(est[0], t))
Tg, Te = poses_to_matrices(S), poses_to_matrices(E)
vg = np.einsum('nij,nj->ni', Tg[:, :3, :3], S[:, 7:10]); ve = np.einsum('nij,nj->ni', Te[:, :3, :3], E[:, 7:10])
phi = rotvec(Te[:, :3, :3] @ np.swapaxes(Tg[:, :3, :3], 1, 2)); yaw = phi @ up; tilt = np.linalg.norm(phi - np.outer(yaw, up), axis=1)
err = Te[:, :3, 3] - Tg[:, :3, 3]
print('up', up.round(3))
for i in range(0, len(t)):
    tt = t[i] - t[0]
    if tt > tmax: break
    if i % 5: continue
    print(f'{tt:5.2f} vt {vg[i,0]:+5.2f} {vg[i,1]:+5.2f} {vg[i,2]:+5.2f} ve {ve[i,0]:+5.2f} {ve[i,1]:+5.2f} {ve[i,2]:+5.2f} |dv| {np.linalg.norm(ve[i]-vg[i]):4.2f} err {err[i,0]:+5.2f} {err[i,1]:+5.2f} {err[i,2]:+5.2f} yaw {yaw[i]:+.3f} tilt {tilt[i]:.3f}')
