"""python -B -m research.single_model.servertail.runpool NAME WASM POOLDIR [workers] -> results/single_model/st_NAME/<pool>/..., tables/NAME__POOL.json"""
import json, os, sys, subprocess
from pathlib import Path
os.environ['VIOBENCH_PNG_CACHE'] = '0'
from research.single_model import run_variant as RV
name, wasm, pool = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]); W = int(sys.argv[4]) if len(sys.argv) > 4 else 32
HERE = Path(__file__).resolve().parent
out = RV.ROOT / 'research/results/single_model' / ('lj_' + name) / pool.name
sc = RV.run_guest_fast(wasm, pool, out, workers=W, name=name)
ev = Path(sc).parent
env = dict(os.environ, POOL=str(pool))
subprocess.run([sys.executable, str(HERE / 'mets.py'), str(ev), str(HERE / 'tables' / f'{name}__{pool.name}.json')], env=env, check=True)
rows = json.loads((HERE / 'tables' / f'{name}__{pool.name}.json').read_text())
a = [r['ate_rmse'] for r in rows if r.get('ate_rmse') is not None]
print(name, pool.name, 'n', len(a), 'mean %.4f' % (sum(a) / len(a)), 'peak', max(r['peak'] for r in rows), 'filled', sum((r.get('filled_frames') or 0) > 0 for r in rows))

summary = f"- Result {name} / {pool.name}: n={len(a)}, mean unaligned ATE={sum(a)/len(a):.6f}, peak={max(r['peak'] for r in rows)/1e6:.3f} M, tails >3/5/10=" + '/'.join(str(sum(x>t for x in a)) for t in (3,5,10)) + f", filled={sum((r.get('filled_frames') or 0) for r in rows)}, completed={sum(r.get('ok',False) for r in rows)}.\n"
with (HERE/'NOTES.md').open('a') as f: f.write(summary)
