import sys, json
sys.argv=['x','diag_counters1']
exec(open('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/diag/report.py').read().split("S,bad=run('search')")[0])
W=json.loads((ROOT/'research/results/single_model/diag_counters1/windows.json').read_text())
for r in rows: r.update(W[r['ep']])
for r in rows:
    for a,b in ((20,40),(40,60),(60,100)):
        r[f'gr_{a}_{b}']=r[f'gate_{a}_{b}']/max(r[f'att_{a}_{b}']-r[f'tri_{a}_{b}'],1); r[f'tr_{a}_{b}']=r[f'tri_{a}_{b}']/max(r[f'att_{a}_{b}'],1)
    r['used_20_60']=r['used_20_40']+r['used_40_60']
    r['used_0_100']=sum(r[f'used_{a}_{b}'] for a,b in ((0,20),(20,40),(40,60),(60,100)))
for sl in ('search','val'):
    S=sel(sl); ates=col(S,'ate'); bad=ates>3
    print('\n==',sl,len(S),bad.sum())
    ks=[k for k in S[0] if k.startswith(('used_','gr_','tr_','spd_','Pv_','Pth_','live3_','att_','tilt_err_','verr_'))]
    res=[(abs(auc(col(S,k),bad)-.5),k) for k in ks]
    for _,k in sorted(res,reverse=True)[:22]:
        x=col(S,k); a=auc(x,bad); acc,t,sg=best_thr(x,bad)
        print(f"{k:14s} AUC {a:.2f} good {np.nanmean(x[~bad]):8.3f} bad {np.nanmean(x[bad]):8.3f} thr {'>=' if sg>0 else '<='}{t:.2f} acc {acc:.2f}")
