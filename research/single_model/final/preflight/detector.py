"""Motion-detector confusion table + noise/bias perturbation margins. Uses only IMU windows (sensor data) + the
start_type tag from perflight.jsonl (a label; not truth trajectory). Window = frame-1 IMU window (first non-empty
one the guest sees: step 0 gets zero IMU rows). Detector replicated exactly from f0.c initialize()."""
import sys, json, glob
sys.path.insert(0, '.')
import numpy as np
from viobench.tools.datasets.storage import read_episode
from research.single_model.run_variant import tags, fold, slice_of, EPISODES
DG, DF = 0.2, 8.8
tg = tags()
rows = []
for z in sorted(EPISODES.glob('*.zip')):
    e = read_episode(z); ep = z.stem
    w0 = e.imu_window(0); w = e.imu_window(1)
    rows.append(dict(ep=ep, start=tg[ep]['start'], sl=slice_of(fold(tg[ep])), n0=len(w0), n=len(w), w=w[:, 1:7].copy(), dt=float(np.diff(w[:, 0]).mean()) if len(w) > 1 else None))
def det(w):
    f = np.linalg.norm(w[:, 0:3].mean(0)); g = np.linalg.norm(w[:, 3:6].mean(0))
    return f, g, (g > DG) or (f > DF)
print('window0 sizes', sorted(set(r['n0'] for r in rows)), 'window1 sizes', sorted(set(r['n'] for r in rows)))
out = []
for r in rows:
    f, g, m = det(r['w']); r.update(f=f, g=g, moving=bool(m))
def table(sl):
    sel = [r for r in rows if sl is None or r['sl'] in sl]
    t = {(s, m): sum(1 for r in sel if r['start'] == s and r['moving'] == m) for s in ('static', 'mid') for m in (False, True)}
    return t
print('ALL 171 (confusion; detector label only, no score):', table(None))
print('search+val (n=144):', table(('search', 'val')))
for s in ('static', 'mid'):
    for sl, name in ((('search', 'val'), 'search+val'), (None, 'all171')):
        sel = [r for r in rows if r['start'] == s and (sl is None or r['sl'] in sl)]
        f = np.array([r['f'] for r in sel]); g = np.array([r['g'] for r in sel])
        print(f'{s:6s} {name:10s} n={len(sel)} |f| min/med/max {f.min():.3f}/{np.median(f):.3f}/{f.max():.3f}  |gyro| min/med/max {g.min():.4f}/{np.median(g):.4f}/{g.max():.4f}  moving={sum(r["moving"] for r in sel)}')
# margins: for 'mid' flights, flagged moving because of gyro and/or force?
mid = [r for r in rows if r['start'] == 'mid']; st = [r for r in rows if r['start'] == 'static']
print('static: max gyro', max(r['g'] for r in st), ' ; force range', min(r['f'] for r in st), max(r['f'] for r in st), '(threshold 8.8)')
print('mid: min gyro', min(r['g'] for r in mid), ' count gyro>0.2:', sum(r['g'] > DG for r in mid), ' count force>8.8:', sum(r['f'] > DF for r in mid))
print('mid not detected:', [(r['ep'], round(r['f'], 3), round(r['g'], 4), r['sl']) for r in mid if not r['moving']])
print('static detected:', [(r['ep'], round(r['f'], 3), round(r['g'], 4), r['sl']) for r in st if r['moving']])
# nearest-to-threshold flights
print('closest static to thresholds: gyro', sorted(((DG - r['g']), r['ep']) for r in st)[:3], 'force', sorted(((DF - r['f']), r['ep']) for r in st)[:3])
print('closest mid to thresholds (min over both margins):', sorted(((max(r['g'] - DG, r['f'] - DF)), r['ep'], round(r['f'],2), round(r['g'],3)) for r in mid)[:5])
# perturbation: noise per sample (preset accel 0.28, gyro 0.07 at 200Hz), bias; 2x preset. Window mean over n samples.
rng = np.random.default_rng(7)
preset = dict(an=0.28, gn=0.07, ab=0.2, gb=0.02)
def perturb(k, extra_noise_only_added=True):
    flips = {'static->moving': 0, 'mid->static': 0}; tot = {'static': 0, 'mid': 0}
    for rep in range(200):
        for r in rows:
            n = r['n']; w = r['w'].copy()
            # ADD extra independent noise at k x preset std per sample and an extra uniform bias up to k x preset bias max per axis
            w[:, 0:3] += rng.normal(0, k * preset['an'], w[:, 0:3].shape) + rng.uniform(-k * preset['ab'], k * preset['ab'], 3)
            w[:, 3:6] += rng.normal(0, k * preset['gn'], w[:, 3:6].shape) + rng.uniform(-k * preset['gb'], k * preset['gb'], 3)
            m = det(w)[2]
            tot[r['start']] += 1
            if r['start'] == 'static' and m: flips['static->moving'] += 1
            if r['start'] == 'mid' and not m: flips['mid->static'] += 1
    return {k_: f'{v}/{tot[k_.split("->")[0]]} = {v / tot[k_.split("->")[0]]:.4f}' for k_, v in flips.items()}
for k in (1, 2, 4):
    print(f'extra noise+bias at {k}x preset (added on top of existing; i.e. total noise std sqrt(1+{k}^2)x):', perturb(k))
# bias-only worst-case: gyro bias that flips static: 0.2 rad/s = 10x preset max; accel bias norm needed
print('static |f| headroom to 8.8 =', min(r['f'] for r in st) - DF, ' -> accel bias norm needed to flip (worst axis aligned):', min(r['f'] for r in st) - DF)
print('preset window-mean noise: accel std/axis %.3f, gyro std/axis %.4f (n=10)' % (0.28 / np.sqrt(10), 0.07 / np.sqrt(10)))
json.dump([{k: v for k, v in r.items() if k != 'w'} for r in rows], open('research/single_model/final/preflight/detector_rows.json', 'w'), indent=0)
