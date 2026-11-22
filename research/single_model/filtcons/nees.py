"""NEES / consistency analysis of FC_LOG=1 TC_LOG=1 runs (analysis only; truth never feeds the estimator).
  cd eecs116_projects; PY -B research/single_model/filtcons/nees.py EVALDIR POOLDIR OUT.json [workers]
Per flight: position/velocity NEES (expected 3) over frames, |e|^2/tr(C) ratios, yaw error vs predicted yaw sd,
split by starvation class (accepted features in the last 1 s) and time. Also checks logged position == estimate.tum."""
import sys, glob, json, os, re
import numpy as np
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
RX = re.compile(r'D f=(\d+) t=([\d.]+) live=(\d+) used=\d+ u20=\d+ att=(\d+) gate=(\d+) tri=(\d+) nis=([\d.]+) .* fire=(\d+) Pv=([\d.]+)')
POOL = None

def sym(a):
    return np.array([[a[0], a[3], a[4]], [a[3], a[1], a[5]], [a[4], a[5], a[2]]])

def yaw(Rm):
    return np.arctan2(Rm[..., 1, 0], Rm[..., 0, 0])

def one(d):
    ep = os.path.basename(d)
    try:
        est = glob.glob(f'{d}/report/logs/*/estimate.tum')[0]; se = est.replace('estimate.tum', 'stderr.txt')
        e = read_episode(f'{POOL}/{ep}.zip', frames='none')
        t = np.asarray(e.frame_times); S = np.asarray(e.ground_truth_state()); n = len(t)
        E = fill_missing_states(load_estimates(est, t))
        Tg, Te = poses_to_matrices(S), poses_to_matrices(E)
        vg = np.einsum('nij,nj->ni', Tg[:, :3, :3], S[:, 7:10])     # truth camera-centre velocity, world
        N = []; L = []; live = np.zeros(n); acc = np.zeros(n); fire = np.zeros(n); k = 0
        for line in open(se):
            if line.startswith('N '):
                N.append([float(x) for x in line.split()[1:]])
            elif line.startswith('L '):
                L.append([float(x) for x in line.split()[1:]])
            else:
                m = RX.match(line)
                if m:
                    f = int(m.group(1)) - 1
                    if 0 <= f < n:
                        live[f] = int(m.group(3)); acc[f] = int(m.group(4)) - int(m.group(5)) - int(m.group(6)); fire[f] = int(m.group(8))
        N = np.array(N); N = np.vstack([N[:1], N])[:n]; m_ = len(N)   # frame 0 (init) logs nothing
        fidx = {int(fn): i for i, fn in enumerate(N[:, 0])}; N = N[:, 1:]
        pc, Cp, vc, Cv, yv = N[:, 0:3], N[:, 3:9], N[:, 9:12], N[:, 12:18], N[:, 18]
        ep_ = pc - Te[:m_, :3, 3]                              # logged vs output position (consistency check)
        epos = pc - Tg[:m_, :3, 3]; evel = vc - vg[:m_]
        nees_p = np.array([epos[i] @ np.linalg.solve(sym(Cp[i]) + 1e-12 * np.eye(3), epos[i]) for i in range(m_)])
        nees_v = np.array([evel[i] @ np.linalg.solve(sym(Cv[i]) + 1e-12 * np.eye(3), evel[i]) for i in range(m_)])
        rv = (evel ** 2).sum(1) / np.maximum(Cv[:, :3].sum(1), 1e-12)
        ey = (yaw(Te[:m_, :3, :3] @ np.transpose(Tg[:m_, :3, :3], (0, 2, 1))) + np.pi) % (2 * np.pi) - np.pi
        acc1 = np.convolve(acc, np.ones(20), 'full')[:n][:m_]
        tt = t[:m_] - t[0]
        err = Te[:, :3, 3] - Tg[:, :3, 3]
        out = dict(ep=ep, ate=float(np.sqrt(np.mean(np.sum(err ** 2, 1)))), logchk=float(np.abs(ep_).max()),
                   vrmse=float(np.sqrt(np.mean((evel ** 2).sum(1)))), pv_sd=float(np.sqrt(np.median(Cv[:, :3].sum(1)))),
                   yaw_rms=float(np.sqrt(np.mean(ey ** 2))), yaw_sd=float(np.sqrt(np.median(np.maximum(yv, 0)))), nfire=int((fire > 0).sum()))
        for name, mask in (('all', tt >= 1.0), ('starv', (acc1 < 10) & (tt >= 1.0)), ('good', (acc1 >= 30) & (tt >= 1.0)), ('t1_5', (tt >= 1) & (tt < 5))):
            if mask.sum() < 5: continue
            out[f'np_{name}'] = float(np.median(nees_p[mask])); out[f'nv_{name}'] = float(np.median(nees_v[mask]))
            out[f'npm_{name}'] = float(np.mean(nees_p[mask])); out[f'nvm_{name}'] = float(np.mean(nees_v[mask]))
            out[f'rv_{name}'] = float(np.mean(rv[mask])); out[f'f_{name}'] = float(mask.mean())
            out[f'ny_{name}'] = float(np.mean(ey[mask] ** 2 / np.maximum(yv[mask], 1e-12)))
        if N.shape[1] >= 24:
            g = N[:, 21:24]; be = np.einsum('nji,nj->ni', Te[:m_, :3, :3], g); bt = np.einsum('nji,nj->ni', Tg[:m_, :3, :3], g)
            tilt = np.arccos(np.clip((be * bt).sum(1) / np.linalg.norm(be, axis=1) / np.linalg.norm(bt, axis=1), -1, 1)); tv = np.maximum(N[:, 19], 1e-12)
            msk = tt >= 1.0
            out.update(tilt_rms=float(np.sqrt(np.mean(tilt[msk] ** 2))), tilt_sd=float(np.sqrt(np.median(tv[msk]))), ntilt=float(np.mean(tilt[msk] ** 2 / tv[msk])),
                       tilt_max=float(tilt.max()), bg_sd=float(np.sqrt(np.median(N[msk, 20]))))
        out['spd_ratio'] = float(np.linalg.norm(vc, axis=1).mean() / max(np.linalg.norm(vg[:m_], axis=1).mean(), 1e-9))
        Z = []
        for l in L:
            fa, fk, na = int(l[0]), int(l[1]), int(l[2]); i = fidx.get(fk)
            if i is None: continue
            mw = np.array(l[3:6]); sd = np.array(l[6:9]); vw = np.array(l[9:12]); A = np.array(l[12:21]).reshape(3, 3); C = sym(l[21:27])
            g = vg[i]; zb = A.T @ (mw - g) / sd; zf = (vw - g) @ np.linalg.solve(C + 1e-12 * np.eye(3), vw - g)
            Z.append(dict(t=float(t[i] - t[0]), na=na, z=zb.tolist(), sd=sd.tolist(), nis_f=float(zf), net_spd=float(np.linalg.norm(mw)),
                          true_spd=float(np.linalg.norm(g)), filt_spd=float(np.linalg.norm(vw)), ef=float(np.linalg.norm(vw - g)), en=float(np.linalg.norm(mw - g))))
        out['L'] = Z
        return out
    except Exception as ex:
        import traceback
        return dict(ep=ep, error=traceback.format_exc()[-500:])

if __name__ == '__main__':
    run, POOL, outp = sys.argv[1], sys.argv[2], sys.argv[3]; w = int(sys.argv[4]) if len(sys.argv) > 4 else 16
    dirs = sorted(d for d in glob.glob(run + '/*') if os.path.isdir(d + '/report'))
    with ProcessPoolExecutor(w, initializer=globals().__setitem__, initargs=('POOL', POOL)) as ex:
        rows = list(ex.map(one, dirs, chunksize=2))
    json.dump(rows, open(outp, 'w')); print(len(rows), sum('error' in r for r in rows))
