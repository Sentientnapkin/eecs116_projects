"""fold-3 unselected pool (107 flights) runner: python -B -m research.single_model.bulk.run_f3_bk --name bk_x --wasm path ; table bulk/tables/<name>.f3.json"""
import argparse, json, os
from pathlib import Path
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV
POOL = Path('/data/backups/rganapa/Sebastian/tmp/lc_fold3_pool'); HERE = Path(__file__).resolve().parent
F = json.load(open(HERE.parent / 'learned_c/feats.json'))
ap = argparse.ArgumentParser(); ap.add_argument('--name', required=True); ap.add_argument('--wasm', type=Path, required=True); ap.add_argument('--workers', type=int, default=28)
a = ap.parse_args()
out = RV.ROOT / 'research/results/single_model' / ('bk_f3_' + a.name.replace('bk_', ''))
sc = RV.run_guest_fast(a.wasm, POOL, out / 'eval', workers=a.workers, name=a.name)
rows = [dict(episode=r['episode'], ate=r.get('ate_full'), peak_fuel=r.get('peak_fuel_per_frame'), filled=r.get('filled_full')) for r in json.loads(Path(sc).read_text())['rows'] if r['episode'] in F]
(HERE / 'tables' / f'{a.name}.f3.json').write_text(json.dumps(rows))
v = [r['ate'] for r in rows]; print(a.name, 'f3 n', len(v), 'mean', sum(v) / len(v))
