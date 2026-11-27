"""Shared loaders: GT (camera0 pose at 200 Hz), frames, IMU, intrinsics, C-tracker tracks from the AUD_TRK stderr."""
import json, zipfile, io, numpy as np, collections as C

def qmat(w, x, y, z):
    n = np.sqrt(w*w+x*x+y*y+z*z); w, x, y, z = w/n, x/n, y/n, z/n
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])

def csv(z, suffix):
    n = [x for x in z.namelist() if x.endswith(suffix)][0]
    return np.loadtxt(io.StringIO(z.read(n).decode()), delimiter=',', comments='#', dtype=np.float64, ndmin=2)

class Flight:
    def __init__(self, zpath):
        z = zipfile.ZipFile(zpath); self.z = z
        self.ep = json.loads(z.read([x for x in z.namelist() if x.endswith('episode.json')][0]))
        c = self.ep['config']['camera']; self.K640 = (c['fx'], c['fy'], c['cx'], c['cy'])
        gt = csv(z, 'state_groundtruth_estimate0/data.csv'); self.gt_t = gt[:, 0].astype(np.int64)
        self.gt_p = gt[:, 1:4]; self.gt_Rb = np.array([qmat(*q) for q in gt[:, 4:8]])  # R_wb: gyro == GT angular rate in this frame (checked)
        imu = csv(z, 'imu0/data.csv'); self.imu_t = imu[:, 0].astype(np.int64); self.gyr = imu[:, 1:4]; self.acc = imu[:, 4:7]
        cam = np.loadtxt(io.StringIO(z.read([x for x in z.namelist() if x.endswith('cam0/data.csv')][0]).decode()), delimiter=',', comments='#', dtype=str, ndmin=2)
        self.fr_t = cam[:, 0].astype(np.int64); self.fr_name = cam[:, 1]
        T = np.array(self.ep['config']['imu']['T_cam_imu']).reshape(4, 4); self.R_ci = T[:3, :3]
        self.gt_R = self.gt_Rb @ self.R_ci.T  # R_wc
        self.gi = {t: i for i, t in enumerate(self.gt_t)}
        self.fgi = np.array([self.gi.get(t, np.argmin(abs(self.gt_t - t))) for t in self.fr_t])
        self.meta = self.ep['meta']['flight']; self.exposure = self.ep['config']['episode']['exposure_seconds']
        self.fov = self.ep['config']['camera']['horizontal_fov_degrees']

    def K(self, w):  # intrinsics at width w (host resize from 640)
        s = w / 640.0; fx, fy, cx, cy = self.K640
        return fx*s, fy*s, (cx+.5)*s-.5, (cy+.5)*s-.5

    def frame_pose(self, k):
        i = self.fgi[k]; return self.gt_R[i], self.gt_p[i]

    def image(self, k):
        import cv2
        n = [x for x in self.z.namelist() if x.endswith('cam0/data/' + self.fr_name[k])][0]
        return cv2.imdecode(np.frombuffer(self.z.read(n), np.uint8), cv2.IMREAD_GRAYSCALE)

def c_tracks(stderr_path):
    """AUD_TRK lines 'T frame slot born x y' -> dict key -> (frames[], xy[]) ; S lines -> array."""
    tr = C.defaultdict(list); S = []
    for l in open(stderr_path):
        if l.startswith('T ') and len(l.split()) == 6 and l.endswith('\n'):
            a = l.split(); tr[(int(a[2]), int(a[3]))].append((int(a[1]), float(a[4]), float(a[5])))
        elif l.startswith('S '):
            S.append([float(x) for x in l.split()[1:]])
    out = {}
    for k, v in tr.items():  # split on frame gaps (slot reuse with same born is impossible, but be safe)
        v.sort(); seg = [v[0]]; n = 0
        for a in v[1:]:
            if a[0] != seg[-1][0] + 1:
                out[k + (n,)] = np.array(seg); seg = []; n += 1
            seg.append(a)
        out[k + (n,)] = np.array(seg)
    return out, np.array(S)

def triangulate(Rs, ps, uv):
    """GT-pose triangulation of normalized bearings uv (m x 2): linear LS + 5 GN steps. Returns X, residuals (m x 2, normalized)."""
    A = []; b = []
    for R, p, (u, v) in zip(Rs, ps, uv):
        Rc = R.T
        for e in (np.array([1, 0, -u]), np.array([0, 1, -v])):
            a = e @ Rc; A.append(a); b.append(a @ p)
    A = np.array(A); b = np.array(b)
    X = np.linalg.lstsq(A, b, rcond=None)[0]
    for _ in range(5):
        J = []; r = []
        for R, p, (u, v) in zip(Rs, ps, uv):
            q = R.T @ (X - p)
            if q[2] <= 1e-6: return None, None
            r += [q[0]/q[2]-u, q[1]/q[2]-v]
            J.append((np.array([1/q[2], 0, -q[0]/q[2]**2]) @ R.T)); J.append((np.array([0, 1/q[2], -q[1]/q[2]**2]) @ R.T))
        J = np.array(J); r = np.array(r)
        try: X = X - np.linalg.solve(J.T @ J + 1e-12*np.eye(3), J.T @ r)
        except np.linalg.LinAlgError: return None, None
    res = []
    for R, p, (u, v) in zip(Rs, ps, uv):
        q = R.T @ (X - p)
        if q[2] <= 1e-6: return None, None
        res.append([q[0]/q[2]-u, q[1]/q[2]-v])
    return X, np.array(res)
