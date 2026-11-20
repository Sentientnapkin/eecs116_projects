import sys, json
sys.argv=['x','diag_counters1']
exec(open('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/diag/report.py').read().split("S,bad=run('search')")[0])
for sl in ('search','val'):
    S=sel(sl); a=col(S,'ate'); bad=a>3
    print(sl,'n',len(S),'bad',bad.sum(),'mean ate',a.mean().round(2),'bad contrib',(a[bad].sum()/len(a)).round(2),'good contrib',(a[~bad].sum()/len(a)).round(2))
    for k in ('true_tilt0','tilt_err0','v0_true','first_msckf_frame','live_mean_1s','live3_mean_1s','live_mean_2s','live3_mean_2s','Pth0','Pth2','tnees_2s','vnees_2s'):
        x=col(S,k); print(f'  {k:18s} mean {np.nanmean(x):.3f} p50 {np.nanmedian(x):.3f} p90 {np.nanpercentile(x,90):.3f} max {np.nanmax(x):.2f}')
    # textureless-starved
    live=col(S,'live3_mean_2s'); st=live<6
    print('  starved (live3_2s<6): n',st.sum(),'bad',bad[st].sum(),'ATE sum share of bad excess', (a[st&bad].sum()/a[bad].sum()).round(2))
    # first vision update
    f=col(S,'first_msckf_frame'); print('  first update frame: median',np.nanmedian(f),'>=40:',(f>=40).sum(),'nan',np.isnan(f).sum())
    # err ratio at 2s in %: initial speed err & tilt compare
    print('  speed_est_2s/true: good',np.nanmean((col(S,'speed_est_2s')/col(S,'speed_true_2s'))[~bad]).round(2),'bad',np.nanmean((col(S,'speed_est_2s')/col(S,'speed_true_2s'))[bad]).round(2))
    for k in ('Pv_60','Pv_100','spd_100','tr_40_60'): pass
