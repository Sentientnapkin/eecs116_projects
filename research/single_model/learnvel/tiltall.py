import sys, glob, json, numpy as np
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, '.')
from tilt import series
run, pool, tab = sys.argv[1], sys.argv[2], sys.argv[3]
T = {r['ep']: r for r in json.load(open(tab))}
def one(ep):
    e = glob.glob(f'{run}/*/{ep}/report/logs/*/estimate.tum')[0]; o = series(e, f'{pool}/{ep}.zip')
    return ep, float(o[:, 1].mean()), float(np.percentile(o[:, 1], 90)), float(o[:, 2].mean())
with ProcessPoolExecutor(32) as ex: R = list(ex.map(one, sorted(T)))
a = np.array([T[e]['ate_rmse'] for e, *_ in R]); tm = np.array([r[1] for r in R]); t90 = np.array([r[2] for r in R]); rot = np.array([r[3] for r in R])
print('corr log ATE vs log mean tilt %.2f, vs log rot %.2f' % (np.corrcoef(np.log(a), np.log(tm))[0, 1], np.corrcoef(np.log(a), np.log(rot))[0, 1]))
for lo, hi in [(0, .3), (.3, .6), (.6, 1), (1, 2), (2, 99)]:
    m = (a >= lo) & (a < hi); print('ATE %.1f-%.1f n %3d mean tilt %.2f deg  p90 tilt %.2f  mean rot %.2f' % (lo, hi, m.sum(), tm[m].mean(), t90[m].mean(), rot[m].mean()))
json.dump(R, open(sys.argv[4], 'w'))
