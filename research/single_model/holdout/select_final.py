"""Truth-statistic-only selection of the final holdout (no estimator result is used anywhere).
From the generated candidates in gen/raw-holdout/bench choose 120 static + 120 mid flights without replacement so the
set mean of zero-motion ATE (extent) and travel_m matches the server anchors (4.694 m, 59.6 m) as closely as possible, with
at most CAP flights per scene per start type and a catalog mix close to the selected-171 mix. Seeded local search.
python select_final.py [--n 120]  -> cfg/final_selection.json, final/ symlinks, tags.json
"""
import argparse, glob, json, os, random, collections
import numpy as np
OUT = '/data/backups/rganapa/Sebastian/gen/raw-holdout'
HERE = os.path.dirname(os.path.abspath(__file__))
EXT, PATH = 4.694450928701121, 59.6
BAD = {'stalled', 'travel<2m', 'hover>50%'}

def pick(c, n, cap, rng, iters=60000):
    ext = np.array([d['audit']['zero_motion_ate_m'] for d in c]); trv = np.array([d['audit']['travel_m'] for d in c])
    scene = [d['catalog'] + '|' + d['scene'] for d in c]; cat = [d['catalog'] for d in c]
    maxhv, minhs = int(round(0.17 * n)), int(round(0.2 * n))
    def cost(S):
        S = list(S); me, mt = ext[S].mean(), trv[S].mean()
        sc = collections.Counter(scene[i] for i in S); cc = collections.Counter(cat[i] for i in S)
        pen = sum(max(0, v - cap) for v in sc.values()) * 10 + max(0, cc['hssd-val'] - maxhv) * 10 + max(0, minhs - cc['hssd-train']) * 10
        return ((me - EXT) / 0.02) ** 2 + ((mt - PATH) / 0.2) ** 2 + pen
    # start: tilted weighted sample
    z = (ext - ext.mean()) / ext.std() + (trv - trv.mean()) / trv.std()
    w = np.exp(0.8 * z); w /= w.sum()
    S = list(rng.choice(len(c), n, replace=False, p=w)); inS = set(S); cur = cost(S)
    for it in range(iters):
        i = rng.randrange(n); j = rng.randrange(len(c))
        if j in inS: continue
        old = S[i]; S[i] = j; new = cost(S)
        if new <= cur or rng.random() < np.exp(-(new - cur) / max(0.02, 3 * (1 - it / iters))):
            inS.discard(old); inS.add(j); cur = new
        else: S[i] = old
    return S, cur

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--n', type=int, default=120); ap.add_argument('--cap', type=int, default=3)
    a = ap.parse_args()
    rng = random.Random(7)
    cands = [json.load(open(p)) for p in sorted(glob.glob(OUT + '/bench/*.json'))]
    cands = [d for d in cands if os.path.exists(OUT + '/bench/' + d['file']) and not (set(d['audit']['flags']) & BAD)]
    chosen = []
    for kind, pre in (('static', 'fast-'), ('mid', 'fastmid-')):
        c = [d for d in cands if d['id'].startswith(pre)]
        S, cost = pick(c, a.n, a.cap, rng)
        sel = [c[i] for i in S]
        print(kind, 'candidates', len(c), 'selected', len(sel), 'extent %.3f path %.2f' % (np.mean([d['audit']['zero_motion_ate_m'] for d in sel]), np.mean([d['audit']['travel_m'] for d in sel])), 'cost %.2f' % cost,
              dict(collections.Counter(d['catalog'] for d in sel)))
        chosen += sel
    os.makedirs(OUT + '/final', exist_ok=True)
    tags = {}
    for d in chosen:
        dst = OUT + '/final/' + d['file']
        if not os.path.lexists(dst): os.symlink(OUT + '/bench/' + d['file'], dst)
        tags[d['id']] = dict(scene=d['scene'], catalog=d['catalog'], group=d['group'], start='mid' if d['id'].startswith('fastmid') else 'static', setting=d['setting'])
    json.dump(tags, open(HERE + '/tags.json', 'w'), indent=0)
    json.dump({'selected': sorted(tags), 'targets': {'extent': EXT, 'path': PATH}}, open(OUT + '/cfg/final_selection.json', 'w'), indent=1)
    print('final', len(tags))
main()
