"""Compare a (regenerated) flight's truth to the teammate's feats.json: path length and starting speed.
    python regen_check.py FEATS.json ZIP..."""
import json, os, sys
import numpy as np
from viobench.tools.datasets.sources import episodes
F = json.load(open(sys.argv[1]))
for z in sys.argv[2:]:
    name = os.path.basename(z)[:-4]
    gt = next(episodes([z])).ground_truth_state()
    travel = float(np.sum(np.linalg.norm(np.diff(gt[:, :3], axis=0), axis=1)))
    v0 = float(np.linalg.norm(gt[0, 7:10]))
    f = F.get(name, {})
    print(f"{name}: travel {travel:.2f} (feats {f.get('travel')})  start speed {v0:.3f} (feats speed0 {f.get('speed0')})")
