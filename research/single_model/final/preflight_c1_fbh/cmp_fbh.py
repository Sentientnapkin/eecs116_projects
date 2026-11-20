import json,glob,hashlib,sys,numpy as np,math,re
sys.path.insert(0,'.')
from research.single_model.run_variant import tags,fold,slice_of
R='research/results/single_model/'
def L(n):
    d=json.load(open(glob.glob(R+n+'/eval/*/scores.json')[0])); return d,{r['episode']:r for r in d['rows']},glob.glob(R+n+'/eval/*/')[0]
da,A,fa=L('preflight_c1_fbh_a');db,B,fb=L('preflight_c1_fbh_b');di,I,fi=L('inv_adopted');df,F,ff=L('fe2_fbh_r0')
print('sha a/b/c1/fe2_fbh_r0',[x['guest']['sha256'][:12] for x in (da,db,di,df)])
def tum(f,e): return glob.glob(f+e+'/report/logs/*/estimate.tum')[0]
def sh(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
print('estimate.tum identical a vs b:',sum(sh(tum(fa,e))==sh(tum(fb,e)) for e in A),'/',len(A))
print('ate_full a==b',sum(A[e]['ate_full']==B[e]['ate_full'] for e in A))
print('estimate.tum identical a vs fe2_fbh_r0 (frontend run):',sum(sh(tum(fa,e))==sh(tum(ff,e)) for e in A),'/',len(A),' ate_full equal',sum(A[e]['ate_full']==F[e]['ate_full'] for e in A),'maxdiff',max(abs(A[e]['ate_full']-F[e]['ate_full']) for e in A))
nonfin=[]
for e in A:
    for l in open(tum(fa,e)):
        if l.startswith('#'): continue
        if not all(math.isfinite(float(x)) for x in l.split()): nonfin.append(e);break
    s=glob.glob(fa+e+'/report/logs/*/stderr*')+glob.glob(fa+e+'/evaluate.log')
    for p in s:
        if re.search(r'\bnan\b|\binf\b',open(p,errors='replace').read(),re.I): nonfin.append(('stderr',e,p))
print('non-finite in estimate.tum/stderr/evaluate.log:',nonfin)
for n,D in (('a',A),('b',B),('C1',I)):
    print(n,'filled_full!=0',[e for e,r in D.items() if r['filled_full']],'incomplete',[e for e,r in D.items() if not r['completed']],'failure',[e for e,r in D.items() if r['failure']],'err',[e for e,r in D.items() if 'error' in r],'frames',set(r['frames'] for r in D.values()),set(r['frames_attempted'] for r in D.values()))
    pk=[r['peak_fuel_per_frame'] for r in D.values()];p95=[r['p95_fuel_per_frame'] for r in D.values()]
    print(' peak %.3fM (%.4f%% of 2e10) worst p95 %.3fM median p95 %.3fM mean p95 %.3fM'%(max(pk)/1e6,100*max(pk)/2e10,max(p95)/1e6,np.median(p95)/1e6,np.mean(p95)/1e6), 'median-of-median',np.median([r.get('median_fuel_per_frame',np.nan) for r in D.values()]))
dp=[A[e]['p95_fuel_per_frame']-I[e]['p95_fuel_per_frame'] for e in A]
print('FB-C1 per-flight p95 delta mean %.0f median %.0f max %.0f'%(np.mean(dp),np.median(dp),max(dp)))
tg=tags(); rows=[(e,tg[e]['start'],fold(tg[e]),tg[e]['scene'],I[e]['ate_full'],A[e]['ate_full']) for e in sorted(A)]
for sl in('search','val'):
  for st in('static','mid'):
    s=[r for r in rows if slice_of(r[2])==sl and r[1]==st];print(sl,st,len(s),'C1 %.3f FB %.3f'%(np.mean([r[4] for r in s]),np.mean([r[5] for r in s])))
s=[r for r in rows if slice_of(r[2])=='search'];print('search all',len(s),'C1 %.3f FB %.3f'%(np.mean([r[4] for r in s]),np.mean([r[5] for r in s])))
n4=0;print('flights differing from C1 by >0.5 m (folds 0-3):')
for r in rows:
    if abs(r[5]-r[4])>0.5 and r[2]==4: n4+=1
    elif abs(r[5]-r[4])>0.5: print('  %s %s fold%d C1 %.3f FB %.3f d %+.3f'%(r[0],r[1],r[2],r[4],r[5],r[5]-r[4]))
print('  fold-4 differing >0.5 m (count only):',n4)
