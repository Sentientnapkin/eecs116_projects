"""usage (repo root): python -B research/single_model/frontend/cmprep2.py refname arm...   (names have _r0.._r2)"""
import sys, json; sys.path.insert(0, '.')
import numpy as np
from research.single_model.run_variant import OUT, slice_of, paired
def load(n): return [{x['e']: x for x in json.loads((OUT / f'{n}_r{i}/report.json').read_text())['rows_visible']} for i in range(3)]
def fuel(n):
    pk=[];p95=[]
    for i in range(3):
        d=json.loads(next((OUT/f'{n}_r{i}'/'eval').glob('*/scores.json')).read_text())['rows']
        rs=[r for r in d if 'peak_fuel_per_frame' in r]; pk.append(max(r['peak_fuel_per_frame'] for r in rs)); p95.append(max(r['p95_fuel_per_frame'] for r in rs))
    return max(pk)/1e6, max(p95)/1e6
ref = load(sys.argv[1])
for n in sys.argv[2:]:
    try: new = load(n)
    except Exception: print(n,'incomplete'); continue
    out=[]
    for sl in ('search','val'):
        for st in ('all','static','mid'):
            ks=[e for e in new[0] if slice_of(new[0][e]['fold'])==sl and (st=='all' or new[0][e]['start']==st)]
            x=[np.mean([r[e]['new'] for r in ref]) for e in ks]; y=[np.mean([r[e]['new'] for r in new]) for e in ks]
            d,lo,hi=paired(x,y,[new[0][e]['scene'] for e in ks])
            c5=[sum(r[e]['new']>5 for e in ks) for r in new]; c10=[sum(r[e]['new']>10 for e in ks) for r in new]
            reps=[round(np.mean([r[e]['new'] for e in ks]),3) for r in new]
            out.append(f'{sl}/{st}: ref {np.mean(x):.3f} arm {np.mean(y):.3f} d {d:+.3f} [{lo:+.3f},{hi:+.3f}] reps {reps} >5 {c5} >10 {c10}')
    f=fuel(n)
    print(n, f'fuel peak {f[0]:.1f}M maxp95 {f[1]:.1f}M'); print('  '+'\n  '.join(out))
