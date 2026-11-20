import sys; sys.argv=['x','diag_counters1']
exec(open('/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/diag/stats.py').read())
S=sel('search'); print(len(S),'search mid')
ates=col(S,'ate'); print(np.sort(ates).round(2))
keys=['tilt_err0','true_tilt0','v0_true','v0_est','v0_err','v0_err_dir_deg','v0_mag_err','w0_true','tilt_err_2s','verr_2s','verr_5s','tilt_err_5s','baerr_2s','first_msckf_frame','first_feat_frame','live_mean_2s','live3_mean_2s','used_2s','used_5s','trifail_2s','gaterej_2s','dark_fraction','flat_fraction','Pv0','Pth0','Pv2','Pth2','vnees_2s','tnees_2s','ep_act_2s','ep_v0_2s','ep_tilt_2s','ep_bias_2s','ep_res_2s','ep_act_5s','ep_v0_5s','ep_tilt_5s','ep_bias_5s','ep_res_5s','ba_true_norm','g_est_norm']
bad=ates>3; 
print('bad',bad.sum(),'good',(~bad).sum())
for k in keys:
    x=col(S,k); print(f"{k:20s} good {np.nanmean(x[~bad]):8.3f} (med {np.nanmedian(x[~bad]):8.3f})  bad {np.nanmean(x[bad]):8.3f} (med {np.nanmedian(x[bad]):8.3f})  corr(ate) {np.corrcoef(np.nan_to_num(x),ates)[0,1]:+.2f}")
