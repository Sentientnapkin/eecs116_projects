"""Inventory: run -> pool -> number of flights with estimate.tum (excludes holdout_*). Writes inventory.json."""
import os, json
from multiprocessing import Pool
R = '/data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model/'
POOLS = ['st2dev', 'st2conf', 'st1dev', 'st1conf', 'probe', 'fdev', 'fconf', 'st3']
def one(run):
    out = {}
    for p in POOLS:
        d = R + run + '/' + p
        if not os.path.isdir(d): continue
        names = set()
        for sub in os.scandir(d):
            if not sub.is_dir(): continue
            for fl in os.scandir(sub.path):
                lg = fl.path + '/report/logs'
                if os.path.isdir(lg):
                    for h in os.scandir(lg):
                        if os.path.exists(h.path + '/estimate.tum'): names.add(fl.name); break
        if names: out[p] = sorted(names)
    return run, out
if __name__ == '__main__':
    runs = sorted(r for r in os.listdir(R) if not r.startswith('holdout') and os.path.isdir(R + r))
    with Pool(32) as p: res = dict(p.map(one, runs))
    res = {k: v for k, v in res.items() if v}
    json.dump(res, open(os.path.dirname(os.path.abspath(__file__)) + '/inventory.json', 'w'))
    for p in POOLS:
        rs = [(k, len(v[p])) for k, v in res.items() if p in v]
        print(p, len(rs), 'runs')
