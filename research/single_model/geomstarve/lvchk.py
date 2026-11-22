"""lvchk.py RUNDIR POOL: for logged lines (LO), truth-pose free fit angle from vertical vs truth-pose VERTICAL-model fit RMS (px)"""
import sys, glob, re, numpy as np
sys.argv, A = sys.argv[:1], sys.argv[1:]
exec(open('lchk.py').read().split('RUN, POOL = sys.argv[1:3]')[0])
RUN, POOL = A
out = []
for d in sorted(glob.glob(RUN + '/*/')):
    ep = d.rstrip('/').split('/')[-1]; se = glob.glob(d + 'report/logs/*/stderr.txt')
    if not se: continue
    e = read_episode(f'{POOL}/{ep}.zip', frames='none'); C = np.asarray(e.camera_poses_world()); T = poses_to_matrices(np.concatenate([C, np.zeros((len(C), 6))], 1))
    for line in open(se[0]):
        if not line.startswith('LO '): continue
        v = line.split('|')[1].split(); m = len(v) // 6; fr = [int(v[6 * k]) for k in range(m)]; obs = [tuple(float(x) for x in v[6 * k + 1:6 * k + 6]) for k in range(m)]
        Rs = [T[f][:3, :3] for f in fr]; ps = [T[f][:3, 3] for f in fr]
        try: rf = fit(Rs, ps, obs)
        except Exception: continue
        D = LASTD; ang = np.degrees(np.arccos(min(1, abs(D[2]))))
        if ang > 20: continue
        # vertical model: Q free in xy, D = z
        Dv = np.array([0, 0, 1.0]); Q = np.zeros(3)
        N = []
        for R, p, o in zip(Rs, ps, obs):
            x, y, ex, ey, hl = o; l = np.array([ex, ey, -(ex * x + ey * y)]); n = R @ l; N.append(n / np.linalg.norm(n))
        A_ = sum(np.outer(n, n) for n in N) + np.outer(Dv, Dv); b_ = sum(n * (n @ p) for n, p in zip(N, ps)) + Dv * (Dv @ ps[0]); Q = np.linalg.solve(A_, b_)
        def rv(q): return np.concatenate([res(np.array([q[0], q[1], Q[2]]), Dv, R, p, o) for R, p, o in zip(Rs, ps, obs)])
        q = Q[:2].copy()
        for it in range(6):
            r0 = rv(q); J = np.stack([(rv(q + np.eye(2)[k] * 1e-6) - rv(q - np.eye(2)[k] * 1e-6)) / 2e-6 for k in range(2)], 1); q = q + np.linalg.lstsq(J, -r0, rcond=None)[0]
        out.append((ang, rf, np.sqrt(np.mean(rv(q) ** 2)) * FX))
O = np.array(out)
for lo, hi in [(0, 2), (2, 4), (4, 8), (8, 15), (15, 20)]:
    m = (O[:, 0] >= lo) & (O[:, 0] < hi)
    if m.any(): print('free-fit angle %2d-%2d deg: n %3d free rms med %.2f | vertical-model rms med %.2f p90 %.2f frac<1px %.2f' % (lo, hi, m.sum(), np.median(O[m, 1]), np.median(O[m, 2]), np.percentile(O[m, 2], 90), np.mean(O[m, 2] < 1)))
