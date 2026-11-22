import json, sys, numpy as np
R = json.load(open(sys.argv[1]))
g = lambda k: np.array([r[k] if r[k] is not None else np.nan for r in R], float)
ne, fe, sp, live, u20, pv, tex, sig = g('nerr'), g('ferr'), g('spd'), g('live'), g('u20'), g('pv'), g('tex'), g('sig')
z = np.array([r['z'] for r in R])
def show(name, m):
    if m.sum() < 20: return
    print('%-28s n %6d  net %.3f (rms %.3f)  filter %.3f (rms %.3f)  net<filter %.2f  sig %.3f zrms %.2f' % (name, m.sum(), ne[m].mean(), np.sqrt((ne[m]**2).mean()), np.nanmean(fe[m]), np.sqrt(np.nanmean(fe[m]**2)), (ne[m] < fe[m]).mean(), sig[m].mean(), np.sqrt((z[m]**2).mean())))
show('all', np.ones(len(R), bool))
for lo, hi in [(0, 10), (10, 20), (20, 40), (40, 999)]: show(f'live {lo}-{hi}', (live >= lo) & (live < hi))
for lo, hi in [(0, 1), (1, 10), (10, 40), (40, 9999)]: show(f'u20 {lo}-{hi}', (u20 >= lo) & (u20 < hi))
for lo, hi in [(0, .1), (.1, .25), (.25, .5), (.5, 9)]: show(f'Pv {lo}-{hi}', (pv >= lo) & (pv < hi))
for lo, hi in [(0, .3), (.3, 1), (1, 2), (2, 3), (3, 9)]: show(f'speed {lo}-{hi}', (sp >= lo) & (sp < hi))
for lo, hi in [(0, .03), (.03, .07), (.07, .15), (.15, 1)]: show(f'tex {lo}-{hi}', (tex >= lo) & (tex < hi))
show('starved live<20 & spd>1', (live < 20) & (sp > 1))
show('filter err > 0.5', fe > 0.5)
show('filter err > 1.0', fe > 1.0)
