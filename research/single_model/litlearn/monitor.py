"""Risk-monitor test: net-vs-filter disagreement (2 s windows, filter attitude used for rotation) as early predictor of high final ATE, fold-3 flights. python monitor.py B 2.0"""
import sys, glob, json, numpy as np
sys.path.insert(0, "/dev/shm/sebastian-vio/viobench")
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
from viobench.tools.geometry import poses_to_matrices
var, WL = sys.argv[1], float(sys.argv[2]); n = int(WL * 20)
P = json.load(open(f'research/single_model/litlearn/imuvel_pred_{var}_{WL}.json'))
EV = 'research/results/single_model/lc_b11_r0/eval_f3'
R = []
for ep, v in P.items():
    p = glob.glob(f'{EV}/*/{ep}/report/logs/*/estimate.tum')
    e = read_episode(f'/data/backups/rganapa/Sebastian/tmp/lc_fold3_pool/{ep}.zip', frames='none')
    t = np.asarray(e.frame_times); S = np.asarray(e.ground_truth_state()); G = S[:, :3]; Es = fill_missing_states(load_estimates(p[0], t)); E = Es[:, :3]
    Rbc = np.asarray(e.T_body_camera)[:3, :3]; RE = poses_to_matrices(Es)[:, :3, :3]
    j = np.array(v['j']); sel = j % n == 0; js = j[sel]; mu = np.array(v['mu'])[sel]; sd = np.sqrt(np.exp(np.array(v['lv'])[sel]))
    dn = np.einsum('nij,nj->ni', RE[js] @ Rbc.T, mu); de = E[js] - E[js - n]
    dis = np.linalg.norm(dn - de, axis=1); z = np.linalg.norm((dn - de) / (sd + 0.05), axis=1)
    R.append(dict(ep=ep, ate=float(np.sqrt(np.mean(np.sum((E - G) ** 2, 1)))), t=t[js], dis=dis, z=z, err=np.linalg.norm(E[js] - G[js], axis=1)))
ate = np.array([r['ate'] for r in R])
def auc(s, y):
    o = np.argsort(s); rk = np.empty(len(s)); rk[o] = np.arange(len(s)); pos = y.astype(bool)
    return (rk[pos].mean() - (pos.sum() - 1) / 2) / (len(s) - pos.sum())
for T in (6, 10, 20, 60):
    s = np.array([np.mean(r['dis'][r['t'] <= T]) for r in R]); sm = np.array([np.max(r['dis'][r['t'] <= T]) for r in R])
    for thr in (1.0, 0.7):
        y = ate > thr
        print(f'first {T:2d}s  label ate>{thr}: n_pos={y.sum()}  AUC(mean dis)={auc(s, y):.2f}  AUC(max dis)={auc(sm, y):.2f}')
# detection time: first window where dis (2 s) > c, for flights with ate>1 vs false alarms
for c in (0.5, 0.7, 1.0):
    fa = [r['ep'] for r in R if r['ate'] <= 1 and (r['dis'] > c).any()]; hit = [(r['ep'], round(float(r['t'][np.argmax(r['dis'] > c)]), 1), round(float(r['err'][np.argmax(r['dis'] > c)]), 2)) for r in R if r['ate'] > 1 and (r['dis'] > c).any()]
    print(f'thr {c}: flagged bad {len(hit)}/{(ate > 1).sum()}  false alarms {len(fa)}/{(ate <= 1).sum()}  (ep, t_detect, err_at_detect) {hit[:9]}')
