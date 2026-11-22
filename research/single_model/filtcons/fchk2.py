"""fchk2.py EVALDIR POOL : for FO features, triangulation rms under TRUTH poses vs under ESTIMATED poses (estimate.tum);
can an estimate-only rms threshold separate truth outliers? (analysis only)"""
import sys, glob, numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
d, pool = sys.argv[1], sys.argv[2]; FX = 150.0
def tri(T, obs):
    A = np.zeros((3, 3)); bb = np.zeros(3)
    for fi, x, y in obs:
        r = T[fi][:3, :3] @ np.array([x, y, 1.0]); r /= np.linalg.norm(r); M = np.eye(3) - np.outer(r, r); A += M; bb += M @ T[fi][:3, 3]
    P = np.linalg.solve(A, bb); res = []
    for fi, x, y in obs:
        pc = T[fi][:3, :3].T @ (P - T[fi][:3, 3]); res += [x - pc[0] / pc[2], y - pc[1] / pc[2]]
    return float(np.sqrt(np.mean(np.square(res)))) * FX
out = []
for f in sorted(glob.glob(d + '/*/report/logs/*/stderr.txt')):
    ep = f.split('/report/')[0].split('/')[-1]
    e = read_episode(f'{pool}/{ep}.zip', frames='none'); Tg = poses_to_matrices(e.camera_poses_world()); t = np.asarray(e.frame_times)
    Te = poses_to_matrices(fill_missing_states(load_estimates(f.replace('stderr.txt', 'estimate.tum'), t))); n = len(Tg)
    cf = {}
    for line in open(f):
        if line.startswith('C '): a, b = line.split()[1:3]; cf[int(a)] = int(b)
        elif line.startswith('FO '):
            h, b = line.split('|'); hv = h.split(); acc, ratio, no = int(hv[2]), float(hv[3]), int(hv[4]); v = b.split()
            obs = [(cf.get(int(v[3 * k])), float(v[3 * k + 1]), float(v[3 * k + 2])) for k in range(no)]
            if any(o[0] is None or o[0] >= n for o in obs): continue
            try: out.append((acc, ratio, no, tri(Tg, obs), tri(Te, obs)))
            except np.linalg.LinAlgError: pass
O = np.array(out); a = O[O[:, 0] == 1]
bad = a[:, 3] > 2
print('accepted', len(a), 'truth-outliers(>2px)', bad.sum())
for th in (0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
    rej = a[:, 4] > th
    print('est-rms > %.2f px: rejects %.3f of accepted; catches %.2f of outliers; inlier loss %.3f' % (th, rej.mean(), (rej & bad).sum() / max(bad.sum(), 1), (rej & ~bad).sum() / max((~bad).sum(), 1)))
print('est-rms median inliers %.2f outliers %.2f' % (np.median(a[~bad, 4]), np.median(a[bad, 4])))
