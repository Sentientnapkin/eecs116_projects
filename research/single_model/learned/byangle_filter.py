"""ATE by start-velocity heading angle (analysis only; truth from oracle/truth_init.json) for mid flights: base / heading arm / learned arms."""
import json, sys
from pathlib import Path
import numpy as np
R = Path(__file__).resolve().parents[2] / 'results/single_model'
ti = json.load(open(Path(__file__).resolve().parents[1] / 'oracle/truth_init.json'))
arms = ['startup_c2c_head'] + sys.argv[1:]
rows = {a: {r['e']: r for r in json.load(open(R / a / 'report.json'))['rows_visible']} for a in arms}
ang = {}
for e in rows[arms[0]]:
    vb = np.array(ti[e]['vb']); sp = np.linalg.norm(vb)
    if rows[arms[0]][e]['start'] == 'mid' and sp > 0.3: ang[e] = np.degrees(np.arccos(vb[0] / sp))
print('| angle(body x, v0) | n | base | heading prior | ' + ' | '.join(arms[1:]) + ' |'); print('|---|---|---|---|' + '---|' * len(arms[1:]))
for lo, hi in ((0, 45), (45, 90), (90, 181)):
    ks = [e for e in ang if lo <= ang[e] < hi]
    print(f'| {lo}-{hi} deg | {len(ks)} | {np.mean([rows[arms[0]][e]["base"] for e in ks]):.2f} | ' + ' | '.join(f'{np.mean([rows[a][e]["new"] for e in ks]):.2f}' for a in arms) + ' |')
