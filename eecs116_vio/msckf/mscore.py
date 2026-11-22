"""Score a host build of an ABI solution (no debug exports needed) on episode zips.

    python mscore.py lib=/path/libX.so EP.zip ...
Prints "name ATE a zeros z" per episode (the format hf_sum.py reads) and caches the estimate to
~/ws_proto/cache/<libname>/<name>_<hash6>.npz (est, gt, t) for trajectory comparisons.
"""
import ctypes
import json
import os
import shutil
import sys
import tempfile

import numpy as np

from viobench.tools.datasets.sources import episodes
from viobench.tools.runner.metrics import evaluate_trajectory

lib_path = next(a[4:] for a in sys.argv[1:] if a.startswith("lib="))
files = [a for a in sys.argv[1:] if not a.startswith("lib=")]
cache = os.path.expanduser(f"~/ws_proto/cache/{os.path.basename(lib_path)[:-3]}")
os.makedirs(cache, exist_ok=True)
rows = []
for k, ep in enumerate(episodes(files)):
    tmp = os.path.join(tempfile.gettempdir(), f"ms_{os.getpid()}_{k}.so")
    shutil.copy(lib_path, tmp)
    lib = ctypes.CDLL(tmp, mode=os.RTLD_LOCAL)
    os.unlink(tmp)
    lib.init.argtypes = [ctypes.c_char_p, ctypes.c_uint32]
    lib.step.argtypes = [ctypes.c_double, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p]
    config, frames = ep.adapt((320, 240))
    text = json.dumps({a: (np.asarray(b).tolist() if isinstance(b, np.ndarray) else b) for a, b in config.items()}).encode()
    if lib.init(text, len(text)) != 0:
        raise RuntimeError("init failed")
    out = np.zeros(13)
    est = []
    for t, f, imu in ep.steps(frames):
        f = np.ascontiguousarray(f, dtype=np.uint8)
        imu = np.ascontiguousarray(imu, dtype=np.float64)
        if lib.step(float(t), f.ctypes.data, imu.ctypes.data, len(imu), out.ctypes.data) != 0:
            raise RuntimeError("step failed")
        est.append(out.copy())
    est = np.array(est)
    gt = ep.ground_truth_state()
    m = evaluate_trajectory(gt, est, ep.frame_times)
    zeros = float(np.sqrt(np.mean(np.sum(gt[:, :3] ** 2, 1))))
    np.savez(f"{cache}/{ep.name}_{str(ep.hash)[:6]}.npz", est=est, gt=gt, t=ep.frame_times)
    rows.append((m.ate_rmse, zeros))
    if hasattr(lib, "prof_report"):
        lib.prof_report()
    print(f"{ep.name[:30]:30s} ATE {m.ate_rmse:5.2f} zeros {zeros:5.2f} | sim3 {m.sim3_ate_rmse:5.2f} scale {m.sim3_scale:4.2f}", flush=True)
print(f"\nMEAN ATE {np.mean([r[0] for r in rows]):.2f}  zeros {np.mean([r[1] for r in rows]):.2f}")
