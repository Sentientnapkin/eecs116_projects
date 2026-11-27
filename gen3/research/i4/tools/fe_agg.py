import json, glob, numpy as np, sys
R = [json.load(open(f)) for f in sorted(glob.glob('fe/s3v3*.json'))]
keys = ['life_mean','live_mean','frac_frames_lt10','coverage12','n_tri','reproj_track_rms_med','reproj_obs_med','reproj_obs_rms_clip3','frac_tracks_rms_gt2px','frac_tracks_rms_lt05px','depth_pct','frac_depth_gt10','parallax_deg_pct','frac_par_lt1deg','rot_per_frame_deg_med','rot_per_frame_deg_p90','gyro_resid_deg_med','gyro_resid_px_med','gyro_resid_px_p90','flow_px_med','flow_derot_px_med','tri_rej_rate','gate_rej_rate','klt_fail_per_frame','fb_rej_per_frame','det_per_frame','detnew_per_frame','rows_per_frame']
def agg(rs, label):
    print('##', label, 'n=%d' % len(rs))
    for s in ('2','5','10','20','40','80'): print(' surv>=%s %.3f' % (s, np.mean([r['surv'][s] for r in rs])), end='')
    print()
    for k in keys:
        v = np.array([r[k] for r in rs], float)
        print(' %-24s' % k, ' '.join('%.3f' % x for x in (np.nanmean(v, 0) if v.ndim > 1 else [np.nanmean(v)])))
    ba = np.array([[x if x is not None else np.nan for x in r['reproj_by_age']] for r in rs], float)
    print(' reproj_by_age(<5,<10,<20,<40,<80,80+)', np.round(np.nanmean(ba, 0), 3))
agg(R, 'all')
for c in ('room','warehouse','forest'): agg([r for r in R if r['cls'] == c], c)
agg([r for r in R if r['exposure'] > .035], 'exp>35ms'); agg([r for r in R if r['exposure'] <= .015], 'exp<=15ms')
agg([r for r in R if r['start']=='hover'], 'hover'); agg([r for r in R if r['start']!='hover'], 'mid')
# correlation with baseline ATE
ev = {r['id']: r['ate'] for r in json.load(open('../../evals/i4_ctl__s80.json'))}
ids = [r['id'] for r in R]; a = np.array([ev[i] for i in ids])
print('## spearman-ish corr with ctl ATE (log)')
def spearmanr(x,y):
    rx=np.argsort(np.argsort(x));ry=np.argsort(np.argsort(y));return (np.corrcoef(rx,ry)[0,1],)
for k in keys:
    v = np.array([r[k] if not isinstance(r[k], list) else r[k][1] for r in R], float)
    m = ~np.isnan(v); print(' %-24s rho=%+.2f' % (k, spearmanr(v[m], a[m])[0]))
