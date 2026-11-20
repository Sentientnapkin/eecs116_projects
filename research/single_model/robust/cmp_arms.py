"""python -m research.single_model.robust.cmp_arms B7 rb_soft ...  -> table of variance metrics (dev/confirm/all)."""
import json, sys, numpy as np
from pathlib import Path
from research.single_model import run_variant as RV
H = Path(__file__).resolve().parent
def load(n):
    d = json.loads((H / 'out' / n / 'replicates_fresh.json').read_text()); return {r['episode']: r for r in d['rows']}
names = sys.argv[1:]; B = load(names[0]); eps = sorted(B)
def met(D, sel):
    A = np.array([D[e]['reps'] for e in sel]); R = A.shape[1]; m = A.mean(0)
    sd = A.std(axis=1, ddof=1); hv = sum(1 for e in sel if D[e]['high_variance'])
    return dict(n=len(sel), mean=m.mean(), spread=m.std(ddof=1), rng=m.max() - m.min(), fstd=sd.mean(), hv=hv, g3=(A > 3).sum(0).mean(), g5=(A > 5).sum(0).mean(), med=np.median(A.mean(1)), p95=np.percentile(A.mean(1), 95), R=R)
tg = {e: B[e]['scene'] for e in eps}
for part, sel in (('dev', [e for e in eps if B[e]['split'] == 'dev']), ('confirm', [e for e in eps if B[e]['split'] == 'confirm']), ('all', eps)):
    print(f'--- {part} (n={len(sel)})')
    print(f'{"arm":12s} R  mean   spread rng   fstd  hv  >3  >5  med   p95  | paired d(mean) vs {names[0]} [95% scene CI]')
    for n in names:
        D = load(n); s2 = [e for e in sel if e in D]; m = met(D, s2)
        if n == names[0]: pd = ''
        else:
            dm, lo, hi = RV.paired([B[e]['mean'] for e in s2], [D[e]['mean'] for e in s2], [tg[e] for e in s2], n=2000); pd = f'{dm:+.3f} [{lo:+.3f},{hi:+.3f}]'
        print(f'{n:12s} {m["R"]}  {m["mean"]:.3f}  {m["spread"]:.3f} {m["rng"]:.3f} {m["fstd"]:.3f} {m["hv"]:3d} {m["g3"]:4.1f} {m["g5"]:4.1f} {m["med"]:.3f} {m["p95"]:.2f} | {pd}')
