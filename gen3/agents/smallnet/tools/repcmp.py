"""repcmp.py POOL BASE1,BASE2,... NEW1,NEW2,... : per-flight rep-mean comparison (raw + server-weighted, paired bootstrap CI), peak = max over reps."""
import sys, json, random, statistics as s
sys.path.insert(0, '/data/backups/rganapa/Sebastian/gen3'); 
W = {'room': (12/24, 1/12), 'warehouse': (6/24, 4/6), 'forest': (6/24, 1/6)}
G = '/data/backups/rganapa/Sebastian/gen3/evals/'
pool = sys.argv[1]
def load(names):
    R = [{r['id']: r for r in json.load(open(G + n + '__' + pool + '.json')) if r.get('ate') is not None} for n in names.split(',')]
    ids = set.intersection(*[set(r) for r in R])
    return {i: dict(R[0][i], ate=s.mean(r[i]['ate'] for r in R), peak=max(r[i]['peak'] or 0 for r in R)) for i in ids}
def sw(rows, ids):
    if pool != 'v3val': return float('nan')
    t = 0
    for c, (wc, hv) in W.items():
        h = [rows[i]['ate'] for i in ids if rows[i]['setting_class'] == c and rows[i]['start'] == 'hover']; m = [rows[i]['ate'] for i in ids if rows[i]['setting_class'] == c and rows[i]['start'] != 'hover']
        t += wc * (hv * s.mean(h) + (1 - hv) * s.mean(m))
    return t
A = load(sys.argv[2]); sets = [load(x) for x in sys.argv[3:]]
ids = sorted(set(A).intersection(*[set(b) for b in sets]))
print('flights', len(ids)); print(f"{sys.argv[2][:50]:50s} raw {s.mean(A[i]['ate'] for i in ids):.3f} sw {sw(A, ids):.3f} >3m {sum(A[i]['ate'] > 3 for i in ids)} peak {max(A[i]['peak'] for i in ids)/1e6:.2f}M")
for nm, B in zip(sys.argv[3:], sets):
    d = [B[i]['ate'] - A[i]['ate'] for i in ids]; rng = random.Random(0); bs = []; bsw = []
    for _ in range(2000):
        smp = rng.choices(ids, k=len(ids)); bs.append(s.mean(B[i]['ate'] - A[i]['ate'] for i in smp))
        if pool == 'v3val':
            try: bsw.append(sw(B, smp) - sw(A, smp))
            except Exception: pass
    bs.sort(); bsw.sort()
    ci = f"[{bs[50]:+.3f},{bs[1949]:+.3f}]"; cisw = f"[{bsw[int(.025*len(bsw))]:+.3f},{bsw[int(.975*len(bsw))-1]:+.3f}]" if bsw else ''
    print(f"{nm[:50]:50s} raw {s.mean(B[i]['ate'] for i in ids):.3f} sw {sw(B, ids):.3f} >3m {sum(B[i]['ate'] > 3 for i in ids)} peak {max(B[i]['peak'] for i in ids)/1e6:.2f}M  d raw {s.mean(d):+.3f} {ci}  d sw {sw(B, ids) - sw(A, ids):+.3f} {cisw}")
