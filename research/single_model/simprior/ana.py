"""python -B simprior/ana.py ref arm [arm...]   (names without path; fresh tables ftable_<name>.json; search/val from results/single_model/<name>/report.json)
Fresh: dev (folds 0-2) / confirm (3-4) by scene hash; tails; classes; persistence vs ref. Replicate arms: pass names ending _r0 -> uses rep mean."""
import sys, json, hashlib
from pathlib import Path
import numpy as np
H = Path(__file__).resolve().parent; R = H.parents[1] / 'results/single_model'
tf = {r['episode']: r for r in json.load(open(H.parent / 'fresh/truth_feats.json'))}
def fold(r): return int(hashlib.sha256(f"{r['catalog']}:{r['scene']}".encode()).hexdigest()[:8], 16) % 5
def fresh(n):
    p = H / f'ftable_{n}.json'
    if not p.exists(): return None
    return {r['episode']: r for r in json.load(open(p))}
def sv(n):
    p = R / n / 'report.json'
    if not p.exists(): return None
    return {r['e']: r for r in json.load(open(p))['rows_visible']}
def tl(a): a = np.asarray(a); return f'{a.mean():.3f} >3/5/10 {int((a>3).sum())}/{int((a>5).sum())}/{int((a>10).sum())}'
def cls(r):
    t = tf[r['episode']]
    if r['start'] == 'static': return 'static'
    a = t['angle']; s = t['speed0']
    return 'mid<0.5' if s < 0.5 else 'mid a0-45' if a < 45 else 'mid a45-90' if a < 90 else 'mid a>90'
ref = sys.argv[1]
for n in sys.argv[2:]:
    print('=====', n, 'vs', ref)
    a, b = sv(ref), sv(n)
    if a and b:
        for sl in ('search', 'val'):
            for st in ('all', 'static', 'mid'):
                ks = [e for e in b if (('search' if b[e]['fold'] in (0,1,2) else 'val' if b[e]['fold']==3 else 'x') == sl) and (st == 'all' or b[e]['start'] == st)]
                print(f'  {sl:6s} {st:6s} n={len(ks):3d} ref {tl([a[e]["new"] for e in ks])} | arm {tl([b[e]["new"] for e in ks])}')
    fa, fb = fresh(ref), fresh(n)
    if fa and fb:
        ks = sorted(fb)
        for nm, sel in (('all', lambda r: True), ('dev', lambda r: fold(r) <= 2), ('confirm', lambda r: fold(r) >= 3)):
            for st in ('all', 'static', 'mid'):
                k2 = [e for e in ks if sel(fb[e]) and (st == 'all' or fb[e]['start'] == st)]
                print(f'  fresh {nm:7s} {st:6s} n={len(k2):3d} ref {tl([fa[e]["ate"] for e in k2])} | arm {tl([fb[e]["ate"] for e in k2])} | d {np.mean([fb[e]["ate"]-fa[e]["ate"] for e in k2]):+.3f}')
        cl = {}
        for e in ks: cl.setdefault(cls(fb[e]), []).append(e)
        for c, k2 in sorted(cl.items()):
            print(f'  class {c:11s} n={len(k2):3d} ref {tl([fa[e]["ate"] for e in k2])} | arm {tl([fb[e]["ate"] for e in k2])}')
        newf = [e for e in ks if fb[e]['ate'] > 3 and fa[e]['ate'] <= 3]; fixed = [e for e in ks if fa[e]['ate'] > 3 and fb[e]['ate'] <= 3]
        print('  persistence: newly >3', len(newf), [(e[5:], round(fa[e]['ate'], 2), round(fb[e]['ate'], 2)) for e in newf][:12], '| fixed', len(fixed))
        print('  new >10:', [(e, round(fb[e]['ate'], 1)) for e in ks if fb[e]['ate'] > 10 and fa[e]['ate'] <= 10])
