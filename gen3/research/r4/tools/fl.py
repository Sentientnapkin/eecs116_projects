"""fl.py: flight loading (GT pose/vel at frame times, IMU, intrinsics) straight from the EuRoC zip (no PNG decode)."""
import zipfile, json, io, numpy as np

def qmat(q):
    """q (...,4) as w,x,y,z -> (...,3,3)"""
    q = q / np.linalg.norm(q, axis=-1, keepdims=True); w, x, y, z = np.moveaxis(q, -1, 0)
    return np.stack([1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w), 2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w), 2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)], -1).reshape(q.shape[:-1] + (3, 3))
POOLS = '/data/backups/rganapa/Sebastian/gen3/pools/'
def zpath(fid, pool='v3val'): return f'{POOLS}{pool}/{fid}.zip'
def _csv(z, name):
    n = [x for x in z.namelist() if x.endswith(name)][0]
    return np.loadtxt(io.StringIO(z.read(n).decode()), delimiter=',', comments='#')
class Flight:
    def __init__(self, fid, pool='v3val', qorder='wxyz'):
        z = zipfile.ZipFile(zpath(fid, pool)); self.id = fid
        self.ep = json.loads(z.read([x for x in z.namelist() if x.endswith('episode.json')][0]))
        c = self.ep['config']; self.cam = c['camera']; self.W = c['image']['width']
        g = _csv(z, 'state_groundtruth_estimate0/data.csv'); self.gt_t = g[:, 0] * 1e-9; self.gt_p = g[:, 1:4]
        q = g[:, 4:8]; self.q = q if qorder == 'wxyz' else q[:, [3, 0, 1, 2]]
        self.q = self.q * np.sign(np.cumprod(np.r_[1, np.sign(np.sum(self.q[1:] * self.q[:-1], 1))]))[:, None]
        im = _csv(z, 'imu0/data.csv'); self.imu_t = im[:, 0] * 1e-9; self.gyro = im[:, 1:4]; self.acc = im[:, 4:7]
        self.cam_t = np.array([float(l.split(',')[0]) for l in z.read([x for x in z.namelist() if x.endswith('cam0/data.csv')][0]).decode().splitlines() if l and l[0] != '#']) * 1e-9
        T = np.array(c['imu']['T_imu_cam']).reshape(4, 4); self.R_bc = T[:3, :3]; self.p_bc = T[:3, 3]
        # world velocity by central differences on the 200 Hz GT
        self.gt_v = np.gradient(self.gt_p, self.gt_t, axis=0)
        self.meta = self.ep['meta']['flight']
    def pose(self, t):
        """camera pose at time(s) t: (R_wc (n,3,3), p_wc (n,3)) by interpolation (nlerp at 200 Hz)"""
        t = np.atleast_1d(t); p = np.stack([np.interp(t, self.gt_t, self.gt_p[:, k]) for k in range(3)], 1)
        q = np.stack([np.interp(t, self.gt_t, self.q[:, k]) for k in range(4)], 1); return qmat(q) @ self.R_bc, p
    # NOTE (verified vs the accelerometer): the GT quaternion is the IMU-axes (body) orientation R_wb; R_wc = R_wb R_bc
    def vel_w(self, t):
        t = np.atleast_1d(t); return np.stack([np.interp(t, self.gt_t, self.gt_v[:, k]) for k in range(3)], 1)
    def vel_body(self, t):
        """IMU-axes body velocity (= R_bc * camera-axes velocity; lever arm is zero in this sim)"""
        R, _ = self.pose(t); vc = np.einsum('nji,nj->ni', R, self.vel_w(t)); return vc @ self.R_bc.T  # = R_wb^T v_w
