"""lchk.py RUNDIR POOL: truth-pose check of logged line features (LO lines, GS_DIAG=2): refit each 3-D line with TRUE camera poses,
report endpoint-distance residual RMS in px (fx from 120 deg / 320 px). Analysis only."""
import sys, glob, re, numpy as np
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import poses_to_matrices
FX = 160 / np.tan(np.radians(60))
def res(Q, D, R, p, o):
    Qc = R.T @ (Q - p); Dc = R.T @ D; l = np.cross(Qc, Dc); nn = np.hypot(l[0], l[1])
    x, y, ex, ey, hl = o; t = np.array([-ey, ex]); out = []
    for sg in (-1, 1):
        q = np.array([x, y]) + sg * hl * t; out.append((l[0] * q[0] + l[1] * q[1] + l[2]) / nn)
    return out
def fit(Rs, ps, obs):
    N = []
    for R, p, o in zip(Rs, ps, obs):
        x, y, ex, ey, hl = o; l = np.array([ex, ey, -(ex * x + ey * y)]); n = R @ l; N.append(n / np.linalg.norm(n))
    best = 0; D = None
    for a in range(len(N)):
        for b in range(a + 1, len(N)):
            c = np.cross(N[a], N[b])
            if c @ c > best: best = c @ c; D = c
    D = D / np.linalg.norm(D)
    A = sum(np.outer(n, n) for n in N) + np.outer(D, D); bb = sum(n * (n @ p) for n, p in zip(N, ps)) + D * (D @ ps[0])
    Q = np.linalg.solve(A, bb)
    def r(v):
        e1 = np.cross(D, [1, 0, 0] if abs(D[0]) < 0.6 else [0, 1, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(D, e1)
        Qn = Q + v[0] * e1 + v[1] * e2; Dn = D + v[2] * e1 + v[3] * e2; Dn /= np.linalg.norm(Dn)
        return np.concatenate([res(Qn, Dn, R, p, o) for R, p, o in zip(Rs, ps, obs)]), Qn, Dn
    for it in range(6):
        r0, _, _ = r(np.zeros(4)); J = np.zeros((len(r0), 4))
        for k in range(4):
            v = np.zeros(4); v[k] = 1e-6; J[:, k] = (r(v)[0] - r(-v)[0]) / 2e-6
        st = np.linalg.lstsq(J, -r0, rcond=None)[0]; _, Q, D = r(st)
    r0 = r(np.zeros(4))[0]
    global LASTD; LASTD = D
    return np.sqrt(np.mean(r0 ** 2)) * FX
RUN, POOL = sys.argv[1:3]
VANG = []
for d in sorted(glob.glob(RUN + '/*/')):
    ep = d.rstrip('/').split('/')[-1]; se = glob.glob(d + 'report/logs/*/stderr.txt')
    if not se: continue
    e = read_episode(f'{POOL}/{ep}.zip', frames='none')
    C = np.asarray(e.camera_poses_world()); T = poses_to_matrices(np.concatenate([C, np.zeros((len(C), 6))], 1))
    rows = []
    for line in open(se[0]):
        if not line.startswith('LO '): continue
        head, rest = line.split('|'); rms_f = float(re.search(r'rms=([\d.]+)', head).group(1)); v = rest.split()
        m = len(v) // 6; fr = [int(v[6 * k]) for k in range(m)]; obs = [tuple(float(x) for x in v[6 * k + 1:6 * k + 6]) for k in range(m)]
        out = [rms_f]
        vz = []
        for off in (-1, 0, 1):
            try:
                Rs = [T[f + off][:3, :3] for f in fr]; ps = [T[f + off][:3, 3] for f in fr]; out.append(fit(Rs, ps, obs))
                if off == 0: VANG.append(np.degrees(np.arccos(min(1, abs(LASTD[2])))))
            except Exception: out.append(np.nan)
        rows.append(out)
    R = np.array(rows)
    print(ep, 'n', len(R), 'filter-pose rms med %.2f | truth rms (off -1/0/+1) med %s p90 %s frac>2px %s' % (np.median(R[:, 0]), np.round(np.nanmedian(R[:, 1:], 0), 2), np.round(np.nanpercentile(R[:, 1:], 90, axis=0), 2), np.round(np.mean(R[:, 1:] > 2, 0), 2)))

h = np.histogram(VANG, bins=[0, 1, 2, 4, 8, 15, 30, 60, 80, 85, 88, 90])
print('truth line angle from vertical (deg) histogram:', list(zip(h[1][:-1].tolist(), h[0].tolist())))
