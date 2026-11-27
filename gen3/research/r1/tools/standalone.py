"""Standalone translation-direction evaluation vs GT.
python standalone.py LIST.txt OUTDIR WORKERS   (LIST: one zip path per line)
Per flight writes OUTDIR/<id>.npz with a record table (see COLS) + tracker stats."""
import sys, os, json, time
os.environ.setdefault('OMP_NUM_THREADS', '1'); os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from pathlib import Path
import numpy as np, cv2
cv2.setNumThreads(1)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
import r1dir as D
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import poses_to_matrices

G = Path('/data/backups/rganapa/Sebastian/gen3')
BASE_EVAL = G / 'evals/sw_a1_Ze0/v3val/sw_a1_Ze0-670bc1da'
KS = (1, 2, 3, 5, 10)
CONFIGS = [  # (name, method, rotation source, tracker)
    ('eig', 'eig', 'gyro', 'g'), ('eign', 'eign', 'gyro', 'g'), ('irls', 'irls', 'gyro', 'g'),
    ('ransac', 'ransac', 'gyro', 'g'), ('rirls', 'ransac_irls', 'gyro', 'g'), ('joint', 'joint', 'gyro', 'g'),
    ('rirls_gt', 'ransac_irls', 'gt', 'g'), ('rirls_bc', 'ransac_irls', 'gyro_b', 'g'),
    ('rirls_ug', 'ransac_irls', 'gyro', 'u'), ('cv5', 'cv5', None, 'g')]
COLS = ['j', 'k', 'cfg', 'err', 'err_us', 'sgn_ok', 'vote', 'ninl', 'n', 'par_med', 'par_p90', 'rrms', 'evr', 'ev1', 'sig_pred',
        'base_len', 'spd_gt', 'err_twist_gt', 'err_filter', 'spd_filter', 'cover']


def so3_exp(w): return D.so3_exp(w)


def gyro_rel(imu, t0, t1, bias):
    """body rotation R_b0^T R_b1 by integrating gyro (piecewise constant, sample k valid on (t_{k-1}, t_k])"""
    R = np.eye(3)
    ts = imu[:, 0]
    k = np.searchsorted(ts, t0, side='right')
    t = t0
    while t < t1 - 1e-12 and k < len(ts):
        te = min(ts[k], t1)
        R = R @ so3_exp((imu[k, 4:7] - bias) * (te - t))
        t = te; k += 1
    return R


class Tracker:
    def __init__(self, K, guided, maxn=160, minn=110):
        self.K, self.guided, self.maxn, self.minn = K, guided, maxn, minn
        self.pts = np.zeros((0, 2), np.float32); self.ids = np.zeros(0, int); self.nid = 0
        self.hist = {}  # frame -> (ids, pts)
        self.stats = dict(tracked=0, lost=0, fbfail=0)

    def detect(self, img, f):
        mask = np.full(img.shape, 255, np.uint8)
        for p in self.pts: cv2.circle(mask, (int(p[0]), int(p[1])), 8, 0, -1)
        need = self.maxn - len(self.pts)
        if need > 0:
            c = cv2.goodFeaturesToTrack(img, need, 0.01, 8, mask=mask, blockSize=5)
            if c is not None:
                c = c.reshape(-1, 2).astype(np.float32)
                self.pts = np.vstack([self.pts, c]); self.ids = np.concatenate([self.ids, np.arange(self.nid, self.nid + len(c))]); self.nid += len(c)

    def step(self, prev, img, f, R_ji):
        if len(self.pts):
            p0 = self.pts.reshape(-1, 1, 2)
            if self.guided:
                b = D.bearings(self.pts.astype(float), *self.K); q = b @ R_ji.T
                guess = np.stack([self.K[0] * q[:, 0] / q[:, 2] + self.K[2], self.K[1] * q[:, 1] / q[:, 2] + self.K[3]], 1)
                bad = q[:, 2] < 0.2; guess[bad] = self.pts[bad]
                p1 = guess.astype(np.float32).reshape(-1, 1, 2).copy()
                p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, img, p0, p1, winSize=(15, 15), maxLevel=3, flags=cv2.OPTFLOW_USE_INITIAL_FLOW,
                                                    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03))
            else:
                p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, img, p0, None, winSize=(15, 15), maxLevel=3,
                                                    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03))
            pb, st2, _ = cv2.calcOpticalFlowPyrLK(img, prev, p1, p0.copy(), winSize=(15, 15), maxLevel=3, flags=cv2.OPTFLOW_USE_INITIAL_FLOW)
            p1 = p1.reshape(-1, 2); fb = np.linalg.norm(pb.reshape(-1, 2) - self.pts, axis=1)
            h, w = img.shape
            ok = (st.ravel() == 1) & (st2.ravel() == 1) & (fb < 1.0) & (p1[:, 0] >= 2) & (p1[:, 0] < w - 2) & (p1[:, 1] >= 2) & (p1[:, 1] < h - 2)
            self.stats['tracked'] += int(ok.sum()); self.stats['lost'] += int((~ok).sum()); self.stats['fbfail'] += int(((st.ravel() == 1) & (fb >= 1.0)).sum())
            self.pts = p1[ok]; self.ids = self.ids[ok]
        if len(self.pts) < self.minn: self.detect(img, f)
        self.hist[f] = (self.ids.copy(), self.pts.copy())
        for old in [x for x in self.hist if x < f - max(KS)]: del self.hist[old]

    def pairs(self, i, j):
        if i not in self.hist or j not in self.hist: return None, None
        ii, pi = self.hist[i]; jj, pj = self.hist[j]
        com, ai, aj = np.intersect1d(ii, jj, return_indices=True)
        return pi[ai].astype(float), pj[aj].astype(float)


def run(zp):
    zp = Path(zp); fid = zp.stem
    ep = read_episode(zp, frames='lazy'); cfg, frames = ep.adapt((320, 240))
    K = (cfg['fx'], cfg['fy'], cfg['cx'], cfg['cy']); f = cfg['fx']
    ft = ep.frame_times; N = min(len(ft), int(os.environ.get('R1_NMAX', 100000)))
    Twc = poses_to_matrices(ep.camera_poses_world()); Rwc = Twc[:, :3, :3]; c = Twc[:, :3, 3]
    tw = ep.ground_truth_twist()
    R_bc = ep.T_body_camera[:3, :3]
    imu = ep.imu
    # oracle constant gyro bias: mean(w_meas - w_true) over the flight (body axes)
    w_true_b = tw[:, 3:6] @ R_bc.T
    wm = np.stack([np.interp(ft, imu[:, 0], imu[:, 4 + a]) for a in range(3)], 1)
    bias_or = np.median(wm - w_true_b, 0)
    # baseline filter twist (cam axes)
    fl = None
    for p in BASE_EVAL.glob(f'{fid}/report/logs/*/twist.txt'):
        fl = np.loadtxt(p)
    trk = {'g': Tracker(K, True), 'u': Tracker(K, False)}
    rng = np.random.default_rng(1)
    rows = []; prev = None; Rcache = {}
    t0 = time.time()
    def Rji(i, j, src):
        if src == 'gt': return Rwc[j].T @ Rwc[i]
        key = (i, j, src)
        if key not in Rcache:
            Rb = gyro_rel(imu, ft[i], ft[j], bias_or if src == 'gyro_b' else np.zeros(3))
            Rcache[key] = (R_bc.T @ Rb @ R_bc).T
        return Rcache[key]
    for j in range(N):
        img = cv2.cvtColor(np.asarray(frames[j]), cv2.COLOR_RGB2GRAY)
        if j == 0:
            for t in trk.values(): t.detect(img, 0); t.hist[0] = (t.ids.copy(), t.pts.copy())
            prev = img; continue
        R1 = Rji(j - 1, j, 'gyro')
        for t in trk.values(): t.step(prev, img, j, R1)
        prev = img
        for k in [x for x in Rcache if x[1] < j - max(KS)]: del Rcache[k]
        if not (j <= 120 or j % 4 == 0): continue
        for k in KS:
            i = j - k
            if i < 0: continue
            dgt = Rwc[j].T @ (c[j] - c[i]); L = np.linalg.norm(dgt); dgt = dgt / max(L, 1e-12)
            vt = tw[j, :3]; spd = np.linalg.norm(vt)
            etw = np.degrees(np.arccos(np.clip(dgt @ vt / max(spd, 1e-12), -1, 1)))
            if fl is not None and j < len(fl):
                vf = fl[j, 1:4]; sf = np.linalg.norm(vf); ef = np.degrees(np.arccos(np.clip(dgt @ vf / max(sf, 1e-12), -1, 1)))
            else: sf = ef = np.nan
            cache_pairs = {}
            for ci, (name, meth, src, tk) in enumerate(CONFIGS):
                if tk not in cache_pairs: cache_pairs[tk] = trk[tk].pairs(i, j)
                ui, uj = cache_pairs[tk]
                if ui is None or len(ui) < 8: continue
                bi = D.bearings(ui, *K); bj = D.bearings(uj, *K)
                cover = float(np.linalg.det(np.cov(uj.T)) ** 0.25 / 100.0)
                if meth == 'cv5':
                    try:
                        E, msk = cv2.findEssentialMat(ui, uj, np.array([[K[0], 0, K[2]], [0, K[1], K[3]], [0, 0, 1]]), cv2.RANSAC, 0.999, 1.0)
                        if E is None or E.shape != (3, 3): continue
                        _, Rr, tr, _ = cv2.recoverPose(E, ui, uj, np.array([[K[0], 0, K[2]], [0, K[1], K[3]], [0, 0, 1]]), mask=msk)
                    except cv2.error:
                        continue
                    d = -tr.ravel(); d = d / np.linalg.norm(d)
                    r = dict(d=d, vote=np.nan, ninl=int(msk.sum()), n=len(ui), par_med=np.nan, par_p90=np.nan, rrms=np.nan, evr=np.nan, ev1=np.nan, sig_pred=np.nan)
                else:
                    r = D.estimate(bi, bj, Rji(i, j, src), f, meth, rot_sd=0.02 * k * 0.05 + 1e-3, rng=rng)
                    if r is None: continue
                cosd = float(np.clip(r['d'] @ dgt, -1, 1))
                err = np.degrees(np.arccos(cosd)); eus = np.degrees(np.arccos(abs(cosd)))
                rows.append([j, k, ci, err, eus, float(cosd > 0), r['vote'], r['ninl'], r['n'], r['par_med'], r['par_p90'], r['rrms'], r['evr'], r['ev1'],
                             r['sig_pred'], L, spd, etw, ef, sf, cover])
    out = dict(rows=np.array(rows, np.float64), cols=np.array(COLS), cfgs=np.array([c_[0] for c_ in CONFIGS]),
               trk=json.dumps({k: v.stats for k, v in trk.items()}), bias_or=bias_or, secs=time.time() - t0)
    return fid, out


if __name__ == '__main__':
    lst, od, W = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
    od.mkdir(parents=True, exist_ok=True)
    zs = [l.strip() for l in open(lst) if l.strip()]
    zs = [z for z in zs if not (od / (Path(z).stem + '.npz')).exists()]
    from multiprocessing import Pool
    def job(z):
        try:
            fid, out = run(z); np.savez_compressed(od / (fid + '.npz'), **out); return fid, out['secs']
        except Exception as e:
            import traceback; traceback.print_exc(); return z, str(e)
    if W == 1:
        for z in zs: print(job(z), flush=True)
    else:
        with Pool(W) as p:
            for r in p.imap_unordered(job, zs): print(r, flush=True)
