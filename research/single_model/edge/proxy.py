"""Proxy-set draws with arms. ATE sources: existing 5 candidates from sig.json (non-fold-4 pool); arms: sel from results/single_model/edge_*/eval/*/scores.json, fresh from ftable_*.json. Fold 4 dropped everywhere."""
import json, sys, glob, numpy as np
from pathlib import Path
E=Path('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/edge/'); R=E.parents[1]/'results/single_model'
s=json.load(open(E/'sig.json')); a=json.load(open(E/'audit.json')); f=json.load(open(E/'flightstats.json'))
arms=[x for x in sys.argv[1:]]
eps=[e for e in s if all(c in s[e] for c in ('base','f0','G','T','M'))]
A={c:np.array([s[e][c]['ate_rmse'] for e in eps]) for c in ('base','f0','G','T','M')}
for arm in arms:
    sel={}
    for p in glob.glob(str(R/arm/'eval/*/scores.json')):
        for r in json.load(open(p))['rows']: sel[r['episode']]=r.get('ate_full')
    fr=json.load(open(E/f'ftable_{arm}.json')) if (E/f'ftable_{arm}.json').exists() else {}
    A[arm]=np.array([sel.get(e) if a[e]['pool']=='sel' else fr.get(e) for e in eps],float)
    if np.isnan(A[arm]).any(): print('missing',arm,np.isnan(A[arm]).sum())
REP={'G3':('G','edge_g_r1','edge_g_r2'),'vb3':('edge_vb','edge_vb_r1','edge_vb_r2'),'cmbx3':('edge_cmbx','edge_cmbx_r1','edge_cmbx_r2')}
for k,v in REP.items():
    if all(x in A for x in v): A[k]=np.mean([A[x] for x in v],0)
C=list(A)
trav=np.array([a[e]['travel'] for e in eps]); mid=np.array([a[e]['start']=='mid' for e in eps]); pool=np.array([a[e]['pool'] for e in eps])
sd=np.array([72.70,56.89,80.38,48.19,58.52,39.49,63.23,59.53,58.93,61.71,74.03,41.54])
out=[]; P=lambda *x: out.append(' '.join(str(i) for i in x))
P('## Whole pool (non-fold-4, n=%d: sel %d, fresh %d)'%(len(eps),(pool=='sel').sum(),(pool=='fresh').sum()))
P('| cand | mean all | static | mid | >3 | >5 | >10 | fresh mean | sel mean |'); P('|--|--|--|--|--|--|--|--|--|')
for c in C:
    x=A[c]; P('| %s | %.3f | %.3f | %.3f | %d | %d | %d | %.3f | %.3f |'%(c,np.nanmean(x),np.nanmean(x[~mid]),np.nanmean(x[mid]),(x>3).sum(),(x>5).sum(),(x>10).sum(),np.nanmean(x[pool=='fresh']),np.nanmean(x[pool=='sel'])))
# pairwise vs G on whole pool
P('\n## Paired vs G (all pool): arm-G mean diff [scene-bootstrap 95%], #flights worse>1.5, better>1.5')
sc=np.array([a[e]['catalog']+a[e]['scene'] for e in eps]); u,inv=np.unique(sc,return_inverse=True)
rng=np.random.default_rng(3)
for c in C:
    if c=='G': continue
    d=A[c]-A['G']; sm=np.bincount(inv,weights=d); k=np.bincount(inv); ix=rng.integers(0,len(u),(3000,len(u))); b=sm[ix].sum(1)/k[ix].sum(1)
    P('%-9s %+.3f [%+.3f,%+.3f]  worse %d better %d'%(c,d.mean(),*np.percentile(b,[2.5,97.5]),(d>1.5).sum(),(d<-1.5).sum()))
K=60; idx=[np.argsort(np.abs(trav-d))[:K] for d in sd]
P('\nslot candidate sets: nearest %d flights by distance; max |dist error| per slot (m):'%K, np.round([np.abs(trav[i]-d).max() for i,d in zip(idx,sd)],1))
rng=np.random.default_rng(11); N=30000
def draw(pm):
    res=np.zeros((N,12),int)
    for j,i in enumerate(idx):
        im=i[mid[i]]; ist=i[~mid[i]]; ism=rng.random(N)<pm
        res[:,j]=np.where(ism,rng.choice(im,N),rng.choice(ist,N))
    return res
def table(title,r):
    P('\n### '+title+' (n=%d draws)'%len(r)); P('| cand | mean of 12-mean | p5 | p50 | p95 | P(12-mean>=1.244) | P(any >5) | P(>=2 >5) | mean ex-worst |'); P('|--|--|--|--|--|--|--|--|--|')
    for c in C:
        x=A[c][r]; m=x.mean(1); n5=(x>5).sum(1)
        P('| %s | %.3f | %.2f | %.2f | %.2f | %.2f | %.2f | %.2f | %.3f |'%(c,m.mean(),*np.percentile(m,[5,50,95]),(m>=1.244).mean(),(n5>=1).mean(),(n5>=2).mean(),((x.sum(1)-x.max(1))/11).mean()))
for pm in (0.0,0.5,1.0):
    r=draw(pm); table('p_mid=%.1f'%pm,r)
    if pm==0.5:
        mb=A['base'][r].mean(1); m=np.abs(mb-3.226)<0.6; table('ABC: base 12-mean within 3.226+-0.6, p_mid 0.5',r[m])
        m=m&((A['base'][r]>5).sum(1)>=3); table('ABC + >=3 base episodes >5 m',r[m])
open(E/'proxy_out.md','w').write('\n'.join(out)); print('\n'.join(out))

# posterior of the mid-start share from the old-gp_msckf aggregate (ABC): accept draws with >=3 base eps >5 m and base 12-mean in 3.226+-0.6
out2=['\n## ABC likelihood of server base aggregate (>=3 base eps >5 m AND 12-mean 3.226+-0.6) vs share of mid starts']
lik=[]
for pm in np.linspace(0,1,11):
    r=draw(pm); xb=A['base'][r]; ok=((xb>5).sum(1)>=3)&(np.abs(xb.mean(1)-3.226)<0.6); lik.append(ok.mean())
    out2.append('p_mid %.1f  P(accept)=%.4f   P(>=3 base eps>5)=%.4f'%(pm,ok.mean(),((xb>5).sum(1)>=3).mean()))
lik=np.array(lik); post=lik/lik.sum()
out2.append('posterior (uniform prior) over p_mid grid: '+' '.join('%.1f:%.2f'%(p,q) for p,q in zip(np.linspace(0,1,11),post))+'  posterior mean %.2f'%(post*np.linspace(0,1,11)).sum())
open(E/'proxy_out.md','a').write('\n'.join(out2)); print('\n'.join(out2))

# replicate-averaged paired comparison vs G3 (3-replicate mean)
out3=['\n## Replicate-averaged (3 chaos replicates) paired vs G3, whole non-fold-4 pool: mean diff [scene-bootstrap 95%], flights worse/better by >1.0 m']
for c in ('vb3','cmbx3'):
    if c in A and 'G3' in A:
        d=A[c]-A['G3']; sm=np.bincount(inv,weights=d); k=np.bincount(inv); ix=np.random.default_rng(5).integers(0,len(u),(3000,len(u))); b=sm[ix].sum(1)/k[ix].sum(1)
        out3.append('%s vs G3: %+.3f [%+.3f,%+.3f]  worse %d better %d | mid-only %+.3f | per-replicate >5 counts: %s'%(c,d.mean(),*np.percentile(b,[2.5,97.5]),(d>1).sum(),(d<-1).sum(),d[mid].mean(),''))
for pref,reps in (('G',('G','edge_g_r1','edge_g_r2')),('vb',('edge_vb','edge_vb_r1','edge_vb_r2')),('cmbx',('edge_cmbx','edge_cmbx_r1','edge_cmbx_r2'))):
    out3.append('%s replicates: pool mean %s; >5 counts %s; >10 counts %s'%(pref,[round(float(np.nanmean(A[x])),3) for x in reps],[int((A[x]>5).sum()) for x in reps],[int((A[x]>10).sum()) for x in reps]))
open(E/'proxy_out.md','a').write('\n'.join(out3)); print('\n'.join(out3))
