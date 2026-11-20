"""Pareto table: python pareto.py name1 name2 ... (run names without the fuel_ prefix; uses search+val rows only, never fold 4)."""
import sys, json, glob, numpy as np
sys.path.insert(0, '/data/backups/rganapa/Sebastian/eecs116_projects')
from research.single_model import run_variant as RV
R = RV.OUT; tg = RV.tags()
def load(n):
    p = glob.glob(str(R / f'fuel_{n}/eval/*/scores.json'))[0]
    return {r['episode']: r for r in json.load(open(p))['rows']}
def sl(e): return RV.slice_of(RV.fold(tg[e]))
base = load('base')
print('%-14s %7s %7s %5s %5s | %8s %8s %8s %8s | d_search [95%% CI]' % ('arm','srchATE','valATE','>5','>10','peak(s+v)','medpeak','p95','median'))
for n in sys.argv[1:]:
    try: d = load(n)
    except Exception: print(n, 'missing'); continue
    eps = [e for e in d if sl(e) != 'sealed' and d[e].get('ate_full') is not None]
    S = [e for e in eps if sl(e) == 'search']; V = [e for e in eps if sl(e) == 'val']
    a = lambda E: np.mean([d[e]['ate_full'] for e in E])
    pk = max(d[e]['peak_fuel_per_frame'] for e in eps) / 1e6
    mp = np.median([d[e]['peak_fuel_per_frame'] for e in eps]) / 1e6
    p95 = np.mean([d[e]['p95_fuel_per_frame'] for e in eps]) / 1e6
    md = np.mean([d[e]['median_fuel_per_frame'] for e in eps]) / 1e6
    dm, lo, hi = RV.paired([base[e]['ate_full'] for e in S], [d[e]['ate_full'] for e in S], [tg[e]['scene'] for e in S])
    print('%-14s %7.3f %7.3f %5d %5d | %8.2f %8.2f %8.2f %8.2f | %+.3f [%+.3f,%+.3f]' % (n, a(S), a(V), sum(d[e]['ate_full'] > 5 for e in S), sum(d[e]['ate_full'] > 10 for e in S), pk, mp, p95, md, dm, lo, hi))
