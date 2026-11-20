import json,numpy as np
d='research/single_model/'
L=lambda p:{r['episode']:r for r in json.load(open(d+p))}
me=L('fresh/table_pfbh_fresh.json'); fe=L('fresh/table_fe2_fbh.json'); c1=L('inventive/fresh_table_c1.json')
k=sorted(me)
print('n',len(k),'mean %.4f'%np.mean([me[e]['ate'] for e in k]))
print('ate equal to frontend fe2_fbh table:',sum(me[e]['ate']==fe[e]['ate'] for e in k),'/',len(k),'maxdiff',max(abs(me[e]['ate']-fe[e]['ate']) for e in k))
print('completed all',all(me[e]['completed'] for e in k),'filled nonzero',[e for e in k if me[e]['filled']],'errors',[e for e in k if me[e]['error']],'nan ate',[e for e in k if not np.isfinite(me[e]['ate'])])
pk=np.array([me[e]['peak_fuel'] for e in k])/1e6; c1f=L('final/preflight_c1/table_pfc1_c1.json'); pc=np.array([c1f[e]['peak_fuel'] for e in k])/1e6
print('fresh peak FB %.2fM (C1 %.2fM), median-of-peaks FB %.2f C1 %.2f, p95-of-peaks FB %.2f C1 %.2f, max %% of 2e10 %.4f'%(pk.max(),pc.max(),np.median(pk),np.median(pc),np.percentile(pk,95),np.percentile(pc,95),100*pk.max()*1e6/2e10))
for st in('all','static','mid'):
    s=[e for e in k if st=='all' or me[e]['start']==st]; x=np.array([c1[e]['ate'] for e in s]);y=np.array([me[e]['ate'] for e in s]);sc=[me[e]['scene'] for e in s]
    u=sorted(set(sc)); idx={a:[i for i,v in enumerate(sc) if v==a] for a in u}; rng=np.random.default_rng(1);dd=y-x
    bt=[dd[[i for p in rng.integers(0,len(u),len(u)) for i in idx[u[p]]]].mean() for _ in range(2000)]
    print(st,len(s),'C1 %.3f FB %.3f d %+.3f'%(x.mean(),y.mean(),dd.mean()),np.percentile(bt,[2.5,97.5]).round(3),'>5',int((x>5).sum()),int((y>5).sum()),'>10',int((x>10).sum()),int((y>10).sum()),'max %.2f'%y.max())
dd=[(me[e]['ate']-c1[e]['ate'],e) for e in k]
print('worse >0.5:',sum(1 for a,e in dd if a>0.5),'better >0.5:',sum(1 for a,e in dd if a<-0.5),'worse>0.3',sum(1 for a,e in dd if a>0.3),'better>0.3',sum(1 for a,e in dd if a<-0.3))
for a,e in sorted(dd,reverse=True)[:8]+sorted(dd)[:8]: print('  %s %s C1 %.2f FB %.2f d %+.2f'%(e,me[e]['start'],c1[e]['ate'],me[e]['ate'],a))
