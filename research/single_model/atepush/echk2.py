"""echk2.py RUN EP: with truth poses, fit the 3-D line of each logged edgelet feature (planes LS), then per observation:
normal angle error (deg) vs the projected true line, distance (px) of z_k from the line, slide along the edge (px)."""
import sys, glob, numpy as np
sys.path.insert(0, '.')
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
run, ep = sys.argv[1:3]; FX = 102.1616
e = read_episode(f'/data/backups/rganapa/Sebastian/tmp/fresh_pool/{ep}.zip', frames='none'); Twc = poses_to_matrices(e.camera_poses_world())
f = glob.glob(f'research/results/single_model/{run}/eval/*/{ep}/report/logs/*/stderr.txt')[0]
ang, dist, slide = [], [], []
for line in open(f):
    if not line.startswith('EO'): continue
    v = line.split('|')[1].split(); m = len(v) // 5
    fr = [int(v[5 * k]) for k in range(m)]; z = np.array([[float(x) for x in v[5 * k + 1:5 * k + 5]] for k in range(m)])
    T = [Twc[i] for i in fr]; N = []
    for k in range(m):
        l = np.array([z[k, 2], z[k, 3], -(z[k, 2] * z[k, 0] + z[k, 3] * z[k, 1])]); n = T[k][:3, :3] @ l; n /= np.linalg.norm(n)
        N.append(np.r_[n, -n @ T[k][:3, 3]])
    A = np.array(N); _, _, Vt = np.linalg.svd(A)  # line = null space (2-dim) of the 4xm plane matrix
    X1, X2 = Vt[-1], Vt[-2]
    P = []
    for X in (X1, X2):
        if abs(X[3]) < 1e-9: X = X + (X2 if X is X1 else X1)
        P.append(X[:3] / X[3])
    for k in range(m):
        R, c = T[k][:3, :3], T[k][:3, 3]
        q = [R.T @ (p - c) for p in P]
        if q[0][2] < 0.05 or q[1][2] < 0.05: continue
        a, b = q[0][:2] / q[0][2], q[1][:2] / q[1][2]; t = (b - a) / np.linalg.norm(b - a); nl = np.array([-t[1], t[0]])
        zz = z[k, :2]; dist.append(abs(nl @ (zz - a)) * FX)
        ang.append(np.degrees(np.arccos(min(1, abs(nl @ z[k, 2:4])))))
        if k == 0: z0 = zz
        else: slide.append(abs(t @ (zz - z0)) * FX)
ang, dist, slide = map(np.array, (ang, dist, slide))
print(ep, 'n', len(ang), 'ang med %.1f p90 %.1f | dist med %.2f p90 %.2f | slide med %.1f p90 %.1f' % (np.median(ang), np.percentile(ang, 90), np.median(dist), np.percentile(dist, 90), np.median(slide), np.percentile(slide, 90)))
