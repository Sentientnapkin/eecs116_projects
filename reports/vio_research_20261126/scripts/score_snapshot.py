"""Exact scoring arithmetic against a saved frontier; no server access or inference.
Run from repository root with venv-teacher/bin/python.
"""
import csv
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
snap = json.loads((ROOT / 'eecs116_vio/stage3/comparison.json').read_text())
X, Y = snap['fuel_reference'], snap['error_reference']
B = [(p['fuel_per_frame_max'], p['ate_rmse_mean']) for p in snap['points'] if p['is_baseline']]

def area(points):
    previous, best, total = 0., math.log(Y / .001), 0.
    xmax, ymax = math.log(X), best
    for x, y in sorted((math.log(max(f, 1)), math.log(max(a, .001)/.001))
                       for f, a in points if 0 <= f < X and 0 <= a < Y):
        if y >= best:
            continue
        total += (x-previous)*(ymax-best)
        previous, best = x, y
    return total + (xmax-previous)*(ymax-best)

BA = area(B)
DEN = math.log(X)*math.log(Y/.001)
def score(f, a):
    return 100*max(0, area(B+[(f,a)])-BA)/DEN

rows=[]
for f in [1e6,5e6,10e6,25e6,100e6,500e6,1e9]:
    for a in [.05,.1,.15,.25,.5,.665,1.]:
        rows.append(dict(peak_fuel=int(f),ate_m=a,score_percent=score(f,a)))
with (OUT/'data/score_grid.csv').open('w') as h:
    w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
named={n:dict(fuel=f,ate=a,score_percent=score(f,a)) for n,f,a in [
    ('A hypothetical',1e6,.5),('C hypothetical',100e6,.15),('D hypothetical',1e9,.05),
    ('Recorded server approximate',4.1e6,.586),('Saved GSLV exact',4393770,1.1782347562680695)]}
combined=100*(area(B+[(1e6,.5),(100e6,.15),(1e9,.05)])-BA)/DEN
(OUT/'data/score_snapshot.json').write_text(json.dumps(dict(
    source='eecs116_vio/stage3/comparison.json',fuel_reference=X,error_reference=Y,
    baseline_area=BA,named=named,union_area_hypothetical_percent=combined,
    actual_team_credit_if_all_targets_achieved=max(x['score_percent'] for n,x in named.items() if 'hypothetical' in n)),indent=2))

fig,ax=plt.subplots(figsize=(9,5.5))
fs=np.geomspace(1e5,2e9,180)
for a in [.05,.1,.15,.25,.5,1.]:
    ax.plot(fs/1e6,[score(f,a) for f in fs],label=f'{a:g} m ATE')
for n in ['A hypothetical','C hypothetical','D hypothetical']:
    d=named[n];ax.scatter(d['fuel']/1e6,d['score_percent'],s=60,color='black');ax.annotate(n,(d['fuel']/1e6,d['score_percent']),xytext=(6,7),textcoords='offset points',fontsize=8)
ax.set(xscale='log',xlabel='Peak WASM fuel per frame (millions)',ylabel='Single-submission score (%)',title='Hypothetical scores against saved stage-3 baseline frontier')
ax.legend(ncol=2);ax.grid(alpha=.25);fig.tight_layout();fig.savefig(OUT/'figures/score_curves.png',dpi=170);plt.close(fig)
print(json.dumps(named,indent=2));print('Hypothetical combined frontier area',combined,'but team receives best single only')
