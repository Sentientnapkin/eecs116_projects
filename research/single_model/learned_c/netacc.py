"""Direct accuracy of the C net on the evaluation flights (anchor 0 = what the filter sees): fold 0-3 of the 171 selected + 107 fold-3 unselected.
  netacc.py <weights dir> <tag>   -> tables/netacc_<tag>.json {episode: mu(3) sd(3) truth(3)} headK (velocity at frame 5, body frame)"""
import sys, subprocess, json, struct
from pathlib import Path
import numpy as np, cv2
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, '/dev/shm/sebastian-vio/viobench'); sys.path.insert(0, str(HERE.parents[2]))
import parity_lib as PL
wdir, tag = sys.argv[1], sys.argv[2]
F = json.load(open(HERE / 'feats.json'))
SEL = '/data/backups/rganapa/Sebastian/gen/raw-fast/selected'; F3 = '/data/backups/rganapa/Sebastian/tmp/lc_fold3_pool'
items = [(SEL if v['selected'] else F3, e) for e, v in sorted(F.items())]
res = PL.run_c(wdir, items)
json.dump(res, open(HERE / 'tables' / f'netacc_{tag}.json', 'w'))
err = np.array([np.linalg.norm(np.array(v['mu']) - np.array(v['truth'])) for v in res.values()])
mid = np.array([F[e]['start'] == 'mid' for e in res])
print(tag, 'n', len(res), 'headK err all %.3f static %.3f mid %.3f' % (err.mean(), err[~mid].mean(), err[mid].mean()))
