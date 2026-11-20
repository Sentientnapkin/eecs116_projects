import json,glob,hashlib,sys,numpy as np
sys.path.insert(0,'.')
from research.single_model.run_variant import tags,fold,slice_of
R='research/results/single_model/'
def L(n): 
    d=json.load(open(glob.glob(R+n+'/eval/*/scores.json')[0])); return d,{r['episode']:r for r in d['rows']},glob.glob(R+n+'/eval/*/')[0]
da,A,fa=L('preflight_gate_a');db,B,fb=L('preflight_gate_b');dg,G,fg=L('gate_adopted');df,F,ff=L('final_f0')
print('n',len(A),len(B),len(G),len(F),'sha',da['guest']['sha256'],db['guest']['sha256'],dg['guest']['sha256'])
def sh(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
nd=0;bad=[];nmiss=0
for e in A:
    pa=glob.glob(fa+e+'/report/logs/*/estimate.tum');pb=glob.glob(fb+e+'/report/logs/*/estimate.tum')
    if not pa or not pb: nmiss+=1;continue
    if sh(pa[0])==sh(pb[0]): nd+=1
    else: bad.append(e)
print('estimate.tum identical a vs b:',nd,'/',len(A),'missing',nmiss,'bad',bad)
print('ate_full a==b bit-identical',sum(A[e]['ate_full']==B[e]['ate_full'] for e in A),' a==gate agent',sum(A[e]['ate_full']==G[e]['ate_full'] for e in A),'maxdiff',max(abs(A[e]['ate_full']-G[e]['ate_full']) for e in A))
# gate agent estimate.tum equality
ng=sum(1 for e in A if glob.glob(fa+e+'/report/logs/*/estimate.tum') and sh(glob.glob(fa+e+'/report/logs/*/estimate.tum')[0])==sh(glob.glob(fg+e+'/report/logs/*/estimate.tum')[0]))
print('estimate.tum identical a vs gate agent',ng)
for n,D in (('a',A),('b',B)):
    print(n,'filled_full!=0',[e for e,r in D.items() if r['filled_full']],'incomplete',[e for e,r in D.items() if not r['completed']],'failure',[e for e,r in D.items() if r['failure']],'err',[e for e,r in D.items() if 'error' in r],'frames',set(r['frames'] for r in D.values()),set(r['frames_attempted'] for r in D.values()))
    pk=[r['peak_fuel_per_frame'] for r in D.values()];p95=[r['p95_fuel_per_frame'] for r in D.values()]
    print(' peak',max(pk),'worst p95',max(p95),'frac',max(pk)/2e10,'worst',max(D,key=lambda e:D[e]['peak_fuel_per_frame']),'median p95',np.median(p95))
for n,D in (('f0',F),('base',json.load(open(glob.glob('research/results/loop/gp-msckf-pool/gp_msckf-c7413a81/scores.json')[0]))['rows'])):
    if n=='base': D={r['episode']:r for r in D}
    pk=[r.get('peak_fuel_per_frame') for r in D.values() if r.get('peak_fuel_per_frame')];p95=[r['p95_fuel_per_frame'] for r in D.values() if r.get('p95_fuel_per_frame')]
    print(n,'peak',max(pk),'worst p95',max(p95))
tg=tags()
print('vs f0 per-flight |diff|>0.1:')
rows=[]
for e in sorted(A):
    d=A[e]['ate_full']-F[e]['ate_full']
    t=tg[e];rows.append((e,t['start'],fold(t),F[e]['ate_full'],A[e]['ate_full'],d))
big=[r for r in rows if abs(r[5])>0.1 and r[2]!=4]
nbig4=sum(1 for r in rows if abs(r[5])>0.1 and r[2]==4)
print(' differ>0.1 (all):',sum(abs(r[5])>0.1 for r in rows),'of 171; of which fold4 (ids hidden):',nbig4)
for r in big: print('  %s %s fold%d f0 %.3f gate %.3f d %+.3f'%r)
print(' bit-identical to f0:',sum(r[5]==0 for r in rows),'static:',sum(r[5]==0 for r in rows if r[1]=='static'),'/',sum(r[1]=='static' for r in rows))
for sl in('search','val'):
  for st in('static','mid'):
    s=[r for r in rows if slice_of(r[2])==sl and r[1]==st];print(sl,st,len(s),'f0 %.3f gate %.3f'%(np.mean([r[3] for r in s]),np.mean([r[4] for r in s])))
json.dump(dict(rows=rows),open('research/single_model/final/preflight_gate/vs_f0.json','w'))
