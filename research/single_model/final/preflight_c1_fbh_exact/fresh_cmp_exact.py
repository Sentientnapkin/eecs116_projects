import json,numpy as np
d='research/single_model/fresh/'
L=lambda p:{r['episode']:r for r in json.load(open(d+p))}
me=L('table_pfbx_fresh.json'); b6=L('table_pfbh_fresh.json'); k=sorted(me)
print('n',len(k),'mean %.6f B6 %.6f'%(np.mean([me[e]['ate'] for e in k]),np.mean([b6[e]['ate'] for e in k])))
print('ate identical to B6 table:',sum(me[e]['ate']==b6[e]['ate'] for e in k),'/',len(k))
print('completed all',all(me[e]['completed'] for e in k),'filled nonzero',[e for e in k if me[e]['filled']],'errors',[e for e in k if me[e]['error']],'nonfinite ate',[e for e in k if not np.isfinite(me[e]['ate'])])
for nm,t in(('B7',me),('B6',b6)):
    pk=np.array([t[e]['peak_fuel'] for e in k])/1e6;print(nm,'fresh peak %.2fM median-of-peaks %.2f p95-of-peaks %.2f'%(pk.max(),np.median(pk),np.percentile(pk,95)),[c for c in t[k[0]]][:20])
