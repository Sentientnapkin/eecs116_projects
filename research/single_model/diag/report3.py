import sys, json
sys.argv=['x','diag_counters1']
exec(open('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/diag/report.py').read().split("S,bad=run('search')")[0])
W=json.loads((ROOT/'research/results/single_model/diag_counters1/windows.json').read_text())
for r in rows: r.update(W[r['ep']])
for sl in ('search','val'):
    S=sel(sl); ates=col(S,'ate'); bad=ates>3
    print('\n==',sl)
    for k in ('aerr0','aerr0_cos_v0','aerr0_along_v0'):
        x=col(S,k); print(k,'AUC',round(auc(x,bad),2),'good',np.nanmean(x[~bad]).round(3),'bad',np.nanmean(x[bad]).round(3))
    tt=col(S,'true_tilt0'); vv=col(S,'v0_true')
    for lo,hi in ((0,4),(4,8),(8,100)):
        m=(tt>=lo)&(tt<hi); print(f'tilt0 {lo}-{hi}: n={m.sum()} bad {bad[m].sum()} ({bad[m].mean() if m.sum() else 0:.2f}) mean ate {ates[m].mean():.2f}  mean verr2s {np.nanmean(col(S,"verr_2s")[m]):.2f}')
    for lo,hi in ((0,0.5),(0.5,1.0),(1.0,1.5),(1.5,3)):
        m=(vv>=lo)&(vv<hi); print(f'v0 {lo}-{hi}: n={m.sum()} bad {bad[m].sum()} ({bad[m].mean() if m.sum() else 0:.2f}) mean ate {ates[m].mean():.2f}')
    x=col(S,'aerr0')
    for lo,hi in ((0,0.5),(0.5,1),(1,1.5),(1.5,9)):
        m=(x>=lo)&(x<hi); print(f'aerr0 {lo}-{hi}: n={m.sum()} bad {bad[m].sum()} ({bad[m].mean() if m.sum() else 0:.2f}) mean ate {ates[m].mean():.2f}')
    # speed-est runaway: fraction where speed_est_2s > 1.5 x true
    sp=col(S,'speed_est_2s'); st=col(S,'speed_true_2s'); m=sp>1.5*st+0.3
    print('runaway at 2s (est>1.5*true+0.3):',m.sum(),'bad among them',bad[m].sum(),'; not runaway',(~m).sum(),'bad',bad[~m].sum())
    # simple 2-feature: Pth tilt at 2s?
    # mean ATE by class (what a perfect fix of bad would give)
print('\nmean ATE (search mid) if bad ones had good-mean:', )
