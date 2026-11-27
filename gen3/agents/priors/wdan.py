import glob,json,re,numpy as np,sys
E='/data/backups/rganapa/Sebastian/gen3/evals/'
res={r['id']:r for r in json.load(open(E+'pr_wddbg__v3val.json'))}
rows=[]
for f in glob.glob(E+'pr_wddbg/v3val/pr_wddbg-*/*/report/logs/*/stderr.txt'):
    ep=f.split('/')[-5];a=[]
    for l in open(f):
        if l.startswith('WDF'): a.append([float(x) for x in l.split()[1:]])
    a=np.array(a);
    if not len(a) or ep not in res: continue
    att,nis,stk,sp,ba,bg,pv=a[:,1],a[:,2],a[:,3],a[:,4],a[:,5],a[:,6],a[:,7]
    ok=att>=3
    rows.append((res[ep]['ate'],res[ep]['start'],stk.max(),np.median(nis[ok]) if ok.any() else -1,(nis[ok]>1.8).mean() if ok.any() else 0,sp.max(),ba.max(),bg.max(),(att<3).mean(),ep))
rows.sort()
for r in rows: print('%.2f %-10s stkmax %3d nismed %.2f frac>1.8 %.2f spmax %.2f bamax %.2f bgmax %.3f starve %.2f %s'%r)
