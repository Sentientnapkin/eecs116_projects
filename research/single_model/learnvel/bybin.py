import json, sys, numpy as np
pool = sys.argv[1]; L=lambda n:{r['ep']:r['ate_rmse'] for r in json.load(open(f'tables/{n}__{pool}.json'))}
B=[L('hm40'),L('hm40_r1'),L('hm40_r2')]
for arm in sys.argv[2:]:
    A=L(arm); ks=sorted(A); b=np.array([np.mean([x[k] for x in B]) for k in ks]); a=np.array([A[k] for k in ks])
    print(arm, ' '.join('[%.1f-%.1f n%d %.3f->%.3f]'%(lo,hi,((b>=lo)&(b<hi)).sum(),b[(b>=lo)&(b<hi)].mean(),a[(b>=lo)&(b<hi)].mean()) for lo,hi in [(0,0.3),(0.3,0.6),(0.6,1),(1,2),(2,99)]), 'all %.3f->%.3f'%(b.mean(),a.mean()))
