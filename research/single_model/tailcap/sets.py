"""Honest evaluation sets for tailcap. python -B research/single_model/tailcap/sets.py  -> writes sets.json and symlink pools."""
import hashlib, json, os, sys
from pathlib import Path
sys.path.insert(0, '.'); sys.path.insert(0, 'research/single_model/learned_c')
import split2
HERE = Path(__file__).resolve().parent
FRESH = Path('/data/backups/rganapa/Sebastian/tmp/fresh_pool')
def fold(c, s): return int(hashlib.sha256(f'{c}:{s}'.encode()).hexdigest()[:8], 16) % 5
rows = split2.load_rows()
train = {(r['catalog'], r['scene']) for r in rows if r['role'] == 'train'}
tags = json.load(open('research/single_model/fresh/tags.json'))
out = {}
for ep, t in tags.items():
    k = (t['catalog'], t['scene']); f = fold(*k)
    out[ep] = dict(scene=t['scene'], catalog=t['catalog'], start=t['start'], fold=f, in_train=k in train)
json.dump(out, open(HERE / 'fresh_sets.json', 'w'))
import collections
c = collections.Counter((v['fold'], v['in_train']) for v in out.values()); print('fresh (fold,in_train): n', sorted(c.items()))
honest = {e: v for e, v in out.items() if not v['in_train']}
print('honest fresh', len(honest), 'dev(f0-2)', sum(v['fold'] < 3 for v in honest.values()), 'confirm(f3-4)', sum(v['fold'] >= 3 for v in honest.values()))
for nm, sel in (('fresh_dev', lambda v: v['fold'] < 3), ('fresh_conf', lambda v: v['fold'] >= 3)):
    d = HERE / ('pool_' + nm); d.mkdir(exist_ok=True)
    for e, v in honest.items():
        if sel(v):
            for ext in ('zip', 'json'):
                p = d / f'{e}.{ext}'
                if not p.exists(): os.symlink(FRESH / f'{e}.{ext}', p)
