import json, sys, numpy as np
rows=json.load(open(sys.argv[1]))
def dec(r,k,thr,rule):
    d=[x for x in r['d'][:k] if x>=0]
    if len(d)<min(k,2): return None
    return bool((max(d) if rule=='max' else np.mean(d))<thr)  # True = release (at rest)
bins=[(0,0.2),(0.2,0.5),(0.5,1.0),(1.0,9)]
for rule in ('max','mean'):
  for k in (2,3,5):
    print(f'--- rule {rule} of first {k} pairs (t~{0.045+0.2*k:.2f}s)')
    for thr in (1.0,1.5,1.8,2.0,2.5,3.0):
        out=[]
        for st in ('static','mid'):
            R=[r for r in rows if r['start']==st]; D=[dec(r,k,thr,rule) for r in R]
            ud=sum(x is None for x in D); rel=sum(x is True for x in D)
            out.append(f'{st}: release {rel}/{len(R)-ud} (undecided {ud})')
        sb=[]
        for lo,hi in bins:
            R=[r for r in rows if lo<=r['sp05']<hi and r['start']=='mid']; D=[dec(r,k,thr,rule) for r in R]
            sb.append(f'{lo}-{hi}:{sum(x is True for x in D)}/{len(R)}')
        print(f' thr {thr:3.1f} | '+' | '.join(out)+' | mid by true speed (released/n) '+' '.join(sb))
