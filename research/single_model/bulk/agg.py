import json, numpy as np, sys
R = json.load(open('research/single_model/bulk/decomp_fresh_fe2_fbh.json'))
tab = {r['episode']: r for r in json.load(open('research/single_model/fresh/table_fe2_fbh.json'))}
st = np.array([tab[r['ep']]['start'] for r in R]); ate = np.array([r['ate'] for r in R])
q25, q75 = np.percentile(ate, [25, 75]); print('pooled p25/p75', q25, q75)
def col(k): return np.array([np.nan if r.get(k) is None else r[k] for r in R], float)
keys = ['ate','o_yaw','o_tilt','o_rot','o_scale_pl','o_scale_s3','o_speed1s','o_rot_speed','o_start2','o_start5','o_start10','mean_off','o_vert0']
def rep(m, lab):
    print(f'\n== {lab} n={m.sum()}  (mean RMSE; oracle value = ATE after replacement)')
    for k in keys: print(f'  {k:12s} mean {np.nanmean(col(k)[m]):.3f} median {np.nanmedian(col(k)[m]):.3f}')
    for k in ['sim3_scale','path_ratio','off2','off5','off10','mse_first5','f_vert','f_along','f_cross','yaw_end','yaw_rms','tilt_rms','yaw_slope','speed_mean','path','dur']:
        v = col(k)[m]; v2 = np.abs(v) if k in ('yaw_end','yaw_slope') else v
        print(f'  {k:12s} mean {np.nanmean(v2):.3f} median {np.nanmedian(v2):.3f}')
for lab, m in [('all', np.ones(len(R), bool)), ('typical p25-p75', (ate >= q25) & (ate <= q75)),
               ('typical static', (ate >= q25) & (ate <= q75) & (st == 'static')), ('typical mid', (ate >= q25) & (ate <= q75) & (st == 'mid')),
               ('static', st == 'static'), ('mid', st == 'mid'), ('best75 (<p75)', ate <= q75)]:
    rep(m, lab)
# drift per metre vs per second: error growth after 5 s
m = (ate >= q25) & (ate <= q75)
g = col('grow')[m]; L = col('path_after5')[m]; D = col('t_after5')[m]
X = np.column_stack([np.log(L + 1e-3), np.log(D)]); y = np.log(g + 1e-3)
print('\ncorr(log grow, log path)', np.corrcoef(X[:, 0], y)[0, 1], 'corr(log grow, log dur)', np.corrcoef(X[:, 1], y)[0, 1])
print('corr(path,dur)', np.corrcoef(L, D)[0, 1], 'grow/m median', np.median(g / L), 'grow/s median', np.median(g / D))
print('corr(ate, speed_mean)', np.corrcoef(ate, col('speed_mean'))[0, 1], 'corr(ate,path)', np.corrcoef(ate, col('path'))[0,1], 'corr(ate,tilt_rms)', np.corrcoef(ate, col('tilt_rms'))[0,1], 'corr(ate,yaw_rms)', np.corrcoef(ate, col('yaw_rms'))[0,1])
print('corr(ate,|logpathratio|)', np.corrcoef(ate, np.abs(np.log(col('path_ratio'))))[0,1])
