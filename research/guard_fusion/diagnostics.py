"""Truth-assisted offline error decomposition; never an inference component.

Reports unaligned ATE only. Oracle velocity/attitude and fitted-scale arms are
explicitly nondeployable diagnostics. Speed bias is measured on all moving
frames, rather than only the convenient static-start development distribution.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path

import numpy as np

from .traj import DEFAULT_RAW, DEFAULT_SELECTED, list_episodes, load_episode
from viobench.tools.geometry import poses_to_matrices


def integrate(t, velocity):
    p = np.zeros_like(velocity)
    p[1:] = np.cumsum(.5 * (velocity[:-1] + velocity[1:]) * np.diff(t)[:, None], axis=0)
    return p


def rmse(a, b):
    return float(np.sqrt(np.mean(np.sum((a-b)**2, axis=-1))))


def one(args):
    selected, raw, episode = args
    e = load_episode(selected, raw, episode, {'n2': 'n2_kfinputs_s217-8b05b203'})
    t, truth, s = e['t'], e['truth'], e['sources']['n2']
    R = s['T'][:, :3, :3]
    Rgt = poses_to_matrices(truth)[:, :3, :3]
    v, gt = s['states'][:, 7:10], truth[:, 7:10]
    world = (R @ v[..., None])[..., 0]
    p = integrate(t, world)
    target = truth[:, :3]
    denom = np.sum(p*p)
    scale = max(0., float(np.sum(p * target) / denom)) if denom else 1.
    speed, real = np.linalg.norm(v, axis=1), np.linalg.norm(gt, axis=1)
    edges = [0., .25, .5, 1., 2., 3., 4., 6., 100.]
    bins = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (real >= lo) & (real < hi) & s['valid']
        bins.append({'lo': lo, 'hi': hi, 'n': int(m.sum()),
                     'pred_sum': float(speed[m].sum()), 'truth_sum': float(real[m].sum()),
                     'projection_sum': float(np.sum(v[m]*gt[m] / np.maximum(real[m,None], 1e-12)))})
    moving = real > 1
    return {'episode': episode, **e['tags'], 'ate_m': rmse(s['states'][:, :3], target),
            'velocity_integrated_ate_m': rmse(p, target),
            'oracle_true_velocity_estimated_attitude_ate_m': rmse(integrate(t, (R @ gt[...,None])[...,0]), target),
            'oracle_estimated_velocity_true_attitude_ate_m': rmse(integrate(t, (Rgt @ v[...,None])[...,0]), target),
            'oracle_fitted_global_scale': scale, 'oracle_fitted_scale_ate_m': rmse(scale*p, target),
            'moving_speed_ratio': float(speed[moving].sum()/real[moving].sum()) if moving.any() else None,
            'speed_bins': bins}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--selected', type=Path, default=DEFAULT_SELECTED)
    p.add_argument('--raw', type=Path, default=DEFAULT_RAW)
    p.add_argument('--workers', type=int, default=32)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    with ProcessPoolExecutor(max_workers=min(a.workers, 160)) as pool:
        rows = list(pool.map(one, [(a.selected, a.raw, e) for e in list_episodes(a.selected)]))
    keys = [k for k in rows[0] if k.endswith('_ate_m') or k == 'ate_m']
    summary = {k: {'mean': float(np.mean([r[k] for r in rows])),
                   'median': float(np.median([r[k] for r in rows]))} for k in keys}
    bins = []
    for j in range(len(rows[0]['speed_bins'])):
        values = [r['speed_bins'][j] for r in rows]
        n = sum(b['n'] for b in values)
        gt = sum(b['truth_sum'] for b in values)
        bins.append({'lo': values[0]['lo'], 'hi': values[0]['hi'], 'frames': n,
                     'speed_ratio': sum(b['pred_sum'] for b in values)/gt if gt else None,
                     'directional_ratio': sum(b['projection_sum'] for b in values)/gt if gt else None})
    report = {'diagnostic_only': True, 'n': len(rows), 'summary': summary,
              'speed_bins': bins, 'rows': rows}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'summary': summary, 'speed_bins': bins}, indent=2))


if __name__ == '__main__':
    main()
