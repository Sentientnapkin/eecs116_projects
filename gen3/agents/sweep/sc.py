"""python3 sc.py [--pool=v3val] [--base=ref] NAME[+NAME2+NAME3] ...   paired vs base (also may be a+b+c rep-mean) on common flights.
Prints n, raw, server-weighted (score.py weights), d raw [95% boot CI], d sw [CI], classes, hover/mid, >3m, peak (max over reps)."""
import sys,json,random,statistics as s
E='/data/backups/rganapa/Sebastian/gen3/evals/'
W={'room':(12/24,1/12),'warehouse':(6/24,4/6),'forest':(6/24,1/6)}
pool=next((x.split('=')[1] for x in sys.argv if x.startswith('--pool=')),'v3val')
base=next((x.split('=')[1] for x in sys.argv if x.startswith('--base=')),'ref')
names=[x for x in sys.argv[1:] if not x.startswith('--')]
def f(n): return E+(n[3:] if n.startswith('ev:') else 'sw_'+n)+f'__{pool}.json'
def load(spec):
    parts=spec.split('+');Rs=[{r['id']:r for r in json.load(open(f(p))) if r.get('ate') is not None} for p in parts]
    ids=set.intersection(*[set(r) for r in Rs]);out={}
    for i in ids:
        r=dict(Rs[0][i]);r['ate']=s.mean(R[i]['ate'] for R in Rs);r['peak']=max((R[i].get('peak') or 0) for R in Rs);out[i]=r
    return out
B=load(base);runs=[load(n) for n in names]
keep=set(open(f'/data/backups/rganapa/Sebastian/gen3/agents/sweep/pools/{pool}.keep').read().split()) if '--all' not in sys.argv else set(B)
ids=sorted(set(B).intersection(*[set(r) for r in runs],keep))
def swm(rows):
    tot=0
    for c,(wc,hv) in W.items():
        h=[r['ate'] for r in rows if r['setting_class']==c and r['start']=='hover'];m=[r['ate'] for r in rows if r['setting_class']==c and r['start']!='hover']
        if not h or not m: return float('nan')
        tot+=wc*(hv*s.mean(h)+(1-hv)*s.mean(m))
    return tot
def line(n,R):
    rows=[R[i] for i in ids];a=[r['ate'] for r in rows]
    cl='/'.join('%.3f'%s.mean(r['ate'] for r in rows if r['setting_class']==c) for c in W)
    st='/'.join('%.3f'%s.mean(r['ate'] for r in rows if r['start']==k) for k in ('hover','mid-flight'))
    o='%-34s n%4d raw %.3f sw %.3f med %.3f >3m %2d peak %.2fM ro/wa/fo %s hov/mid %s'%(n,len(ids),s.mean(a),swm(rows),s.median(a),sum(x>3 for x in a),max(r['peak'] for r in rows)/1e6,cl,st)
    if R is not B:
        d=[R[i]['ate']-B[i]['ate'] for i in ids];rng=random.Random(0);bs=[];bw=[]
        for _ in range(1000):
            k=rng.choices(range(len(ids)),k=len(ids));bs.append(s.mean(d[j] for j in k))
            bw.append(swm([R[ids[j]] for j in k])-swm([B[ids[j]] for j in k]))
        bs.sort();bw.sort()
        o+='  d %+.3f [%+.3f,%+.3f] dsw %+.3f [%+.3f,%+.3f]'%(s.mean(d),bs[25],bs[974],swm(rows)-swm([B[i] for i in ids]),bw[25],bw[974])
    return o
print(line(base,B))
for n,R in zip(names,runs): print(line(n,R))
