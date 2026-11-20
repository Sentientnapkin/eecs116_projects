import struct, subprocess, sys
from pathlib import Path
import numpy as np, cv2
HERE = Path(__file__).parent
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import poses_to_matrices, interpolate_poses

def truth_vb(ep, j):
    gt = ep.ground_truth; t = ep.frame_times[j]; h = 0.005
    tt = [max(t - h, gt[0, 0]), t, min(t + h, gt[-1, 0])]
    Tb = [poses_to_matrices(interpolate_poses(gt[:, 0], gt[:, 1:8], np.array([x])))[0] for x in tt]
    vw = (Tb[2][:3, 3] - Tb[0][:3, 3]) / (tt[2] - tt[0])
    return Tb[1][:3, :3].T @ vw

def run_c(wdir, items, extra_cflags=()):
    exe = HERE / f'lc_test_{abs(hash(str(wdir))) % 10**6}.bin'
    subprocess.check_call(['gcc', '-O2', '-w', '-I', str(wdir), '-I', str(HERE), '-o', str(exe), str(HERE / 'lc_test.c'), '-lm', *extra_cflags])
    dumpf = HERE / f'lc_dump_{exe.stem}.bin'; outf = HERE / f'lc_out_{exe.stem}.bin'
    truth = []
    with open(dumpf, 'wb') as f:
        f.write(struct.pack('i', len(items)))
        for d, name in items:
            ep = read_episode(Path(d) / f'{name}.zip', frames='lazy'); cam = ep.config['camera']; Rbc = np.asarray(ep.T_body_camera)[:3, :3]
            f.write(np.array([cam['fx'] * 0.5, 159.5, 119.5, *Rbc.ravel()], np.float64).tobytes())
            for k in range(6):
                fr = cv2.resize(ep.frames[k], (320, 240), interpolation=cv2.INTER_AREA); w = np.asarray(ep.imu_window(k), np.float64)
                f.write(np.ascontiguousarray(fr).tobytes()); f.write(struct.pack('i', len(w))); f.write(w.tobytes())
            truth.append(truth_vb(ep, 5))
    subprocess.check_call([str(exe), str(dumpf), str(outf)])
    raw = np.fromfile(outf, np.uint8); per = 4 * (48 * 64 * 5 + 19 + 12) + 2 * 96 * 128
    out = {}
    for i, (d, name) in enumerate(items):
        fl = np.frombuffer(raw[i * per:i * per + 4 * (15360 + 31)].tobytes(), np.float32)[15379:]
        lv = np.clip(fl[9:12], -7, 4)
        out[name] = dict(mu=fl[6:9].tolist(), sd=np.exp(0.5 * lv).tolist(), truth=truth[i].tolist(), mu0=fl[0:3].tolist())
    exe.unlink(); dumpf.unlink(); outf.unlink()
    return out
