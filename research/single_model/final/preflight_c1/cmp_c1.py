import json,glob,hashlib,sys,numpy as np
sys.path.insert(0,'.')
from research.single_model.run_variant import tags,fold,slice_of
R='research/results/single_model/'
def L(n):
    d=json.load(open(glob.glob(R+n+'/eval/*/scores.json')[0])); return d,{r['episode']:r for r in d['rows']},glob.glob(R+n+'/eval/*/')[0]
da,A,fa=L('preflight_c1_a');db,B,fb=L('preflight_c1_b');di,I,fi=L('inv_adopted');dg,G,fg=L('inv_gbase_r0')
_,GS,_=L('preflight_gate_a');dd,Dg,fd=L('preflight_c1_dbg')
print('G reference inv_gbase_r0 vs submitted-gate preflight_gate_a ate_full identical:',sum(G[e]['ate_full']==GS[e]['ate_full'] for e in G),'/171')
print('n',len(A),len(B),len(I),len(G),'sha a/b/inv',da['guest']['sha256'][:12],db['guest']['sha256'][:12],di['guest']['sha256'][:12],'G-run sha',dg['guest']['sha256'][:12])
def tum(f,e): return glob.glob(f+e+'/report/logs/*/estimate.tum')[0]
def sh(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
print('estimate.tum identical a vs b:',sum(sh(tum(fa,e))==sh(tum(fb,e)) for e in A),'/',len(A))
print('estimate.tum identical a vs inventive run:',sum(sh(tum(fa,e))==sh(tum(fi,e)) for e in A),'/',len(A))
print('ate_full a==b',sum(A[e]['ate_full']==B[e]['ate_full'] for e in A),' a==inventive',sum(A[e]['ate_full']==I[e]['ate_full'] for e in A),'maxdiff a-inv',max(abs(A[e]['ate_full']-I[e]['ate_full']) for e in A))
# dbg build must equal a except last row first 3 numbers
nd=0
for e in A:
    ra=[l.split() for l in open(tum(fa,e)).read().splitlines() if not l.startswith('#')]; rd=[l.split() for l in open(tum(fd,e)).read().splitlines() if not l.startswith('#')]
    nd+= len(ra)==len(rd) and all(x[0]==y[0] and x[4:]==y[4:] for x,y in zip(ra,rd))
print('dbg build rows identical to a except last-row xyz:',nd,'/',len(A))
for n,D in (('a',A),('b',B),('G(inv_gbase_r0)',G)):
    print(n,'filled_full!=0',[e for e,r in D.items() if r['filled_full']],'incomplete',[e for e,r in D.items() if not r['completed']],'failure',[e for e,r in D.items() if r['failure']],'err',[e for e,r in D.items() if 'error' in r],'frames',set(r['frames'] for r in D.values()),set(r['frames_attempted'] for r in D.values()))
    pk=[r['peak_fuel_per_frame'] for r in D.values()];p95=[r['p95_fuel_per_frame'] for r in D.values()]
    print(' peak %.3fM (%.4f%% of 2e10) worst p95 %.3fM median p95 %.3fM mean p95 %.3fM  worst-peak flight %s'%(max(pk)/1e6,100*max(pk)/2e10,max(p95)/1e6,np.median(p95)/1e6,np.mean(p95)/1e6,max(D,key=lambda e:D[e]['peak_fuel_per_frame'])))
    print(' per-flight mean fuel p95 sum',np.mean([r['p95_fuel_per_frame'] for r in D.values()]))
dp=[A[e]['p95_fuel_per_frame']-G[e]['p95_fuel_per_frame'] for e in A]; dk=[A[e]['peak_fuel_per_frame']-G[e]['peak_fuel_per_frame'] for e in A]
print('C1-G per-flight p95 fuel delta: mean %.0f median %.0f max %.0f ; peak delta mean %.0f max %.0f min %.0f'%(np.mean(dp),np.median(dp),max(dp),np.mean(dk),max(dk),min(dk)))
tg=tags(); rows=[]
for e in sorted(A):
    t=tg[e]; rows.append((e,t['start'],fold(t),G[e]['ate_full'],A[e]['ate_full']))
for sl in('search','val'):
  for st in('static','mid'):
    s=[r for r in rows if slice_of(r[2])==sl and r[1]==st];print(sl,st,len(s),'G %.3f C1 %.3f'%(np.mean([r[3] for r in s]),np.mean([r[4] for r in s])))
n4=0
print('flights differing from G by >0.3 m (fold4 ids/values hidden, counted only):')
for r in rows:
    if abs(r[4]-r[3])>0.3 and r[2]==4: n4+=1
    elif abs(r[4]-r[3])>0.3: print('  %s %s fold%d G %.3f C1 %.3f d %+.3f'%(r[0],r[1],r[2],r[3],r[4],r[4]-r[3]))
print('  fold-4 flights differing >0.3 m:',n4)
print('bit-identical to G (static):',sum(r[3]==r[4] for r in rows if r[1]=='static'),'/',sum(r[1]=='static' for r in rows),' mid:',sum(r[3]==r[4] for r in rows if r[1]=='mid'),'/',sum(r[1]=='mid' for r in rows))
json.dump(dict(rows=[r for r in rows if r[2]!=4]),open('research/single_model/final/preflight_c1/vs_G.json','w'))
