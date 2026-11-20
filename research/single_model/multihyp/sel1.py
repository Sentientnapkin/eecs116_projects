import sys; sys.path.insert(0,'.')
from ana import *
names=sys.argv[1:]
Ts=[T('mh_'+n) for n in names]; eps=sorted(Ts[0])
for Tw in (2,3,5):
    keys=('nis','fchi','pri','acc','rej','Pv')
    FE=[[flightfeats(n,e,Tw) for n in names] for e in eps]
    ates=np.array([[t[e]['ate'] for t in Ts] for e in eps]); orc=ates.argmin(1)
    for k in keys:
        v=np.array([[f[k] for f in row] for row in FE])
        pk=v.argmax(1) if k=='acc' else v.argmin(1)
        ach=ates[np.arange(len(eps)),pk].mean()
        sig=(ates.max(1)-ates.min(1))>0.5
        print(Tw,k,'mean %.3f'%ach,'acc on spread>0.5 (n=%d) %.2f'%(sig.sum(),(pk[sig]==orc[sig]).mean()), 'picks',np.bincount(pk,minlength=len(names)))
