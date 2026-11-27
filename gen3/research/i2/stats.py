import json, numpy as np
from pathlib import Path
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
I2 = Path('/data/backups/rganapa/Sebastian/gen3/research/i2')
R = json.load(open(I2 / 'perflight_summary.json')); n = len(R)
A = lambda k: np.array([np.nan if r.get(k) is None else r[k] for r in R], float)
ate = A('ate'); out = []
P = lambda *a: out.append(' '.join(str(x) for x in a))
P('n', n, 'mean ATE', ate.mean().round(3), 'median', np.median(ate).round(3))
P('\n## horizon table (mean / median over flights)')
P('h | pos | pos_h | |z| | vel | tilt deg | yaw deg(abs) | |bg| | |ba|')
for h in (0.25, 0.5, 1, 2, 5, 10, 20, 40, 'end'):
    f = lambda k, ab=False: (lambda x: (np.nanmean(np.abs(x) if ab else x), np.nanmedian(np.abs(x) if ab else x)))(A(f'{k}_{h}'))
    row = [f('pos'), f('posh'), f('posz', True), f('vel'), f('tilt'), f('yaw', True), f('bg'), f('ba')]
    P(h, ' | '.join(f'{a:.3f}/{b:.3f}' for a, b in row))
P('\n## ATE decomposition: share of squared ATE from vertical', (np.mean(A('ate_v')**2)/np.mean(ate**2)).round(3), 'mean ate_h', A('ate_h').mean().round(3), 'mean ate_v', A('ate_v').mean().round(3))
P('median ate_v/ate_h', np.median(A('ate_v')/A('ate_h')).round(3))
P('\n## growth: slope median', np.nanmedian(A('slope')).round(2), 'IQR', np.nanpercentile(A('slope'), [25, 75]).round(2))
P('median pos err at 2/5/10/20/40/end:', [np.nanmedian(A(f'pos_{h}')).round(3) for h in (2,5,10,20,40,'end')])
P('RPE1 mean', A('rpe1').mean().round(3), 'RPE5', A('rpe5').mean().round(3), 'rel1 median', np.nanmedian(A('rpe1_rel')).round(3), 'rel5', np.nanmedian(A('rpe5_rel')).round(3))
P('scale LS median', np.nanmedian(A('scale')).round(3), 'IQR', np.nanpercentile(A('scale'), [25,75]).round(3), 'plen ratio median', np.nanmedian(A('plen_ratio')).round(3), 'IQR', np.nanpercentile(A('plen_ratio'), [25,75]).round(3))
P('vel err rms mean', A('vel_err_rms').mean().round(3), 'speed err rms', A('spd_err_rms').mean().round(3))
ac = np.array([r['vac'] for r in R]); P('vel-err autocorr lag 5,10,20,40,80,160 frames (frames=0.05 s?) mean', ac.mean(0).round(2))
P('\n## start share: error at 1s,2s vs end; fraction of flights where pos_2 > 0.5*ate')
for h in (0.5, 1, 2, 5): P(h, 'mean pos', np.nanmean(A(f'pos_{h}')).round(3), 'rms-equiv share (pos_h/ATE mean ratio)', (np.nanmean(A(f'pos_{h}'))/ate.mean()).round(3))
# failure concentration
s = np.sort(ate)[::-1]; cs = np.cumsum(s)/s.sum(); P('\nworst 10% share of sum ATE', cs[int(.1*n)-1].round(3), 'worst 25%', cs[int(.25*n)-1].round(3), 'ATE pct 50/90/99', np.percentile(ate,[50,90,99]).round(3))
sq = np.sort(ate**2)[::-1]; P('worst 10% share of sum ATE^2', (np.cumsum(sq)/sq.sum())[int(.1*n)-1].round(3))
# correlations
P('\n## Spearman corr of ATE with variables')
def spearmanr(a,b):
    a=np.argsort(np.argsort(np.asarray(a,float)));b=np.argsort(np.argsort(np.asarray(b,float)));r=np.corrcoef(a,b)[0,1];return r,float('nan')
for k in ('path','spd_mean','spd0','acc_rms','gyro_rms','accel_hf','fov_deg','exposure_s','live_mean','live_lt5','gt_zstd','vz_rms','tilt_mean2','baz_abs2','pos_1','pos_2','vel_1','tilt_5','start_fwd_speed','Ez_off','plen_ratio','scale','rpe1','rpe5'):
    x = A(k); m = np.isfinite(x); rho, p = spearmanr(x[m], ate[m]); P(f'{k}: rho {rho:+.2f} (p={p:.1g}, n={m.sum()})')
# by-class
P('\n## breakdowns (mean ATE, n)')
def br(name, keys, bins=None):
    P(name, '; '.join(f'{k}: {ate[m].mean():.3f} (n={m.sum()})' for k, m in keys))
cls = np.array([r['setting_class'] for r in R]); st = np.array([r['start'] for r in R]); rg = np.array([r['regime'] for r in R])
br('scene', [(c, cls == c) for c in ('room', 'warehouse', 'forest')]); br('start', [(c, st == c) for c in ('hover', 'mid-flight')]); br('regime', [(c, rg == c) for c in ('benchmark', 'free-yaw')])
def q(k, nm, edges):
    edges=list(edges); edges[-1]+=1e-6; x = A(k); br(nm, [(f'{edges[i]}-{edges[i+1]}', (x >= edges[i]) & (x < edges[i+1])) for i in range(len(edges)-1)])
q('spd0', 'initial speed', [0, .1, .5, 1, 1.5, 3]); q('fov_deg', 'FoV', [0, 95, 105, 115, 200]); q('exposure_s', 'exposure s', [-1, .001, .015, .035, 1])
q('gyro_rms', 'gyro rms', list(np.percentile(A('gyro_rms'), [0, 25, 50, 75, 100]).round(2)))
q('acc_rms', 'acc rms', list(np.percentile(A('acc_rms'), [0, 25, 50, 75, 100]).round(2)))
q('path', 'path len', list(np.percentile(A('path'), [0, 25, 50, 75, 100]).round(1)))
q('live_mean', 'mean live tracks', list(np.percentile(A('live_mean'), [0, 25, 50, 75, 100]).round(1)))
for c in ('room','warehouse','forest'):
    m = cls == c; P(c, 'ATE', ate[m].mean().round(3), 'h', A('ate_h')[m].mean().round(3), 'v', A('ate_v')[m].mean().round(3), 'pos_1', np.nanmean(A('pos_1')[m]).round(3), 'pos_end', np.nanmean(A('pos_end')[m]).round(3), 'tilt_5', np.nanmean(A('tilt_5')[m]).round(2), 'plen', A('path')[m].mean().round(1))
# vertical
P('\n## vertical (Q7)')
P('GT z std (m) mean/median', A('gt_zstd').mean().round(3), np.median(A('gt_zstd')).round(3), 'z range mean', A('gt_zrange').mean().round(3), 'vz rms (m/s)', A('vz_rms').mean().round(3), 'speed mean', A('spd_mean').mean().round(3))
P('est z std mean', A('zest_std').mean().round(3))
vg_ = A('vert_gain'); P('vert gain (est/true vertical motion LS) median', np.nanmedian(vg_).round(2), 'IQR', np.nanpercentile(vg_,[25,75]).round(2), 'n', np.isfinite(vg_).sum())
P('Ez: offset |.| mean', np.nanmean(np.abs(A('Ez_off'))).round(3), 'drift rate |.| m/s', np.nanmean(np.abs(A('Ez_drift_rate'))).round(4), 'resid rms', A('Ez_res_rms').mean().round(3), 'Ez_std', A('Ez_std').mean().round(3))
# share of Ez variance by component: ate_v^2 ~ off^2+drift+res (approx) -> compute from stats
P('mean ate_v by gt_zstd tercile:', [A('ate_v')[(lambda x,lo,hi:(x>=lo)&(x<hi))(A('gt_zstd'),lo,hi)].mean().round(3) for lo,hi in zip(np.percentile(A('gt_zstd'),[0,33,67]),np.percentile(A('gt_zstd'),[33,67,100]))])
for k in ('gt_zstd','vz_rms','v0z','tilt_5','tilt_mean2','baz_abs2','pos_1','Ez_end'):
    x = A(k); m = np.isfinite(x); rho, p = spearmanr(np.abs(x[m]) if k in ('v0z','Ez_end') else x[m], A('ate_v')[m]); P(f'ate_v vs {k}: rho {rho:+.2f} p={p:.1g}')
P('corr(|ba| err, |Ez drift|)', spearmanr(A('baz_abs2'), np.abs(A('Ez_drift_rate')))[0].round(2))
P('ate_v by scene:', {c: float(A('ate_v')[cls==c].mean().round(3)) for c in ('room','warehouse','forest')}, 'gt_zstd by scene', {c: float(A('gt_zstd')[cls==c].mean().round(3)) for c in ('room','warehouse','forest')})
P('flat flights (gt_zstd<0.1): n', int((A('gt_zstd')<1.0).sum()), 'ate_v', A('ate_v')[A('gt_zstd')<1.0].mean().round(3), 'est zstd (false vertical motion)', A('zest_std')[A('gt_zstd')<1.0].mean().round(3), 'ate_h', A('ate_h')[A('gt_zstd')<1.0].mean().round(3))
# ceilings: oracle vertical removal -> ATE if z error zero
ate_noz = np.sqrt(np.maximum(ate**2 - A('ate_v')**2, 0)); P('ATE if vertical error zeroed (mean)', ate_noz.mean().round(3), 'vs', ate.mean().round(3))
# yaw
P('yaw err deg end |.| mean', np.nanmean(np.abs(A('yaw_end'))).round(2), 'median', np.nanmedian(np.abs(A('yaw_end'))).round(2))
open(I2 / 'stats.txt', 'w').write('\n'.join(out)); print('\n'.join(out))
