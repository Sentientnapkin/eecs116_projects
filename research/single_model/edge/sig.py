"""Server-style per-flight metrics (rotation RMSE, velocity RMSE, sim3 scale, sim3 ATE, drift/m) for candidates on pool flights (fold 4 excluded)."""
import json, sys, glob, hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0, '/data/backups/rganapa/Sebastian/eecs116_projects'); sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
from viobench.tools.runner.metrics import evaluate_trajectory
from viobench.tools.runner.score import load_estimates
from research.guard_fusion.traj import load_truth
R = Path('/data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model')
RAW = {'sel': '/data/backups/rganapa/Sebastian/gen/raw-fast/selected', 'fresh': '/data/backups/rganapa/Sebastian/tmp/fresh_pool'}
BASE_SEL = Path('/data/backups/rganapa/Sebastian/eecs116_projects/research/results/loop/gp-msckf-pool/gp_msckf-c7413a81')
CAND = {'base': ('base', 'fresh_base'), 'f0': ('final_f0', 'fresh_f0'), 'G': ('preflight_gate_a', 'fresh_gate'),
        'T': ('tails_adopted', 'fresh_tails'), 'M': ('fgt_merged', 'fresh_fgt')}
def edir(name, pool):
    if name == 'base' and pool == 'sel': return BASE_SEL
    d = R / name / 'eval'
    c = sorted(p for p in d.glob('*') if p.is_dir())
    return c[0] if c else None
aud = json.load(open('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/edge/audit.json'))
def main(cands):
    out = {}
    for ep, a in sorted(aud.items()):
        if a['fold'] == 4: continue
        pool = a['pool']
        try: t, gt, meta = load_truth(RAW[pool], ep)
        except Exception as e: print('truth fail', ep, e); continue
        row = {}
        for c in cands:
            nm = CAND[c][0 if pool == 'sel' else 1]
            d = edir(nm, pool)
            if d is None: continue
            ps = sorted((d / ep / 'report/logs').glob('*/estimate.tum')) if (d / ep).exists() else []
            if len(ps) != 1: continue
            try:
                est = load_estimates(ps[0], t)
                m = evaluate_trajectory(gt, est, t).as_dict()
            except Exception as e:
                print('fail', c, ep, e); continue
            row[c] = {k: m[k] for k in ('ate_rmse', 'rotation_rmse', 'rotation_max', 'velocity_rmse', 'sim3_scale', 'sim3_ate_rmse', 'final_drift', 'drift_per_metre', 'distance') if k in m}
        out[ep] = row
    json.dump(out, open('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/edge/sig.json', 'w'))
    print(len(out))
if __name__ == '__main__': main(sys.argv[1:] or list(CAND))
