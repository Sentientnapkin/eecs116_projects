"""Score a prebuilt wasm ONCE on the final holdout set (gen/raw-holdout/final symlinks). Copy of fresh/run_fresh.py with
this set's pool and tags. python -B -m research.single_model.holdout.run_holdout --name base --wasm X.wasm   (from eecs116_projects/)
"""
import argparse, csv, json, os, sys
from pathlib import Path
os.environ['VIOBENCH_PNG_CACHE'] = '0'
os.environ.setdefault('VIOBENCH_SHARED_CACHE_ROOT', '/dev/shm/sebastian-holdout/guard-cache')
from research.single_model import run_variant as RV

POOL = Path('/data/backups/rganapa/Sebastian/gen/raw-holdout/final')
HERE = Path(__file__).resolve().parent
OUT = RV.ROOT / 'research/results/single_model'

def table(name, scores):
    tags = json.loads((HERE / 'tags.json').read_text())
    d = json.loads(Path(scores).read_text())
    rows = []
    for r in d['rows']:
        t = tags[r['episode']]
        rows.append(dict(episode=r['episode'], start=t['start'], scene=t['scene'], catalog=t['catalog'], group=t['group'],
                         ate=r.get('ate_full'), completed=r.get('completed'), filled=r.get('filled_full'),
                         peak_fuel=r.get('peak_fuel_per_frame'), error=r.get('error')))
    (HERE / f'table_{name}.json').write_text(json.dumps(rows, indent=0))
    with open(HERE / f'table_{name}.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True); ap.add_argument('--wasm', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=24)
    a = ap.parse_args()
    if (HERE / f'table_{a.name}.json').exists():
        sys.exit(f'holdout rule: {a.name} was already scored once; refusing to rescore')
    out = OUT / ('holdout_' + a.name)
    os.environ['VIOBENCH_SHARED_CACHE'] = '/dev/shm/sebastian-holdout/guard-cache/' + a.name
    sc = RV.run_guest_fast(a.wasm, POOL, out / 'eval', workers=a.workers, name=a.name)
    rows = table(a.name, sc)
    ok = [r['ate'] for r in rows if r['ate'] is not None]
    print(a.name, 'n', len(ok), 'mean', sum(ok) / len(ok))

if __name__ == '__main__':
    main()
