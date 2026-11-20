"""Track-count and NEES analysis of a TEX_DEBUG run (stderr logs). Usage: analyze.py <results/single_model/NAME> [--nees-only]"""
import sys, json, re, glob, hashlib
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from research.guard_fusion import traj as T
from research.single_model.run_variant import tags, fold, slice_of, ate_rows

def parse(path):
    rows, cnt = [], []
    for ln in Path(path).read_text().splitlines():
        if not ln.startswith('T '): continue
        a, b = ln.split('|')
        rows.append([float(x) for x in a.split()[1:]])
        kv = b.split()
        cnt.append({kv[i]: float(kv[i + 1]) for i in range(0, len(kv), 2)})
    return np.array(rows), cnt

def sym(c6):
    c = np.zeros((len(c6), 3, 3)); k = 0
    for i in range(3):
        for j in range(i, 3):
            c[:, i, j] = c[:, j, i] = c6[:, k]; k += 1
    return c

def nees(err, C):
    out = np.full(len(err), np.nan)
    for i in range(len(err)):
        try: out[i] = err[i] @ np.linalg.solve(C[i], err[i])
        except Exception: pass
    return out

def per_flight(folder):
    tg = tags(); res = {}
    ate = ate_rows(Path(folder) / 'scores.json')
    for e in sorted(ate):
        p = glob.glob(f'{folder}/{e}/report/logs/*/stderr.txt')
        if not p: continue
        rows, cnt = parse(p[0])
        t, truth, _ = T.load_truth(T.DEFAULT_RAW, e)
        n = min(len(rows), len(truth) - 1)
        tr = truth[1:1 + n]
        ep = rows[:n, 1:4] - tr[:, 0:3]; ev = rows[:n, 4:7] - tr[:, 7:10]
        cp = sym(rows[:n, 7:13]); cv = sym(rows[:n, 13:19])
        npos = nees(ep, cp); nvel = nees(ev, cv)
        a = json.loads(Path(f'/data/backups/rganapa/Sebastian/gen/raw-fast/bench/{e}.json').read_text())['audit']
        c = {k: np.array([x[k] for x in cnt[:n]]) for k in cnt[0]}
        res[e] = dict(ate=ate[e], start=tg[e]['start'], scene=tg[e]['scene'], slice=slice_of(fold(tg[e])),
                      dark=a['dark_fraction'], flat=a['flat_fraction'], nees_p=npos, nees_v=nvel, c=c, n=n,
                      verr=np.linalg.norm(ev, axis=1))
    return res

if __name__ == '__main__':
    folder = next(Path(sys.argv[1]).glob('eval/*'))
    r = per_flight(folder)
    import pickle; pickle.dump(r, open(Path(sys.argv[1]) / 'perflight.pkl', 'wb'))
    print(len(r), 'flights')
