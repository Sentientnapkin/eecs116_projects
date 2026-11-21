"""Pool-level comparison of runpool runs vs B16 r0 (diag table).  python pcmp.py run1,run2 pools"""
import sys, json, glob
import numpy as np
D = {r['episode']: r['ate'] for r in json.load(open('research/single_model/lateinit/diag_tc_b16r_r0_all.json'))}
runs = sys.argv[1].split(','); pools = sys.argv[2].split(',')
for p in pools:
    res = {}
    for run in runs:
        f = glob.glob(f'research/results/single_model/{run}/eval_{p}/*/scores.json')
        if not f: continue
        res[run] = {r['episode']: r['ate_full'] for r in json.load(open(f[0]))['rows']}
    eps = sorted(set.intersection(*[set(v) for v in res.values()]), key=lambda e: -D[e])
    print(f'== {p} n={len(eps)} B16 mean {np.mean([D[e] for e in eps]):.3f} | ' + ' '.join(f'{r} {np.mean([res[r][e] for e in eps]):.3f}' for r in res))
    if '-v' in sys.argv:
        for e in eps: print(f'{e[:34]:34s} {D[e]:5.2f} ' + ' '.join(f'{res[r][e]:5.2f}' for r in res))
