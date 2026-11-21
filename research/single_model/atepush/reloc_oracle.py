"""reloc_oracle.py RUNDIR OUT: ceiling of relocalization against early keyframes (analysis only, truth).
For each flight: revisit frames = frames after T_MIN whose TRUE camera pose is within DIST m and ANG deg (optical axis) of a
keyframe pose from the first T_KF s. Counterfactual: at every revisit the position error is reset to the keyframe's error
(error at that keyframe time), drift continues from there (increments kept)."""
import sys, glob, json, os, numpy as np
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, '.')
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
CFG = [(1.0, 1.0, 30), (2.0, 1.0, 30), (3.0, 1.0, 35), (2.0, 0.5, 20), (5.0, 1.5, 45)]
def one(d):
    ep = os.path.basename(d)
    e = read_episode(f'/data/backups/rganapa/Sebastian/tmp/fresh_pool/{ep}.zip', frames='none')
    t = np.asarray(e.frame_times); S = np.asarray(e.ground_truth_state()); n = len(t)
    E = fill_missing_states(load_estimates(glob.glob(f'{d}/report/logs/*/estimate.tum')[0], t))
    Tg, Te = poses_to_matrices(S), poses_to_matrices(E); Tc = poses_to_matrices(e.camera_poses_world())
    err = Te[:, :3, 3] - Tg[:, :3, 3]; rms = lambda x: float(np.sqrt(np.mean(np.sum(x ** 2, 1))))
    out = dict(episode=ep, ate=rms(err))
    pc = Tc[:, :3, 3]; ax = Tc[:, :3, 2]
    inc = np.diff(err, axis=0, prepend=err[:1])
    for (tk, dist, ang) in CFG:
        nk = int(tk * 20); kf = np.arange(0, nk, 4)
        D = np.linalg.norm(pc[:, None, :] - pc[None, kf, :], axis=2); C = ax @ ax[kf].T
        ok = (D < dist) & (C > np.cos(np.radians(ang)))
        rv = ok.any(1); rv[:nk + 40] = False
        best = np.where(ok, D, 1e9).argmin(1)
        r = err.copy(); cur = err[0].copy()
        for i in range(n):
            cur = cur + inc[i] if i else err[0].copy()
            if rv[i]: cur = err[kf[best[i]]].copy()
            r[i] = cur
        out[f'cf_{tk}_{dist}_{ang}'] = rms(r); out[f'rv_{tk}_{dist}_{ang}'] = float(rv.mean())
    return out
if __name__ == '__main__':
    dirs = sorted(d for d in glob.glob(sys.argv[1] + '/*') if os.path.isdir(d + '/report'))
    with ProcessPoolExecutor(32) as ex: rows = list(ex.map(one, dirs, chunksize=4))
    json.dump(rows, open(sys.argv[2], 'w'))
    a = np.array([r['ate'] for r in rows]); print('n', len(rows), 'ate %.3f' % a.mean())
    for (tk, dist, ang) in CFG:
        k = f'{tk}_{dist}_{ang}'; c = np.array([r['cf_' + k] for r in rows]); f = np.array([r['rv_' + k] for r in rows])
        print(k, 'cf mean %.3f' % c.mean(), 'flights revisiting %.2f' % (f > 0).mean(), 'frac frames %.3f' % f.mean(), '>1m %d->%d' % ((a > 1).sum(), (c > 1).sum()))
