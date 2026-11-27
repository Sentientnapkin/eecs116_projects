"""Fusion rules vs what we would otherwise submit: the PRIMARY FAMILY's single-run average (GSLV replicas for V-primary sets,
linejac replicas for J-primary sets). Paired, scene-bootstrap CI; pools separately and pooled. python vsprim.py"""
import json, numpy as np
from cons_sum import scene, boot, w10
from cons import SETS
RULES = ['mean', 'gm', 'cmed', 'trim', 'wdis', 'medoid', 'ginc_obs0.5', 'gm_obs0.5', 'gm_obs2', 'reanch5']
base = {'V': ['lv_glNP', 'lv_glNP_r1', 'lv_glNP_r2'], 'J': ['lj_ajc', 'lj_ajc_r1', 'lj_ajc_r2']}
J = {p: json.load(open('cons_%s.json' % p)) for p in ['st2conf', 'fconf']}
for sn, mem in SETS.items():
    fam = 'J' if mem[0].startswith('lj') else ('V' if mem[0].startswith('lv_glNP') else None)
    if fam is None: continue
    line = '%-7s' % sn
    for p in ['st2conf', 'fconf', 'both']:
        pools = ['st2conf', 'fconf'] if p == 'both' else [p]
        names = [(q, n) for q in pools for n in sorted(J[q])]; sc = [q + scene(n) for q, n in names]
        b = np.array([np.mean([J[q][n]['single'][r] for r in base[fam]]) for q, n in names])
        best = None
        for r in RULES:
            if r not in J[pools[0]][names[0][1]]['sets'][sn]: continue
            a = np.array([J[q][n]['sets'][sn][r] for q, n in names]); d = 100 * (a.mean() / b.mean() - 1); ci = 100 * boot(a - b, sc, 1000) / b.mean()
            if best is None or d < best[1]: best = (r, d, ci, w10(a), w10(b), (a > 1).sum(), (b > 1).sum())
            if r in ('mean', 'gm') : line += ' | %s %s %+.1f[%+.1f,%+.1f]' % (p, r, d, ci[0], ci[1])
        line += ' | %s best=%s %+.1f w10 %.3f vs %.3f >1m %d vs %.1f' % (p, best[0], best[1], best[3], best[4], best[5], best[6])
    print(line)
