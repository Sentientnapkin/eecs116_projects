"""Cheap vision for the stage-3 low-fuel guest: direction of travel from a few rotation-compensated patches.

Everything here is written to be ported 1:1 to C (no OpenCV, fixed loop counts):
  * GRID points on a fixed grid in frame k-1; template = PATCH x PATCH samples at STRIDE px spacing (gray image)
  * rotation prediction: x' = K dR K^-1 x with dR from the guest's own gyro attitude (infinite-depth homography)
  * ITERS inverse-compositional Lucas-Kanade steps (bilinear sampling) refine x' -> measured position x''
  * translational flow u = x'' - x' at normalised position m = K^-1 x'. For translation t, u is parallel to
    (m_x t_z - t_x, m_y t_z - t_y), i.e. n . t = 0 with n = (u_y, -u_x, u_x m_y - u_y m_x)
  * A_k = EMA_TAU( sum_i w_i n_i n_i^T ); direction d_k = eigenvector of A_k's smallest eigenvalue (power iteration on
    tr(A) I - A), sign chosen so that the predicted flow agrees with the measured one (positive depths)
  * flow magnitude q_k = EMA of mean |u|/f (rad per frame): speed / depth, a speed cue
Points whose template has too little texture (min eigenvalue of the LK Hessian) or whose match residual is large are
dropped for that frame.

    python3 vis3.py --check ZIP [ZIP ...]     direction accuracy and ATE upper-bound checks on full episode zips
"""
import os
import sys

import numpy as np

GRID = tuple(int(v) for v in os.environ.get("VIS_GRID", "10,8").split(","))          # candidate points across, down (the NP most textured are tracked)
NP = int(os.environ.get("VIS_NP", 16))
CAND_PATCH, CAND_STRIDE = (int(v) for v in os.environ.get("VIS_CAND", "3,4").split(","))   # cheap texture test per candidate
PATCH = int(os.environ.get("VIS_PATCH", 5)); STRIDE = int(os.environ.get("VIS_STRIDE", 3))  # template samples per side, px spacing
ITERS = int(os.environ.get("VIS_ITERS", 2))
TAU = float(os.environ.get("VIS_TAU", 0.3))   # s, smoothing of the direction normal equations
GAP = int(os.environ.get("VIS_GAP", 3))        # track from frame k-GAP to k (GAP=2 doubles the flow)
MIN_EIG = 1.0          # texture threshold on the (mean) LK Hessian min eigenvalue
MAX_RES = float(os.environ.get("VIS_MAXRES", 25.0))         # max RMS match residual (gray levels)
DT = 0.05


def gray_of_rgb(frame):
    """v2: the green channel (one byte read per sample in the guest)"""
    return frame[..., 1].astype(np.float64)


def grid_points(W, H):
    m = STRIDE * (PATCH // 2) + 8
    xs = np.linspace(m, W - 1 - m, GRID[0]); ys = np.linspace(m, H - 1 - m, GRID[1])
    return np.array([(x, y) for y in ys for x in xs])


OFF = (np.arange(PATCH) - PATCH // 2) * STRIDE
OX, OY = np.meshgrid(OFF, OFF)


def bilinear(img, x, y):
    H, W = img.shape
    x = np.clip(x, 0, W - 1.001); y = np.clip(y, 0, H - 1.001)
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); ax = x - x0; ay = y - y0
    return ((1 - ay) * ((1 - ax) * img[y0, x0] + ax * img[y0, x0 + 1]) + ay * ((1 - ax) * img[y0 + 1, x0] + ax * img[y0 + 1, x0 + 1]))


class Tracker:
    def __init__(self, K, W, H):
        self.K = K; self.Ki = np.linalg.inv(K); self.f = K[0, 0]
        self.C = grid_points(W, H); self.P = self.C[:NP].copy()
        self.A = np.zeros((3, 3)); self.d = np.array([0.0, 0.0, 1.0]); self.q = 0.0
        self.tmpl = None

    def select(self, img):
        """the NP candidates with the largest structure-tensor min eigenvalue on a sparse CAND_PATCH^2 sample"""
        o = (np.arange(CAND_PATCH) - CAND_PATCH // 2) * CAND_STRIDE
        cx, cy = np.meshgrid(o, o)
        xs = self.C[:, 0, None, None] + cx; ys = self.C[:, 1, None, None] + cy
        gx = img[ys.astype(int), (xs + 1).astype(int)] - img[ys.astype(int), (xs - 1).astype(int)]
        gy = img[(ys + 1).astype(int), xs.astype(int)] - img[(ys - 1).astype(int), xs.astype(int)]
        a, b, c = (gx * gx).sum((1, 2)), (gx * gy).sum((1, 2)), (gy * gy).sum((1, 2))
        score = (a + c - np.sqrt((a - c) ** 2 + 4 * b * b)) / 2
        self.P = self.C[np.argsort(-score, kind="stable")[:NP]].copy()

    def set_template(self, img):
        self.select(img)
        x = self.P[:, 0, None, None] + OX; y = self.P[:, 1, None, None] + OY
        T = img[y.astype(int), x.astype(int)]                       # integer grid: no interpolation
        gx = np.zeros_like(T); gy = np.zeros_like(T)
        gx[:, :, 1:-1] = (T[:, :, 2:] - T[:, :, :-2]) / (2 * STRIDE); gy[:, 1:-1, :] = (T[:, 2:, :] - T[:, :-2, :]) / (2 * STRIDE)
        hxx = (gx * gx).sum((1, 2)); hxy = (gx * gy).sum((1, 2)); hyy = (gy * gy).sum((1, 2))
        det = hxx * hyy - hxy ** 2
        tr = hxx + hyy
        mineig = (tr - np.sqrt(np.maximum(tr ** 2 - 4 * det, 0))) / 2 / (PATCH * PATCH)
        self.tmpl = (T, gx, gy, hxx, hxy, hyy, det, mineig)

    def step(self, img, dR, retemplate=True):
        """dR: rotation camera k -> camera k-1 coordinates? We use d_k = dR^T d_{k-1} with dR = R_{k-1}^T R_k."""
        T, gx, gy, hxx, hxy, hyy, det, mineig = self.tmpl
        m0 = (self.Ki @ np.c_[self.P, np.ones(len(self.P))].T)      # (3, n) bearings in frame k-1
        m1 = dR.T @ m0
        xp = (self.K @ (m1 / m1[2])).T[:, :2]                        # rotation-predicted pixel positions in frame k
        x = xp.copy()
        H, W = img.shape
        R0 = STRIDE * (PATCH // 2)
        ok = (mineig > MIN_EIG) & (det > 1e-9)
        res = np.zeros(len(x))
        for _ in range(ITERS):
            # v2: the whole patch must lie inside the image (no per-sample clamping); one bilinear weight per patch
            ok &= (x[:, 0] - R0 >= 0) & (x[:, 0] + R0 < W - 1) & (x[:, 1] - R0 >= 0) & (x[:, 1] + R0 < H - 1)
            xs = np.where(ok, x[:, 0], R0); ys = np.where(ok, x[:, 1], R0)
            I = bilinear(img, xs[:, None, None] + OX, ys[:, None, None] + OY)
            e = I - T
            res = np.sqrt((e ** 2).mean((1, 2)))                    # v2: residual of the last iteration, before its update
            bx = (gx * e).sum((1, 2)); by = (gy * e).sum((1, 2))
            dx = (hyy * bx - hxy * by) / np.where(ok, det, 1); dy = (hxx * by - hxy * bx) / np.where(ok, det, 1)
            x -= np.c_[dx, dy] * ok[:, None]
        ok &= (res < MAX_RES) & (np.abs(x - xp).max(1) < 12)
        u = (x - xp) / self.f                                          # normalised translational flow
        mn = (self.Ki @ np.c_[xp, np.ones(len(xp))].T).T
        n = np.c_[u[:, 1], -u[:, 0], u[:, 0] * mn[:, 1] - u[:, 1] * mn[:, 0]] * ok[:, None]
        a = DT / TAU
        self.A = (1 - a) * self.A + a * (n.T @ n)
        # power iteration on tr(A) I - A starting from the previous direction (continuity)
        B = np.trace(self.A) * np.eye(3) - self.A
        d = self.d
        for _ in range(4):
            d = B @ d; d /= np.linalg.norm(d) + 1e-30
        pred = np.c_[mn[:, 0] * d[2] - d[0], mn[:, 1] * d[2] - d[1]]
        if ((pred * u).sum(1) * ok).sum() < 0:
            d = -d
        self.d = d
        nv = ok.sum()
        qk = np.sqrt((u ** 2).sum(1))[ok].mean() if nv else 0.0
        self.q = (1 - a) * self.q + a * qk
        if retemplate:
            self.set_template(img)
        return d.copy(), self.q, nv


ALT = os.environ.get("VIS_ALT", "0") == "1"   # alternate frames: even = select + template, odd = track (fuel: max, not sum)


def features_alt(frames_gray, R, K):
    """Two trackers; tracker (k//2)%2 takes its template on even frame k and tracks it on odd frame k+3.
    The direction / flow EMAs update on tracking frames only (every 2 frames, so alpha = 2 DT / TAU)."""
    N, H, W = frames_gray.shape
    trs = [Tracker(K, W, H) for _ in range(2)]
    Rs = [np.eye(3)] + list(R)
    shared = trs[0]
    out = np.zeros((N - 1, 5)); nv = 0
    global DT
    for k in range(0, N):
        if k % 2 == 0:
            trs[(k // 2) % 2].set_template(frames_gray[k])
        elif k >= 3:
            t = trs[((k - 3) // 2) % 2]
            t.A, t.d, t.q = shared.A, shared.d, shared.q
            dt0 = DT; DT = 2 * dt0
            try:
                d, q, nv = t.step(frames_gray[k], Rs[k - 3].T @ Rs[k], retemplate=False)
            finally:
                DT = dt0
            shared = t
        if k >= 1:
            out[k - 1] = [*shared.d, shared.q, nv]
    return out


def features_for(frames_gray, R, K):
    """frames_gray: (N, H, W); R: (N-1, 3, 3) guest attitude for frames 1..N-1 (fit_cheap.prep). -> (N-1, 5).
    With GAP=2 two trackers alternate, each matching frame k against frame k-2; they share the direction estimate."""
    if ALT:
        return features_alt(frames_gray, R, K)
    N, H, W = frames_gray.shape
    trs = [Tracker(K, W, H) for _ in range(GAP)]
    Rs = [np.eye(3)] + list(R)                     # attitude of frames 0..N-1
    for g in range(GAP):
        trs[g].set_template(frames_gray[g])
    shared = trs[0]
    out = np.zeros((N - 1, 5))
    for k in range(1, N):
        if k < GAP:
            out[k - 1] = [*shared.d, shared.q, 0]; continue
        t = trs[k % GAP]
        t.A, t.d, t.q = shared.A, shared.d, shared.q
        d, q, nv = t.step(frames_gray[k], Rs[k - GAP].T @ Rs[k])
        shared = t
        out[k - 1] = [*d, q, nv]
    return out


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import fit_cheap as fc
    from s3oracle import true_vcam, ate
    from viobench.tools.datasets.storage import read_episode
    from viobench.tools.abi.config import pinhole_intrinsics
    rows = []
    for path in sys.argv[2:]:
        name = os.path.basename(path)[:-4]
        f = np.load(os.path.expanduser(f"~/data/imucache/s3nb/{name}.npz"))
        f = {k: f[k] for k in f.files}
        ep = read_episode(path, frames="lazy")
        cfg, frames = ep.adapt((320, 240))
        K = np.array([[cfg["fx"], 0, cfg["cx"]], [0, cfg["fy"], cfg["cy"]], [0, 0, 1]])
        G = np.stack([gray_of_rgb(frames[i]) for i in range(len(frames))])
        R, _ = fc.prep(f)
        F = features_for(G, R, K)
        vt = true_vcam(f)[:len(R)]; sp = np.linalg.norm(vt, axis=1)
        dt = vt / np.maximum(sp[:, None], 1e-9)
        ang = np.degrees(np.arccos(np.clip((F[:, :3] * dt).sum(1), -1, 1)))
        moving = sp > 0.3
        z = float(np.sqrt((f["cam"] ** 2).sum(1).mean()))
        a_const = ate(f, R, F[:, :3] * 1.1)
        a_true = ate(f, R, F[:, :3] * sp[:, None])
        rows.append((z, a_const, a_true))
        print(f"{name:22s} dir err median {np.median(ang[moving]):5.1f} deg  (p75 {np.percentile(ang[moving], 75):5.1f})  "
              f"valid pts {F[:, 4].mean():4.1f}  ATE zero {z:5.2f}  est dir+1.1m/s {a_const:5.2f}  est dir+true speed {a_true:5.2f}", flush=True)
    r = np.array(rows)
    print(f"MEAN zero {r[:, 0].mean():.3f}  est-dir+const {r[:, 1].mean():.3f}  est-dir+true-speed {r[:, 2].mean():.3f}")


def nbr_one(path):
    """vision features for a full episode zip (RGB -> (R+2G+B)/4 gray at 320x240, like the guest) -> viscache/s3nb"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import fit_cheap as fc
    from viobench.tools.datasets.storage import read_episode
    name = os.path.basename(path)[:-4]
    SETN = os.environ.get("VIS_SET", "s3nb"); dst = os.path.expanduser(f"~/data/viscache/{SETN}/{name}.npz")
    if os.path.exists(dst):
        return name
    z = np.load(os.path.expanduser(f"~/data/imucache/{SETN}/{name}.npz")); f = {k: z[k] for k in z.files}
    ep = read_episode(path, frames="lazy")
    cfg, frames = ep.adapt((320, 240))
    K = np.array([[cfg["fx"], 0, cfg["cx"]], [0, cfg["fy"], cfg["cy"]], [0, 0, 1]])
    G = np.stack([gray_of_rgb(frames[i]) for i in range(len(frames))])
    R, _ = fc.prep(f)
    np.savez(dst, vis=features_for(G, R, K), fov=ep.config["camera"]["horizontal_fov_degrees"])
    return name


if __name__ == "__main__":
    if sys.argv[1] == "--check":
        main()
    elif sys.argv[1] == "--nbr":   # vis3.py --nbr ZIP ...
        from multiprocessing import Pool
        os.makedirs(os.path.expanduser(f"~/data/viscache/{os.environ.get('VIS_SET', 's3nb')}"), exist_ok=True)
        with Pool(int(os.environ.get("PROCS", 4))) as p:
            for n in p.imap_unordered(nbr_one, sys.argv[2:]):
                pass
        print("done", len(sys.argv) - 2)
