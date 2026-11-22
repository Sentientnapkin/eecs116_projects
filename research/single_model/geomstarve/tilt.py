"""tilt.py RUNDIR POOL EP [T0 T1]: tilt error (deg, angle between est and true body z axes in world) and yaw error over time + re-anchor marks"""
import sys, glob, re, numpy as np
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
RUN, POOL, ep = sys.argv[1:4]; T0 = float(sys.argv[4]) if len(sys.argv) > 4 else 0; T1 = float(sys.argv[5]) if len(sys.argv) > 5 else 1e9
d = f'{RUN}/{ep}'; est = glob.glob(f'{d}/report/logs/*/estimate.tum')[0]; se = est.replace('estimate.tum', 'stderr.txt')
e = read_episode(f'{POOL}/{ep}.zip', frames='none'); t = np.asarray(e.frame_times); S = np.asarray(e.ground_truth_state())
E = fill_missing_states(load_estimates(est, t)); Tg, Te = poses_to_matrices(S), poses_to_matrices(E)
zt = Tg[:, :3, 2]; ze = Te[:, :3, 2]; tilt = np.degrees(np.arccos(np.clip(np.sum(zt * ze, 1), -1, 1)))
Rrel = np.einsum('nji,njk->nik', Tg[:, :3, :3], Te[:, :3, :3]); 
xt = Tg[:, :3, 0]; xe = Te[:, :3, 0]; yaw = np.degrees(np.arctan2(xe[:, 1], xe[:, 0]) - np.arctan2(xt[:, 1], xt[:, 0])); yaw = (yaw + 180) % 360 - 180
nan = {}
for line in open(se):
    if line.startswith('D '):
        f = int(line.split()[1][2:]); m = re.search(r'nanch=(\d+)', line); nan[f] = int(m.group(1))
prev = 0; tt = t - t[0]
for i in range(len(t)):
    a = nan.get(i + 1, prev); mark = '*' if a > prev else ' '; prev = a
    if T0 <= tt[i] <= T1 and (i % 10 == 0 or mark == '*'): print('%6.2f %s tilt %5.2f yaw %6.2f' % (tt[i], mark, tilt[i], yaw[i]))
print('tilt mean %.2f p90 %.2f max %.2f | yaw final %.1f' % (tilt.mean(), np.percentile(tilt, 90), tilt.max(), yaw[-1]))
