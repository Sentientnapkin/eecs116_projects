import json,sys,numpy as np
F='../fresh/'
tf={d['episode']:d for d in json.load(open(F+'truth_feats.json'))}
def T(n): return {r['episode']:r for r in json.load(open(F+f'table_{n}.json'))}
ref=T('fe2_fbh'); base=T('base'); G=T('gate'); c1=json.load(open('../inventive/fresh_table_c1.json'))
c1={r['episode']:r for r in c1} if isinstance(c1,list) else None
arms=sys.argv[1:]; A={a:T(a) for a in arms}
eps=sorted(ref)
def m(t,es): return np.mean([t[e]['ate'] for e in es])
def tails(t,es,th): return sum(t[e]['ate']>th for e in es)
cls=[e for e in eps if G[e]['ate']-base[e]['ate']>1.5]
print('regression class n',len(cls),'base %.2f G %.2f B6 %.2f'%(m(base,cls),m(G,cls),m(ref,cls)),' '.join('%s %.2f'%(a,m(A[a],cls)) for a in arms))
print('overall mean B6 %.3f'%m(ref,eps),' '.join('%s %.3f'%(a,m(A[a],eps)) for a in arms))
print('tails >3/5/10: B6',[tails(ref,eps,x) for x in(3,5,10)],' '.join('%s %s'%(a,[tails(A[a],eps,x) for x in(3,5,10)]) for a in arms))
mid=[e for e in eps if ref[e]['start']!='static']
print('mid mean B6 %.3f'%m(ref,mid),' '.join('%s %.3f'%(a,m(A[a],mid)) for a in arms))
def binrep(name,key,edges):
    print(name)
    for lo,hi in zip(edges[:-1],edges[1:]):
        es=[e for e in mid if lo<=tf[e][key]<hi]
        if not es: continue
        print(f' [{lo},{hi}) n={len(es)} B6 mean %.2f >3 %d'%(m(ref,es),tails(ref,es,3)),' | '.join('%s mean %.2f >3 %d'%(a,m(A[a],es),tails(A[a],es,3)) for a in arms))
binrep('angle (mid)','angle',[0,45,90,135,181]); binrep('speed (mid)','speed0',[0,0.3,0.6,1.0,1.8,99])
ds=np.array([A[arms[0]][e]['ate']-ref[e]['ate'] for e in eps]); print('worst regress',sorted([(round(d,2),e) for d,e in zip(ds,eps)])[-4:],'best',sorted([(round(d,2),e) for d,e in zip(ds,eps)])[:4])
