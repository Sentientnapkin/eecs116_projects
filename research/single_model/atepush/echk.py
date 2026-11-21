"""echk.py RUN EP: residuals (px) of logged edgelet features (EO lines) under TRUTH camera poses (analysis only)."""
import sys, glob, numpy as np
sys.path.insert(0, '.')
from viobench.tools.geometry import poses_to_matrices
from viobench.tools.datasets.storage import read_episode
run, ep = sys.argv[1:3]; FX = 204.3232 / 2
e = read_episode(f'/data/backups/rganapa/Sebastian/tmp/fresh_pool/{ep}.zip', frames='none')
Twc = poses_to_matrices(e.camera_poses_world())
f = glob.glob(f'research/results/single_model/{run}/eval/*/{ep}/report/logs/*/stderr.txt')[0]
out = []
for line in open(f):
    if not line.startswith('EO'): continue
    h, b = line.split('|'); nis = float(h.split('nis=')[1].split()[0]); v = b.split(); m = len(v) // 5
    fr = [int(v[5 * k]) for k in range(m)]; z = np.array([[float(x) for x in v[5 * k + 1:5 * k + 5]] for k in range(m)])
    for off in (0, -1, 1):
        try:
            T = [Twc[i + off] for i in fr]
        except IndexError: continue
        N = []; C = []
        for k in range(m):
            l = np.array([z[k, 2], z[k, 3], -(z[k, 2] * z[k, 0] + z[k, 3] * z[k, 1])]); n = T[k][:3, :3] @ l; N.append(n / np.linalg.norm(n)); C.append(T[k][:3, 3])
        w0 = T[0][:3, :3] @ np.array([z[0, 0], z[0, 1], 1.0])
        a = np.array([N[k] @ w0 for k in range(1, m)]); bb = np.array([N[k] @ (C[k] - C[0]) for k in range(1, m)])
        d = (a @ bb) / (a @ a); P = C[0] + d * w0
        r = []
        for k in range(m):
            pc = T[k][:3, :3].T @ (P - C[k]); r.append(z[k, 2] * (z[k, 0] - pc[0] / pc[2]) + z[k, 3] * (z[k, 1] - pc[1] / pc[2]))
        out.append((off, nis, d, np.sqrt(np.mean(np.square(r))) * FX))
o = np.array(out)
for off in (0, -1, 1):
    s = o[o[:, 0] == off]
    print('off', off, 'n', len(s), 'rms px median %.2f p90 %.2f frac>2px %.2f' % (np.median(s[:, 3]), np.percentile(s[:, 3], 90), (s[:, 3] > 2).mean()), 'nis med %.2f gated %.2f' % (np.median(s[:, 1]), (s[:, 1] > 1).mean()))
