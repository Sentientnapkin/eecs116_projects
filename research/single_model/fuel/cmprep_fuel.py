"""cmprep_fuel.py ref arm [arm..] : per-flight mean over chaos replicates fuel_<n>_r0..2 (search & val), paired scene bootstrap of arm-ref."""
import sys, json, glob, numpy as np
sys.path.insert(0, '/data/backups/rganapa/Sebastian/eecs116_projects')
from research.single_model import run_variant as RV
tg = RV.tags()
def load(n):
    out = []
    for i in range(3):
        p = glob.glob(str(RV.OUT / f'fuel_{n}_r{i}/eval/*/scores.json'))
        if not p: return None
        out.append({r['episode']: r for r in json.load(open(p[0]))['rows']})
    return out
ref = load(sys.argv[1])
for n in sys.argv[2:]:
    new = load(n)
    if new is None: print(n, 'incomplete'); continue
    for sl in ('search', 'val'):
        ks = [e for e in new[0] if RV.slice_of(RV.fold(tg[e])) == sl and new[0][e].get('ate_full') is not None]
        x = [np.mean([r[e]['ate_full'] for r in ref]) for e in ks]; y = [np.mean([r[e]['ate_full'] for r in new]) for e in ks]
        d, lo, hi = RV.paired(x, y, [tg[e]['scene'] for e in ks])
        per = lambda rr: [round(float(np.mean([r[e]['ate_full'] for e in ks])), 3) for r in rr]
        c10 = lambda rr: [sum(r[e]['ate_full'] > 10 for e in ks) for r in rr]
        pk = max(r[e]['peak_fuel_per_frame'] for r in new for e in new[0] if RV.slice_of(RV.fold(tg[e])) != 'sealed') / 1e6
        print(f'{n:10s} {sl:6s} n={len(ks):3d} ref {np.mean(x):.3f} arm {np.mean(y):.3f} | d {d:+.3f} [{lo:+.3f},{hi:+.3f}] | reps ref {per(ref)} arm {per(new)} | >10m ref {c10(ref)} arm {c10(new)} | peak {pk:.2f}M')
