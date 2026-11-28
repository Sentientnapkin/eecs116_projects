"""parity.py EV_DIR CACHE_DIR: per-episode wasm ATE (EV_DIR/episodes.json from build.sh eval) vs fit_cheap.py's model."""
import json, os, sys
import numpy as np
import fit_cheap as fc
eps = json.load(open(os.path.join(sys.argv[1], "episodes.json")))
w = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights.npy"))
d = []
for e in eps:
    p = os.path.join(os.path.expanduser(sys.argv[2]), e["name"] + ".npz")
    if not os.path.exists(p): continue
    z = np.load(p); f = {k: z[k] for k in z.files}
    d.append((e["metrics"]["ate_rmse"], fc.ate(f, *fc.prep(f), w), e["name"]))
d = np.array([(a, b) for a, b, _ in d])
print(f"n={len(d)} wasm mean {d[:,0].mean():.4f} python mean {d[:,1].mean():.4f} max |diff| {np.abs(d[:,0]-d[:,1]).max():.2e}")
