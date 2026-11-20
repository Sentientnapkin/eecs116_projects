import json,sys,os,numpy as np
sys.path.insert(0,'.')
from research.single_model.fresh import truth_feats as TF
B='research/single_model/b6fix/'
SEL='/data/backups/rganapa/Sebastian/gen/raw-fast/selected'
tf={r['episode']:r for r in json.load(open('research/single_model/fresh/truth_feats.json'))}
TF.POOL=SEL
tags=json.load(open('research/single_model/fresh/tags.json'))
rv={r['e']:r for r in json.load(open('research/results/single_model/b6f_diag/report.json'))['rows_visible']}
reg=json.load(open(B+'regimp.json'))['reg']
nofb={r['ep']:r['ate'] for r in json.load(open(B+'mech_reg_nofb.json'))}
def cls(r,f,start):
    sp=f['speed0'] if f['speed0'] is not None else 0; ang=f['angle'] or 0
    starved = r['live_med']<25
    on=r['onset'] if r['onset'] is not None else 99
    if r['live_med']<5: return 'textureless (tracks dead)'
    if starved: return 'starved coasting (low live tracks)'
    if on<6:
        if start=='mid' and ang>90 and sp>0.5: return 'startup wrong direction (>90 deg)'
        if sp>1.8: return 'startup fast (>1.8 m/s)'
        return 'startup lock-out (no accepted features, w_used<0.15)' if r['w_used']<0.15 else 'startup other (runaway, slow/ambiguous)'
    if r['rot_at_onset'] is not None and r['rot_at_onset']>8: return 'late tilt/attitude drift'
    return 'late scale/bias drift'
rows=[]
for nm,fn in (('fresh',B+'mech_fresh_bad.json'),('sel',B+'mech_sel_bad.json')):
    for r in json.load(open(fn)):
        ep=r['ep']
        if nm=='fresh': f=tf[ep]; start=tags[ep]['start']
        else:
            f=TF.one(ep) if ep.startswith(('fast','fastmid')) else None
            start='mid' if ep.startswith('fastmid') else 'static'
            if rv.get(ep): start=rv[ep]['start']
        c=cls(r,f,start)
        fbind = ep in reg and nofb.get(ep,9)<3 and nm=='fresh'
        rows.append(dict(set=nm,ep=ep,start=start,ate=r['ate'],cls=c,fb_induced=fbind,onset=r['onset'],sp0=f['speed0'],ang=f['angle'],live=r['live_med'],live3=r['w_live3']))
json.dump(rows,open(B+'mech_table.json','w'),indent=0)
from collections import Counter,defaultdict
for nm in ('fresh','sel'):
    c=Counter(r['cls'] for r in rows if r['set']==nm); a=defaultdict(float)
    for r in rows:
        if r['set']==nm: a[r['cls']]+=r['ate']
    print(nm,len([r for r in rows if r['set']==nm]),{k:(v,round(a[k]/v,2)) for k,v in c.items()},'FB-induced(noFB<3m):',sum(r['fb_induced'] for r in rows if r['set']==nm))
for r in rows: print(r['set'],r['ep'][-20:],r['start'][:3],round(r['ate'],2),r['cls'],'FBind' if r['fb_induced'] else '')
