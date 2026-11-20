import json,glob,numpy as np,sys,random
sys.path.insert(0,'.')
from research.single_model.b6fix.mech import parse
B='research/single_model/b6fix/'
bad=set(open(B+'bad_fresh.txt').read().split(','))
tab={r['episode']:r['ate'] for r in json.load(open('research/single_model/fresh/table_b6f_diag.json'))}
random.seed(1)
eps=sorted(tab); good=[e for e in eps if e not in bad]; sample=random.sample(good,60)
def st(e):
    f=glob.glob(f'research/results/single_model/fresh_b6f_diag/eval/*/{e}/report/logs/*/stderr.txt')[0]
    rows=parse(f); used=np.array([r['used'] for r in rows]); live3=np.array([r['live3'] for r in rows])
    s20=np.convolve(used,np.ones(20),'full')[:len(used)]
    m=(np.arange(len(used))>=20)
    return dict(zero20=float(((s20==0)&m&(live3>=8)).mean()), zero20_any=float(((s20==0)&m).mean()), first=int(np.argmax(used>0)), live3=float(live3.mean()), used=float(used.mean()))
for nm,L in (('bad',sorted(bad)),('good',sample)):
    R=[st(e) for e in L]
    print(nm,{k:round(float(np.mean([r[k] for r in R])),3) for k in R[0]}, 'med zero20',np.median([r['zero20'] for r in R]),'p90',np.percentile([r['zero20'] for r in R],90))
