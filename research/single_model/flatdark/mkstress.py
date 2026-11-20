import json,glob,hashlib,sys,os,numpy as np
sys.path.insert(0,'.')
from research.single_model.b6fix.mech import parse
M='research/single_model/matrix/store/'
S={b:json.load(open(M+b+'.json')) for b in ('B0','B2','B7')}
B='/data/backups/rganapa/Sebastian/gen/raw-fast/bench/'
def fold(cat,scene): return int(hashlib.sha256(f'{cat}:{scene}'.encode()).hexdigest()[:8],16)%5
rows=[]
for setn,key,run in (('sel','sel','b6f_diag'),('fresh','fresh','fresh_b6f_diag')):
    for ep,ate7 in S['B7'][key].items():
        ate7=ate7 if not isinstance(ate7,dict) else ate7.get('ate')
        sc=json.load(open(B+ep+'.json'))
        f=fold(sc['catalog'],sc['scene'])
        if setn=='sel' and f==4: continue
        g=glob.glob(f'research/results/single_model/{run}/eval/*/{ep}/report/logs/*/stderr.txt')
        live=live3=used=None
        if g:
            r=parse(g[0]); live=float(np.median([x['live'] for x in r])); live3=float(np.median([x['live3'] for x in r])); used=float(np.mean([x['used'] for x in r]))
        a=sc['audit']
        def get(b):
            v=S[b][key].get(ep); return v if not isinstance(v,dict) else v.get('ate')
        rows.append(dict(ep=ep,set=setn,catalog=sc['catalog'],scene=sc['scene'],fold=f,flat=a['flat_fraction'],dark=a['dark_fraction'],flags=a['flags'],
          travel=a['travel_m'],live=live,live3=live3,used=used,B7=ate7,G=get('B2'),B0=get('B0')))
json.dump(rows,open('research/single_model/flatdark/stress_all.json','w'))
print(len(rows))
