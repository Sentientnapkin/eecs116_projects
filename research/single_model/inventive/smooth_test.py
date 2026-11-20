"""Offline test of causal output smoothing (idea M). Uses saved estimate.tum of fgt_rep_r0 (search+val only, no fold 4) and truth positions."""
import sys, json; sys.path.insert(0, '.')
import numpy as np
from pathlib import Path
from research.guard_fusion import traj as T
from research.single_model.run_variant import OUT, slice_of
rows = json.loads((OUT / 'fgt_rep_r0/report.json').read_text())['rows_visible']
folder = next((OUT / 'fgt_rep_r0/eval').glob('fgt_rep_r0-*'))
res = {}
def rmse(a, b): return float(np.sqrt(np.mean(np.sum((a - b) ** 2, 1))))
for r in rows:
    if slice_of(r['fold']) != 'search': continue
    e = r['e']
    t, truth, _ = T.load_truth(T.DEFAULT_RAW, e)
    paths = sorted((folder / e / 'report/logs').glob('*/estimate.tum'))
    est = T.fill_missing_states(T.load_estimates(paths[0], t))
    p = est[:, :3]; tr = truth[:, :3]
    out = {'raw': rmse(p, tr), 'ate': r['new']}
    for a in (0.5, 0.3, 0.15):
        q = p.copy()
        for i in range(1, len(p)): q[i] = q[i-1] + a * (p[i] - q[i-1])
        out[f'ema{a}'] = rmse(q, tr)
        # lag compensated: q + (1-a)/a * (q - q_prev)  (double EMA style)
        q2 = q.copy(); q2[1:] = q[1:] + (1 - a) / a * (q[1:] - q[:-1])
        out[f'lead{a}'] = rmse(q2, tr)
    out['jitter'] = float(np.mean(np.linalg.norm(np.diff(p, 2, axis=0), axis=1)))
    res[e] = out
ks = ['ate', 'raw', 'ema0.5', 'ema0.3', 'ema0.15', 'lead0.5', 'lead0.3', 'lead0.15', 'jitter']
for k in ks: print(k, round(np.mean([v[k] for v in res.values()]), 4))
