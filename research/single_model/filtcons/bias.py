"""bias.py EVALDIR POOL : gyro-bias estimate vs truth-derived bias (gyro - R_bc w_true, flight mean) for FC_LOG runs (N line >= 27 fields)"""
import sys, glob, os, numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.datasets.storage import read_episode
d, pool = sys.argv[1], sys.argv[2]
for f in sorted(glob.glob(d + '/*/report/logs/*/stderr.txt')):
    ep = f.split('/report/')[0].split('/')[-1]
    e = read_episode(f'{pool}/{ep}.zip', frames='none'); imu = np.asarray(e.imu); t = np.asarray(e.frame_times); S = np.asarray(e.ground_truth_state())
    Rbc = np.asarray(e.T_body_camera)[:3, :3]; wb = S[:, 10:13] @ Rbc.T
    gi = np.searchsorted(imu[:, 0], t); gm = np.array([imu[gi[k - 1]:gi[k], 4:7].mean(0) for k in range(1, len(t))])
    bt = (gm - 0.5 * (wb[1:] + wb[:-1])).mean(0)
    N = np.array([[float(x) for x in l.split()[1:]] for l in open(f) if l.startswith('N ')])
    bg = N[:, 25:28]; bv = N[:, 21]
    s = []
    for ts in (1, 3, 5, 10, 30, 59):
        k = min(int(ts * 20) - 1, len(N) - 1); eb = bg[k] - bt
        s.append('%2ds |e| %.4f sd %.4f' % (ts, np.linalg.norm(eb), np.sqrt(bv[k])))
    print('%-34s btrue %s | %s' % (ep[:34], np.round(bt, 3), ' | '.join(s)))
