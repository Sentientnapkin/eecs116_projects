import json,glob,hashlib,sys,numpy as np,math,re,collections
sys.path.insert(0,'.')
from research.single_model.run_variant import tags,fold,slice_of
R='research/results/single_model/'
def L(n):
    d=json.load(open(glob.glob(R+n+'/eval/*/scores.json')[0])); return d,{r['episode']:r for r in d['rows']},glob.glob(R+n+'/eval/*/')[0]
da,A,fa=L('preflight_c1_fbh_exact_a');db,B,fb=L('preflight_c1_fbh_exact_b');d6,S,f6=L('preflight_c1_fbh_a');dm,M,fm=L('mx_B7')
print('sha a/b/B6/mx_B7',[x['guest']['sha256'][:12] for x in (da,db,d6,dm)],'n',len(A),len(S))
def lg(f,e,n): return glob.glob(f+e+'/report/logs/*/'+n)[0]
def sh(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
print('determinism a vs b: estimate.tum identical',sum(sh(lg(fa,e,'estimate.tum'))==sh(lg(fb,e,'estimate.tum')) for e in A),'/',len(A),' ate_full equal',sum(A[e]['ate_full']==B[e]['ate_full'] for e in A),' fuel.npy equal',sum(sh(lg(fa,e,'fuel.npy'))==sh(lg(fb,e,'fuel.npy')) for e in A))
print('B7 vs B6 estimate.tum byte-identical',sum(sh(lg(fa,e,'estimate.tum'))==sh(lg(f6,e,'estimate.tum')) for e in A if e in S),'/',len(A),' twist.txt identical',sum(sh(lg(fa,e,'twist.txt'))==sh(lg(f6,e,'twist.txt')) for e in A),' ate_full equal',sum(A[e]['ate_full']==S[e]['ate_full'] for e in A))
print('B7 vs mx_B7 matrix run estimate.tum identical',sum(sh(lg(fa,e,'estimate.tum'))==sh(lg(fm,e,'estimate.tum')) for e in A if e in M),'/',len(A))
nonfin=[]
for e in A:
    for l in open(lg(fa,e,'estimate.tum')):
        if l.startswith('#'): continue
        if not all(math.isfinite(float(x)) for x in l.split()): nonfin.append(e);break
    for p in glob.glob(fa+e+'/report/logs/*/stderr*')+glob.glob(fa+e+'/report/logs/*/stdout*')+glob.glob(fa+e+'/evaluate.log'):
        if re.search(r'\bnan\b|\binf\b',open(p,errors='replace').read(),re.I): nonfin.append(('txt',e,p))
    for l in open(lg(fa,e,'twist.txt')):
        if l.startswith('#'): continue
        if not all(math.isfinite(float(x)) for x in l.split()): nonfin.append(('twist',e));break
print('non-finite in estimate.tum/twist/stderr/stdout/evaluate.log:',nonfin)
for n,D in (('B7',A),('B7b',B),('B6',S)):
    print(n,'filled_full!=0',[e for e,r in D.items() if r['filled_full']],'incomplete',[e for e,r in D.items() if not r['completed']],'failure',[e for e,r in D.items() if r['failure']],'frames',set(r['frames'] for r in D.values()),set(r['frames_attempted'] for r in D.values()))
    pk=[r['peak_fuel_per_frame'] for r in D.values()];p95=[r['p95_fuel_per_frame'] for r in D.values()]
    print(' peak %.3fM (%.4f%% of 2e10) worst p95 %.3fM median p95 %.3fM mean p95 %.3fM median-of-medians %.3fM median-of-peaks %.3fM'%(max(pk)/1e6,100*max(pk)/2e10,max(p95)/1e6,np.median(p95)/1e6,np.mean(p95)/1e6,np.median([r['median_fuel_per_frame'] for r in D.values()])/1e6,np.median(pk)/1e6))
ph=collections.Counter();allmax=(0,None,None);fr=collections.Counter()
for e in A:
    f=np.load(lg(fa,e,'fuel.npy')).astype(float); i=int(np.argmax(f)); ph[i]+=1
    if f.max()>allmax[0]: allmax=(f.max(),e,i)
print('fuel.npy len',set(len(np.load(lg(fa,e,'fuel.npy'))) for e in A))
print('global max fuel %.3fM flight %s frame %d'%(allmax[0]/1e6,allmax[1],allmax[2]))
print('argmax frame histogram (top 12 frames):',ph.most_common(12)); print('argmax frame range',min(ph),max(ph),'; fraction of flights with argmax <=60:',sum(v for k,v in ph.items() if k<=60)/len(A))
f0=[np.load(lg(fa,e,'fuel.npy'))[0]/1e6 for e in A];print('frame0 fuel mean %.2fM max %.2fM'%(np.mean(f0),max(f0)))
