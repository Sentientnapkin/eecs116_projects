"""ts.py EVALDIR POOLDIR EP T0 T1 [step]: per-frame time series (truth vs filter) for one flight of an FC_LOG+TC_LOG run"""
import sys, glob, re, numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
d, pool, ep, t0, t1 = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5]); st = int(sys.argv[6]) if len(sys.argv) > 6 else 5
se = glob.glob(f'{d}/{ep}/report/logs/*/stderr.txt')[0]
e = read_episode(f'{pool}/{ep}.zip', frames='none'); t = np.asarray(e.frame_times); S = np.asarray(e.ground_truth_state()); Tg = poses_to_matrices(S)
vg = np.einsum('nij,nj->ni', Tg[:, :3, :3], S[:, 7:10])
N = []; Dl = []
for line in open(se):
    if line.startswith('N '): N.append([float(x) for x in line.split()[1:]])
    elif line.startswith('D '): Dl.append(line.strip())
N = np.array(N); 
for k in range(0, len(N), 1):
    i = k + 1; tt = t[i] - t[0]
    if tt < t0 or tt > t1 or k % st: continue
    vc = N[k, 10:13]; pv = np.sqrt(N[k, 13:16].sum()); ep_ = N[k, 1:4] - Tg[i, :3, 3]
    m = re.search(r'live=(\d+) used=(\d+) u20=(\d+) att=(\d+) gate=(\d+) tri=(\d+) nis=([\d.]+).*fire=(\d+)', Dl[k])
    print('t %5.2f true %s |%.2f| filt %s |%.2f| ev %.2f pvsd %.3f perr %.2f | live %s u20 %s att %s gate %s tri %s nis %s fire %s' % (tt, np.round(vg[i], 2), np.linalg.norm(vg[i]), np.round(vc, 2), np.linalg.norm(vc), np.linalg.norm(vc - vg[i]), pv, np.linalg.norm(ep_), *m.groups()[0:1], *m.groups()[2:8]))
