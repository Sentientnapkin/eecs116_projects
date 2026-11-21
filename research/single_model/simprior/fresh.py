"""Fresh-711 scoring of a built sp_ wasm: python -B -m research.single_model.simprior.fresh --name sp_x  (wasm = results/single_model/<name>/solution.wasm)
Outputs to results/single_model/sp_fresh_<name>; per-flight table in simprior/ftable_<name>.json."""
import argparse, json, os
from pathlib import Path
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV
POOL = Path('/data/backups/rganapa/Sebastian/tmp/fresh_pool'); HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser(); ap.add_argument('--name', required=True); ap.add_argument('--workers', type=int, default=24)
a = ap.parse_args()
wasm = RV.OUT / a.name / 'solution.wasm'
sc = RV.run_guest_fast(wasm, POOL, RV.OUT / ('sp_fresh_' + a.name.removeprefix('sp_')) / 'eval', workers=a.workers, name=a.name)
tags = json.loads((HERE.parent / 'fresh/tags.json').read_text())
rows = [dict(episode=r['episode'], ate=r.get('ate_full'), peak_fuel=r.get('peak_fuel_per_frame'), **tags[r['episode']]) for r in json.loads(Path(sc).read_text())['rows']]
(HERE / f'ftable_{a.name}.json').write_text(json.dumps(rows))
ok = [r['ate'] for r in rows if r['ate'] is not None]; print(a.name, len(ok), sum(ok) / len(ok))
