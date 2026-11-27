"""r6 flight loader + IMU preintegration + KLT tracks (python prototype; privileged GT only for evaluation/oracles)."""
import sys, json
import numpy as np
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import quaternion_to_matrix, interpolate_poses

G9 = 9.81


def skew(a):
    return np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])


def expm(w):
    th = np.linalg.norm(w)
    K = skew(w)
    if th < 1e-9: return np.eye(3) + K
    return np.eye(3) + np.sin(th) / th * K + (1 - np.cos(th)) / th ** 2 * K @ K


def logm(R):
    c = np.clip((np.trace(R) - 1) / 2, -1, 1); th = np.arccos(c)
    w = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    return w * (0.5 if th < 1e-9 else th / (2 * np.sin(th)))


class Flight:
    def __init__(self, zpath, nframes=41, frames=True, res=(320, 240)):
        ep = read_episode(zpath, frames='lazy' if frames else 'none')
        self.ep = ep; self.name = ep.name; self.meta = ep.meta.get('flight', {})
        self.ft = ep.frame_times[:nframes].copy(); self.N = len(self.ft)
        self.imu = ep.imu  # t, ax, ay, az, gx, gy, gz (body)
        cam = ep.config['camera']; s = res[0] / 640.0
        self.K = np.array([[cam['fx'] * s, 0, (cam['cx'] + .5) * s - .5], [0, cam['fy'] * s, (cam['cy'] + .5) * s - .5], [0, 0, 1]])
        self.Kinv = np.linalg.inv(self.K); self.res = res
        self.T_bc = ep.T_body_camera; self.R_bc = self.T_bc[:3, :3]; self.p_bc = self.T_bc[:3, 3]
        gt = ep.ground_truth; self.gt = gt
        if frames:
            import cv2
            self.gray = []
            for k in range(self.N):
                f = ep.frames[k]; f = cv2.resize(f, res, interpolation=cv2.INTER_AREA)
                self.gray.append(cv2.cvtColor(f, cv2.COLOR_RGB2GRAY))

    # ---------------- ground truth (body = IMU frame, world z up) ----------------
    def gt_pose(self, t):
        P = interpolate_poses(self.gt[:, 0], self.gt[:, 1:8], np.atleast_1d(t))
        return np.array([quaternion_to_matrix(p[3:7]) for p in P]), P[:, :3]

    def gt_vel(self, t, h=0.005):
        t = np.atleast_1d(t)
        _, pa = self.gt_pose(t + h); _, pb = self.gt_pose(t - h)
        return (pa - pb) / (2 * h)

    def oracle_biases(self, T=20.0):
        """LS estimates of (constant) accel + gyro bias over the first T s from GT (offline oracle)."""
        im = self.imu[(self.imu[:, 0] > self.gt[0, 0] + 0.05) & (self.imu[:, 0] < min(T, self.gt[-1, 0] - 0.05))]
        t = im[:, 0]; h = 0.005
        Rw, p0 = self.gt_pose(t); _, pp = self.gt_pose(t + h); _, pm = self.gt_pose(t - h)
        aw = (pp - 2 * p0 + pm) / h ** 2
        f = np.einsum('nji,nj->ni', Rw, aw - np.array([0, 0, -G9]))
        Ra, _ = self.gt_pose(t - h); Rb, _ = self.gt_pose(t + h)
        w = np.array([logm(Ra[i].T @ Rb[i]) / (2 * h) for i in range(len(t))])
        ba = np.median(im[:, 1:4] - f, 0); bg = np.mean(im[:, 4:7] - w, 0)
        return ba, bg, (im[:, 1:4] - f - ba).std(0), (im[:, 4:7] - w - bg).std(0)

    # ---------------- preintegration from frame 0 ----------------
    def preint(self, bg=np.zeros(3), ba_lin=np.zeros(3), Rgt=False):
        """For frames k: R_k (b0->bk rotation, i.e. R_{b0 bk}), alpha_k, beta_k (accel-only position/velocity increments in b0),
        Bp_k, Bv_k (bias Jacobians: p_k = t v0 + .5 t^2 g + alpha - Bp ba), dt_k = t_k - t_0.
        Zero-order hold: the IMU row at t_n covers (t_{n-1}, t_n]. Rgt: rotations from GT instead of gyro."""
        t0 = self.ft[0]; im = self.imu[self.imu[:, 0] > t0 - 0.0051]
        out = {k: [] for k in ('R', 'al', 'be', 'Bp', 'Bv', 'dt')}
        R = np.eye(3); al = np.zeros(3); be = np.zeros(3); Bp = np.zeros((3, 3)); Bv = np.zeros((3, 3)); tc = t0
        if Rgt:
            Rg, _ = self.gt_pose(np.concatenate([[t0], im[:, 0]])); R0gt = Rg[0]
        n = 0
        for k in range(self.N):
            tk = self.ft[k]
            while tc < tk - 1e-9:
                tn = im[n, 0]; te = min(tn, tk); dt = te - tc
                if dt > 0:
                    a = im[n, 1:4] - ba_lin
                    if Rgt:
                        Rm = R0gt.T @ interpolate_rot(self, 0.5 * (tc + te))
                    else:
                        Rm = R @ expm((im[n, 4:7] - bg) * dt * 0.5)
                    al = al + be * dt + 0.5 * Rm @ a * dt * dt; be = be + Rm @ a * dt
                    Bp = Bp + Bv * dt + 0.5 * Rm * dt * dt; Bv = Bv + Rm * dt
                    R = (R0gt.T @ interpolate_rot(self, te)) if Rgt else R @ expm((im[n, 4:7] - bg) * dt)
                    tc = te
                if tn <= tk + 1e-9: n += 1
            out['R'].append(R.copy()); out['al'].append(al.copy()); out['be'].append(be.copy())
            out['Bp'].append(Bp.copy()); out['Bv'].append(Bv.copy()); out['dt'].append(tk - t0)
        return {k: np.array(v) for k, v in out.items()}

    def gt_init(self):
        """Truth in b0 frame: v0, g (gravity vector in b0), and per frame position/velocity of body in b0."""
        Rw, pw = self.gt_pose(self.ft); vw = self.gt_vel(self.ft)
        R0 = Rw[0]
        return {'v0': R0.T @ vw[0], 'g': R0.T @ np.array([0, 0, -G9]), 'p': (pw - pw[0]) @ R0, 'v': vw @ R0,
                'Rrel': np.einsum('ji,njk->nik', R0, Rw)}


_rot_cache = {}


def interpolate_rot(fl, t):
    R, _ = fl.gt_pose(t); return R[0]


# ---------------- KLT tracks ----------------
def tracks(fl, Rrel=None, maxc=150, minc=100, fb=0.7):
    """KLT tracks over the window. Rrel: optional per-frame b0->bk rotations for gyro-guided prediction.
    returns dict track_id -> list of (k, u, v)"""
    import cv2
    lk = dict(winSize=(15, 15), maxLevel=3, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
    T = {}; nid = 0
    def detect(img, pts):
        mask = np.full(img.shape, 255, np.uint8)
        for p in pts: cv2.circle(mask, (int(p[0]), int(p[1])), 8, 0, -1)
        c = cv2.goodFeaturesToTrack(img, maxCorners=maxc - len(pts), qualityLevel=0.01, minDistance=8, mask=mask, blockSize=5)
        return [] if c is None else c.reshape(-1, 2)
    cur = {}  # id -> (u,v)
    for p in detect(fl.gray[0], []):
        T[nid] = [(0, p[0], p[1])]; cur[nid] = p; nid += 1
    for k in range(1, fl.N):
        if cur:
            ids = list(cur); P0 = np.array([cur[i] for i in ids], np.float32).reshape(-1, 1, 2)
            flags = 0; P1i = None
            if Rrel is not None:  # rotation-only homography prediction (camera frame)
                Rc = fl.R_bc.T @ Rrel[k].T @ Rrel[k - 1] @ fl.R_bc  # c_{k-1} -> c_k
                H = fl.K @ Rc @ fl.Kinv
                ph = np.c_[P0.reshape(-1, 2), np.ones(len(ids))] @ H.T; P1i = (ph[:, :2] / ph[:, 2:]).astype(np.float32).reshape(-1, 1, 2)
                flags = cv2.OPTFLOW_USE_INITIAL_FLOW
            P1, st, _ = cv2.calcOpticalFlowPyrLK(fl.gray[k - 1], fl.gray[k], P0, P1i.copy() if P1i is not None else None, flags=flags, **lk)
            Pb, st2, _ = cv2.calcOpticalFlowPyrLK(fl.gray[k], fl.gray[k - 1], P1, P0.copy(), flags=cv2.OPTFLOW_USE_INITIAL_FLOW, **lk)
            err = np.linalg.norm((Pb - P0).reshape(-1, 2), axis=1)
            W, H_ = fl.res
            new = {}
            for j, i in enumerate(ids):
                u, v = P1[j, 0]
                if st[j, 0] and st2[j, 0] and err[j] < fb and 2 <= u < W - 2 and 2 <= v < H_ - 2:
                    new[i] = P1[j, 0]; T[i].append((k, float(u), float(v)))
            cur = new
        if len(cur) < minc:
            for p in detect(fl.gray[k], list(cur.values())):
                T[nid] = [(k, p[0], p[1])]; cur[nid] = p; nid += 1
    return {i: np.array(o) for i, o in T.items() if len(o) >= 2}
