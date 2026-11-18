"""Run IMU-only Solution classes (VIOBench step() API) on proxy flights offline; unaligned ATE vs zero output.

    python imu_baselines.py "data/val/*.npz"
"""
import importlib.util, sys, glob
import numpy as np
from common import Flight, ate

VB = "/Users/School/Desktop/Fa26 Berkeley/EECS 116/eecs116_projects/Final Project/viobench/viobench/solution/examples/python/dead_reckoning/solution.py"
OURS = {"instructor dead_reckoning (11/17)": VB}


def load_cls(path):
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    spec = importlib.util.spec_from_file_location("sol_" + str(abs(hash(path))), path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m.Solution


def run(cls, f):
    cfg = {"T_cam_imu": np.linalg.inv(f.T_bc).tolist(), "T_imu_cam": f.T_bc.tolist(), "intrinsics": f.K,
           "camera": {"width": 160, "height": 120}, "imu": {"rate_hz": 200.0}, "frame_rate_hz": 20.0}
    try:
        s = cls(cfg)
    except Exception:
        s = cls(dict(cfg, config=cfg))
    P = []
    for k in range(f.F):
        out = s.step(float(f.ft[k]), None, f.win[k] if k else f.imu[:0])
        P.append(np.asarray(out[:3], float))
    return np.array(P)


def main():
    fl = [Flight(p) for p in sorted(glob.glob(sys.argv[1]))]
    print(f"{len(fl)} flights; unaligned ATE")
    print(f"  {'zero output':36s} {np.mean([ate(np.zeros_like(f.cam_gt), f.cam_gt) for f in fl]):.3f}")
    for name, path in OURS.items():
        try:
            cls = load_cls(path)
            r = [ate(run(cls, f), f.cam_gt) for f in fl]
            print(f"  {name:36s} {np.mean(r):.3f}  (median {np.median(r):.3f}, max {np.max(r):.1f})")
        except Exception as e:
            print(f"  {name:36s} failed: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
