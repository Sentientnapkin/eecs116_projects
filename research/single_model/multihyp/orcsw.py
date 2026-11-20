import sys; sys.path.insert(0,'.')
from splice import *
from ana import T
A=T('mh_h0'); B=T('mh_h2')
eps=[e for e in sorted(A) if abs(A[e]['ate']-B[e]['ate'])>0.3]
print(len(eps),'flights differing >0.3')
tot={k:0 for k in (0,10,20,40,60)}; base=0; orc=0
for ep in eps:
    a,b=A[ep]['ate'],B[ep]['ate']; base+=a; orc+=min(a,b)
    Ea=est('h0',ep);Eb=est('h2',ep)
    better=1 if b<a else 0
    for k in tot:
        tot[k]+= ate(ep,splice(Ea,Eb,k)) if better and k>0 else (b if (better and k==0) else a)
N=711
print('delta mean over 711 vs base: oracle-final %.3f'%((orc-base)/N),{k:'%.3f'%((v-base)/N) for k,v in tot.items()})
