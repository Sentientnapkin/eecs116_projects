"""Trigger analysis: compare RB_DEBUG replicate runs (results/single_model/rb_dbg_r{k}) on the high-variance flights."""
import json, re, sys, numpy as np
from pathlib import Path
from collections import Counter
R = Path('/data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model')
HERE = Path(__file__).resolve().parent
K = 5
def load(k):
    sc = sorted((R / f'rb_dbg_r{k}/eval').glob('*/scores.json'))[-1]
    d = json.loads(sc.read_text()); out = {}
    for r in d['rows']:
        e = r['episode']
        if r.get('ate_full') is None: continue
        g = sc.parent / e / 'report/logs'
        tum = next(g.glob('*/estimate.tum')); err = next(g.glob('*/stderr.txt'))
        P = np.loadtxt(tum)[:, 1:4]
        D = []
        for line in err.read_text().splitlines():
            if line.startswith('D '):
                kv = dict(x.split('=') for x in line[2:].split())
                D.append({a: (float(b) if ',' not in b else b) for a, b in kv.items()})
        out[e] = (r['ate_full'], P, D)
    return out
reps = [load(k) for k in range(K)]
base = {r['episode']: r for r in json.loads((HERE / 'out/B7/replicates_fresh.json').read_text())['rows']}
res = []
KEYS = ['kf', 'fbd', 'tri', 'gate', 'used', 'att']
for e in sorted(set.intersection(*[set(r) for r in reps])):
    ates = [r[e][0] for r in reps]
    a, b = int(np.argmin(ates)), int(np.argmax(ates))
    if ates[b] - ates[a] < 0.5: continue
    Pa, Pb = reps[a][e][1], reps[b][e][1]; Da, Db = reps[a][e][2], reps[b][e][2]
    n = min(len(Pa), len(Pb)); d = np.linalg.norm(Pa[:n] - Pb[:n], axis=1)
    fdiv = int(np.argmax(d > 0.2)) if (d > 0.2).any() else -1
    nd = min(len(Da), len(Db))
    def diff(i):  # D index i == frame i+1
        x, y = Da[i], Db[i]
        s = [kk for kk in KEYS if x[kk] != y[kk]]
        fl = [kk for kk in ('mov', 'rel', 'hold') if x[kk] != y[kk]]
        return s, fl
    fsplit, stype, fl_ = -1, None, None
    for i in range(nd):
        s, fl = diff(i)
        if s or fl:
            fsplit = i + 1; stype = (s, fl); break
    # jump frame
    inc = np.diff(d[:(fdiv + 1 if fdiv > 0 else n)]) if n > 1 else np.zeros(1)
    fjump = int(np.argmax(inc)) + 1 if len(inc) else -1
    # classify jump
    jt = None
    if fjump > 0 and fjump - 1 < nd:
        s, fl = diff(fjump - 1); jt = (s, fl)
        s2, fl2 = diff(fjump - 2) if fjump >= 2 else ([], [])
    # lockout in the worse run
    run = best = 0
    for x in Db:
        if x['used'] == 0 and x['att'] >= 3: run += 1; best = max(best, run)
        else: run = 0
    near_split = None
    if fsplit > 0: near_split = (Da[fsplit - 1]['near'], Db[fsplit - 1]['near'])
    # position of d at split frame
    res.append(dict(episode=e, ates=ates, best=a, worst=b, fdiv=fdiv, fsplit=fsplit, split_keys=stype[0] if stype else None, split_flags=stype[1] if stype else None,
                    d_at_split=float(d[fsplit]) if 0 < fsplit < n else None, fjump=fjump, jump_keys=jt[0] if jt else None, jump_flags=jt[1] if jt else None,
                    jump_size=float(inc[fjump - 1]) if fjump > 0 and len(inc) >= fjump else None, near=near_split, lockout=best,
                    start=base[e]['start'], t_split=Da[fsplit - 1]['t'] if fsplit > 0 and fsplit - 1 < len(Da) else None))
(HERE / 'out/B7/triggers.json').write_text(json.dumps(res, indent=0, default=str))
def typ(keys, flags):
    if flags: return 'flag:' + '+'.join(flags)
    if not keys: return 'none'
    ks = set(keys)
    for t, nm in (('tri', 'triangulation'), ('gate', 'chi2-gate'), ('used', 'chi2-gate/used'), ('fbd', 'FB-drop'), ('kf', 'KLT-fail'), ('att', 'track-lifetime')):
        if t in ks: return nm
L = []
P = lambda *x: L.append(' '.join(map(str, x)))
P(f'{len(res)} hv flights with best/worst replicate gap >= 0.5 m (of {len(set.intersection(*[set(r) for r in reps]))} debug-run hv flights); never-diverged (no d>0.2): {sum(r["fdiv"]<0 for r in res)}')
P('first discrete split between best and worst replicate (type = first counter that differs):')
c = Counter(typ(r['split_keys'], r['split_flags']) for r in res); [P(f'  {k}: {v}') for k, v in c.most_common()]
P('  detail (counter sets): ', Counter(tuple(r['split_keys'] or []) + tuple(r['split_flags'] or []) for r in res).most_common(8))
P(f'  split frame median {np.median([r["fsplit"] for r in res if r["fsplit"]>0]):.0f}; divergence>0.2m frame median {np.median([r["fdiv"] for r in res if r["fdiv"]>0]):.0f}; d at split median {np.nanmedian([r["d_at_split"] for r in res if r["d_at_split"] is not None]):.4f} m')
P('largest single-frame jump in best-worst distance (before reaching 0.2 m): type at that frame:')
c = Counter(typ(r['jump_keys'], r['jump_flags']) for r in res if r['jump_keys'] is not None or r['jump_flags'] is not None); [P(f'  {k}: {v}') for k, v in c.most_common()]
P(f'  jump size median {np.median([r["jump_size"] for r in res if r["jump_size"]]):.3f} m, share of flights whose divergence is a >0.1 m single-frame jump: {np.mean([(r["jump_size"] or 0)>0.1 for r in res]):.2f}')
P(f'lock-out (>=40 consecutive frames with >=3 features attempted and 0 used in the worse replicate): {sum(r["lockout"]>=40 for r in res)} / {len(res)}; max run median {np.median([r["lockout"] for r in res]):.0f}')
st = Counter(r['start'] for r in res); P('start types', dict(st))
P('time of divergence (frame of d>0.2): <3 s (60 frames) %d, 3-10 s %d, 10-30 s %d, >30 s %d' % tuple(sum(a <= r['fdiv'] < b for r in res) for a, b in ((0, 60), (60, 200), (200, 600), (600, 5000))))
(HERE / 'out/B7/triggers.txt').write_text('\n'.join(L) + '\n'); print('\n'.join(L))
