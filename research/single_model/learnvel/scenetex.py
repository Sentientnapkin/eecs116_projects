"""per-scene texture (fraction of strong-gradient pixels in gray128) over lc_cache flights -> tables/scenetex.json"""
import sys, json, numpy as np, collections
from pathlib import Path
sys.path.insert(0, '../learned_c'); sys.path.insert(0, '../learned')
import split2
rows = [r for r in split2.load_rows() if r['role'] in ('train', 'val')]
C = Path('/data/backups/rganapa/Sebastian/tmp/lc_cache'); S = collections.defaultdict(list)
for r in rows:
    f = C / f"{r['name']}.npz"
    if not f.exists(): continue
    x = np.load(f)['frames0'][::4].astype(np.float32)
    gx = np.abs(x[:, 1:-1, 2:] - x[:, 1:-1, :-2]); gy = np.abs(x[:, 2:, 1:-1] - x[:, :-2, 1:-1])
    t = (np.maximum(gx, gy) > 8).mean((1, 2))
    S[(r['catalog'], r['scene'])].append((float(t.mean()), float((t < 0.03).mean()), r['fold']))
out = {f'{c}|{s}': dict(tex=np.mean([a for a, b, f in v]), lowfrac=np.mean([b for a, b, f in v]), n=len(v), fold=v[0][2]) for (c, s), v in S.items()}
json.dump(out, open('tables/scenetex.json', 'w'), indent=0)
for k, v in sorted(out.items(), key=lambda kv: kv[1]['tex'])[:40]: print(k, '%.3f %.2f n%d f%d' % (v['tex'], v['lowfrac'], v['n'], v['fold']))
