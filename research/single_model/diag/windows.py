import sys, json
sys.path.insert(0,'/data/backups/rganapa/Sebastian/eecs116_projects')
import numpy as np
from pathlib import Path
from research.single_model.diag import analyze as A
folder=next((Path('research/results/single_model/diag_counters1/eval')).glob('diag_counters1-*'))
rows=json.load(open('research/results/single_model/diag_counters1/diag_table.json'))
out={}
for r in rows:
    log=next((folder/r['ep']/'report/logs').glob('*/stderr.txt'))
    d0,rs=A.parse(log)
    w={}
    for a,b in ((0,20),(20,40),(40,60),(60,100),(100,200)):
        seg=rs[a:b]
        w[f'used_{a}_{b}']=sum(x['used'] for x in seg); w[f'att_{a}_{b}']=sum(x['att'] for x in seg)
        w[f'tri_{a}_{b}']=sum(x['trifail'] for x in seg); w[f'gate_{a}_{b}']=sum(x['gaterej'] for x in seg)
        w[f'live3_{a}_{b}']=float(np.mean([x['live3'] for x in seg]))
    # speed estimate and cov trace over time
    for fr in (10,20,30,40,60,100):
        x=rs[fr-1]; w[f'spd_{fr}']=float(np.linalg.norm(x['v'])); w[f'Pv_{fr}']=float(np.sqrt(sum(x['Pv'])))
        w[f'Pth_{fr}']=float(np.sqrt(x['Pth'][0]+x['Pth'][1]))
    out[r['ep']]=w
json.dump(out,open('research/results/single_model/diag_counters1/windows.json','w'))
