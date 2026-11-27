"""fuel.py NAME POOL: per-run fuel stats (peak, p95 over all frames, mean) + finiteness from gen3/evals/NAME/POOL/*/ reports."""
import sys, glob, json, numpy as np
from pathlib import Path
G = Path('/data/backups/rganapa/Sebastian/gen3/evals'); name, pool = sys.argv[1], sys.argv[2]
ids = [r['id'] for r in json.load(open(G / f'{name}__{pool}.json'))]
allf = []; bad = 0; n = 0
for d in sorted(glob.glob(str(G / name / pool / f'{name}-*/'))):
    pass
dirs = sorted(glob.glob(str(G / name / pool / f'{name}-*')), key=lambda p: Path(p).stat().st_mtime)[-1:]
for i in ids:
    for f in glob.glob(f'{dirs[0]}/{i}/report/logs/*/fuel.npy'):
        allf.append(np.load(f)); n += 1
    for t in glob.glob(f'{dirs[0]}/{i}/report/logs/*/estimate.tum'):
        a = np.loadtxt(t)
        if not np.all(np.isfinite(a)): bad += 1
a = np.concatenate(allf)
print(f'{name} {pool}: flights {n} peak {a.max()/1e6:.3f}M p99 {np.percentile(a,99)/1e6:.3f}M p95 {np.percentile(a,95)/1e6:.3f}M mean {a.mean()/1e6:.3f}M nonfinite-traj {bad}')
