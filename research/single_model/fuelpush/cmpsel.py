import json, sys, hashlib, numpy as np
from pathlib import Path
H = Path(__file__).resolve().parent
meta = {}
for l in open(H.parents[1] / 'campaign/perflight.jsonl'):
    r = json.loads(l); meta[r['episode']] = int(hashlib.sha256((r['catalog'] + ':' + r['scene']).encode()).hexdigest()[:8], 16) % 5
for n in sys.argv[1:]:
    c = {r['episode']: r['ate'] for r in json.load(open(H / 'tables' / f'sel_{n}.json')) if r['ate'] is not None}
    b = {r['episode']: r['ate'] for r in json.load(open(H.parent / __import__('os').environ.get('SBASE','tailcap/tables/b16r_r0.json'))) if r.get('set') == 'sel' and r['ate'] is not None}
    for nm, fs in (('search', (0, 1, 2)), ('val', (3,))):
        e = [x for x in c if x in b and meta.get(x) in fs]
        C = np.array([c[x] for x in e]); B = np.array([b[x] for x in e])
        print('%s sel %s n=%d B16 %.3f cand %.3f d=%+.3f >3 B16 %d cand %d' % (n, nm, len(e), B.mean(), C.mean(), (C - B).mean(), (B > 3).sum(), (C > 3).sum()))
