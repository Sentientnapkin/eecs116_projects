"""i2 per-flight diagnostics of the frozen baseline (instrumented build i2_dbg == sw_a1_Ze0 estimates).
usage: python perflight.py EVALDIR POOLDIR CACHEDIR [workers]
Writes CACHEDIR/<id>.npz with per-frame series (c0 frame; 'up' = true gravity-up in c0) and scalar dict (json in 'meta')."""
import sys, json, glob
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
from viobench.tools.geometry import quaternion_to_matrix, interpolate_poses, poses_to_matrices, rotation_vectors

EV, POOL, CACHE = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
G = 9.81


def qm(q):
    return np.stack([quaternion_to_matrix(x) for x in q])


def parse_i2(path):
    rows = {}
    for l in open(path):
        if l.startswith('I2 '):
            f = l.split()
            rows[int(f[1])] = np.array(f[2:], float)
    return rows


def bias_truth(ep, win=5.0):
    """offline LS estimate of gyro and accel bias per window (body = IMU frame) from GT + IMU."""
    imu = ep.imu; ti = imu[:, 0]
    gtt = ep.ground_truth[:, 0]; gtp = ep.ground_truth[:, 1:8]
    t0, t1 = max(ti[0], gtt[0]) + 0.1, min(ti[-1], gtt[-1]) - 0.1
    T = poses_to_matrices(interpolate_poses(gtt, gtp, ti.clip(t0, t1)))
    Rwb = T[:, :3, :3]
    dR = np.einsum('nji,njk->nik', Rwb[:-1], Rwb[1:])
    w_true = rotation_vectors(dR) / np.diff(ti)[:, None]
    tm = 0.5 * (ti[:-1] + ti[1:])
    gyro_mid = 0.5 * (imu[:-1, 4:7] + imu[1:, 4:7])  # read_episode imu = [t, accel, gyro]
    out_t, bg, ba = [], [], []
    def pos(t):
        return poses_to_matrices(interpolate_poses(gtt, gtp, np.atleast_1d(t)))[:, :3, 3]
    for a in np.arange(t0, t1 - win + 1e-6, win):
        m = (tm >= a) & (tm < a + win)
        bg.append((gyro_mid[m] - w_true[m]).mean(0))
        # accel: sub-windows of 1 s: dv = int R (a - ba) dt - g z dt  ->  (int R dt) ba = int R a dt - g z dt - dv
        A, b = [], []
        for s in np.arange(a, a + win - 0.999, 1.0):
            k = (ti >= s) & (ti < s + 1.0); dt = np.gradient(ti)[k]
            Ri = Rwb[k]; ai = imu[k, 1:4]
            h = 0.02
            v0 = (pos(s + h) - pos(s - h))[0] / (2 * h); v1 = (pos(s + 1 + h) - pos(s + 1 - h))[0] / (2 * h)
            A.append((Ri * dt[:, None, None]).sum(0)); b.append(np.einsum('nij,nj->i', Ri * dt[:, None, None], ai) - np.array([0, 0, G]) * dt.sum() - (v1 - v0))
        x = np.linalg.lstsq(np.concatenate(A), np.concatenate(b), rcond=None)[0]
        out_t.append(a + win / 2); ba.append(x)
    return np.array(out_t), np.array(bg), np.array(ba)


def one(work):
    work = Path(work); fid = work.name
    try:
        arch = POOL / (fid + '.zip')
        logd = sorted((work / 'report/logs').glob('*/estimate.tum'))[0].parent
        ep = read_episode(arch, frames='none'); t = ep.frame_times - ep.frame_times[0]; n = len(t)
        gt = ep.ground_truth_state(); est = fill_missing_states(load_estimates(logd / 'estimate.tum', ep.frame_times))
        Twc = poses_to_matrices(ep.camera_poses_world())
        up = Twc[0, :3, :3].T @ np.array([0, 0, 1.0])  # true up in c0 axes
        Rg = qm(gt[:, 3:7]); Re = qm(est[:, 3:7])
        E = est[:, :3] - gt[:, :3]
        vg = np.einsum('nij,nj->ni', Rg, gt[:, 7:10]); ve = np.einsum('nij,nj->ni', Re, est[:, 7:10])  # c0-frame velocity
        dv = ve - vg
        rv = rotation_vectors(np.einsum('nij,nkj->nik', Re, Rg))  # c0-frame rotation error vector
        yaw = rv @ up
        rtilt = np.linalg.norm(rv - yaw[:, None] * up, axis=1)
        # internal state
        I = parse_i2(next(logd.glob('stderr.txt')))
        R_bc = ep.T_body_camera[:3, :3]
        Rwb_gt = np.einsum('nij,kj->nik', Twc[:, :3, :3], R_bc)
        gb_gt = Rwb_gt[:, 2, :]  # R^T z
        tilt = np.full(n, np.nan); bge = np.full((n, 3), np.nan); bae = np.full((n, 3), np.nan); Pd = np.full((n, 15), np.nan)
        trk = np.full((n, 7), np.nan); bgi = np.full((n, 3), np.nan); bai = np.full((n, 3), np.nan)
        spd_int = np.full(n, np.nan)
        for k, r in I.items():
            if 0 <= k < n:
                Rk = r[1:10].reshape(3, 3); gb = Rk[2, :]
                tilt[k] = np.degrees(np.arccos(np.clip(gb @ gb_gt[k] / np.linalg.norm(gb), -1, 1))) if r[0] > 0 else np.nan
                bgi[k] = r[16:19]; bai[k] = r[19:22]; Pd[k] = r[22:37]; trk[k] = r[37:44]; spd_int[k] = np.linalg.norm(r[10:13])
        # frame alignment check: internal speed vs output speed
        spd_out = np.linalg.norm(est[:, 7:10], axis=1)
        ok = np.isfinite(spd_int)
        align = float(np.median(np.abs(spd_int[ok] - spd_out[ok]))) if ok.any() else np.nan
        bt, bgt, bat = bias_truth(ep)
        # bias error per frame (interp truth)
        for j in range(3):
            bge[:, j] = bgi[:, j] - np.interp(t + ep.frame_times[0], bt, bgt[:, j])
            bae[:, j] = bai[:, j] - np.interp(t + ep.frame_times[0], bt, bat[:, j])
        np.savez_compressed(CACHE / (fid + '.npz'), t=t, E=E, up=up, dv=dv, vg=vg, yaw=yaw, rtilt=rtilt, tilt=tilt, bge=bge, bae=bae,
                            Pd=Pd, trk=trk, pg=gt[:, :3], pe=est[:, :3], bt=bt, bgt=bgt, bat=bat,
                            meta=json.dumps({'id': fid, 'align_med_speed_diff': align, 'n_i2': len(I)}))
        return fid, align
    except Exception as ex:
        return fid, 'ERR ' + repr(ex)[:200]


if __name__ == '__main__':
    CACHE.mkdir(parents=True, exist_ok=True)
    works = sorted(str(Path(p).parent) for p in glob.glob(str(EV / '*/report')))
    works = [w for w in works if not (CACHE / (Path(w).name + '.npz')).exists()]
    W = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    with ProcessPoolExecutor(W) as ex:
        for fid, a in ex.map(one, works, chunksize=2):
            print(fid, a, flush=True)
