import json,numpy as np
F='research/single_model/'
def T(p): return {r['episode']:r for r in json.load(open(p))}
c1=T(F+'fresh/table_pfc1_c1.json'); g=T(F+'fresh/table_pfc1_g.json'); ic=T(F+'inventive/fresh_table_c1.json'); gg=T(F+'fresh/table_gate.json')
def st(D,k,sel=None):
    a=np.array([D[e][k] for e in D if D[e][k] is not None and (sel is None or D[e]['start']==sel)]); return len(a),a.mean(),np.median(a),(a>5).sum(),(a>10).sum()
for n,D,k in (('G (my run)',g,'ate'),('C1 (my run)',c1,'ate'),('G (existing fresh/table_gate)',gg,'ate'),('C1 (inventive table)',ic,'ate')):
    print(n,'all n=%d mean %.4f median %.3f >5 %d >10 %d'%st(D,k),'| static n=%d mean %.3f'%st(D,k,'static')[:2],'| mid n=%d mean %.3f'%st(D,k,'mid')[:2])
print('C1 mine == inventive per-flight:',sum(c1[e]['ate']==ic[e]['ate'] for e in c1),'/',len(c1),' G mine == existing G table:',sum(g[e]['ate']==gg[e]['ate'] for e in g),'/',len(g))
print('failed/incomplete/filled flights C1:',sum(1 for r in c1.values() if r['error'] or not r['completed'] or r['filled']),'G:',sum(1 for r in g.values() if r['error'] or not r['completed'] or r['filled']))
print('peak fuel C1 %.3fM G %.3fM'%(max(r['peak_fuel'] for r in c1.values())/1e6,max(r['peak_fuel'] for r in g.values())/1e6))
d=np.array([c1[e]['ate']-g[e]['ate'] for e in c1])
print('paired delta mean %.4f ; improved>0.3: %d regressed>0.3: %d ; worst regress %.2f, best %.2f'%(d.mean(),(d<-0.3).sum(),(d>0.3).sum(),d.max(),d.min()))
sc=sorted({r['scene'] for r in c1.values()}); rng=np.random.default_rng(0); idx={s:[e for e in c1 if c1[e]['scene']==s] for s in sc}
bs=[]
for _ in range(2000):
    pick=rng.choice(len(sc),len(sc)); es=[e for i in pick for e in idx[sc[i]]]; bs.append(np.mean([c1[e]['ate']-g[e]['ate'] for e in es]))
print('scene bootstrap delta 95%% CI [%.3f, %.3f] (n scenes %d)'%(np.percentile(bs,2.5),np.percentile(bs,97.5),len(sc)))
print('worst C1 flights:',sorted(((round(c1[e]['ate'],1),e) for e in c1),reverse=True)[:5])
