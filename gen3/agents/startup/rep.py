"""rep.py [--v1] A1,A2,A3 B1,B2,B3 : per-flight mean over replicates, paired bootstrap (raw and server-weighted)."""
import sys,json,random,statistics as s
sys.argv=[a for a in sys.argv]; pool='v1val' if '--v1' in sys.argv else 'v3val'; args=[a for a in sys.argv[1:] if not a.startswith('--')]
E='/data/backups/rganapa/Sebastian/gen3/evals/'
def fn(n): return E+(n if n.startswith(('net_','pr_','gslv','nv2_')) else 'st_'+n)+f'__{pool}.json'
def load(p): return {r['id']:r for r in json.load(open(p)) if r.get('ate') is not None}
W={'room':(12/24,1/12),'warehouse':(6/24,4/6),'forest':(6/24,1/6)}
def swm(rows):
    tot=0
    for c,(wc,hv) in W.items():
        h=[r['ate'] for r in rows if r['setting_class']==c and r['start']=='hover'];m=[r['ate'] for r in rows if r['setting_class']==c and r['start']!='hover']
        if not h or not m: return float('nan')
        tot+=wc*(hv*s.mean(h)+(1-hv)*s.mean(m))
    return tot
G=[[load(fn(n)) for n in a.split(',')] for a in args]
ids=sorted(set.intersection(*[set(r) for g in G for r in g]))
M=[{i:dict(g[0][i],ate=s.mean(r[i]['ate'] for r in g),peak=max(r[i].get('peak') or 0 for r in g)) for i in ids} for g in G]
base=M[0]
for a,m in zip(args,M):
    rows=[m[i] for i in ids];d=[m[i]['ate']-base[i]['ate'] for i in ids]
    rng=random.Random(0);bs=sorted(s.mean(rng.choices(d,k=len(d))) for _ in range(2000))
    rng=random.Random(1);bw=sorted(x for x in (swm([m[i] for i in x])-swm([base[i] for i in x]) for x in (rng.choices(ids,k=len(ids)) for _ in range(500))) if x==x)
    hv=s.mean(r['ate'] for r in rows if r['start']=='hover');md=s.mean(r['ate'] for r in rows if r['start']!='hover');a_=[r['ate'] for r in rows]
    print(f"{a:40s} n{len(ids)} raw {s.mean(a_):.3f} sw {swm(rows):.3f} d {s.mean(d):+.3f} [{bs[50]:+.3f},{bs[1949]:+.3f}] dsw {swm(rows)-swm([base[i] for i in ids]):+.3f} [{bw[int(.025*len(bw))]:+.3f},{bw[int(.975*len(bw))-1]:+.3f}] hov {hv:.3f} mid {md:.3f} >1/2/3 {sum(x>1 for x in a_)}/{sum(x>2 for x in a_)}/{sum(x>3 for x in a_)} peakmax {max(r['peak'] for r in rows)/1e6:.2f}M")
