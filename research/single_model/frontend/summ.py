import sys, json
sys.path.insert(0,'.')
import numpy as np
from research.single_model.run_variant import OUT, slice_of, paired
def load(n):
    return {x['e']: x for x in json.loads((OUT / n / 'report.json').read_text())['rows_visible']}
def fuel(n):
    d = json.loads(next((OUT/n/'eval').glob('*/scores.json')).read_text())
    rows=[r for r in d['rows'] if 'peak_fuel_per_frame' in r]
    return max(r['peak_fuel_per_frame'] for r in rows), float(np.percentile([r['p95_fuel_per_frame'] for r in rows],95)), max(r['p95_fuel_per_frame'] for r in rows)
ref = sys.argv[1]
R = load(ref)
for n in sys.argv[2:]:
    A = load(n); out=[]
    for sl in ('search','val'):
        for st in ('all','static','mid'):
            ks=[e for e in R if slice_of(R[e]['fold'])==sl and (st=='all' or R[e]['start']==st)]
            x=[R[e]['new'] for e in ks]; y=[A[e]['new'] for e in ks]
            d,lo,hi=paired(x,y,[R[e]['scene'] for e in ks])
            if st=='all': out.append(f'{sl} {np.mean(y):.3f} (ref {np.mean(x):.3f}) d={d:+.3f}[{lo:+.3f},{hi:+.3f}] >5:{sum(v>5 for v in y)} >10:{sum(v>10 for v in y)}')
            else: out.append(f'{st} {np.mean(y):.3f}')
    try: f=fuel(n); fs=f'fuel peak {f[0]/1e6:.1f}M maxp95 {f[2]/1e6:.1f}M'
    except Exception as e: fs=str(e)
    print(n,'|',' | '.join(out),'|',fs)
