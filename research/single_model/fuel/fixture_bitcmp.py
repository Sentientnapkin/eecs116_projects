"""Replay each sensor-only fixture through two wasms (full 1200 frames) and compare all pose/twist rows bit for bit."""
import sys, glob, numpy as np
from pathlib import Path
sys.path.insert(0, 'research'); import check_future_poison as C
a, b = Path(sys.argv[1]), Path(sys.argv[2]); tmp = Path('/data/backups/rganapa/Sebastian/tmp/fxcmp'); tmp.mkdir(exist_ok=True)
ok = 0; fx = sorted(glob.glob('research/results/single_model/fuel_preflight/fx_*.npz'))
for i, f in enumerate(fx):
    C.replay(a, Path(f), tmp / f'a{i}.npz', 'full', 600, 1); C.replay(b, Path(f), tmp / f'b{i}.npz', 'full', 600, 1)
    A = np.load(tmp / f'a{i}.npz')['states']; B = np.load(tmp / f'b{i}.npz')['states']
    same = A.shape == B.shape and np.array_equal(A, B); ok += same; print(Path(f).stem, A.shape, 'bit-identical' if same else 'DIFFERENT', flush=True)
print('identical', ok, '/', len(fx))
