"""Summaries of tables/<name>_r*.json on the evaluation sets.  python summ.py name[,name2...] [--reps K]"""
import json, sys, glob
import numpy as np
from pathlib import Path
HERE = Path(__file__).resolve().parent
FS = json.load(open(HERE / 'fresh_sets.json'))
FEATS = json.load(open(HERE / '../learned_c/feats.json'))
def groups(rows):
    g = {}
    for r in rows:
        e = r['episode']
        if r['set'] == 'fresh':
            f = FS[e]['fold']; g.setdefault('fresh_dev(f0-2)' if f < 3 else 'fresh_f3' if f == 3 else 'fresh_f4', []).append(e)
            g.setdefault('fresh_conf(f3-4)' if f >= 3 else 'x', []).append(e)
            g.setdefault('fresh_all', []).append(e)
            g.setdefault('fresh_static' if FS[e]['start'] == 'static' else 'fresh_mid', []).append(e)
        else:
            F = FEATS[e]; fo = F['fold']
            g.setdefault('sel_search(f0-2)' if fo < 3 else 'sel_val(f3)', []).append(e)
    g.pop('x', None)
    return g
def load(name, reps=None):
    fs = sorted(glob.glob(str(HERE / 'tables' / f'{name}_r[0-9].json')))
    if reps: fs = fs[:reps]
    T = [{(r['set'], r['episode']): r for r in json.load(open(f))} for f in fs]
    return T
def table(name, reps=None, ref=None):
    T = load(name, reps); k = len(T)
    keys = sorted(set.intersection(*[set(t) for t in T]))
    rows = [dict(episode=e, set=s) for s, e in keys]
    ate = {key: np.mean([t[key]['ate'] for t in T]) for key in keys}
    allv = {key: [t[key]['ate'] for t in T] for key in keys}
    G = groups(rows); out = {}
    for gname, eps in G.items():
        st = 'fresh' if gname.startswith('fresh') else 'sel'
        v = np.array([ate[(st, e)] for e in eps]); allr = np.array([allv[(st, e)] for e in eps])  # n x k
        out[gname] = dict(n=len(v), mean=float(v.mean()), med=float(np.median(v)), gt3=float((allr > 3).sum(0).mean()), gt5=float((allr > 5).sum(0).mean()), gt10=float((allr > 10).sum(0).mean()),
                          fuel=float(max((t[(st, e)]['peak_fuel'] or 0) for t in T for e in eps) / 1e6))
    return k, out
if __name__ == '__main__':
    names = sys.argv[1].split(','); reps = None
    for nm in names:
        k, out = table(nm, reps)
        print(f'== {nm} (reps {k}; counts are per-replicate means)')
        for g, o in out.items():
            print(f'  {g:18s} n={o["n"]:3d} mean {o["mean"]:.3f} med {o["med"]:.2f} >3: {o["gt3"]:.1f} >5: {o["gt5"]:.1f} >10: {o["gt10"]:.1f} peak {o["fuel"]:.1f} M')
