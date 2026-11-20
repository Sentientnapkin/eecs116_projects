"""Render one row per guest SHA and seed; only eligible final rows rank."""
import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path


def eligibility(row):
    reasons = []
    for key in ('mean_unaligned_ate_m', 'median_unaligned_ate_m'):
        value = row.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            reasons.append('invalid_' + key)
    if row.get('status') != 'final': reasons.append('not_final')
    if row.get('preflight_pass') is not True: reasons.append('preflight_incomplete')
    if row.get('post_hoc'): reasons.append('post_hoc')
    if row.get('bound'): reasons.append('bound_not_guest')
    if row.get('learned') and set(row.get('evaluated_seeds', [])) != {217, 218, 219}: reasons.append('three_seeds_required')
    if row.get('train_excludes_reserved') is not True and row.get('learned'): reasons.append('training_split_unverified')
    if row.get('metric') != 'mean_unaligned_ate_m': reasons.append('wrong_metric')
    if not row.get('declared_at') or not row.get('first_score_at'):
        reasons.append('declaration_provenance_missing')
    else:
        try:
            if datetime.fromisoformat(row['declared_at'].replace('Z', '+00:00')) > datetime.fromisoformat(row['first_score_at'].replace('Z', '+00:00')):
                reasons.append('declared_after_scoring')
        except (ValueError, TypeError): reasons.append('invalid_timestamp')
    return reasons


def render(rows, output):
    seen = set(); slices = {r['slice'] for r in rows}
    if len(slices) != 1: raise ValueError('a leaderboard must have one declared slice')
    for row in rows:
        key = (row['guest_sha256'], row.get('seed'))
        if key in seen: raise ValueError(f'duplicate guest SHA/seed {key}')
        seen.add(key)
    rows = [{**r, 'exclusion_reasons': ','.join(eligibility(r))} for r in rows]
    rows.sort(key=lambda r: (bool(r['exclusion_reasons']), r['mean_unaligned_ate_m']))
    rank = 0
    for r in rows:
        if not r['exclusion_reasons']: rank += 1; r['rank'] = rank
        else: r['rank'] = ''
    fields = ['rank', 'name', 'guest_sha256', 'seed', 'slice', 'mean_unaligned_ate_m', 'median_unaligned_ate_m', 'status', 'exclusion_reasons']
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore'); writer.writeheader(); writer.writerows(rows)
    lines = ['# Campaign leaderboard', '', 'Ranking metric: mean raw unaligned ATE (m). Exploratory rows are unranked.', '', '| Rank | Guest | Seed | Mean | Median | Status / exclusions |', '|---:|---|---:|---:|---:|---|']
    for r in rows:
        lines.append(f"| {r['rank']} | {r['name']} | {r.get('seed', '')} | {r['mean_unaligned_ate_m']:.4f} | {r['median_unaligned_ate_m']:.4f} | {r['exclusion_reasons'] or 'final'} |")
    output.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--rows', required=True); p.add_argument('--output', required=True)
    a = p.parse_args(); render(json.loads(Path(a.rows).read_text()), a.output)


if __name__ == '__main__': main()
