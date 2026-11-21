"""runpool.py NAME WASM POOL [workers]: score a pool dir -> tables/pool_NAME.json"""
import json, os, sys
from pathlib import Path
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV
H = Path(__file__).resolve().parent
name, wasm, pool = sys.argv[1], Path(sys.argv[2]), H / sys.argv[3]; w = int(sys.argv[4]) if len(sys.argv) > 4 else 40
sc = RV.run_guest_fast(wasm, pool, RV.ROOT / 'research/results/single_model' / ('app_' + name) / 'eval', workers=w, name=name)
d = json.loads(Path(sc).read_text())
rows = [dict(episode=r['episode'], ate=r.get('ate_full'), peak_fuel=r.get('peak_fuel_per_frame'), error=r.get('error')) for r in d['rows']]
(H / 'tables' / f'pool_{name}.json').write_text(json.dumps(rows))
ok = [r['ate'] for r in rows if r['ate'] is not None]
print(name, sys.argv[3], 'n', len(ok), 'mean %.3f' % (sum(ok) / len(ok)), 'peak', max(r['peak_fuel'] or 0 for r in rows), 'err', sum(1 for r in rows if r['error']))
