import json,glob,sys,numpy as np
from pathlib import Path
R=Path('research/results/single_model')
def fuel(n):
    f=glob.glob(f'{R}/{n}/eval/*/scores.json')[0]; d=json.load(open(f))
    return max(r.get('peak_fuel_per_frame') or 0 for r in d['rows'])/1e6
for n in sys.argv[1:]:
    L=[l for l in open(f'{R}/{n}/report.txt')]
    g=lambda p:[l for l in L if l.startswith(p)][0]
    def parse(l):
        t=l.split(); i=t.index('mean'); return float(t[i+1]), float(t[t.index('median')+1]), int(t[t.index('>5m')+1]), int(t[t.index('>10m')+1]), l[l.index('paired'):l.index('| err')].strip()
    a=parse(g('search all')); s=parse(g('search static')); m=parse(g('search mid')); v=parse(g('val    all'))
    print(f'{n:22s} S mean {a[0]:.3f} med {a[1]:.2f} static {s[0]:.3f} mid {m[0]:.3f} >5 {a[2]} >10 {a[3]} {a[4]} | val {v[0]:.3f} | fuel {fuel(n):.1f}M' if len(sys.argv)<0 else f'{n:22s} S mean {a[0]:.3f} med {a[1]:.2f} static {s[0]:.3f} mid {m[0]:.3f} >5 {a[2]} >10 {a[3]} {a[4]} | fuel {fuel(n):.1f}M')
