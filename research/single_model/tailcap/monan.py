"""Monitor feature analysis on the TC_LOG run: per flight early-window features vs final ATE>3 (B11 base labels, same flights)."""
import sys, glob, json
import numpy as np
sys.path.insert(0, 'research/single_model/tailcap')
import summ
HERE = 'research/single_model/tailcap'
def parse(p):
    R = []
    for ln in open(p, errors='replace'):
        if ln.startswith('D '):
            kv = {}
            for tok in ln[2:].split():
                k, v = tok.split('='); kv[k] = [float(x) for x in v.split(',')] if ',' in v else float(v)
            R.append(kv)
    return R
tab = {(r['set'], r['episode']): r['ate'] for r in json.load(open(f'{HERE}/tables/log_r0.json'))}
rows = []
for (st, ep), ate in tab.items():
    f = glob.glob(f'research/results/single_model/tc_log_r0/eval_{st}/*/{ep}/report/logs/*/stderr.txt')
    if not f or ate is None: continue
    L = parse(f[0])
    if len(L) < 100: continue
    t = np.array([l['t'] for l in L]); col = lambda k: np.array([l[k] for l in L])
    live, used, u20, sp, psp, Pv, nis = col('live'), col('used'), col('u20'), col('sp'), col('psp'), col('Pv'), col('nis')
    def w(a, t0, t1, fn): m = (t >= t0) & (t < t1); return float(fn(a[m])) if m.any() else np.nan
    d = dict(ep=ep, st=st, ate=ate, tail=ate > 3)
    for (a, b) in ((0, 1), (1, 2), (2, 3), (3, 5), (5, 10)):
        d[f'live_{a}'] = w(live, a, b, np.mean); d[f'u_{a}'] = w(used, a, b, np.mean); d[f'pv_{a}'] = w(Pv, a, b, np.mean); d[f'nis_{a}'] = w(nis, a, b, np.mean)
        d[f'sp_{a}'] = w(sp, a, b, np.mean)
        rat = sp / np.maximum(np.where(psp > 0, psp, np.nan), 0.2); d[f'rat_{a}'] = w(rat, a, b, lambda x: np.nanmean(x))
    d['live_all_med'] = float(np.median(live)); d['frac_live_lt25'] = float((live[t > 3] < 25).mean())
    d['u20min_1_3'] = w(u20, 1, 3, np.min)
    rows.append(d)
json.dump(rows, open(f'{HERE}/monan_rows.json', 'w'))
print(len(rows), 'flights;', sum(r['tail'] for r in rows), 'tails')
keys = [k for k in rows[0] if k not in ('ep', 'st', 'ate', 'tail')]
for k in keys:
    a = np.array([r[k] for r in rows if r['tail']]); b = np.array([r[k] for r in rows if not r['tail']])
    a = a[~np.isnan(a)]; b = b[~np.isnan(b)]
    # AUC tail vs non-tail
    allv = np.concatenate([a, b]); rk = allv.argsort().argsort() + 1; auc = (rk[:len(a)].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b))
    print(f'{k:16s} tail med {np.median(a):7.2f} ok med {np.median(b):7.2f}  AUC {auc:.2f}')
