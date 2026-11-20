"""Score a prebuilt wasm on the fresh pool (711 unselected flights); writes only under inventive/ and results/single_model/inv_fresh_*.
usage (from repo root): python -B research/single_model/inventive/fresh_run.py --name X --wasm path.wasm"""
import argparse, json, os, sys
from pathlib import Path
sys.path.insert(0, '.')
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV
from research.single_model.fresh import run_fresh as RF
ap = argparse.ArgumentParser(); ap.add_argument('--name', required=True); ap.add_argument('--wasm', type=Path, required=True); ap.add_argument('--workers', type=int, default=24)
a = ap.parse_args()
out = RV.OUT / ('inv_fresh_' + a.name)
sc = RV.run_guest_fast(a.wasm, RF.POOL, out / 'eval', workers=a.workers, name=a.name)
tags = json.loads((RF.HERE / 'tags.json').read_text())
d = json.loads(Path(sc).read_text()); rows = []
for r in d['rows']:
    t = tags[r['episode']]
    rows.append(dict(episode=r['episode'], start=t['start'], scene=t['scene'], ate=r.get('ate_full')))
Path(__file__).with_name(f'fresh_table_{a.name}.json').write_text(json.dumps(rows))
ok = [r['ate'] for r in rows if r['ate'] is not None]
print(a.name, 'n', len(ok), 'mean', sum(ok) / len(ok))
