"""Summarise cons_POOL.json: mean / worst-10% / >3 m per rule vs single runs, scene-bootstrap CI of paired change vs
member-average single ATE. python cons_sum.py"""
import json, os, re
import numpy as np
from cons import SETS, RUNS

D = os.path.dirname(os.path.abspath(__file__))
SHOW = ['mean', 'cmed', 'gm', 'gm_obs0.5', 'gm_obs1', 'gm_obs2', 'gm_obs4', 'gm_obs8', 'vint', 'ginc_obs0.5', 'ginc_obs2', 'ginc_obs8', 'ginc_inf',
        'mean_obs2', 'trim', 'trim_obs2', 'wdis', 'wdis_obs2', 'wgm_obs2', 'wvel_obs2', 'reanch1', 'reanch5', 'medoid']
rng = np.random.default_rng(0)


def scene(n):
    m = re.search(r'(\d+)-\d+$', n)
    return m.group(1) if m else n


def boot(diff, sc, B=2000):
    us = sorted(set(sc)); idx = {u: np.where(np.array(sc) == u)[0] for u in us}; out = []
    for _ in range(B):
        pick = rng.choice(us, len(us)); ii = np.concatenate([idx[u] for u in pick]); out.append(diff[ii].mean())
    return np.percentile(out, [2.5, 97.5])


def w10(a): s = np.sort(a)[::-1]; return s[:max(1, int(round(0.1 * len(a))))].mean()


summary = {}
for pool in ['st2conf', 'fconf']:
    J = json.load(open(D + '/cons_%s.json' % pool)); names = sorted(J); sc = [scene(n) for n in names]
    print('\n######## pool %s  flights %d' % (pool, len(names)))
    single = {r: np.array([J[n]['single'][r] for n in names]) for r in RUNS}
    for r in RUNS:
        print('  single %-11s mean %.4f  w10 %.3f  >3m %d  vel-rms %.3f' % (r, single[r].mean(), w10(single[r]), (single[r] > 3).sum(),
                                                                         np.mean([J[n]['vsingle'][r] for n in names])))
    L = np.log(np.stack([single[r] for r in RUNS]))
    C = np.corrcoef(L); print('  per-flight log-ATE corr: V-V %.2f  J-J %.2f  M-M %.2f  V-J %.2f  V-M %.2f  J-M %.2f' % (
        np.mean([C[0, 1], C[0, 2], C[1, 2]]), np.mean([C[3, 4], C[3, 5], C[4, 5]]), np.mean([C[6, 7], C[6, 8], C[7, 8]]),
        C[0:3, 3:6].mean(), C[0:3, 6:9].mean(), C[3:6, 6:9].mean()))
    summary[pool] = {}
    for sn, mem in SETS.items():
        avg = np.mean([single[r] for r in mem], 0); best = np.min([single[r] for r in mem], 0)
        print('  --- set %s (%s) K=%d | member-avg single %.4f w10 %.3f >3m %.1f | primary %s %.4f | hindsight best-of %.4f (%+.1f%%) | vgm-rms %.3f' % (
            sn, '+'.join(mem), len(mem), avg.mean(), np.mean([w10(single[r]) for r in mem]), np.mean([(single[r] > 3).sum() for r in mem]),
            mem[0], single[mem[0]].mean(), best.mean(), 100 * (best.mean() / avg.mean() - 1), np.mean([J[n]['sets'][sn]['_vgm_rms'] for n in names])))
        summary[pool][sn] = {'avg': avg.mean(), 'best': best.mean()}
        for rule in SHOW:
            if rule not in J[names[0]]['sets'][sn]: continue
            a = np.array([J[n]['sets'][sn][rule] for n in names])
            ci = boot(a - avg, sc)
            summary[pool][sn][rule] = dict(mean=a.mean(), w10=w10(a), gt3=int((a > 3).sum()), d=100 * (a.mean() / avg.mean() - 1), ci=list(100 * ci / avg.mean()))
            print('     %-11s %.4f (%+5.1f%% [%+5.1f,%+5.1f])  w10 %.3f  >3m %d  wins-vs-avg %d/%d' % (
                rule, a.mean(), 100 * (a.mean() / avg.mean() - 1), 100 * ci[0] / avg.mean(), 100 * ci[1] / avg.mean(), w10(a), (a > 3).sum(),
                (a < avg).sum(), len(a)))
json.dump(summary, open(D + '/cons_summary.json', 'w'), default=float, indent=0)
