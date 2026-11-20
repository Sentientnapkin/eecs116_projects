"""Consolidate bench_eval scores without dropping failed flights.

python -m campaign.perflight --scores ROOT --metadata RAW/bench --output table.jsonl
"""
import argparse
import json
from pathlib import Path
import numpy as np

REQUIRED_TAGS = ('group', 'catalog', 'scene', 'start_type', 'source_pool')


def consolidate(scores_root, metadata_root, weights=None, expected=None):
    metadata = {p.stem: json.loads(p.read_text()) for p in Path(metadata_root).glob('*.json')}
    tables = []
    for path in sorted(Path(scores_root).glob('*/scores.json')):
        data = json.loads(path.read_text())
        guest = data['guest']
        records = {r['episode']: r for r in data['rows']}
        if len(records) != len(data['rows']):
            raise ValueError(f'duplicate episode rows: {path}')
        names = sorted(expected or {Path(p).stem for p in guest.get('archives', [])} or records)
        for name in names:
            if name not in metadata:
                raise ValueError(f'missing split metadata: {name}')
            m = metadata[name]
            if any(not m.get(k) for k in ('group', 'catalog', 'scene')):
                raise ValueError(f'incomplete split metadata: {name}')
            r = records.get(name)
            # A missing score is never silently removed or replaced with an approximate
            # audit statistic. Rescore it with pinned wasm_eval first.
            if r is None or r.get('ate_full') is None:
                raise ValueError(f'unscored flight {guest["name"]}/{name}: rescore with the pinned evaluator')
            ate = float(r['ate_full'])
            if not np.isfinite(ate) or ate < 0:
                raise ValueError(f'invalid ATE: {guest["name"]}/{name}')
            tables.append({**r, 'guest': guest['name'], 'guest_sha256': guest['sha256'],
                           'group': m['group'], 'catalog': m['catalog'], 'scene': m['scene'],
                           'start_type': 'mid' if name.startswith('fastmid-') or m.get('crop_start_s', 0) else 'static',
                           'source_pool': str(Path(metadata_root).parent.resolve()),
                           'draw_weight': float((weights or {}).get(name, 1.0)),
                           'ate_full': ate, 'score_origin': str(path.resolve())})
    return tables


def load_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scores', required=True); p.add_argument('--metadata', required=True)
    p.add_argument('--selection', help='JSON with selected and optionally selection_weights')
    p.add_argument('--output', required=True)
    a = p.parse_args()
    selection = json.loads(Path(a.selection).read_text()) if a.selection else {}
    rows = consolidate(a.scores, a.metadata, selection.get('selection_weights'), selection.get('selected'))
    out = Path(a.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows))
    print(f'{len(rows)} rows -> {out}')


if __name__ == '__main__': main()
