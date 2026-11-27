"""gen_tab.py OUTDIR POOL... -> OUTDIR/or_tab.bin + or_meta.json : per-flight GT side data for the i3 oracle harness (offline diagnostics ONLY).
Binary: int32 nflights; per flight: double key[3] (frame-0 window first IMU row accel), int32 nframes, int32 float-offset;
then float32 data, 16 per frame: p_g[3] (IMU/body position, GT world), q_gb[4] (xyzw body->world), v_g[3] (world velocity, central diff +-5 ms),
bg[3], ba[3] (offline LS biases: +-1 s moving mean of (meas - GT-derived true) at 200 Hz)."""
import sys, json, glob, struct
import numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from multiprocessing import Pool
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import interpolate_poses, poses_to_matrices, rotation_vectors

def one(z):
    e = read_episode(z, frames='none')
    gt = e.ground_truth; tg = gt[:, 0]; ft = e.frame_times
    Tbc = np.asarray(e.T_body_camera)
    def body(times):
        return poses_to_matrices(interpolate_poses(tg, gt[:, 1:8], np.clip(times, tg[0], tg[-1])))
    Tb = body(ft); h = 0.005
    pb, pa = body(ft - h)[:, :3, 3], body(ft + h)[:, :3, 3]
    vg = (pa - pb) / (2 * h)
    q = interpolate_poses(tg, gt[:, 1:8], ft)[:, 3:7]
    # biases from 200 Hz IMU
    imu = e.imu; ti = imu[:, 0]
    sel = (ti - h >= tg[0]) & (ti + h <= tg[-1]); ti2 = ti[sel]
    T0, Tm, Tp = body(ti2), body(ti2 - h), body(ti2 + h)
    w = rotation_vectors(np.swapaxes(Tm[:, :3, :3], 1, 2) @ Tp[:, :3, :3]) / (2 * h)
    a = (Tp[:, :3, 3] - 2 * T0[:, :3, 3] + Tm[:, :3, 3]) / h ** 2
    f = np.einsum('nji,nj->ni', T0[:, :3, :3], a + np.array([0, 0, 9.81]))
    rg = imu[sel, 4:7] - w; ra = imu[sel, 1:4] - f
    cg, ca = np.cumsum(np.vstack([np.zeros(3), rg]), 0), np.cumsum(np.vstack([np.zeros(3), ra]), 0)
    lo = np.searchsorted(ti2, ft - 1.0); hi = np.searchsorted(ti2, ft + 1.0)
    n = np.maximum(hi - lo, 1)[:, None]
    bg = (cg[hi] - cg[lo]) / n; ba = (ca[hi] - ca[lo]) / n
    # residual check (should be ~ white noise 0.07 / 0.28 per axis)
    ig = np.clip(np.searchsorted(ft, ti2), 0, len(ft) - 1)
    sg = float(np.std(rg - bg[ig])); sa = float(np.std(ra - ba[ig]))
    key = e.imu_window(0)[0, 1:4]
    D = np.hstack([Tb[:, :3, 3], q, vg, bg, ba]).astype(np.float32)
    meta = dict(id=e.name, n=len(ft), key=key.tolist(), res_g=sg, res_a=sa, bg0=bg[0].tolist(), ba0=ba[0].tolist(),
                bg_drift=float(np.linalg.norm(bg[-1] - bg[0])), ba_drift=float(np.linalg.norm(ba[-1] - ba[0])),
                lever=float(np.linalg.norm(Tbc[:3, 3])), vmax=float(np.linalg.norm(vg, axis=1).max()))
    return meta, D

if __name__ == '__main__':
    out = sys.argv[1]; zs = [z for p in sys.argv[2:] for z in sorted(glob.glob(p + '/*.zip'))]
    with Pool(8) as p: R = p.map(one, zs)
    hdr = struct.pack('<i', len(R)); off = 0; body_ = []
    for m, D in R:
        hdr += struct.pack('<3dii', *m['key'], m['n'], off); off += D.size; body_.append(D.tobytes())
    pad = (-len(hdr)) % 4
    open(out + '/or_tab.bin', 'wb').write(hdr + b'\0' * pad + b''.join(body_))
    json.dump({'hdr_bytes': len(hdr) + pad, 'flights': [m for m, _ in R]}, open(out + '/or_meta.json', 'w'))
    keys = np.array([m['key'] for m, _ in R]); print(len(R), 'unique keys', len({tuple(k) for k in keys.tolist()}))
    for k in ('res_g', 'res_a', 'bg_drift', 'ba_drift', 'lever', 'vmax'):
        v = np.array([m[k] for m, _ in R]); print(k, 'median %.4f max %.4f' % (np.median(v), v.max()))
