"""Compare eval runs on the SAME flights. python score.py evals/BASE__POOL.json evals/NEW__POOL.json [...]
Prints raw mean ATE, per class / start, server-weighted mean (classes 12/6/6 rooms/warehouse/forest; hover share per class as on the
stage-3 server: rooms 1/12, warehouse 4/6, forest 1/6), paired bootstrap 95% CI of the difference vs the first file, tails, peak fuel."""
import sys,json,random,statistics as s,collections as C
W={'room':(12/24,1/12),'warehouse':(6/24,4/6),'forest':(6/24,1/6)}
def load(p): return {r['id']:r for r in json.load(open(p)) if r.get('ate') is not None}
def swm(rows):
    tot=0
    for c,(wc,hv) in W.items():
        h=[r['ate'] for r in rows if r['setting_class']==c and r['start']=='hover'];m=[r['ate'] for r in rows if r['setting_class']==c and r['start']!='hover']
        if not h or not m: return float('nan')
        tot+=wc*(hv*s.mean(h)+(1-hv)*s.mean(m))
    return tot
runs=[load(p) for p in sys.argv[1:]];ids=sorted(set.intersection(*[set(r) for r in runs]));base=[runs[0][i] for i in ids]
print('flights in common',len(ids))
for p,R in zip(sys.argv[1:],runs):
    rows=[R[i] for i in ids];a=[r['ate'] for r in rows];pk=max((r.get('peak') or 0) for r in rows)
    cl={c:round(s.mean(r['ate'] for r in rows if r['setting_class']==c),3) for c in W if any(r['setting_class']==c for r in rows)}
    st={k:round(s.mean(r['ate'] for r in rows if r['start']==k),3) for k in('hover','mid-flight') if any(r['start']==k for r in rows)}
    line=f"{p.split('/')[-1]:40s} mean {s.mean(a):.3f}  server-weighted {swm(rows):.3f}  median {s.median(a):.3f}  >3m {sum(x>3 for x in a)}  peak {pk/1e6:.2f}M  {cl} {st}"
    if R is not runs[0]:
        d=[R[i]['ate']-runs[0][i]['ate'] for i in ids];rng=random.Random(0);bs=sorted(s.mean(rng.choices(d,k=len(d))) for _ in range(2000))
        line+=f"  d={s.mean(d):+.3f} [{bs[50]:+.3f},{bs[1949]:+.3f}]"
    print(line)
