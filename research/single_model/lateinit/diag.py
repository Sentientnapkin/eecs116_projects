"""Decompose B16 error on flights into start-velocity / yaw / tilt / drift components (analysis only; truth used for scoring).
  python -B research/single_model/lateinit/diag.py RUN [thr] [--all]   RUN e.g. tc_b16r_r0 (dir under research/results/single_model)
Writes lateinit/diag_<RUN>.json (per-flight rows)."""
import sys, glob, json
import numpy as np
sys.path.insert(0, '.')
from research.guard_fusion import traj as T
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
HERE = 'research/single_model/lateinit'
POOLS = {'fresh': '/data/backups/rganapa/Sebastian/tmp/fresh_pool', 'sel': 'research/single_model/tailcap/pool_sel144'}
FS = json.load(open('research/single_model/tailcap/fresh_sets.json'))
FE = json.load(open('research/single_model/learned_c/feats.json'))

def rotvec(R):
    c = np.clip((np.trace(R, axis1=1, axis2=2) - 1) / 2, -1, 1); a = np.arccos(c)
    w = np.stack([R[:, 2, 1] - R[:, 1, 2], R[:, 0, 2] - R[:, 2, 0], R[:, 1, 0] - R[:, 0, 1]], 1)
    s = np.sin(a); f = np.where(s > 1e-9, a / (2 * np.maximum(s, 1e-12)), 0.5)
    return w * f[:, None]

def rot_about(u, ang):
    K = np.array([[0, -u[2], u[1]], [u[2], 0, -u[0]], [-u[1], u[0], 0]])
    return np.eye(3) + np.sin(ang) * K + (1 - np.cos(ang)) * K @ K

def yaw_align(pe, pt, u, trans):
    """best rotation about u (through origin, or with translation) of pe onto pt; returns rmse, angle"""
    best = (1e9, 0)
    for ang in np.linspace(-0.6, 0.6, 241):
        q = pe @ rot_about(u, ang).T
        if trans: q = q + (pt - q).mean(0)
        r = np.sqrt(np.mean(np.sum((q - pt) ** 2, 1)))
        if r < best[0]: best = (r, ang)
    return best

def analyse(run, st, ep):
    est = glob.glob(f'research/results/single_model/{run}/eval_{st}/*/{ep}/report/logs/*/estimate.tum')
    e = read_episode(f'{POOLS[st]}/{ep}.zip', frames='none')
    t = np.asarray(e.frame_times); S = np.asarray(e.ground_truth_state())
    Twc = poses_to_matrices(e.camera_poses_world())
    up = Twc[0, :3, :3].T @ np.array([0, 0, 1.0])  # world up in camera-0 axes
    E = fill_missing_states(load_estimates(est[0], t))
    Tg, Te = poses_to_matrices(S), poses_to_matrices(E)
    pt, pe = Tg[:, :3, 3], Te[:, :3, 3]
    err = pe - pt; en = np.linalg.norm(err, axis=1); ate = float(np.sqrt(np.mean(en ** 2)))
    vg = np.einsum('nij,nj->ni', Tg[:, :3, :3], S[:, 7:10]); ve = np.einsum('nij,nj->ni', Te[:, :3, :3], E[:, 7:10])
    dv = ve - vg
    phi = rotvec(Te[:, :3, :3] @ np.swapaxes(Tg[:, :3, :3], 1, 2))  # left error in c0 axes
    yaw = phi @ up; tilt = np.linalg.norm(phi - np.outer(yaw, up), axis=1)
    tt = t - t[0]
    def at(x, s): return float(x[min(np.searchsorted(tt, s), len(x) - 1)])
    dvn = np.linalg.norm(dv, axis=1)
    # error components
    trans_only = float(np.sqrt(np.mean(np.sum((err - err.mean(0)) ** 2, 1))))
    yo, yang = yaw_align(pe, pt, up, False); y4, y4ang = yaw_align(pe, pt, up, True)
    # 'start-velocity' counterfactual: remove the position error accumulated by t0 (rigid offset from the start phase)
    out = dict(episode=ep, set=st, ate=ate, dist=float(np.sum(np.linalg.norm(np.diff(pt, axis=0), axis=1))),
               rot_rmse=float(np.sqrt(np.mean(np.sum(phi ** 2, 1)))), vel_rmse=float(np.sqrt(np.mean(dvn ** 2))),
               ate_minus_trans=trans_only, ate_yaw0=yo, yaw0=yang, ate_4dof=y4, yaw4=y4ang)
    for s in (1, 2, 3, 5, 10, 20, 40):
        out[f'e{s}'] = at(en, s); out[f'dv{s}'] = at(dvn, s); out[f'yaw{s}'] = at(yaw, s); out[f'tilt{s}'] = at(tilt, s)
    # offset frozen at t0: if we subtract err(t0) from all later errors, how much ATE remains? (startup-explained share)
    for s in (3, 5, 10):
        k = np.searchsorted(tt, s); r = err.copy(); r[k:] -= err[k]; r[:k] = 0
        out[f'ate_post{s}'] = float(np.sqrt(np.mean(np.sum(r ** 2, 1))))
        out[f'ate_pre{s}'] = float(np.sqrt(np.mean(np.sum(np.where(np.arange(len(err))[:, None] < k, err, err[k]) ** 2, 1))))
    out['mean_speed'] = float(np.mean(np.linalg.norm(vg, axis=1))); out['speed0'] = float(np.linalg.norm(vg[0]))
    out['start'] = 'mid' if ep.startswith('fastmid') else 'static'
    return out

if __name__ == '__main__':
    run = sys.argv[1]; thr = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    tab = json.load(open(f'research/single_model/tailcap/tables/{run[3:]}.json')) if run.startswith('tc_') else None
    rows = []
    for r in tab:
        dev = (r['set'] == 'fresh' and FS[r['episode']]['fold'] < 3) or (r['set'] == 'sel' and FE[r['episode']]['fold'] < 3)
        if not dev: continue
        if r['ate'] <= thr and '--all' not in sys.argv: continue
        rows.append(analyse(run, r['set'], r['episode']))
    json.dump(rows, open(f'{HERE}/diag_{run}{"_all" if "--all" in sys.argv else ""}.json', 'w'))
    print(len(rows))
