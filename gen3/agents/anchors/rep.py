"""venv python rep.py [--pool=v3val] NAME[+r1+r2] ...: paired vs Ze0 3-rep mean on the same flights; ATE, sw, d [CI], peak (max over reps),
p95 (pooled frames), ro/wa/fo, area = 0.4*log2(3.77/peak) - 2.2*ln(ATE_eq/0.665) with ATE_eq = 0.665 + d (paired)."""
import sys,json,glob,math,random,statistics as s,numpy as np
E='/data/backups/rganapa/Sebastian/gen3/evals/'
pool=next((x.split('=')[1] for x in sys.argv if x.startswith('--pool=')),'v3val')
BASE={'v3val':['sw_a1_Ze0','sw_a1_Ze0_r1','sw_a1_Ze0_r2'],'v1val':['sw_a1_Ze0_v1']}.get(pool,['sw_a1_Ze0','sw_a1_Ze0_r1','sw_a1_Ze0_r2'])
bp='v1val' if pool=='v1val' else 'v3val';REFATE={'v3val':0.665,'v1val':0.556}[bp]
keep=set(open(f'/data/backups/rganapa/Sebastian/gen3/agents/anchors/pools/{pool}.keep').read().split())
def ld(ns,p):
    Rs=[{r['id']:r for r in json.load(open(E+f'{n}__{p}.json')) if r.get('ate') is not None} for n in ns];ids=set.intersection(*map(set,Rs))
    return {i:dict(Rs[0][i],ate=s.mean(R[i]['ate'] for R in Rs),peak=max(R[i]['peak'] or 0 for R in Rs)) for i in ids}
B=ld(BASE,bp)
for spec in [x for x in sys.argv[1:] if not x.startswith('--')]:
    ns=['an_'+x for x in spec.split('+')];R=ld(ns,pool);ids=sorted(set(R)&set(B)&keep)
    d=[R[i]['ate']-B[i]['ate'] for i in ids];md=s.mean(d);rng=random.Random(0)
    bs=sorted(s.mean(d[j] for j in rng.choices(range(len(d)),k=len(d))) for _ in range(1000))
    fs=[np.load(f).ravel() for n in ns for f in glob.glob(E+f'{n}/{pool}/{n}-*/*/report/logs/*/fuel.npy') if f.split('/')[-5] in keep]
    a=np.concatenate(fs);pk=a.max()/1e6;p95=np.percentile(a,95)/1e6
    cl='/'.join('%.3f'%s.mean(R[i]['ate'] for i in ids if R[i]['setting_class']==c) for c in ('room','warehouse','forest') if any(R[i]['setting_class']==c for i in ids))
    bcl='/'.join('%.3f'%s.mean(B[i]['ate'] for i in ids if B[i]['setting_class']==c) for c in ('room','warehouse','forest') if any(B[i]['setting_class']==c for i in ids))
    ateq=REFATE+md;area=0.4*math.log2(3.77/pk)-2.2*math.log(ateq/REFATE)
    print('%-22s n%3d raw %.3f (ref %.3f) d %+.3f [%+.3f,%+.3f] peak %.2fM p95 %.2fM mean %.2fM area %+.3f | cls %s (ref %s) >3m %d'%(spec,len(ids),s.mean(R[i]['ate'] for i in ids),s.mean(B[i]['ate'] for i in ids),md,bs[25],bs[974],pk,p95,a.mean()/1e6,area,cl,bcl,sum(R[i]['ate']>3 for i in ids)))
