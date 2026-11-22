"""ftab.py: final table: per pool/subset mean over available reps, tails >3/5/10 (summed per rep), max peak."""
import json, os, hashlib, numpy as np
T = json.load(open('../fresh/tags.json'))
fold = lambda e: int(hashlib.sha256((T[e]['catalog'] + ':' + T[e]['scene']).encode()).hexdigest()[:8], 16) % 5
def load(n, p):
    for d in ('tables', '../servertail/tables', '../filtcons/tables'):
        f = f'{d}/{n}__{p}.json'
        if os.path.exists(f): return json.load(open(f))
    if p == 'fresh03':
        f = f'../servertail/tables/{n}__fresh_pool.json'
        if os.path.exists(f): return json.load(open(f))
    return None
SETS = [('st2dev', 'st2dev', None), ('st2conf', 'st2conf', None), ('fresh dev f0-2', 'fresh03', 'dev'), ('fresh conf f3', 'fresh03', 'conf'), ('st1dev', 'st1dev', None), ('st1conf', 'st1conf', None)]
ARMS = [('HM40', ['hm40', 'hm40_r1', 'hm40_r2'], {'st1dev': ['hm40b', 'hm40b_r1'], 'st1conf': ['hm40b', 'hm40b_r1']}),
        ('RSOFT', ['rsoft1t0', 'rsoft1t0_r1', 'rsoft1t0_r2'], {'st1dev': ['rsoft1t0s'], 'st1conf': ['rsoft1t0s']}),
        ('kv1 (HM40+KLT_VEL)', ['kv1', 'kv1_r1', 'kv1_r2'], {}), ('eB edgelets', ['eB', 'eB_r1', 'eB_r2'], {}),
        ('lgVHY lines+Manhattan', ['lgVHY', 'lgVHY_r1', 'lgVHY_r2'], {}), ('lYp5', ['lYp5', 'lYp5_r1', 'lYp5_r2'], {}),
        ('lY3K', ['lY3K', 'lY3K_r1', 'lY3K_r2'], {}), ('lY3KR FINAL', ['lY3KR', 'lY3KR_r1', 'lY3KR_r2'], {})]
for an, names, over in ARMS:
    cells = []
    for lab, p, sub in SETS:
        ms, t3, t5, t10, pk, nr = [], 0, 0, 0, 0, 0
        for n in over.get(p, names):
            R = load(n, p)
            if not R: continue
            if sub: R = [r for r in R if fold(r['ep']) != 4 and ((sub == 'dev' and fold(r['ep']) <= 2) or (sub == 'conf' and fold(r['ep']) == 3))]
            a = np.array([r['ate_rmse'] for r in R]); ms.append(a.mean()); t3 += (a > 3).sum(); t5 += (a > 5).sum(); t10 += (a > 10).sum(); pk = max(pk, max(r['peak'] for r in R)); nr += 1
        cells.append('%.4f(%d) %d/%d/%d %.1fM' % (np.mean(ms), nr, t3, t5, t10, pk / 1e6) if ms else '-')
    print('| %s | %s |' % (an, ' | '.join(cells)))
print('cols:', [s[0] for s in SETS], 'cell = mean over reps (n reps) tails>3/5/10 summed over reps, peak')
