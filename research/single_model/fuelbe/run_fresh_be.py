"""Score a prebuilt wasm on the 711 fresh flights; tables into fuelbe/. usage: python -B -m research.single_model.fuelbe.run_fresh_be --name X --wasm W"""
import argparse, csv, json, os
from pathlib import Path
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV
POOL = Path('/data/backups/rganapa/Sebastian/tmp/fresh_pool')
HERE = Path(__file__).resolve().parent; TAGS = HERE.parent / 'fresh' / 'tags.json'
OUT = RV.ROOT / 'research/results/single_model'
ap = argparse.ArgumentParser(); ap.add_argument('--name', required=True); ap.add_argument('--wasm', type=Path, required=True); ap.add_argument('--workers', type=int, default=24)
a = ap.parse_args()
sc = RV.run_guest_fast(a.wasm, POOL, OUT / ('fb_fresh_' + a.name) / 'eval', workers=a.workers, name=a.name)
tags = json.loads(TAGS.read_text()); d = json.loads(Path(sc).read_text()); rows = []
for r in d['rows']:
    t = tags[r['episode']]
    rows.append(dict(episode=r['episode'], start=t['start'], scene=t['scene'], catalog=t['catalog'], group=t['group'], ate=r.get('ate_full'),
                     completed=r.get('completed'), filled=r.get('filled_full'), peak_fuel=r.get('peak_fuel_per_frame'), error=r.get('error')))
(HERE / f'fresh_table_{a.name}.json').write_text(json.dumps(rows))
ok = [r['ate'] for r in rows if r['ate'] is not None]; pk = [r['peak_fuel'] for r in rows if r['peak_fuel']]
import numpy as np
x = np.array(ok)
print(a.name, 'n', len(ok), 'fresh_mean %.4f median %.3f >3 %d >5 %d >10 %d peak_max %.3fM p95_of_peaks %.3fM' % (x.mean(), np.median(x), (x>3).sum(), (x>5).sum(), (x>10).sum(), max(pk)/1e6, np.percentile(pk,95)/1e6))
