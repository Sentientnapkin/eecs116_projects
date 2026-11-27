"""proto.py: standalone direct linear visual-inertial initialization (r3) on real KLT tracks.
Reference frame = IMU body frame at frame 0.  p(t) = t v0 + 1/2 t^2 g + alpha(t) - B(t) ba,  v(t) = v0 + t g + beta(t) - C(t) ba.
Epipolar coplanarity per feature pair (i,j): n_ij . (pC_j - pC_i) = 0, n_ij = (R_i Rbc f_i) x (R_j Rbc f_j)  -> rows of A x = b,
x = [v0 (3), g (3), ba (3)].  Variants: 3-D (g from thrust axis, ba=0), 6-D (v0,g), 9-D (+ba, prior), |g| constrained GN.
Usage: proto.py OUT.json POOLDIR|ZIP... [--n N]  (caches tracks under r3/cache/)."""
import sys, json, glob, os, pickle, argparse
import numpy as np, cv2
from multiprocessing import Pool
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import quaternion_to_matrix
R3 = '/data/backups/rganapa/Sebastian/gen3/research/r3'
GRAV = 9.81
HOR = (5, 8, 10, 13, 15, 20, 30, 40)
NMAX = 41

def expso3(w):
    th = np.linalg.norm(w)
    K = np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]])
    if th < 1e-12: return np.eye(3) + K
    return np.eye(3) + np.sin(th) / th * K + (1 - np.cos(th)) / th ** 2 * K @ K

def track(ep, n, W=320, H=240):
    s = W / ep.config['image']['width']
    tracks = {}; nid = 0; prev = None; pts = None; ids = []
    for k in range(n):
        img = cv2.cvtColor(np.asarray(ep.frames[k]), cv2.COLOR_RGB2GRAY)
        img = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)
        if prev is not None and len(ids):
            p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, img, pts, None, winSize=(15, 15), maxLevel=3)
            p0b, st2, _ = cv2.calcOpticalFlowPyrLK(img, prev, p1, None, winSize=(15, 15), maxLevel=3)
            ok = (st[:, 0] == 1) & (st2[:, 0] == 1) & (np.linalg.norm(p0b - pts, axis=2)[:, 0] < 0.5)
            ok &= (p1[:, 0, 0] > 2) & (p1[:, 0, 0] < W - 3) & (p1[:, 0, 1] > 2) & (p1[:, 0, 1] < H - 3)
            pts = p1[ok]; ids = [i for i, o in zip(ids, ok) if o]
            for i, p in zip(ids, pts[:, 0]): tracks[i].append((k, float(p[0]), float(p[1])))
        if len(ids) < 120:
            mask = np.full(img.shape, 255, np.uint8)
            for p in (pts[:, 0] if len(ids) else []): cv2.circle(mask, (int(p[0]), int(p[1])), 8, 0, -1)
            new = cv2.goodFeaturesToTrack(img, 150 - len(ids), 0.01, 8, mask=mask)
            if new is not None:
                for p in new[:, 0]:
                    tracks[nid] = [(k, float(p[0]), float(p[1]))]; ids.append(nid); nid += 1
                pts = np.concatenate([pts, new], 0) if len(ids) > len(new) else new.astype(np.float32)
        prev = img
    c = ep.config['camera']
    K = np.array([[c['fx'] * s, 0, (c['cx'] + .5) * s - .5], [0, c['fy'] * s, (c['cy'] + .5) * s - .5], [0, 0, 1]])
    return {i: np.array(t) for i, t in tracks.items() if len(t) >= 2}, K

def load(z):
    fid = os.path.basename(z)[:-4]
    cp = f'{R3}/cache/{fid}.pkl'
    if os.path.exists(cp): return pickle.load(open(cp, 'rb'))
    ep = read_episode(z)
    tr, K = track(ep, NMAX)
    Tci = np.array(ep.config['imu']['T_cam_imu']).reshape(4, 4); Tic = np.linalg.inv(Tci)
    ft = ep.frame_times[:NMAX]
    imu = ep.imu[(ep.imu[:, 0] > ft[0] - 0.06) & (ep.imu[:, 0] <= ft[-1] + 1e-6)]
    cw = ep.camera_poses_world(ft); gts = ep.ground_truth_state()[:NMAX]
    Rcb = Tci[:3, :3]; Rbc, pbc = Tic[:3, :3], Tic[:3, 3]
    Rwb = np.array([quaternion_to_matrix(q[3:7]) @ Rcb for q in cw])
    vb = np.array([Rbc @ g[7:10] - np.cross(Rbc @ g[10:13], pbc) for g in gts])  # IMU velocity, body axes
    m = ep.meta.get('flight', ep.meta) if isinstance(ep.meta, dict) else {}
    d = dict(id=fid, tracks=tr, K=K, Rbc=Rbc, pbc=pbc, ft=ft, imu=imu, Rwb=Rwb, vb=vb,
             start=m.get('start'), cls=m.get('setting_class'), regime=m.get('regime'), fov=ep.config['camera']['horizontal_fov_degrees'],
             exp=ep.config['episode']['exposure_seconds'])
    os.makedirs(f'{R3}/cache', exist_ok=True); pickle.dump(d, open(cp, 'wb'))
    return d

def preint(d, bg=np.zeros(3)):
    """per frame k: R_k (body k -> body 0), alpha_k, beta_k, B_k, C_k, t_k (relative to frame 0)"""
    ft, imu = d['ft'], d['imu']; t0 = ft[0]
    R = np.eye(3); al = np.zeros(3); be = np.zeros(3); B = np.zeros((3, 3)); C = np.zeros((3, 3)); last = t0
    out = [(R.copy(), al.copy(), be.copy(), B.copy(), C.copy(), 0.0)]
    rows = imu[imu[:, 0] > t0 + 1e-9]; k = 1; fm = []
    for r in rows:
        if k >= len(ft): break
        dt = r[0] - last; last = r[0]
        a = R @ r[1:4]
        al += be * dt + 0.5 * a * dt * dt; be += a * dt
        B += C * dt + 0.5 * R * dt * dt; C += R * dt
        R = R @ expso3((r[4:7] - bg) * dt)
        fm.append(r[1:4])
        if r[0] >= ft[k] - 1e-6:
            out.append((R.copy(), al.copy(), be.copy(), B.copy(), C.copy(), ft[k] - t0)); k += 1
    return out, np.array(fm)

def rows_for(d, P, N, gap=2, minpar=np.radians(0.5)):
    Kinv = np.linalg.inv(d['K']); Rbc, pbc = d['Rbc'], d['pbc']
    A, b = [], []
    for t in d['tracks'].values():
        t = t[t[:, 0] < N]
        if len(t) < 2: continue
        f = (Kinv @ np.c_[t[:, 1:3], np.ones(len(t))].T).T
        fr = t[:, 0].astype(int)
        bw = np.array([P[k][0] @ Rbc @ (v / np.linalg.norm(v)) for k, v in zip(fr, f)])
        # pairs: first obs with every later obs at stride gap, plus consecutive-gap pairs
        idx = list(range(0, len(fr)))
        pairs = [(0, j) for j in idx[1:]] + [(i, i + gap) for i in idx[1:-gap:gap]]
        for i, j in pairs:
            n = np.cross(bw[i], bw[j]); s = np.linalg.norm(n)
            if s < np.sin(minpar): continue
            n /= s
            Ri, ai, _, Bi, _, ti = P[fr[i]]; Rj, aj, _, Bj, _, tj = P[fr[j]]
            A.append(np.r_[n * (tj - ti), n * 0.5 * (tj * tj - ti * ti), -(n @ (Bj - Bi))])
            b.append(-n @ (aj - ai + Rj @ pbc - Ri @ pbc))
    return np.array(A).reshape(-1, 9), np.array(b)

def solve(A, b, fm, mode, g_prior=None, tilt_sd=0.15, ba_sd=0.2 / np.sqrt(3), thrust=True, huber=1.5, iters=6, v_prior=None):
    """mode 3: x=v0 (g=g_prior*|g|, ba=0); 6: v0,g; 9: v0,g,ba. |g| enforced by GN on the direction for 6/9."""
    if len(b) < 6: return None
    n = {3: 3, 6: 6, 9: 9}[mode]
    gdir = g_prior / np.linalg.norm(g_prior)
    Ab = A[:, :n].copy(); bb = b.copy()
    if mode == 3: bb = bb - A[:, 3:6] @ (GRAV * gdir)
    # priors (information form)
    Hp = np.zeros((n, n)); hp = np.zeros(n)
    if mode >= 6 and tilt_sd:  # gravity-direction prior (thrust axis), isotropic on g with sd |g| tilt_sd, norm handled by GN
        w = 1 / (GRAV * tilt_sd) ** 2; Hp[3:6, 3:6] += w * np.eye(3); hp[3:6] += w * GRAV * gdir
    if mode == 9:
        Hp[6:9, 6:9] += np.eye(3) / ba_sd ** 2
        if thrust and len(fm):
            st = np.sqrt(0.28 ** 2 / len(fm) + 0.05 ** 2); mxy = fm[:, :2].mean(0)
            for i in range(2): Hp[6 + i, 6 + i] += 1 / st ** 2; hp[6 + i] += mxy[i] / st ** 2
    if v_prior is not None:
        vm, vsd = v_prior; Hp[:3, :3] += np.eye(3) / vsd ** 2; hp[:3] += vm / vsd ** 2
    wts = np.ones(len(bb)); x = None
    for it in range(iters):
        r0 = None
        H = Ab.T @ (wts[:, None] * Ab) + Hp; h = Ab.T @ (wts * bb) + hp
        try: x = np.linalg.solve(H, h)
        except np.linalg.LinAlgError: return None
        if mode >= 6:  # project g onto |g| = GRAV and re-solve the rest with g fixed, then GN on direction
            for _ in range(3):
                gd = x[3:6] / np.linalg.norm(x[3:6])
                T = np.linalg.svd(np.eye(3) - np.outer(gd, gd))[0][:, :2]  # tangent basis
                # params: [v0, d(2), ba]; g = GRAV (gd + T d)
                M = np.zeros((n, n - 1)); M[:3, :3] = np.eye(3); M[3:6, 3:5] = GRAV * T
                if mode == 9: M[6:9, 5:8] = np.eye(3)
                c = np.zeros(n); c[3:6] = GRAV * gd
                Hr = M.T @ H @ M; hr = M.T @ (h - H @ c)
                y = np.linalg.solve(Hr, hr); x = M @ y + c
                x[3:6] = GRAV * x[3:6] / np.linalg.norm(x[3:6])
        r = Ab @ x - bb
        s = 1.4826 * np.median(np.abs(r)) + 1e-9
        u = np.abs(r) / (huber * s); wts = np.where(u <= 1, 1.0, 1.0 / u) / s ** 2
    cov = np.linalg.inv(Ab.T @ (wts[:, None] * Ab) + Hp)
    return x, cov, len(bb)

def evalflight(z, variants):
    d = load(z)
    P, fm_all = preint(d)
    gt_up = d['Rwb'][0].T @ np.array([0, 0, 1.0]); gt_v0 = d['vb'][0]
    res = dict(id=d['id'], start=d['start'], cls=d['cls'], regime=d['regime'], fov=d['fov'], exp=d['exp'],
               v0=float(np.linalg.norm(gt_v0)), ntracks=len(d['tracks']))
    ft = d['ft']; t0 = ft[0]
    rows_imu = d['imu'][d['imu'][:, 0] <= t0 + 1e-6][-10:]
    fthr = rows_imu[:, 1:4].mean(0)  # frame-0 window mean specific force = the filter's tilt init
    res['tilt_thr'] = float(np.degrees(np.arccos(np.clip(fthr @ gt_up / np.linalg.norm(fthr), -1, 1))))
    for N in HOR:
        if N >= len(P): continue
        A, b = rows_for(d, P, N + 1)
        fm = fm_all[:int(round((ft[N] - t0) * 200))]
        for vn, kw in variants.items():
            mode = kw['mode']
            s = solve(A, b, fm, mode, g_prior=-fthr / np.linalg.norm(fthr), **{k: v for k, v in kw.items() if k != 'mode'})
            if s is None: res[f'{vn}_{N}'] = None; continue
            x, cov, nr = s
            v0 = x[:3]; g = x[3:6] if mode >= 6 else -GRAV * fthr / np.linalg.norm(fthr)
            ba = x[6:9] if mode == 9 else np.zeros(3)
            R, al, be, B, C, tN = P[N]
            vN = v0 + g * tN + be - C @ ba  # velocity at frame N in frame-0 body axes
            gtvN = d['Rwb'][0].T @ d['Rwb'][N] @ d['vb'][N]
            res[f'{vn}_{N}'] = dict(ev0=float(np.linalg.norm(v0 - gt_v0)), evN=float(np.linalg.norm(vN - gtvN)),
                                    tilt=float(np.degrees(np.arccos(np.clip(-g @ gt_up / np.linalg.norm(g), -1, 1)))),
                                    sd_v0=float(np.sqrt(np.trace(cov[:3, :3]))), nr=nr,
                                    sd_tilt=float(np.degrees(np.sqrt(np.trace(cov[3:6, 3:6])) / GRAV)) if mode >= 6 else 0.0)
    return res

VARIANTS = {
    'd3': dict(mode=3), 'd6': dict(mode=6), 'd9': dict(mode=9),
    'd6np': dict(mode=6, tilt_sd=0), 'd9np': dict(mode=9, tilt_sd=0),
}
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('src', nargs='+'); ap.add_argument('--j', type=int, default=8)
    a = ap.parse_args()
    zs = sorted(sum([glob.glob(s + '/*.zip') if os.path.isdir(s) else [s] for s in a.src], []))
    with Pool(a.j) as p: R = p.starmap(evalflight, [(z, VARIANTS) for z in zs])
    json.dump(R, open(a.out, 'w'))
    print('n', len(R))
