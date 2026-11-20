"""Raw unaligned ATE reports. Scene bootstrap preserves scene clusters.

python -m campaign.report --table table.jsonl --output report.json --parent vins_mono
"""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from .perflight import load_rows, REQUIRED_TAGS


def distribution(rows, bootstrap=5000, seed=217):
    if not rows:
        raise ValueError('empty report slice')
    x = np.asarray([r['ate_full'] for r in rows], float)
    w = np.asarray([r.get('draw_weight', 1) for r in rows], float)
    if not np.isfinite(x).all() or (x < 0).any(): raise ValueError('ATE must be finite and nonnegative')
    if not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0: raise ValueError('invalid draw weights')
    rng = np.random.default_rng(seed)
    means = x[rng.choice(len(x), (bootstrap, 12), replace=True, p=w/w.sum())].mean(1)
    lo, hi = np.percentile(x, [5, 95])
    count = max(1, math.ceil(.1 * len(x)))
    return {'n': len(x), 'mean_unaligned_ate_m': float(x.mean()), 'median_unaligned_ate_m': float(np.median(x)),
            'trimmed95_mean_m': float(np.sort(x)[:max(1, int(.95 * len(x)))].mean()),
            'winsorized5_95_mean_m': float(np.clip(x, lo, hi).mean()),
            'draw_weighted_mean_m': float(np.average(x, weights=w)),
            'draw12_bootstrap_p5_p95_m': np.percentile(means, [5, 95]).tolist(),
            'n_over_5m': int((x > 5).sum()), 'n_over_10m': int((x > 10).sum()),
            'worst10pct_share': float(np.sort(x)[-count:].sum()/x.sum()) if x.sum() else 0.,
            'maximum_m': float(x.max()),
            'peak_fuel_per_frame': max((r.get('peak_fuel_per_frame') or 0) for r in rows),
            'filled_flight_count': sum((r.get('filled_full') or 0) > 0 for r in rows),
            'failed_flight_count': sum(bool(r.get('failure')) or not r.get('completed', True) for r in rows)}


def paired_scene_bootstrap(rows, parent, bootstrap=5000, seed=217):
    a = {r['episode']: r for r in rows}; b = {r['episode']: r for r in parent}
    if set(a) != set(b): raise ValueError('paired comparison requires identical episode sets')
    scenes = {}
    for ep in sorted(a):
        if a[ep]['scene'] != b[ep]['scene']: raise ValueError('paired scene tags differ')
        scenes.setdefault((a[ep]['catalog'], a[ep]['scene']), []).append(a[ep]['ate_full'] - b[ep]['ate_full'])
    values = list(scenes.values()); sums = np.array([sum(v) for v in values]); counts = np.array([len(v) for v in values])
    rng = np.random.default_rng(seed)
    samples = rng.integers(len(values), size=(bootstrap, len(values)))
    draws = sums[samples].sum(1)/counts[samples].sum(1)
    differences = np.array([a[e]['ate_full'] - b[e]['ate_full'] for e in sorted(a)])
    return {'n': len(a), 'n_scenes': len(scenes), 'mean_difference_m': float(differences.mean()),
            'scene_bootstrap90_interval_m': np.percentile(draws, [5, 95]).tolist(),
            'fraction_no_worse_than_parent': float((differences <= 0).mean())}


def build_report(rows, parent=None, bootstrap=5000):
    for r in rows:
        if any(k not in r or r[k] in (None, '') for k in REQUIRED_TAGS): raise ValueError('mandatory split tags missing')
    guests = {}
    for r in rows: guests.setdefault(r['guest'], []).append(r)
    report = {'metric': 'mean_unaligned_ate_m', 'alignment': 'none', 'bootstrap_seed': 217,
              'bootstrap_replicates': bootstrap, 'guests': {}}
    for name, subset in sorted(guests.items()):
        ids = [r['episode'] for r in subset]
        if len(ids) != len(set(ids)): raise ValueError(f'duplicate flight in {name}')
        out = {'overall': distribution(subset, bootstrap), 'splits': {}}
        for tag in ('group', 'catalog', 'start_type'):
            out['splits'][tag] = {value: distribution([r for r in subset if r[tag] == value], bootstrap)
                                  for value in sorted({r[tag] for r in subset})}
        clean_dev = [r for r in subset if r['group'] == 'clean' or (r['group'] == 'dev' and r['catalog'].lower().startswith('hssd'))]
        if clean_dev: out['clean_plus_dev_hssd'] = distribution(clean_dev, bootstrap)
        if parent:
            if parent not in guests: raise ValueError(f'unknown parent guest {parent}')
            out['paired_parent'] = paired_scene_bootstrap(subset, guests[parent], bootstrap)
        report['guests'][name] = out
    return report


def markdown(report):
    lines = ['# Campaign: raw unaligned ATE', '', '| Guest | Flights | Mean (m) | Median (m) | Draw weighted (m) | >10 m | Filled |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for name, d in report['guests'].items():
        r = d['overall']
        lines.append(f"| {name} | {r['n']} | {r['mean_unaligned_ate_m']:.4f} | {r['median_unaligned_ate_m']:.4f} | {r['draw_weighted_mean_m']:.4f} | {r['n_over_10m']} | {r['filled_flight_count']} |")
    for tag in ('group', 'catalog', 'start_type'):
        lines += ['', f'## By {tag}', '', '| Guest | Slice | Flights | Mean (m) | Median (m) |', '|---|---|---:|---:|---:|']
        for name, data in report['guests'].items():
            for value, r in data['splits'][tag].items():
                lines.append(f"| {name} | {value} | {r['n']} | {r['mean_unaligned_ate_m']:.4f} | {r['median_unaligned_ate_m']:.4f} |")
    lines += ['', 'All flights count, including evaluator-filled failures. No trajectory alignment. Draw weights reproduce the declared selection multiplicities. Bootstrap intervals are sampling uncertainty, not a server guarantee.', '']
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--table', required=True); p.add_argument('--output', required=True)
    p.add_argument('--parent'); p.add_argument('--bootstrap', type=int, default=5000); a = p.parse_args()
    report = build_report(load_rows(a.table), a.parent, a.bootstrap)
    out = Path(a.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2)+'\n'); out.with_suffix('.md').write_text(markdown(report))
    print(out)


if __name__ == '__main__': main()
