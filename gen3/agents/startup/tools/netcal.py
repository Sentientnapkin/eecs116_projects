"""netcal.py EVALNAME POOL: net calibration from LCO debug lines (ST_DBG build) vs GT body velocity.
For each anchor (startup and re-anchors): head0 (v at anchor frame) and headK (v at anchor+5) error, whitened chi2 (3 dof) with the net's sigma."""
import sys, json, glob
from pathlib import Path
from multiprocessing import Pool
import numpy as np
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import quaternion_to_matrix
G = Path('/data/backups/rganapa/Sebastian/gen3')
name, pool = sys.argv[1], sys.argv[2]
meta = {r['id']: r for r in json.load(open(G / 'evals' / f'{name}__{pool}.json'))}
def one(d):
    d = Path(d); fid = [p for p in d.parts if p.startswith('s3')][0]
    z = G / 'pools' / pool / (fid + '.zip')
    if not z.exists(): return []
    ep = read_episode(z, frames='none'); gt = ep.ground_truth_state(); Tbc = np.asarray(ep.T_body_camera)[:3, :3]  # GT state = camera pose relative to camera 0
    out = []
    for l in (d.parent / 'stderr.txt').read_text().splitlines():
        if not l.startswith('LCO '): continue
        f = l.split(); fa, na = int(f[1]), int(f[2]); o = np.array([float(x) for x in f[3:15]])
        row = {'id': fid, 'fa': fa, 'na': na}
        for h, k in ((0, fa + (1 if na else 0)), (1, fa + 5 + (1 if na else 0))):
            if k >= len(gt): continue
            Rg = quaternion_to_matrix(gt[k, 3:7]); vb = Tbc @ gt[k, 7:10]  # GT twist is camera-LOCAL
            mu = o[6 * h:6 * h + 3]; lv = np.clip(o[6 * h + 3:6 * h + 6], -7, 4); sd = np.maximum(np.exp(0.5 * lv), 0.05)
            e = mu - vb
            row[f'h{h}'] = {'err': float(np.linalg.norm(e)), 'chi2': float(np.sum((e / sd) ** 2)), 'spd': float(np.linalg.norm(vb)), 'e': e.tolist(), 'sd': sd.tolist(), 'z': (e / sd).tolist()}
        m = meta.get(fid, {}); row.update({k: m.get(k) for k in ('setting_class', 'start', 'start_fwd_speed')})
        out.append(row)
    return out
if __name__ == '__main__':
    ds = sorted(glob.glob(str(G / 'evals' / name / pool / '*' / '*' / 'report/logs/*/estimate.tum')))
    with Pool(12) as p: R = [x for y in p.map(one, ds) for x in y]
    json.dump(R, open(G / 'agents/startup/ana' / f'netcal_{name}__{pool}.json', 'w'))
    def summ(rows, tag):
        for h in ('h0', 'h1'):
            X = [r[h] for r in rows if h in r]
            if not X: continue
            c = np.array([x['chi2'] for x in X]); er = np.array([x['err'] for x in X]); zz = np.array([x['z'] for x in X])
            print(f'{tag:28s} {h} n {len(X):5d} err {er.mean():.3f} med {np.median(er):.3f} chi2>11.345 {np.mean(c > 11.345) * 100:5.1f}% (nominal 1%)  3sig cover/axis {np.mean(np.abs(zz) < 3) * 100:5.1f}%  z-rms {np.sqrt(np.mean(zz ** 2)):.2f}  z-rms/axis {np.sqrt(np.mean(zz ** 2, 0)).round(2).tolist()}')
    st = [r for r in R if r['na'] == 0]
    summ(st, 'startup all'); summ([r for r in st if r['start'] != 'hover'], 'startup mid-flight'); summ([r for r in st if r['start'] == 'hover'], 'startup hover')
    for c in ('room', 'warehouse', 'forest'): summ([r for r in st if r['start'] != 'hover' and r['setting_class'] == c], f'startup mid {c}')
    summ([r for r in R if r['na'] > 0], 're-anchors')
