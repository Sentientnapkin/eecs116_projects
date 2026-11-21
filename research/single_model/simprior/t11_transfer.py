"""Analysis only (truth): body lateral velocity vs yaw rate, per generated set / planner setting. No estimator scored.
python -B t11_transfer.py -> slope k in vy = k*wz*|vh| (through origin), R2, residual rms by |wz| regime, bang-bang |wz| level, speed; start-window law slope vy ~ wz."""
import sys, json, glob, random
sys.path.insert(0, '/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/simstruct')
from load import *
G = Path('/data/backups/rganapa/Sebastian/gen')
sets = {'fresh(raw-fast/bench)': sorted(glob.glob(str(G / 'raw-fast/bench/*.json'))), 'holdout(final)': sorted(glob.glob(str(G / 'raw-holdout/bench/*.json'))), 'speed(raw-speed)': sorted(glob.glob(str(G / 'raw-speed/bench/*.json')))}
def flight(zf):
    e = read_episode(zf, frames='none'); gt = e.ground_truth; t = gt[:, 0]
    k = 4   # 20 ms
    p = gt[:, 1:4]; Rm = q2R(gt[:, 4:8])
    v = (p[2 * k::k][:-0] - p[:-2 * k:k]) / (t[2 * k::k] - t[:-2 * k:k])[:, None] if False else None
    idx = np.arange(k, len(t) - k, 10)
    v = (p[idx + k] - p[idx - k]) / (t[idx + k] - t[idx - k])[:, None]
    vb = np.einsum('nji,nj->ni', Rm[idx], v)
    wz = rotvec_rel(Rm[idx - k], Rm[idx + k])[:, 2] / (t[idx + k] - t[idx - k])
    m = t[idx] > 2.0
    return vb[m], wz[m], v[m]
out = {}
for name, files in sets.items():
    groups = {}
    for f in files:
        d = json.load(open(f))
        if 'setting' not in d: continue
        if fold(d['catalog'], d['scene']) == 4: continue   # never touch fold-4 scenes
        groups.setdefault(d['setting'] if 'speed' in name else name + ' ' + d['setting'], []).append((f, d))
    for g, lst in sorted(groups.items()):
        random.Random(1).shuffle(lst); lst = lst[:25]
        VB, WZ, VH = [], [], []
        for f, d in lst:
            try: vb, wz, v = flight(f.replace('.json', '.zip'))
            except Exception as ex: continue
            VB.append(vb); WZ.append(wz); VH.append(np.linalg.norm(v[:, :2], axis=1))
        if not VB: continue
        vb = np.vstack(VB); wz = np.concatenate(WZ); vh = np.concatenate(VH); x = wz * vh; y = vb[:, 1]
        mv = vh > 0.2; k = (x[mv] * y[mv]).sum() / (x[mv] ** 2).sum(); res = y[mv] - k * x[mv]
        r2 = 1 - (res ** 2).sum() / (y[mv] ** 2).sum()
        # slope error sensitivity: rms with k*(0.7,1.3)
        s = [np.sqrt(((y[mv] - kk * k * x[mv]) ** 2).mean()) for kk in (0.7, 1.0, 1.3)]
        reg = lambda a, b: (np.abs(wz[mv]) >= a) & (np.abs(wz[mv]) < b)
        rr = [np.sqrt((res[reg(a, b)] ** 2).mean()) if reg(a, b).any() else np.nan for a, b in ((0, .15), (.15, .45), (.45, 9))]
        sat = np.abs(wz[mv]) > 0.45
        print(f'{g:28s} n_fl={len(VB):2d} samples={mv.sum():5d} |vh| mean {vh[mv].mean():.2f}  k={k:.3f} R2={r2:.3f} resid rms {np.sqrt((res**2).mean()):.3f} (raw {np.sqrt((y[mv]**2).mean()):.3f}) | by regime {np.round(rr,3).tolist()} | |wz| sat median {np.median(np.abs(wz[mv][sat])):.2f} frac sat {sat.mean():.2f} | rms at k*0.7/1/1.3: {np.round(s,3).tolist()} | zero-model rms {np.sqrt((y[mv]**2).mean()):.3f}')
