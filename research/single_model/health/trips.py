"""Per-flight trip counts from stderr.txt of a run: python trips.py <name>  (search slice only unless --all)"""
import sys, json, re, glob
from pathlib import Path
sys.path.insert(0,'.')
from research.single_model.run_variant import tags, fold, slice_of, ate_rows, BASELINE
import numpy as np
name=sys.argv[1]; show=slice_of
root=Path('research/results/single_model')/name
folder=next((root/'eval').glob(name+'-*'))
ate=ate_rows(folder/'scores.json'); base=ate_rows(BASELINE); tg=tags()
KEYS=['nis_hi','nis_rej','vmax','vzmax','tilt','starve_fr','starve_n','reset']
rows=[]
for e in sorted(ate):
    if slice_of(fold(tg[e]))!='search': continue
    p=next((folder/e/'report/logs').glob('*/stderr.txt'),None)
    c=dict.fromkeys(KEYS,0); first={}
    if p:
        last=None
        for l in p.read_text(errors='replace').splitlines():
            if l.startswith('HC sum'): last=dict(re.findall(r'(\w+)=(\d+)',l))
            m=re.match(r'HC (\w+) n=\d+ f=\d+ t=([\d.]+)',l)
            if m and m.group(1) not in first: first[m.group(1)]=float(m.group(2))
        if last:
            for k in KEYS: c[k]=int(last.get(k,0))
    rows.append((e,tg[e]['start'],ate[e],base[e],c,first))
print(name,'search flights',len(rows))
for k in KEYS:
    fl=[r for r in rows if r[4][k]>0]
    if not fl: print(f'{k:10s} fires on 0 flights'); continue
    st=sum(r[1]=='static' for r in fl); b5=sum(r[3]>5 for r in fl)
    print(f'{k:10s} fires on {len(fl):3d} flights ({st} static, {len(fl)-st} mid; {b5} of them baseline>5m); total trips {sum(r[4][k] for r in fl)}; mean baseline ATE of firing flights {np.mean([r[3] for r in fl]):.2f} vs all {np.mean([r[3] for r in rows]):.2f}')
bad=[r for r in rows if r[3]>5]
print('baseline>5m flights:',len(bad),' with any trip:',sum(any(r[4][k]>0 for k in KEYS) for r in bad))
if len(sys.argv)>2:
    for r in sorted(rows,key=lambda r:-r[3])[:int(sys.argv[2])]:
        print(r[0],r[1],f'base {r[3]:.1f} new {r[2]:.1f}',{k:v for k,v in r[4].items() if v},{k:v for k,v in r[5].items()})
