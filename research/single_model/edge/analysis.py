import json, numpy as np, sys
E='research/single_model/edge/'
s=json.load(open(E+'sig.json')); a=json.load(open(E+'audit.json')); f=json.load(open(E+'flightstats.json'))
C=['base','f0','G','T','M']
eps=[e for e in s if all(c in s[e] for c in C)]
A={c:np.array([s[e][c]['ate_rmse'] for e in eps]) for c in C}
trav=np.array([a[e]['travel'] for e in eps]); mid=np.array([a[e]['start']=='mid' for e in eps]); pool=np.array([a[e]['pool'] for e in eps])
zm=np.array([a[e]['zm'] for e in eps])
out=[]; P=lambda *x: out.append(' '.join(str(i) for i in x))
P('n flights',len(eps),'sel',(pool=='sel').sum(),'fresh',(pool=='fresh').sum())
for c in C: P(c,'mean %.3f >3 %d >5 %d >10 %d'%(A[c].mean(),(A[c]>3).sum(),(A[c]>5).sum(),(A[c]>10).sum()))
# server aggregates
sd=np.array([72.70,56.89,80.38,48.19,58.52,39.49,63.23,59.53,58.93,61.71,74.03,41.54])
sbase=np.array([2.94,.272,2.74,.271,.723,11.3,7.97,1.57,8.68,.585,.918,.742]); sG=np.array([1.24,.288,.73,.121,.973,.307,.299,.407,1.09,.291,7.70,1.48])
P('server: dist mean %.1f; base mean %.3f median %.3f; G mean %.3f median %.3f; G w/o e7aa %.3f; base w/o e7aa %.3f'%(sd.mean(),sbase.mean(),np.median(sbase),sG.mean(),np.median(sG),np.delete(sG,10).mean(),np.delete(sbase,10).mean()))
P('server: corr(dist, G ate) %.2f corr(dist, base ate) %.2f; base>5 count %d; G>5 count %d; tails of base fixed by G: 3'%(np.corrcoef(sd,sG)[0,1],np.corrcoef(sd,sbase)[0,1],(sbase>5).sum(),(sG>5).sum()))
P('pool: corr(travel, G ate) %.2f; base %.2f'%(np.corrcoef(trav,A['G'])[0,1],np.corrcoef(trav,A['base'])[0,1]))
# travel bins vs ate
for lo,hi in ((0,40),(40,50),(50,60),(60,70),(70,200)):
    m=(trav>=lo)&(trav<hi); P('travel[%d,%d) n=%d base %.2f G %.2f T %.2f >5G %.1f%% mid%% %.0f'%(lo,hi,m.sum(),A['base'][m].mean(),A['G'][m].mean(),A['T'][m].mean(),100*(A['G'][m]>5).mean(),100*mid[m].mean()))
# bootstrap draws
rng=np.random.default_rng(7)
N=40000; K=40
idx=[]
for d in sd:
    o=np.argsort(np.abs(trav-d))
    idx.append(o[:K*3])   # nearest 120 flights by distance
P('slot candidate set: nearest 120 flights per slot; max |dist err| per slot', np.round([np.abs(trav[i]-d).max() for i,d in zip(idx,sd)],1))
def draw(pmid, N=N):
    res=np.zeros((N,12),int)
    for j,i in enumerate(idx):
        im=i[mid[i]]; ist=i[~mid[i]]
        ismid=rng.random(N)<pmid
        res[:,j]=np.where(ismid, rng.choice(im,N), rng.choice(ist,N))
    return res
def summarize(name,res,mask=None):
    if mask is None: mask=np.ones(len(res),bool)
    r=res[mask]; P('\n### draws:',name,'n=%d'%len(r))
    P('| cand | mean of 12-mean | p5 | p50 | p95 | P(mean>=1.244) | P(any ep >5) | P(>=2 eps >5) | mean #>5 | mean ex-worst |'); P('|--|--|--|--|--|--|--|--|--|--|')
    for c in C:
        x=A[c][r]; m=x.mean(1); n5=(x>5).sum(1)
        P('| %s | %.3f | %.2f | %.2f | %.2f | %.2f | %.2f | %.2f | %.2f | %.3f |'%(c,m.mean(),*np.percentile(m,[5,50,95]),(m>=1.244).mean(),(n5>=1).mean(),(n5>=2).mean(),n5.mean(),((x.sum(1)-x.max(1))/11).mean()))
    return r
R={}
for pm in (0.0,0.5,1.0):
    R[pm]=draw(pm); summarize('p_mid=%.1f'%pm,R[pm])
# ABC conditioning on server base mean 3.22 (+-0.6) at p_mid 0.5 and 1.0
for pm in (0.5,1.0):
    r=R[pm]; mb=A['base'][r].mean(1); m=np.abs(mb-sbase.mean())<0.6
    summarize('ABC base mean in 3.22+-0.6, p_mid=%.1f'%pm,r,m)
    # + at least 3 base eps >5
    nb=(A['base'][r]>5).sum(1); m2=m&(nb>=3)
    summarize('ABC base mean in 3.22+-0.6 and >=3 base eps >5 m, p_mid=%.1f'%pm,r,m2)
# where does server G=1.244 land
for pm in (0.0,0.5,1.0):
    mg=A['G'][R[pm]].mean(1); P('p_mid %.1f: percentile of server G 1.244 in G draws: %.0f; percentile of server base 3.22 in base draws: %.0f'%(pm,100*(mg<1.244).mean(),100*(A['base'][R[pm]].mean(1)<3.22).mean()))
# P(G=1.2 and exactly one >5) under pm .5
r=R[0.5]; x=A['G'][r]; P('P(exactly one ep>5 under G, pm .5) %.2f; given that, mean of 12-mean %.2f'%(((x>5).sum(1)==1).mean(), x[(x>5).sum(1)==1].mean()))
# G regressions vs base
d=A['G']-A['base']
P('\n## G worse than base by >1.5 m (all non-fold-4 pool flights)')
for i in np.argsort(-d)[:25]:
    e=eps[i]; g=s[e]['G']; P('%-38s %-5s base %.2f G %.2f f0 %.2f T %.2f | rot %.3f vel %.2f scale %.2f | v0 %.2f ang0 %s trav %.0f'%(e,'mid' if mid[i] else 'stat',A['base'][i],A['G'][i],A['f0'][i],A['T'][i],g['rotation_rmse'],g['velocity_rmse'],g['sim3_scale'],f[e]['v0'],'%.0f'%f[e]['ang0'] if f[e]['ang0']==f[e]['ang0'] else 'nan',trav[i]))
P('count G worse than base by >1.5: %d, >3: %d of %d ; G better by >1.5: %d'%((d>1.5).sum(),(d>3).sum(),len(d),(d<-1.5).sum()))
json.dump(out,open('/data/backups/rganapa/Sebastian/tmp/an.json','w'))
print('\n'.join(out))
