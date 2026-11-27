"""rep3.py A_names B_names : per-flight mean ATE over replicates (comma-separated eval names, gen3/evals/NAME__v3val.json or POOL via --pool),
paired d = B - A on flights common to all, bootstrap 95% CI, per-class, peaks (max over reps)."""
import sys, json, random, statistics as s
G = '/data/backups/rganapa/Sebastian/gen3/evals/'
pool = sys.argv[sys.argv.index('--pool') + 1] if '--pool' in sys.argv else 'v3val'
def load(names):
    D = [{r['id']: r for r in json.load(open(f'{G}{n}__{pool}.json')) if r.get('ate') is not None} for n in names.split(',')]
    ids = set.intersection(*[set(d) for d in D])
    return {i: s.mean(d[i]['ate'] for d in D) for i in ids}, D, ids
a, DA, pa = load(sys.argv[1]); b, DB, pb = load(sys.argv[2]); ids = sorted(set(a) & set(b)); pa = max(d[i]['peak'] or 0 for d in DA for i in ids); pb = max(d[i]['peak'] or 0 for d in DB for i in ids)
meta = DA[0]
d = [b[i] - a[i] for i in ids]; r = random.Random(0)
bs = sorted(s.mean(r.choices(d, k=len(d))) for _ in range(4000))
cls = lambda key: {c: (round(s.mean(a[i] for i in ids if meta[i][key] == c), 3), round(s.mean(b[i] for i in ids if meta[i][key] == c), 3)) for c in sorted(set(str(meta[i][key]) for i in ids)) for _ in [0] if True} if False else None
out = {}
for key in ('setting_class', 'start'):
    for c in sorted(set(meta[i][key] for i in ids)):
        sel = [i for i in ids if meta[i][key] == c]; out[c] = f"{s.mean(a[i] for i in sel):.3f}->{s.mean(b[i] for i in sel):.3f}"
print(f"n {len(ids)} reps {len(DA)}/{len(DB)}  A {s.mean(a[i] for i in ids):.3f}  B {s.mean(b[i] for i in ids):.3f}  d {s.mean(d):+.4f} [{bs[100]:+.4f},{bs[3899]:+.4f}]"
      f"  >3m A {sum(a[i] > 3 for i in ids)} B {sum(b[i] > 3 for i in ids)}  peak A {pa/1e6:.2f}M B {pb/1e6:.2f}M  {out}")
