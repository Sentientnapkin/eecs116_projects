"""offline ceiling: dead-reckon position from the net's body velocities (rotated with TRUTH attitude), ATE vs truth; per flight vs HM40 ATE."""
import sys, json, numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import poses_to_matrices
P = np.load(sys.argv[1]); pool = sys.argv[2]; T = {r['ep']: r['ate_rmse'] for r in json.load(open(sys.argv[3]))}
out = []
for i, ep in enumerate(P['names']):
    m = P['fid'] == i; a = P['anchor'][m]; mu = P['mu'][m]; y = P['y'][m]
    e = read_episode(f'{pool}/{ep}.zip', frames='none'); S = np.asarray(e.ground_truth_state()); n = len(S); t = np.asarray(e.frame_times)
    Tb = poses_to_matrices(S[:, :7]) @ np.linalg.inv(np.asarray(e.T_body_camera))  # world_cam0 <- body? (camera pose * T_cb)
    pos_t = poses_to_matrices(S[:, :7])[:, :3, 3]
    for vv, tag in ((mu, 'net'), (y, 'truthvb')):
        p = np.zeros(3); est = [p.copy()]; fr = [5 * (a[0] + 1)]
        for k in range(len(a)):
            fK = 5 * (a[k] + 1)
            if fK + 5 >= n: break
            vw = Tb[fK, :3, :3] @ vv[k]
            p = p + vw * (t[fK + 5] - t[fK]) if True else p; est.append(p.copy()); fr.append(fK + 5)
        fr = np.array(fr); est = np.array(est) + pos_t[fr[0]]
        err = np.linalg.norm(est - pos_t[fr], axis=1)
        out.append((ep, tag, float(np.sqrt((err ** 2).mean()))))
R = {}
for ep, tag, v in out: R.setdefault(ep, {})[tag] = v
eps = sorted(R, key=lambda e: -T.get(e, 0))
for ep in eps[:12]: print('%-36s HM40 %.2f  netDR %.2f  truthDR %.2f' % (ep, T[ep], R[ep]['net'], R[ep]['truthvb']))
print('mean HM40 %.3f netDR %.3f truthDR %.3f' % (np.mean([T[e] for e in eps]), np.mean([R[e]['net'] for e in eps]), np.mean([R[e]['truthvb'] for e in eps])))
