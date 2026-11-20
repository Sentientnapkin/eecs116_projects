import json,sys,numpy as np
d='research/single_model/'
a={r['episode']:r for r in json.load(open(d+'inventive/fresh_table_c1.json'))}
for arm in sys.argv[1:]:
    b={r['episode']:r for r in json.load(open(d+f'fresh/table_{arm}.json'))}
    ks=[e for e in b if e in a and a[e]['ate'] is not None and b[e]['ate'] is not None]
    for st in ('all','static','mid'):
        k=[e for e in ks if st=='all' or b[e]['start']==st]
        x=np.array([a[e]['ate'] for e in k]); y=np.array([b[e]['ate'] for e in k]); sc=[b[e]['scene'] for e in k]
        u=sorted(set(sc)); idx={s:[i for i,v in enumerate(sc) if v==s] for s in u}; rng=np.random.default_rng(1); dd=y-x
        bt=[dd[[i for p in rng.integers(0,len(u),len(u)) for i in idx[u[p]]]].mean() for _ in range(2000)]
        pk=max(b[e]['peak_fuel'] or 0 for e in k)/1e6
        print(arm,st,len(k),'c1',x.mean().round(3),'arm',y.mean().round(3),'d',dd.mean().round(3),np.percentile(bt,[2.5,97.5]).round(3),'>5',int((x>5).sum()),int((y>5).sum()),'>10',int((x>10).sum()),int((y>10).sum()),'max',y.max().round(1),'peakfuel',pk)
