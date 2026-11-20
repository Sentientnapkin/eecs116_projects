"""Score a prebuilt wasm on the FRESH pool (711 unselected flights): python -B -m research.single_model.fresh.run_fresh --name base --wasm X.wasm
Copy of run_variant's runner with episodes dir = tmp/fresh_pool, PNG cache off, table extraction (no sealed data involved)."""
import argparse, csv, json, os, sys
from pathlib import Path
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV

POOL = Path('/data/backups/rganapa/Sebastian/tmp/fresh_pool')
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
    ap.add_argument('--workers', type=int, default=32)
    a = ap.parse_args()
    out = OUT / ('fresh_' + a.name)
    sc = RV.run_guest_fast(a.wasm, POOL, out / 'eval', workers=a.workers, name=a.name)
    rows = table(a.name, sc)
    ok = [r['ate'] for r in rows if r['ate'] is not None]
    print(a.name, 'n', len(ok), 'mean', sum(ok) / len(ok))

if __name__ == '__main__':
    main()
