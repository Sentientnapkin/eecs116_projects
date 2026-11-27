"""gen_oracle.py OUT.json POOL... : per flight key (first frame-0 IMU row accel) + oracle quantities (body frame = IMU frame):
 vb[k] = GT body velocity at frame k (k=0..40), ub0 = GT world-up in body axes at frame 0, Rwb[k] GT body->world rotations (k<=40)."""
import sys, json, glob
import numpy as np
from multiprocessing import Pool
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import quaternion_to_matrix
def one(z):
    ep = read_episode(z, frames='none')
    w0 = ep.imu_window(0)
    Tbc = np.asarray(ep.T_body_camera); Rbc = Tbc[:3, :3]
    cw = ep.camera_poses_world()             # (N,7) xyz qxyzw camera in world
    tw = ep.ground_truth_twist()
    K = 41
    vb = [(Rbc @ tw[k, :3]).tolist() for k in range(K)]
    Rwb = []
    for k in range(K):
        Rwc = quaternion_to_matrix(cw[k, 3:7]); Rwb.append((Rwc @ Rbc.T).tolist())
    ub0 = (np.array(Rwb[0]).T @ np.array([0, 0, 1.0])).tolist()
    return {'id': ep.name, 'key': w0[0, 1:4].tolist(), 'vb': vb, 'ub0': ub0, 'Rwb': Rwb, 'Rbc': Rbc.tolist(),
            'pc': [cw[k, :3].tolist() for k in range(K)]}
if __name__ == '__main__':
    zs = [z for p in sys.argv[2:] for z in sorted(glob.glob(p + '/*.zip'))]
    with Pool(8) as p: R = p.map(one, zs)
    json.dump(R, open(sys.argv[1], 'w')); print(len(R))
