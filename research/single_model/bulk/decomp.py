"""STEP 1 error decomposition of B6 on 711 fresh flights (post-hoc oracle replacement tests). python -B -m research.single_model.bulk.decomp"""
import glob, json, os, sys
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, "/dev/shm/sebastian-vio/viobench")
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states, valid_states
POOL = '/data/backups/rganapa/Sebastian/tmp/fresh_pool'
RUN = sys.argv[1] if len(sys.argv) > 1 else 'fresh_fe2_fbh'
EV = f'research/results/single_model/{RUN}/eval'
OUTJ = f'research/single_model/bulk/decomp_{RUN}.json'

def rate(pe, pg): return float(np.sqrt(np.mean(np.sum((pe - pg) ** 2, 1))))

def increments(pe, A):  # A: (N,3,3) correction applied to step i
    d = np.diff(pe, axis=0)
    d2 = np.einsum('nij,nj->ni', A[:-1], d)   # A = inverse error rotation
    return np.vstack([pe[:1], pe[:1] + np.cumsum(d2, 0)])

def one(ep):
    p = glob.glob(f'{EV}/*/{ep}/report/logs/*/estimate.tum')
    if not p: return None
    e = read_episode(f'{POOL}/{ep}.zip', frames='none')
    t = np.asarray(e.frame_times); G = np.asarray(e.ground_truth_state())
    E = fill_missing_states(load_estimates(p[0], t))
    pe, pg = E[:, :3], G[:, :3]
    Re = poses_to_matrices(E)[:, :3, :3]; Rg = poses_to_matrices(G)[:, :3, :3]
    # gravity (up) direction in cam0: mean specific force rotated to cam0 with truth attitude
    Rbc = np.asarray(e.T_body_camera)[:3, :3]
    imu = np.asarray(e.imu); ti = imu[:, 0]; f = imu[:, 1:4] @ Rbc   # (R_bc^T f)^T
    idx = np.clip(np.searchsorted(t, ti), 0, len(t) - 1)
    fw = np.einsum('nij,nj->ni', Rg[idx], f)
    up = fw.mean(0); up /= np.linalg.norm(up)
    n = len(t); tt = t - t[0]
    Rerr = np.einsum('nij,nkj->nik', Re, Rg)
    Ru = Rerr @ up
    v = np.cross(np.broadcast_to(up, Ru.shape), Ru); c = Ru @ up
    V = np.zeros((n, 3, 3)); V[:, 0, 1] = -v[:, 2]; V[:, 0, 2] = v[:, 1]; V[:, 1, 0] = v[:, 2]; V[:, 1, 2] = -v[:, 0]; V[:, 2, 0] = -v[:, 1]; V[:, 2, 1] = v[:, 0]
    Sw = np.eye(3)[None] + V + V @ V / (1 + c)[:, None, None]
    Tw = np.einsum('nji,njk->nik', Sw, Rerr)
    sk = np.stack([Tw[:, 2, 1] - Tw[:, 1, 2], Tw[:, 0, 2] - Tw[:, 2, 0], Tw[:, 1, 0] - Tw[:, 0, 1]], 1) / 2
    yaw = np.degrees(np.arctan2(sk @ up, (np.trace(Tw, axis1=1, axis2=2) - 1) / 2))
    tilt = np.degrees(np.arccos(np.clip(c, -1, 1)))
    inv = lambda M: np.transpose(M, (0, 2, 1))
    ate = rate(pe, pg)
    out = dict(ep=ep, ate=ate, n=n, dur=float(tt[-1]))
    step = np.linalg.norm(np.diff(pg, axis=0), axis=1); out['path'] = float(step.sum())
    stepe = np.linalg.norm(np.diff(pe, axis=0), axis=1); out['path_e'] = float(stepe.sum())
    # --- oracle replacements (post-hoc, open loop)
    out['o_yaw'] = rate(increments(pe, inv(Tw)), pg)
    out['o_tilt'] = rate(increments(pe, inv(Sw)), pg)
    out['o_rot'] = rate(increments(pe, inv(Rerr)), pg)
    I = np.tile(np.eye(3), (n, 1, 1))
    from viobench.tools.runner.metrics import umeyama_sim3
    try:
        s3, R3, t3 = umeyama_sim3(pe, pg)
    except Exception:
        s3 = 1.0
    sl = out['path_e'] / max(out['path'], 1e-9)
    out['sim3_scale'] = float(s3); out['path_ratio'] = float(sl)
    out['o_scale_pl'] = rate(pe / sl, pg)
    out['o_scale_s3'] = rate(pe * (1 / s3) if s3 > 0 else pe, pg)
    # windowed (1 s) speed oracle: per-step rescale so est 1 s path length = true
    w = 20
    cs_e = np.concatenate([[0], np.cumsum(stepe)]); cs_g = np.concatenate([[0], np.cumsum(step)])
    ratio = np.ones(n - 1)
    for i in range(n - 1):
        a = max(0, i - w // 2); b = min(n - 1, i + w // 2)
        de = cs_e[b] - cs_e[a]; dg = cs_g[b] - cs_g[a]
        ratio[i] = dg / de if de > 1e-3 and dg > 1e-3 else 1.0
    d = np.diff(pe, axis=0) * np.clip(ratio, 0.2, 5)[:, None]
    pes = np.vstack([pe[:1], pe[:1] + np.cumsum(d, 0)])
    out['o_speed1s'] = rate(pes, pg)
    # speed + full rotation
    d = np.einsum('nij,nj->ni', inv(Rerr)[:-1], np.diff(pe, axis=0)) * np.clip(ratio, 0.2, 5)[:, None]
    out['o_rot_speed'] = rate(np.vstack([pe[:1], pe[:1] + np.cumsum(d, 0)]), pg)
    # startup offset oracles
    for T0 in (2.0, 5.0, 10.0):
        k = int(np.searchsorted(tt, T0)); k = min(k, n - 1)
        pp = pe.copy(); off = pe[k] - pg[k]
        pp[k:] = pe[k:] - off; pp[:k] = pg[:k]
        out[f'o_start{int(T0)}'] = rate(pp, pg)
        out[f'off{int(T0)}'] = float(np.linalg.norm(off))
        out[f'err{int(T0)}'] = float(np.linalg.norm(pe[k] - pg[k]))
    # first-5s error contribution to mse
    err = pe - pg; e2 = np.sum(err ** 2, 1)
    k5 = int(np.searchsorted(tt, 5.0))
    out['mse_first5'] = float(e2[:k5].sum() / e2.sum()) if e2.sum() > 0 else 0
    out['mean_off'] = rate(pe - err.mean(0), pg)       # remove constant mean offset
    # per-axis fractions of squared error
    vert = err @ up; hor = err - vert[:, None] * up[None]
    out['f_vert'] = float((vert ** 2).sum() / e2.sum())
    # travel direction (horizontal), along / cross
    tr = pg[-1] - pg[0]; trh = tr - (tr @ up) * up; nn = np.linalg.norm(trh)
    if nn > 0.3:
        ex = trh / nn; ey = np.cross(up, ex)
        out['f_along'] = float(((err @ ex) ** 2).sum() / e2.sum()); out['f_cross'] = float(((err @ ey) ** 2).sum() / e2.sum())
    else:
        out['f_along'] = out['f_cross'] = None
    out['o_vert0'] = rate(pe - vert[:, None] * up[None], pg)  # vertical error removed
    out['yaw_end'] = float(yaw[-1]); out['yaw_rms'] = float(np.sqrt(np.mean(yaw ** 2)))
    out['tilt_end'] = float(tilt[-1]); out['tilt_rms'] = float(np.sqrt(np.mean(tilt ** 2)))
    out['yaw_rms5'] = float(np.sqrt(np.mean(yaw[k5:] ** 2))) if k5 < n else 0
    out['tilt_rms5'] = float(np.sqrt(np.mean(tilt[k5:] ** 2))) if k5 < n else 0
    # yaw error growth: slope deg/s (lsq) after 5 s
    if n - k5 > 10:
        out['yaw_slope'] = float(np.polyfit(tt[k5:], yaw[k5:], 1)[0])
    # error growth after 5 s
    out['grow'] = float(np.linalg.norm(err[-1] - err[k5])) if k5 < n else 0
    out['path_after5'] = float(step[k5:].sum()); out['t_after5'] = float(tt[-1] - tt[k5])
    out['speed_mean'] = out['path'] / out['dur']
    out['en1hz'] = [float(np.linalg.norm(err[i])) for i in range(0, n, 20)]
    out['ev1hz'] = [float(err[i] @ up) for i in range(0, n, 20)]
    ker = np.ones(41) / 41; sm = np.column_stack([np.convolve(err[:, j], ker, 'same') for j in range(3)])
    out['hf'] = float(np.sqrt(np.mean(np.sum((err - sm) ** 2, 1))))   # error faster than ~2 s
    out['lf'] = float(np.sqrt(np.mean(np.sum(sm ** 2, 1))))
    # error velocity: relative to truth, 1 s RPE-like translation error
    k1 = 20
    rp = (pe[k1:] - pe[:-k1]) - (pg[k1:] - pg[:-k1])
    out['rpe1s'] = float(np.sqrt(np.mean(np.sum(rp ** 2, 1))))
    return out

if __name__ == '__main__':
    eps = sorted(os.path.basename(p)[:-4] for p in glob.glob(POOL + '/*.zip'))
    with Pool(12) as p:
        rows = [r for r in p.map(one, eps) if r]
    json.dump(rows, open(OUTJ, 'w'))
    print(len(rows), np.mean([r['ate'] for r in rows]))
