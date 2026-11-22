"""Per-flight training cache for the displacement teacher (built from viobench-teacher-data shards).

For every selected record (one longest crop per parent flight; holdout-240 and server-171 scenes excluded,
see work/train_records.json) writes <cache>/<sha20>.img.npy (uint8 [n,96,128], the shard's channel 0 =
current gray 128x96 frame) and <cache>/<sha20>.meta.npz:
  R   [n,3,3] float32  causal estimated body->world attitude (the shard's R)
  P   [n,3]   float64  position in that estimated world frame from trapezoid integration of the TRUE body
                       velocity through the estimated attitudes (relative displacement over <=3 s matches the
                       truth camera displacement to ~0.02 %)
  fxw [n]     float32  fx / width at 128x96 (FOV varies per flight)
  W   [n,3]   float64  true velocity in the estimated world frame (R v_body), for the acceleration-only
                       displacement d - v0 tau that the teacher receives as input
  T_bc [4,4]
Re-runnable: skips flights already cached; processes only shards present on disk.

  python -I build_cache.py --data C:/Users/alexa/vio_data
"""
import argparse, json, os
from pathlib import Path
import numpy as np


def one(src, dst_img, dst_meta):
    with np.load(src, allow_pickle=False) as z:
        img = np.ascontiguousarray(z["images"][:, 0])
        R = z["R"].astype(np.float64)
        v = z["v"].astype(np.float64)
        t = z["times"].astype(np.float64)
        fxw = z["imu"][:, 14].astype(np.float32)
        T_bc = z["T_bc"]
    w = np.einsum("nij,nj->ni", R, v)  # world-estimated velocity
    dt = np.diff(t)[:, None]
    P = np.concatenate([np.zeros((1, 3)), np.cumsum(0.5 * (w[1:] + w[:-1]) * dt, axis=0)])
    np.save(str(dst_img) + ".tmp.npy", img)
    os.replace(str(dst_img) + ".tmp.npy", dst_img)
    np.savez(dst_meta, R=R.astype(np.float32), P=P, W=w, fxw=fxw, T_bc=T_bc, times=t)
    return len(img)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="C:/Users/alexa/vio_data")
    a = ap.parse_args()
    data = Path(a.data)
    cache = data / "work/cache"; cache.mkdir(parents=True, exist_ok=True)
    recs = json.load(open(data / "work/train_records.json"))
    done = new = 0
    for r in recs:
        key = r["file"][:20]
        di, dm = cache / f"{key}.img.npy", cache / f"{key}.meta.npz"
        if di.exists() and dm.exists() and "W" in np.load(dm).files:
            done += 1; continue
        src = data / "teacher-data/shards" / r["file"]
        if not src.exists():
            continue
        try:
            one(src, di, dm); new += 1
        except Exception as e:  # partial download etc.
            print("skip", r["file"], type(e).__name__, e)
    print(f"cached {done + new}/{len(recs)} (+{new})")


if __name__ == "__main__":
    main()
