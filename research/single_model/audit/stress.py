"""Edge-case stress suite (local fresh-pool flights only; perturbations are synthetic).

usage: venv-viobench python -B stress.py --wasm W.wasm --out results.json [--cases a,b] [--flights 24] [--workers 24]
Per (case, flight): completed?, failure, filled frames, non-finite outputs, peak/p95 fuel, ATE (unaligned, vs the
case's ground truth), identity-fallback ATE (all-zero output) for a sanity bound, max |position| output.
"""
import argparse, json, os, sys, time, traceback
from pathlib import Path
import numpy as np

sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
POOL = Path('/data/backups/rganapa/Sebastian/tmp/fresh_pool')
TAGS = json.load(open(Path(__file__).resolve().parents[1] / 'fresh/tags.json'))
G = 9.81


def flights(n):
    st = sorted(e for e, t in TAGS.items() if t['start'] == 'static')
    md = sorted(e for e, t in TAGS.items() if t['start'] == 'mid')
    k = n // 2
    return [st[i * len(st) // k] for i in range(k)] + [md[i * len(md) // k] for i in range(k)]


def rel_gt(gt, k0):
    """GT state re-expressed relative to frame k0 (pose), twist unchanged."""
    from viobench.tools.geometry import poses_to_matrices, matrices_to_poses, invert
    T = poses_to_matrices(gt[:, :7])
    Tr = invert(T[k0])[None] @ T
    out = gt.copy(); out[:, :7] = matrices_to_poses(Tr)
    return out


def rotx(a):
    c, s = np.cos(a), np.sin(a); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rotz(a):
    c, s = np.cos(a), np.sin(a); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def hover_imu(t0, n_frames, dt_f, fmean, gmean, rng, start_t):
    """synthetic hover IMU rows: 10 per frame, specific force fmean + N(0,0.28), gyro gmean + N(0,0.07)."""
    rows = []
    for k in range(n_frames):
        tk = start_t + k * dt_f
        ts = tk - dt_f + dt_f / 10 * np.arange(1, 11)
        a = fmean + rng.normal(0, 0.28, (10, 3)); g = gmean + rng.normal(0, 0.07, (10, 3))
        rows.append(np.column_stack([ts, a, g]))
    return rows



def model_imu(ep):
    """noise-free IMU from GT at the GT samples: f = R^T(a + g_up), w = body rate; plus the flight's bias estimate (IMU - model)."""
    from viobench.tools.geometry import quaternion_to_matrix, rotation_vectors
    g8 = ep.ground_truth; tg = g8[:, 0]; p = g8[:, 1:4]
    Rs = np.stack([quaternion_to_matrix(q) for q in g8[:, 4:8]])
    v = np.gradient(p, tg, axis=0); acc = np.gradient(v, tg, axis=0)
    w = np.zeros((len(tg), 3)); rel = rotation_vectors(np.einsum('kji,kjl->kil', Rs[:-2], Rs[2:]))
    w[1:-1] = rel / (tg[2:] - tg[:-2])[:, None]; w[0] = w[1]; w[-1] = w[-2]
    f = np.einsum('kji,kj->ki', Rs, acc + np.array([0, 0, G]))
    im = ep.imu; idx = np.clip(np.searchsorted(tg, im[:, 0] - 1e-6), 0, len(tg) - 1)
    ba = np.median(im[:, 1:4] - f[idx], 0); bg = np.median(im[:, 4:7] - w[idx], 0)
    return Rs, f, w, ba, bg, tg

IDS = np.array([0, 0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 0, 0])


def build(case, ep, rng):
    """returns config, steps (list of (t, frame_callable, imu)), gt (N,13)."""
    from viobench.tools.datasets.episode import Episode
    cfg, frames = ep.adapt((320, 240))
    cfg = dict(cfg)
    N = ep.num_frames; T = ep.frame_times.copy(); dtf = ep.frame_interval
    gt = ep.ground_truth_state()
    imu = [ep.imu_window(i) for i in range(N)]
    F = lambda i: (lambda: frames[i])
    steps = [(T[i], F(i), imu[i]) for i in range(N)]
    if case == 'base':
        return cfg, steps, gt
    w0 = imu[0]; fmean = w0[:, 1:4].mean(0); gmean = w0[:, 4:7].mean(0)
    if case in ('hover3000', 'hover_then_fly', 'long_tail'):
        Rs_, f_, w_, ba_, bg_, tg_ = model_imu(ep)
        k0 = int(np.clip(np.searchsorted(tg_, T[0] - 1e-6), 0, len(tg_) - 1))
        fmean = Rs_[k0].T @ np.array([0, 0, G]) + ba_; gmean = bg_
    noisy0 = lambda: np.clip(frames[0].astype(np.int16) + rng.normal(0, 1.5, frames[0].shape), 0, 255).astype(np.uint8)
    if case == 'hover3000':
        n = 3000; rows = hover_imu(0, n, dtf, fmean, gmean, rng, T[0])
        f0 = frames[0]
        def nf(seed):
            return lambda: np.clip(f0.astype(np.int16) + np.random.default_rng(seed).normal(0, 1.5, f0.shape), 0, 255).astype(np.uint8)
        steps = [(T[0] + k * dtf, nf(k), rows[k]) for k in range(n)]
        g = np.tile(IDS, (n, 1)); return cfg, steps, g
    if case == 'hover_then_fly':
        n = 400; rows = hover_imu(0, n, dtf, fmean, gmean, rng, T[0])
        f0 = frames[0]
        def nf(seed):
            return lambda: np.clip(f0.astype(np.int16) + np.random.default_rng(seed).normal(0, 1.5, f0.shape), 0, 255).astype(np.uint8)
        pre = [(T[0] + k * dtf, nf(k), rows[k]) for k in range(n)]
        off = n * dtf
        post = []
        for i in range(N):
            w = imu[i].copy(); w[:, 0] += off
            post.append((T[i] + off, F(i), w))
        g = np.vstack([np.tile(IDS, (n, 1)), gt]); return cfg, pre + post, g
    if case == 'long_tail':  # flight, then 1800 frames hovering at the last pose (frozen last image + noise)
        from viobench.tools.geometry import quaternion_to_matrix
        from viobench.tools.datasets.episode import interpolate_poses
        body = interpolate_poses(ep.ground_truth[:, 0], ep.ground_truth[:, 1:8], T[-1:])
        Rwb = quaternion_to_matrix(body[0, 3:7])
        body0 = interpolate_poses(ep.ground_truth[:, 0], ep.ground_truth[:, 1:8], T[:1])
        R0 = quaternion_to_matrix(body0[0, 3:7])
        # world gravity sign from the first window of a near-static start: f ~ R^T (0,0,+g) if world z up
        f_end = Rwb.T @ np.array([0, 0, G]) + ba_
        n = 1800; rows = hover_imu(0, n, dtf, f_end, bg_, rng, T[-1] + dtf)
        fl = frames[N - 1]
        def nf(seed):
            return lambda: np.clip(fl.astype(np.int16) + np.random.default_rng(seed).normal(0, 1.5, fl.shape), 0, 255).astype(np.uint8)
        tail = [(T[-1] + (k + 1) * dtf, nf(k), rows[k]) for k in range(n)]
        last = gt[-1].copy(); last[7:] = 0
        return cfg, steps + tail, np.vstack([gt, np.tile(last, (n, 1))])
    if case == 'start200':
        k0 = 200; g = rel_gt(gt, k0)[k0:]
        w = imu[k0 - 1]  # window for the new first frame: one frame interval before
        steps = [(T[i], F(i), imu[i]) for i in range(k0, N)]
        return cfg, steps, g
    img = None
    if case == 'dark': img = lambda f, i: (f.astype(np.float32) * 0.15).astype(np.uint8)
    if case == 'black': img = lambda f, i: np.zeros_like(f)
    if case == 'saturated': img = lambda f, i: np.full_like(f, 255)
    if case == 'flat': img = lambda f, i: np.full_like(f, 128)
    if case == 'black_seg': img = lambda f, i: np.zeros_like(f) if 300 <= i < 700 else f
    if case == 'flat_seg30': img = lambda f, i: np.full_like(f, 128) if 300 <= i < 900 else f
    if case == 'light_step': img = lambda f, i: (f.astype(np.float32) * 0.4).astype(np.uint8) if i >= 300 else f
    if case == 'light_flicker': img = lambda f, i: (f.astype(np.float32) * 0.6).astype(np.uint8) if (i // 10) % 2 else f
    if case == 'overexpose': img = lambda f, i: np.clip(f.astype(np.float32) * 2.5, 0, 255).astype(np.uint8) if i >= 300 else f
    if case == 'blur':
        import cv2
        img = lambda f, i: cv2.blur(f, (9, 1))
    if case == 'noise8':
        img = lambda f, i: np.clip(f.astype(np.int16) + np.random.default_rng(i).normal(0, 8, f.shape), 0, 255).astype(np.uint8)
    if img is not None:
        steps = [(T[i], (lambda i=i: img(frames[i], i)), imu[i]) for i in range(N)]
        return cfg, steps, gt
    if case == 'const_seg':  # camera stall: frames 300..499 repeat frame 299
        steps = [(T[i], F(i if not (300 <= i < 500) else 299), imu[i]) for i in range(N)]
        return cfg, steps, gt
    if case == 'dup10':  # every 10th frame shows the previous image
        steps = [(T[i], F(i - 1 if i % 10 == 9 else i), imu[i]) for i in range(N)]
        return cfg, steps, gt
    if case in ('drop10', 'drop_block'):
        keep = [i for i in range(N) if not ((case == 'drop10' and i % 10 == 5) or (case == 'drop_block' and 300 <= i < 320))]
        st = []; prev = None
        for i in keep:
            lo = prev + 1 if prev is not None else 0
            w = np.vstack([imu[j] for j in range(lo, i + 1)])
            st.append((T[i], F(i), w)); prev = i
        return cfg, st, gt[keep]
    if case == 'jitter':
        Tj = T + rng.uniform(-0.004, 0.004, N); Tj[0] = T[0]
        allimu = ep.imu; st = []
        for i in range(N):
            lo = Tj[i - 1] if i else Tj[0] - dtf
            m = (allimu[:, 0] > lo) & (allimu[:, 0] <= Tj[i])
            st.append((Tj[i], F(i), allimu[m]))
        return cfg, st, gt
    if case == 'imu0':  # every 7th frame gets no IMU rows; its rows arrive with the next frame
        st = []; carry = None
        for i in range(N):
            w = imu[i]
            if carry is not None: w = np.vstack([carry, w]); carry = None
            if i % 7 == 3 and i + 1 < N: carry = w; w = np.zeros((0, 7))
            st.append((T[i], F(i), w))
        return cfg, st, gt
    if case == 'imu_first0':
        st = [(T[0], F(0), np.zeros((0, 7)))] + [(T[i], F(i), imu[i]) for i in range(1, N)]
        return cfg, st, gt
    if case.startswith('short'):
        n = int(case[5:]); return cfg, steps[:n], gt[:n]
    if case in ('imu_spike', 'imu_sat', 'bias_big', 'nan_imu', 'inf_imu', 'imu_gap'):
        st = []
        for i in range(N):
            w = imu[i].copy()
            if case == 'imu_spike':
                m = rng.random(len(w)) < 0.01
                w[m, 1:4] += rng.normal(0, 50, (m.sum(), 3)); w[m, 4:7] += rng.normal(0, 5, (m.sum(), 3))
            if case == 'imu_sat':
                w[:, 1:4] = np.clip(w[:, 1:4], -12, 12); w[:, 4:7] = np.clip(w[:, 4:7], -1.0, 1.0)
            if case == 'bias_big':
                w[:, 1:4] += np.array([0.5, -0.4, 0.45]); w[:, 4:7] += np.array([0.05, -0.04, 0.045])
            if case == 'nan_imu' and i == 300: w[3, 1] = np.nan
            if case == 'inf_imu' and i == 300: w[3, 5] = np.inf
            if case == 'imu_gap' and 300 <= i < 310: w = w[:0]  # 0.5 s of missing IMU (rows never delivered)
            st.append((T[i], F(i), w))
        return cfg, st, gt
    if case.startswith('mount_'):
        Q = {'mount_flip': rotx(np.pi), 'mount_tilt': rotx(np.pi / 3), 'mount_yaw': rotz(np.pi / 2), 'mount_odd': rotz(0.7) @ rotx(2.2)}[case]
        Tci = np.array(cfg['T_cam_imu'], float); Tn = Tci.copy(); Tn[:3, :3] = Tci[:3, :3] @ Q.T
        cfg['T_cam_imu'] = Tn.tolist()
        st = []
        for i in range(N):
            w = imu[i].copy(); w[:, 1:4] = w[:, 1:4] @ Q.T; w[:, 4:7] = w[:, 4:7] @ Q.T
            st.append((T[i], F(i), w))
        return cfg, st, gt
    if case == 'zoom':
        import cv2
        s = 1.25; W, H = 320, 240; cw, ch = int(W / s), int(H / s); x0, y0 = (W - cw) // 2, (H - ch) // 2
        cfg['fx'] = cfg['fx'] * s; cfg['fy'] = cfg['fy'] * s
        cfg['cx'] = (cfg['cx'] - x0 + 0.5) * s - 0.5; cfg['cy'] = (cfg['cy'] - y0 + 0.5) * s - 0.5
        steps = [(T[i], (lambda i=i: cv2.resize(np.ascontiguousarray(frames[i][y0:y0 + ch, x0:x0 + cw]), (W, H), interpolation=cv2.INTER_LINEAR)), imu[i]) for i in range(N)]
        return cfg, steps, gt
    if case in ('synth1', 'speed2', 'speed3'):  # time-compressed flight: IMU re-synthesized from GT (f = R^T(s^2 a + g)), every s-th frame
        from viobench.tools.geometry import quaternion_to_matrix
        s = {'synth1': 1, 'speed2': 2, 'speed3': 3}[case]
        g8 = ep.ground_truth; tg = g8[:, 0]; p = g8[:, 1:4]
        Rs = np.stack([quaternion_to_matrix(q) for q in g8[:, 4:8]])
        v = np.gradient(p, tg, axis=0); acc = np.gradient(v, tg, axis=0)
        # body rate by central differences of R: w = vee(log(R_{k-1}^T R_{k+1})) / (t_{k+1} - t_{k-1})
        from viobench.tools.geometry import rotation_vectors
        w = np.zeros((len(tg), 3))
        rel = rotation_vectors(np.einsum('kji,kjl->kil', Rs[:-2], Rs[2:]))
        w[1:-1] = rel / (tg[2:] - tg[:-2])[:, None]; w[0] = w[1]; w[-1] = w[-2]
        fs = np.einsum('kji,kj->ki', Rs, s * s * acc + np.array([0, 0, G]))
        ba = rng.uniform(-0.2, 0.2, 3); bg = rng.uniform(-0.02, 0.02, 3)
        nf = (N - 1) // s + 1; t0 = T[0]
        Tn = np.array([t0 + (T[s * j] - t0) / s for j in range(nf)])
        tq = t0 + (tg - t0) / s  # every GT sample mapped to new time; keep those on the 200 Hz grid of the new clock
        keep = np.arange(0, len(tg), s)
        rows = np.column_stack([tq[keep], fs[keep] + ba + rng.normal(0, 0.28, (len(keep), 3)), s * w[keep] + bg + rng.normal(0, 0.07, (len(keep), 3))])
        st = []
        for j in range(nf):
            lo = Tn[j - 1] if j else Tn[0] - dtf
            m = (rows[:, 0] > lo + 1e-6) & (rows[:, 0] <= Tn[j] + 1e-6)
            st.append((Tn[j], F(s * j), rows[m]))
        g = gt[[s * j for j in range(nf)]].copy(); g[:, 7:] *= s
        return cfg, st, g
    if case == 'tbig':
        st = []
        for i in range(N):
            w = imu[i].copy(); w[:, 0] += 1e5; st.append((T[i] + 1e5, F(i), w))
        return cfg, st, gt
    if case == 'tneg':
        st = []
        for i in range(N):
            w = imu[i].copy(); w[:, 0] -= 1e3; st.append((T[i] - 1e3, F(i), w))
        return cfg, st, gt
    raise ValueError(case)


def run(args):
    wasm, case, epname, seed = args
    try:
        import png_cache; png_cache.install()
        from viobench.tools.runner.sandbox import Sandbox, SandboxError, Limits
        from viobench.tools.runner.engine import Engine
        from viobench.tools.runner.metrics import evaluate_trajectory
        from viobench.tools.datasets.sources import episodes
        global ENGINE
        if 'ENGINE' not in globals(): ENGINE = Engine()
        ep = next(iter(episodes([str(POOL / (epname + '.zip'))])))
        rng = np.random.default_rng(seed)
        cfg, steps, gt = build(case, ep, rng)
        import tempfile
        logd = tempfile.mkdtemp(prefix='aud_', dir='/data/backups/rganapa/Sebastian/tmp/audit')
        sb = Sandbox(wasm, ENGINE, limits=Limits(), log_dir=logd)
        sb.resolution = (320, 240)
        sb.init(cfg)
        n = len(steps); est = np.full((n, 13), np.nan); fuel = np.zeros(n); failure = None; nonfinite = 0
        for i, (t, ff, w) in enumerate(steps):
            try:
                r = sb.step(t, ff(), w)
            except SandboxError as e:
                failure = 'frame %d: %s' % (i, str(e).splitlines()[0][:200]); fuel[i] = e.fuel; break
            est[i, :7] = r.pose; est[i, 7:] = r.twist; fuel[i] = r.fuel
        m = evaluate_trajectory(gt, est, np.array([s[0] for s in steps]))
        good = np.all(np.isfinite(est), 1)
        ident = float(np.sqrt(np.mean(np.sum(gt[:, :3] ** 2, 1))))
        att = fuel[:i + 1] if failure else fuel
        stats = None
        if os.environ.get('KEEP_STATS'):
            L = [l.split()[1:] for l in open(os.path.join(logd, 'stderr.txt')).read().splitlines() if l.startswith('S ')]
            A = np.array(L, float) if L else np.zeros((0, 25))
            stats = dict(sum=A.sum(0).tolist(), nz=(A > 0).sum(0).tolist(), n=len(A), fuel=fuel.tolist())
        import shutil; shutil.rmtree(logd, ignore_errors=True)
        return dict(case=case, ep=epname, start=TAGS[epname]['start'], n=n, completed=failure is None, failure=failure,
                    filled=int(m.filled_frames), ate=m.ate_rmse, ident=ident, rot=m.rotation_rmse,
                    peak=float(att.max()), p95=float(np.percentile(att, 95)), maxpos=float(np.nanmax(np.abs(est[good, :3]))) if good.any() else None, stats=stats)
    except Exception as e:
        return dict(case=case, ep=epname, error=traceback.format_exc()[-800:])


CASES = ['base', 'hover3000', 'hover_then_fly', 'long_tail', 'start200', 'dark', 'black', 'saturated', 'flat', 'black_seg', 'flat_seg30',
         'light_step', 'light_flicker', 'overexpose', 'blur', 'noise8', 'const_seg', 'dup10', 'drop10', 'drop_block', 'jitter', 'imu0',
         'imu_first0', 'short1', 'short2', 'short5', 'short30', 'imu_spike', 'imu_sat', 'bias_big', 'nan_imu', 'inf_imu', 'imu_gap',
         'mount_flip', 'mount_tilt', 'mount_yaw', 'mount_odd', 'zoom', 'tbig', 'tneg', 'synth1', 'speed2', 'speed3']

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--wasm', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--cases', default=','.join(CASES)); ap.add_argument('--flights', type=int, default=24); ap.add_argument('--workers', type=int, default=24)
    a = ap.parse_args()
    os.makedirs('/data/backups/rganapa/Sebastian/tmp/audit', exist_ok=True)
    fl = flights(a.flights); cases = a.cases.split(',')
    jobs = []
    for c in cases:
        use = fl if c not in ('hover3000', 'hover_then_fly') else [e for e in fl if TAGS[e]['start'] == 'static']
        for k, e in enumerate(use): jobs.append((os.path.abspath(a.wasm), c, e, 1000 + k))
    jobs.sort(key=lambda j: 0 if j[1] in ('hover3000', 'long_tail') else 1)
    from multiprocessing import Pool
    t0 = time.time(); res = []
    with Pool(a.workers) as p:
        for r in p.imap_unordered(run, jobs):
            res.append(r)
            if len(res) % 50 == 0: print(len(res), '/', len(jobs), '%.0fs' % (time.time() - t0), flush=True)
    json.dump(res, open(a.out, 'w'))
    print('done', len(res), '%.0fs' % (time.time() - t0))
