import sys; sys.path.insert(0,'.')
from ana import *
import itertools
names=['h0','h1','h2','h0r']
Ts={n:T('mh_'+n) for n in names}; eps=sorted(Ts['h0'])
A={n:np.array([Ts[n][e]['ate'] for e in eps]) for n in names}
for n in names: print(n,'%.3f'%A[n].mean(),'>3',(A[n]>3).sum(),'>5',(A[n]>5).sum())
for c in [('h0','h0r'),('h0','h1'),('h0','h2'),('h0','h1','h2'),('h0','h0r','h1','h2'),('h0','h2','h0r')]:
    print('oracle',c,'%.3f'%np.min([A[n] for n in c],0).mean())
bad=A['h0']>3
print('B6 bad n',bad.sum(),{n:'%.2f'%A[n][bad].mean() for n in names},'oracle(h0,h1,h2) on bad %.2f'%np.min([A[n][bad] for n in ('h0','h1','h2')],0).mean())
mid=np.array([Ts['h0'][e]['start']!='static' for e in eps])
ang=np.array([tf[e]['angle'] for e in eps])
for lo,hi in [(0,45),(45,90),(90,135),(135,181)]:
    s=mid&(ang>=lo)&(ang<hi)
    print('angle',lo,hi,s.sum(),{n:'%.2f'%A[n][s].mean() for n in names})
