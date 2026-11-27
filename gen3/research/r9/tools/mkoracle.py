"""mkoracle.py -> ana/oracle.json + src/oracle_tab.h
Per flight (v3val + v1val): key = first delivered IMU row accel (ax,ay,az) of frame 0 (what the wasm sees),
v_b0 = GT IMU/body velocity at frame 0 in body axes, up_b0 = world up in body axes at frame 0,
plus body velocities at frames 0..40 (for standalone scoring of hypotheses). OFFLINE ORACLE ONLY (never in a submission)."""
import json, glob, sys
from pathlib import Path
from multiprocessing import Pool
import numpy as np
from viobench.tools.datasets.storage import read_episode
G = Path('/data/backups/rganapa/Sebastian/gen3'); R9 = G / 'research/r9'

def qmat(q):  # xyzw
    x, y, z, w = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])

def one(z):
    ep = read_episode(z, frames='none')
    imu0 = ep.imu_window(0)
    Tbc = np.asarray(ep.T_body_camera); Rbc = Tbc[:3, :3]; pbc = Tbc[:3, 3]
    gt = ep.ground_truth_state(); cw = ep.camera_poses_world()
    out = {'id': ep.name, 'key': [float(v) for v in imu0[0, 1:4]], 'nimu0': int(len(imu0))}
    vb = []
    for k in range(0, 41):
        vc = gt[k, 7:10]; wc = gt[k, 10:13]
        # camera-centre velocity (camera axes) -> body (IMU) velocity: v_b = Rbc (v_c - w_c x r_c), r_c = camera->imu offset in camera axes
        rc = Rbc.T @ (-pbc)
        vb.append((Rbc @ (vc - np.cross(wc, rc))).tolist())
    Rwc = qmat(cw[0, 3:7]); up_c = Rwc.T @ np.array([0, 0, 1.0]); up_b = Rbc @ up_c
    out.update(vb=vb, v_b0=vb[0], up_b0=up_b.tolist(), speed0=float(np.linalg.norm(vb[0])))
    return out

if __name__ == '__main__':
    zs = sorted(glob.glob(str(G / 'pools/v3val/*.zip'))) + sorted(glob.glob(str(G / 'pools/v1val/*.zip')))
    with Pool(8) as p: R = p.map(one, zs)
    keys = np.array([r['key'] for r in R])
    d = np.abs(keys[:, None, :] - keys[None, :, :]).max(-1) + np.eye(len(R)) * 1e9
    print('n', len(R), 'min key separation', d.min())
    json.dump(R, open(R9 / 'ana/oracle.json', 'w'))
    (R9 / 'src').mkdir(exist_ok=True)
    with open(R9 / 'src/oracle_tab.h', 'w') as f:
        f.write(f'#define OR_N {len(R)}\nstatic const double or_tab[OR_N][9] = {{\n')
        for r in R: f.write('{%r,%r,%r,%r,%r,%r,%r,%r,%r},\n' % tuple(r['key'] + r['v_b0'] + r['up_b0']))
        f.write('};\n')
    print('wrote', R9 / 'src/oracle_tab.h')
