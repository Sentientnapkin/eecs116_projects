"""fchk.py EVALDIR POOL : truth check of MSCKF features (FO lines, FC_LOG build): triangulate each feature's observations with
TRUTH camera poses; reprojection rms (px @ fx=150, full res), parallax, true depth; accepted vs gated (analysis only)."""
import sys, glob, os, numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
d, pool = sys.argv[1], sys.argv[2]; FX = 150.0
allr = []
for f in sorted(glob.glob(d + '/*/report/logs/*/stderr.txt')):
    ep = f.split('/report/')[0].split('/')[-1]
    e = read_episode(f'{pool}/{ep}.zip', frames='none'); T = poses_to_matrices(e.camera_poses_world()); n = len(T)
    cf = {}; R = []
    for line in open(f):
        if line.startswith('C '): a, b = line.split()[1:3]; cf[int(a)] = int(b)
        elif line.startswith('FO '):
            h, b = line.split('|'); hv = h.split(); fr, acc, ratio, no = int(hv[1]), int(hv[2]), float(hv[3]), int(hv[4]); v = b.split()
            obs = [(cf.get(int(v[3 * k])), float(v[3 * k + 1]), float(v[3 * k + 2])) for k in range(no)]
            if any(o[0] is None or o[0] >= n for o in obs): continue
            A = np.zeros((3, 3)); bb = np.zeros(3); rays = []
            for fi, x, y in obs:
                Rw = T[fi][:3, :3]; c = T[fi][:3, 3]; r = Rw @ np.array([x, y, 1.0]); r /= np.linalg.norm(r); rays.append(r)
                M = np.eye(3) - np.outer(r, r); A += M; bb += M @ c
            try: P = np.linalg.solve(A, bb)
            except np.linalg.LinAlgError: continue
            res = []
            for fi, x, y in obs:
                pc = T[fi][:3, :3].T @ (P - T[fi][:3, 3]); res += [x - pc[0] / pc[2], y - pc[1] / pc[2]]
            rms = float(np.sqrt(np.mean(np.square(res)))) * FX
            par = max(np.degrees(np.arccos(np.clip(rays[i] @ rays[j], -1, 1))) for i in range(len(rays)) for j in range(i + 1, len(rays)))
            dep = float(np.linalg.norm(P - T[obs[-1][0]][:3, 3]))
            R.append((fr, acc, ratio, no, rms, par, dep))
    R = np.array(R)
    if len(R) == 0: continue
    a = R[R[:, 1] == 1]; g = R[R[:, 1] == 0]
    print('%-34s nfeat %4d (%.2f/frame) acc %4d gated %3d | ACC truth-rms med %.2f p90 %.2f frac>2px %.2f >5px %.2f parallax med %.1f deg depth med %.1f | GATED rms med %.2f' % (
        ep[:34], len(R), len(R) / 1200, len(a), len(g), np.median(a[:, 4]), np.percentile(a[:, 4], 90), (a[:, 4] > 2).mean(), (a[:, 4] > 5).mean(), np.median(a[:, 5]), np.median(a[:, 6]),
        np.median(g[:, 4]) if len(g) else np.nan))
    allr.append(R)
R = np.vstack(allr); a = R[R[:, 1] == 1]
print('ALL acc', len(a), 'rms med %.2f p90 %.2f >2px %.3f >5px %.3f' % (np.median(a[:, 4]), np.percentile(a[:, 4], 90), (a[:, 4] > 2).mean(), (a[:, 4] > 5).mean()))
