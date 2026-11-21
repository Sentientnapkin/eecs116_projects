"""Counterfactual: remove the yaw error incrementally (rotate each estimated position increment by -yaw(t) about up).  python yawcf.py RUN"""
import sys, glob, json
import numpy as np
sys.path.insert(0, '.')
from research.single_model.lateinit.diag import POOLS, rotvec, rot_about, FS, FE
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
from concurrent.futures import ProcessPoolExecutor
run = sys.argv[1]
tab = json.load(open(f'research/single_model/tailcap/tables/{run[3:]}.json'))
def one(r):
    st, ep = r['set'], r['episode']
    e = read_episode(f'{POOLS[st]}/{ep}.zip', frames='none'); t = np.asarray(e.frame_times); S = np.asarray(e.ground_truth_state())
    Twc = poses_to_matrices(e.camera_poses_world()); up = Twc[0, :3, :3].T @ np.array([0, 0, 1.0])
    est = glob.glob(f'research/results/single_model/{run}/eval_{st}/*/{ep}/report/logs/*/estimate.tum')
    E = fill_missing_states(load_estimates(est[0], t)); Tg, Te = poses_to_matrices(S), poses_to_matrices(E)
    phi = rotvec(Te[:, :3, :3] @ np.swapaxes(Tg[:, :3, :3], 1, 2)); yaw = phi @ up
    tilt = phi - np.outer(yaw, up)
    pe = Te[:, :3, 3]; d = np.diff(pe, axis=0)
    d2 = np.array([rot_about(up, -yaw[k + 1]) @ d[k] for k in range(len(d))])
    p2 = np.vstack([pe[:1], pe[:1] + np.cumsum(d2, 0)])
    # also remove the full rotation error (yaw + tilt)
    d3 = np.array([(Tg[k + 1, :3, :3] @ Te[k + 1, :3, :3].T) @ d[k] for k in range(len(d))])
    p3 = np.vstack([pe[:1], pe[:1] + np.cumsum(d3, 0)])
    pt = Tg[:, :3, 3]
    f = lambda p: float(np.sqrt(np.mean(np.sum((p - pt) ** 2, 1))))
    return dict(episode=ep, set=st, ate=f(pe), noyaw=f(p2), norot=f(p3), dev=(st == 'fresh' and FS[ep]['fold'] < 3) or (st == 'sel' and FE[ep]['fold'] < 3))
with ProcessPoolExecutor(8) as ex: R = list(ex.map(one, tab, chunksize=8))
json.dump(R, open(f'research/single_model/lateinit/yawcf_{run}.json', 'w'))
for g in (True, False):
    S = [r for r in R if r['dev'] == g]
    a = np.array([r['ate'] for r in S]); y = np.array([r['noyaw'] for r in S]); z = np.array([r['norot'] for r in S])
    print('dev' if g else 'conf', len(S), f'ate {a.mean():.3f} no-yaw {y.mean():.3f} no-rot {z.mean():.3f} | >1: {(a>1).sum()} {(y>1).sum()} {(z>1).sum()}')
