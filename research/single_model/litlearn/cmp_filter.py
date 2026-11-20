"""Compare net window-displacement error vs the filter's (B11 r0, saved estimate.tum) on 107 fold-3 flights. Rotation-invariant: |d_est - d_truth| over the same frame window.
PYTHONPATH=. python litlearn/cmp_filter.py A 1.0"""
import sys, glob, json, numpy as np
sys.path.insert(0, "/dev/shm/sebastian-vio/viobench")
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.score import load_estimates
from viobench.tools.runner.metrics import fill_missing_states
var, WL = sys.argv[1], float(sys.argv[2]); n = int(WL * 20)
P = json.load(open(f'research/single_model/litlearn/imuvel_pred_{var}_{WL}.json'))
EV = 'research/results/single_model/lc_b11_r0/eval_f3'
rows = []
for ep, v in P.items():
    p = glob.glob(f'{EV}/*/{ep}/report/logs/*/estimate.tum')
    if not p: continue
    e = read_episode(f'/data/backups/rganapa/Sebastian/tmp/lc_fold3_pool/{ep}.zip', frames='none')
    t = np.asarray(e.frame_times); G = np.asarray(e.ground_truth_state())[:, :3]; E = fill_missing_states(load_estimates(p[0], t))[:, :3]
    j = np.array(v['j']); dg = G[j] - G[j - n]; de = E[j] - E[j - n]
    fe = np.linalg.norm(de - dg, axis=1)
    ne = np.linalg.norm(np.array(v['mu']) - np.array(v['y']), axis=1)
    lv = np.array(v['lv']); sd = np.sqrt(np.exp(lv)); z = (np.array(v['mu']) - np.array(v['y'])) / sd
    ate = float(np.sqrt(np.mean(np.sum((E - G) ** 2, 1))))
    # gt window-disp norm (speed)
    sp = np.linalg.norm(dg, axis=1) / WL
    rows.append(dict(ep=ep, ate=ate, fe=fe, ne=ne, t=np.array(v['t']), sp=sp, z=z, sd=sd))
def rms(x): return float(np.sqrt(np.mean(np.concatenate(x) ** 2)))
steady = lambda r: r['t'] > 10
print('flights', len(rows))
print('ALL t>10 s  filter rms %.4f   net rms %.4f' % (rms([r['fe'][steady(r)] for r in rows]), rms([r['ne'][steady(r)] for r in rows])))
print('t<5 s       filter rms %.4f   net rms %.4f' % (rms([r['fe'][r['t'] < 5] for r in rows]), rms([r['ne'][r['t'] < 5] for r in rows])))
print('median per-window: filter %.4f net %.4f' % (np.median(np.concatenate([r['fe'][steady(r)] for r in rows])), np.median(np.concatenate([r['ne'][steady(r)] for r in rows]))))
good = [r for r in rows if r['ate'] < 1.0]; mid = [r for r in rows if 1.0 <= r['ate'] < 3]; bad = [r for r in rows if r['ate'] >= 3]
for lab, g in (('ate<1', good), ('1-3', mid), ('>3', bad)):
    if g: print(lab, len(g), 'filter %.4f net %.4f' % (rms([r['fe'][steady(r)] for r in g]), rms([r['ne'][steady(r)] for r in g])))
# by speed
allr = {k: np.concatenate([r[k][steady(r)] for r in rows]) for k in ('fe', 'ne', 'sp')}
for lo, hi in ((0, .2), (.2, .5), (.5, 1), (1, 1.5), (1.5, 9)):
    m = (allr['sp'] >= lo) & (allr['sp'] < hi)
    if m.sum(): print('speed %.1f-%.1f n=%d filter %.4f net %.4f' % (lo, hi, m.sum(), np.sqrt((allr['fe'][m] ** 2).mean()), np.sqrt((allr['ne'][m] ** 2).mean())))
# fraction of windows where net is better than filter
print('P(net err < filter err) %.3f ; windows where filter err > 0.2 m: n=%d, net better in %.3f' % ((allr['ne'] < allr['fe']).mean(), (allr['fe'] > .2).sum(), (allr['ne'][allr['fe'] > .2] < allr['fe'][allr['fe'] > .2]).mean()))
# calibration of net sd
zz = np.concatenate([r['z'][steady(r)].ravel() for r in rows]); print('net z std %.3f cov1 %.3f' % (zz.std(), (np.abs(zz) < 1).mean()))
# inverse-variance fusion potential (independent-error assumption): combined rms
f, nn_ = allr['fe'], allr['ne']
print('ideal indep fusion rms %.4f' % np.sqrt(1 / (1 / np.mean(f ** 2) + 1 / np.mean(nn_ ** 2))))
# early-warning: does disagreement flag tail flights? max over t of rolling mean of |net-filter| disp diff cannot recompute; use fe proxy: per flight mean fe in first 10 s
for r in rows: r['fe10'] = float(np.mean(r['fe'][r['t'] < 10])); r['ne10'] = float(np.mean(r['ne'][r['t'] < 10]))
ate = np.array([r['ate'] for r in rows]); fe10 = np.array([r['fe10'] for r in rows])
print('corr(ate, filter-window-err first 10s) %.2f' % np.corrcoef(ate, fe10)[0, 1])
print('worst flights:', [(r['ep'], round(r['ate'], 2), round(float(np.sqrt((r['fe'] ** 2).mean())), 3), round(float(np.sqrt((r['ne'] ** 2).mean())), 3)) for r in sorted(rows, key=lambda r: -r['ate'])[:6]])
