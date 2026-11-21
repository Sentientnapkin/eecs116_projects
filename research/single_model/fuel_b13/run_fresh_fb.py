"""Fresh-711 runner: python -B -m research.single_model.fuel_b13.run_fresh_fb --name X --wasm path ; table fuel_b13/tables/X.json (fields ate, peak_fuel...)"""
import argparse, json, os
from pathlib import Path
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV
POOL = Path('/data/backups/rganapa/Sebastian/tmp/fresh_pool')
HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser(); ap.add_argument('--name', required=True); ap.add_argument('--wasm', type=Path, required=True); ap.add_argument('--workers', type=int, default=24)
a = ap.parse_args()
out = RV.ROOT / 'research/results/single_model' / ('fbf_' + a.name)
sc = RV.run_guest_fast(a.wasm, POOL, out / 'eval', workers=a.workers, name=a.name)
tags = json.loads((HERE.parent / 'fresh/tags.json').read_text())
d = json.loads(Path(sc).read_text()); rows = []
for r in d['rows']:
    t = tags[r['episode']]
    rows.append(dict(episode=r['episode'], start=t['start'], scene=t['scene'], catalog=t['catalog'], group=t['group'], ate=r.get('ate_full'), filled=r.get('filled_full'), peak_fuel=r.get('peak_fuel_per_frame'), error=r.get('error')))
(HERE / 'tables').mkdir(exist_ok=True)
(HERE / 'tables' / f'{a.name}.json').write_text(json.dumps(rows))
ok = [r['ate'] for r in rows if r['ate'] is not None]
print(a.name, 'n', len(ok), 'mean', sum(ok) / len(ok), 'median', sorted(ok)[len(ok)//2], 'peak', max(r['peak_fuel'] or 0 for r in rows))
