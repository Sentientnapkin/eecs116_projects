"""selected-144 (visible folds 0-3, no fold 4) runner: python -B -m research.single_model.tier1m.run_sel --name X --wasm path -> tables/sel_X.json"""
import argparse, json, os
from pathlib import Path
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV
HERE = Path(__file__).resolve().parent
POOL = HERE.parent / 'tailcap/pool_sel144'
ap = argparse.ArgumentParser(); ap.add_argument('--name', required=True); ap.add_argument('--wasm', type=Path, required=True); ap.add_argument('--workers', type=int, default=24)
a = ap.parse_args()
sc = RV.run_guest_fast(a.wasm, POOL, RV.ROOT / 'research/results/single_model' / ('t1s_' + a.name) / 'eval', workers=a.workers, name=a.name)
d = json.loads(Path(sc).read_text())
rows = [dict(episode=r['episode'], ate=r.get('ate_full'), peak_fuel=r.get('peak_fuel_per_frame')) for r in d['rows']]
(HERE / 'tables' / f'sel_{a.name}.json').write_text(json.dumps(rows))
