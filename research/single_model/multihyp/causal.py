import sys; sys.path.insert(0,'.')
from splice import *
from ana import flightfeats, T
names=sys.argv[2:]; Ts_=float(sys.argv[1]); key=sys.argv[0] and 'acc'
Tb={n:T('mh_'+n) for n in names}; eps=sorted(Tb[names[0]])
mid=[e for e in eps if Tb[names[0]][e]['start']!='static']
res=[];
for ep in mid:
    a=[Tb[n][ep]['ate'] for n in names]
    if max(a)-min(a)<1e-9: res.append((a[0],a[0],a[0],min(a),0)); continue
    fe=[flightfeats(n,ep,Ts_) for n in names]
    pk=int(np.argmax([f['acc'] for f in fe]))
    k=int(Ts_*20)
    E0=est(names[0],ep)
    sp=ate(ep,splice(E0,est(names[pk],ep),k)) if pk else a[0]
    res.append((a[0],a[pk],sp,min(a),pk))
r=np.array(res); n_static=len(eps)-len(mid)
tot=lambda c: (r[:,c].sum()+sum(Tb[names[0]][e]['ate'] for e in eps if e not in mid))/len(eps)
print('Ts',Ts_,names,'base %.3f commit(noncausal) %.3f spliced-causal %.3f oracle %.3f'%(tot(0),tot(1),tot(2),tot(3)))
sp=r[:,2]; print('tails >3/5/10 base',[(r[:,0]>x).sum() for x in(3,5,10)],'spliced',[(sp>x).sum() for x in (3,5,10)],'picked non-default',(r[:,4]>0).sum(),'worst spliced %.2f'%sp.max())
