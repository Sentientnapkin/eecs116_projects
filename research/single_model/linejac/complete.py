from pathlib import Path
import hashlib,json,sys
w=Path(__file__).resolve().parent
name,wasm,pool=sys.argv[1:];pool=Path(pool)
t=w/'tables'/f'{name}__{pool.name}.json'
if not t.exists():sys.exit(1)
sha=hashlib.sha256(Path(wasm).read_bytes()).hexdigest();g=w.parents[1]/f'results/single_model/lj_{name}'/pool.name/f'{name}-{sha[:8]}'/'guest.json'
if not g.exists() or json.loads(g.read_text())['sha256']!=sha:sys.exit(1)
r=json.loads(t.read_text());expected={p.stem for p in pool.glob('*.zip')}
if {v['ep'] for v in r}!=expected or not all(v.get('ok') and v.get('ate_rmse') is not None for v in r):sys.exit(1)
print(f'{name} {pool.name}: reusing completed evaluation ({len(r)} flights, {sha[:8]})')
