"""Summarize comp_POOL.pkl -> text tables (stdout) + comp_summary_POOL.json.
python comp_report.py POOL [DEVPOOL_FOR_BLEND_WEIGHTS]"""
import sys, pickle, json, itertools, os
import numpy as np
H = os.path.dirname(os.path.abspath(__file__))
pool = sys.argv[1]; dev = sys.argv[2] if len(sys.argv) > 2 else None
D = pickle.load(open(H + '/comp_%s.pkl' % pool, 'rb')); fams = D['fams']; res = D['res']; names = sorted(res)
fr = dict(fams); F = [f for f, _ in fams]
# peak fuel (M) per family: from NOTES/LOOP_LOG (typical/max peak on dev pools; approximate)
PEAK = {'GSLV': 6.8, 'LJA': 4.8, 'LJB4': 4.1, 'GSLM': 7.0, 'LGVHY': 7.0, 'LYPK': 7.0, 'RSOFT': 4.0, 'RSLV': 4.0, 'HM40': 4.0,
        'HM40P': 4.0, 'HFG': 4.0, 'B17X': 16.1, 'BM40': 15.3, 'EDGE': 5.4, 'KV1': 4.0, 'G24M': 3.0, 'C30M': 4.0, 'C30': 4.0,
        'L8': 7.2, 'GB6': 6.0, 'K30': 4.0, 'C34': 4.2, 'OVINS': 4200.0, 'SLBASE': 6.8, 'SLPILOT': 6.7, 'SLPMM': 7.1}
A = {r: np.nan_to_num(np.array([res[n]['ate'][r] for n in names]), nan=999.0) for _, rs in fams for r in rs}
mem = lambda f, i: fr[f][i] if len(fr[f]) > i else fr[f][0]
reps = lambda f: range(min(3, len(fr[f])))
fam_ate = {f: np.mean([A[r] for r in fr[f]], 0) for f in F}          # per-flight mean over replicas
ref = 'GSLV' if 'GSLV' in F else 'HFG'
nt = max(1, int(round(0.1 * len(names))))
T = np.argsort(-fam_ate[ref])[:nt]                                     # tail set: worst 10% by reference family (3-rep mean)
out = {'pool': pool, 'n': len(names), 'tail_ref': ref, 'tail_n': nt}
print('POOL %s  flights %d  tail = worst %d by %s (3-rep mean)' % (pool, len(names), nt, ref))
print('\n[single families]  mean over reps of pool-mean ATE; tail mean; >1m/>3m per rep; replica log-ATE corr; replica err-vector corr')
single = {}
for f in F:
    rs = fr[f]; m = np.mean([A[r].mean() for r in rs]); t = np.mean([A[r][T].mean() for r in rs])
    g1 = np.mean([(A[r] > 1).sum() for r in rs]); g3 = np.mean([(A[r] > 3).sum() for r in rs])
    rc = [np.corrcoef(np.log(A[a]), np.log(A[b]))[0, 1] for a, b in itertools.combinations(rs, 2)]
    ev = [np.mean([res[n]['evc'].get((a, b), res[n]['evc'].get((b, a))) for n in names]) for a, b in itertools.combinations(rs, 2)]
    single[f] = dict(mean=m, tail=t, gt1=g1, gt3=g3, reps=len(rs), rep_logcorr=float(np.mean(rc)) if rc else None,
                     rep_evc=float(np.mean(ev)) if ev else None, peak=PEAK.get(f))
    print('  %-8s reps %d  mean %.4f  tail %.3f  >1m %.1f >3m %.1f  repcorr %s  repEVC %s  peak~%sM' % (
        f, len(rs), m, t, g1, g3, '%.2f' % np.mean(rc) if rc else '  - ', '%.2f' % np.mean(ev) if ev else '  - ', PEAK.get(f)))
out['single'] = single
# family x family correlation (avg over rep index)
def fcorr(a, b):
    return float(np.mean([np.corrcoef(np.log(A[mem(a, i)]), np.log(A[mem(b, i)]))[0, 1] for i in range(3)]))
def fevc(a, b):
    v = []
    for i in range(3):
        ra, rb = mem(a, i), mem(b, i)
        v.append(np.mean([res[n]['evc'].get((ra, rb), res[n]['evc'].get((rb, ra))) for n in names]))
    return float(np.mean(v))
C = {(a, b): fcorr(a, b) for a, b in itertools.combinations(F, 2)}
E = {(a, b): fevc(a, b) for a, b in itertools.combinations(F, 2)}
print('\n[family log-ATE correlation matrix (upper) / error-vector corr (lower)]')
print('         ' + ' '.join('%6s' % f[:6] for f in F))
for x in F:
    row = []
    for y in F:
        if x == y: row.append('   -  ')
        elif (x, y) in C: row.append('%6.2f' % C[(x, y)])
        else: row.append('%6.2f' % E[(y, x)])
    print('  %-6s ' % x[:6] + ' '.join(row))
out['corr'] = {'%s|%s' % k: v for k, v in C.items()}; out['evc'] = {'%s|%s' % k: v for k, v in E.items()}
# sets
keys = ['hind', 'w5s', 'w1s', 'frame', 'mean', 'median', 'medoid']
rows = []
for K in (2, 3, 4):
    for S in itertools.combinations(F, K):
        idx = [i for i in range(3) if (i, S) in res[names[0]]['sets']]
        acc = {k: [] for k in keys}; acct = {k: [] for k in keys}; bs = []; bst = []; avgs = []
        for i in idx:
            M = np.stack([A[mem(f, i)] for f in S])
            per = {'hind': M.min(0)}
            for k in keys[1:]: per[k] = np.nan_to_num(np.array([res[n]['sets'][(i, S)][k] for n in names]), nan=999.0)
            for k in keys: acc[k].append(per[k].mean()); acct[k].append(per[k][T].mean())
            bs.append(M.mean(1).min()); bst.append(M[:, T].mean(1).min()); avgs.append(M.mean())
        b, bt = np.mean(bs), np.mean(bst)
        r = dict(set='+'.join(S), K=K, nrep=len(idx), best_single=b, best_single_tail=bt, avg_single=float(np.mean(avgs)),
                 corr=float(np.mean([C[p] for p in itertools.combinations(S, 2)])),
                 evc=float(np.mean([E[p] for p in itertools.combinations(S, 2)])),
                 peak=float(sum(PEAK.get(f, np.nan) for f in S)))
        if K == 2: acc['medoid'] = acc['mean']; acct['medoid'] = acct['mean']   # medoid undefined for K=2
        for k in keys:
            r[k] = float(np.mean(acc[k])); r[k + '_g'] = 1 - r[k] / b
            r[k + '_t'] = float(np.mean(acct[k])); r[k + '_tg'] = 1 - r[k + '_t'] / bt
        r['causal_best'] = min(('mean', 'median', 'medoid') if K > 2 else ('mean',), key=lambda k: r[k])
        rows.append(r)
out['sets'] = rows
def show(title, sel, n=15):
    print('\n[%s]' % title)
    print('  %-26s K rp  corr  evc  best1   hind(g)        w5s(g)        w1s(g)        mean(g)       med(g)        medoid(g)     | tail best1 hind(g) causal(g)' % 'set')
    for r in sel[:n]:
        cb = r['causal_best']
        print('  %-26s %d %d  %.2f %.2f  %.3f  %.3f(%+5.1f%%) %.3f(%+5.1f%%) %.3f(%+5.1f%%) %.3f(%+5.1f%%) %.3f(%+5.1f%%) %.3f(%+5.1f%%) | %.3f %.3f(%+5.1f%%) %s %.3f(%+5.1f%%)' % (
            r['set'][:26], r['K'], r['nrep'], r['corr'], r['evc'], r['best_single'],
            r['hind'], 100 * r['hind_g'], r['w5s'], 100 * r['w5s_g'], r['w1s'], 100 * r['w1s_g'], r['mean'], 100 * r['mean_g'],
            r['median'], 100 * r['median_g'], r['medoid'], 100 * r['medoid_g'],
            r['best_single_tail'], r['hind_t'], 100 * r['hind_tg'], cb[:3], r[cb + '_t'], 100 * r[cb + '_tg']))
ex = lambda r: 'OVINS' not in r['set']
pairs = [r for r in rows if r['K'] == 2 and ex(r)]
show('pairs ranked by hindsight gain', sorted(pairs, key=lambda r: -r['hind_g']))
show('pairs with corr<0.6 and hindsight gain>=12% (ranked by causal mean gain)',
     sorted([r for r in pairs if r['corr'] < 0.6 and r['hind_g'] >= 0.12], key=lambda r: -r['mean_g']))
show('pairs ranked by causal mean gain', sorted(pairs, key=lambda r: -r['mean_g']))
for K in (3, 4):
    sk = [r for r in rows if r['K'] == K and ex(r)]
    show('K=%d ranked by best causal gain' % K, sorted(sk, key=lambda r: -r[r['causal_best'] + '_g']))
    show('K=%d ranked by hindsight gain' % K, sorted(sk, key=lambda r: -r['hind_g']), 8)
    show('K=%d ranked by absolute best causal ATE' % K, sorted(sk, key=lambda r: r[r['causal_best']]), 8)
top = min(F, key=lambda f: single[f]['mean'])
for K in (2, 3):
    sk = [r for r in rows if r['K'] == K and ex(r) and top in r['set'].split('+')]
    show('K=%d containing best single family %s, ranked by best causal ATE' % (K, top), sorted(sk, key=lambda r: r[r['causal_best']]), 10)
    show('K=%d containing %s, ranked by hindsight ATE' % (K, top), sorted(sk, key=lambda r: r['hind']), 6)
show('pairs/sets containing OVINS', sorted([r for r in rows if not ex(r) and r['K'] == 2], key=lambda r: -r['hind_g']), 6)
# replicate ensembles
print('\n[replicate (chaos) ensembles, 3 reps of one build]  avg single | hind3 | w1s | mean3 | median3 | medoid3 | mean2 (r0+r1) | tail avg single / mean3')
rep = {}
for f in F:
    if len(fr[f]) < 3: continue
    M = np.stack([A[r] for r in fr[f]]); s = M.mean()
    v = {k: np.array([res[n]['rep'][f][k] for n in names]) for k in res[names[0]]['rep'][f]}
    rep[f] = dict(avg_single=float(s), hind=float(M.min(0).mean()), **{k: float(x.mean()) for k, x in v.items()},
                  tail_single=float(M[:, T].mean()), tail_mean3=float(v['mean'][T].mean()), tail_hind=float(M[:, T].min(0).mean()))
    print('  %-8s %.4f | %.4f (%+5.1f%%) | %.4f (%+5.1f%%) | %.4f (%+5.1f%%) | %.4f (%+5.1f%%) | %.4f (%+5.1f%%) | %.4f (%+5.1f%%) | tail %.3f -> %.3f (%+5.1f%%), hind %.3f' % (
        f, s, rep[f]['hind'], 100 * (rep[f]['hind'] / s - 1), rep[f]['w1s'], 100 * (rep[f]['w1s'] / s - 1),
        rep[f]['mean'], 100 * (rep[f]['mean'] / s - 1), rep[f]['median'], 100 * (rep[f]['median'] / s - 1),
        rep[f]['medoid'], 100 * (rep[f]['medoid'] / s - 1), rep[f]['mean2'], 100 * (rep[f]['mean2'] / s - 1),
        rep[f]['tail_single'], rep[f]['tail_mean3'], 100 * (rep[f]['tail_mean3'] / rep[f]['tail_single'] - 1), rep[f]['tail_hind']))
out['rep'] = rep
# blend weights chosen on dev pool, applied here
if dev:
    Dd = pickle.load(open(H + '/comp_%s.pkl' % dev, 'rb')); rd = Dd['res']; nd = sorted(rd)
    print('\n[fixed-weight pair blend: w chosen on %s (min mean ATE over w=0..1 avg reps), applied on %s]' % (dev, pool))
    bl = []
    for r in pairs:
        S = tuple(r['set'].split('+'))
        if any(f not in dict(Dd['fams']) for f in S): continue
        idx = [i for i in range(3) if (i, S) in rd[nd[0]]['blend']]
        cd = np.mean([np.mean([rd[n]['blend'][(i, S)] for n in nd], 0) for i in idx], 0)
        w = int(np.argmin(cd))
        here = np.mean([np.mean([res[n]['blend'][(i, S)][w] for n in names]) for i in idx])
        bl.append(dict(set=r['set'], w=w / 10, dev_gain=1 - cd[w] / min(cd[0], cd[10]), ate=float(here), best_single=r['best_single'],
                       gain=1 - here / r['best_single'], mean_g=r['mean_g']))
    bl.sort(key=lambda x: -x['gain'])
    for x in bl[:12]:
        print('  %-26s w(first)=%.1f dev gain %+5.1f%% -> %s %.4f vs best single %.4f (%+5.1f%%; w=0.5 %+5.1f%%)' % (
            x['set'], x['w'], 100 * x['dev_gain'], pool, x['ate'], x['best_single'], 100 * x['gain'], 100 * x['mean_g']))
    out['blend'] = bl
json.dump(out, open(H + '/comp_summary_%s.json' % pool, 'w'), indent=0, default=float)
