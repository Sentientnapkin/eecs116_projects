"""python -B -m research.single_model.servertail.runpool NAME WASM POOLDIR [workers] -> results/single_model/st_NAME/<pool>/..., tables/NAME__POOL.json"""
import json, os, sys, subprocess
from pathlib import Path
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV
name, wasm, pool = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]); W = int(sys.argv[4]) if len(sys.argv) > 4 else 32
HERE = Path(__file__).resolve().parent
out = RV.ROOT / 'research/results/single_model' / ('lv_' + name) / pool.name
sc = RV.run_guest_fast(wasm, pool, out, workers=W, name=name)
ev = Path(sc).parent
env = dict(os.environ, POOL=str(pool))
subprocess.run([sys.executable, str(HERE / 'mets.py'), str(ev), str(HERE / 'tables' / f'{name}__{pool.name}.json')], env=env, check=True)
rows = json.loads((HERE / 'tables' / f'{name}__{pool.name}.json').read_text())
a = [r['ate_rmse'] for r in rows if r.get('ate_rmse') is not None]
print(name, pool.name, 'n', len(a), 'mean %.4f' % (sum(a) / len(a)), 'peak', max(r['peak'] for r in rows), 'filled', sum((r.get('filled_frames') or 0) > 0 for r in rows))
