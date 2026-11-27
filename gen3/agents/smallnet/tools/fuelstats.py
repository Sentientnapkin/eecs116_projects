"""fuelstats.py EVALNAME[:POOL] ... : per-frame fuel stats from viobench reports (max / p99 / p95 / median / mean per flight),
aggregated over the flights common to all given evals (restricted to pools/v3val keep list by default)."""
import sys, json, glob, numpy as np
from pathlib import Path
G = Path('/data/backups/rganapa/Sebastian/gen3')
def load(name, pool):
    out = {}
    for d in glob.glob(str(G / 'evals' / name / pool / '*')):
        for rp in glob.glob(d + '/*/report/report.json'):
            try: e = json.load(open(rp))['episodes'][0]
            except Exception: continue
            if e.get('fuel_per_frame_max') is None: continue
            out[Path(rp).parent.parent.name] = [e['fuel_per_frame_max'], e['fuel_per_frame_p99'], e['fuel_per_frame_p95'], e['fuel_per_frame_median'], e['fuel_per_frame_mean']]
    return out
args = [a for a in sys.argv[1:]]
R = []
for a in args:
    n, p = (a.split(':') + ['v3val'])[:2]; R.append((n, load(n, p)))
pool = (args[0].split(':') + ['v3val'])[1]
keep = set(x.stem for x in (G / 'pools' / 'v3val').glob('*.zip')) | set(x.stem for x in (G / 'pools' / 'v1val').glob('*.zip'))
ids = sorted(set.intersection(*[set(r) for _, r in R]) & keep)
print('flights', len(ids))
for n, r in R:
    A = np.array([r[i] for i in ids]) / 1e6
    print(f'{n:28s} max {A[:,0].max():.2f}M  mean-of-flight-max {A[:,0].mean():.2f}  p99(flight max) {np.percentile(A[:,0],99):.2f}  mean p99 {A[:,1].mean():.2f}  mean p95 {A[:,2].mean():.2f}  max p95 {A[:,2].max():.2f}  median {A[:,3].mean():.2f}  mean {A[:,4].mean():.2f}')
