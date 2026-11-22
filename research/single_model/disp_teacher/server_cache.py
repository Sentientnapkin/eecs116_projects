"""Server-calibrated flights (epdump npz, dump_eps.py) -> training-cache entries, for domain fine-tuning.

  python -I server_cache.py --folds 0 1     -> work/server_records_f01.json (+ cache files in work/cache)
Only the listed folds are written. Folds 2-3 stay for in-filter evaluation, fold 4 is sealed.
Attitude R = truth (training adds 0.4 deg derotation noise and tilt noise like for the teacher-data flights).
"""
import argparse, glob, hashlib, json
from pathlib import Path
import numpy as np

DATA = Path("C:/Users/alexa/vio_data")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--folds", type=int, nargs="+", required=True)
    a = ap.parse_args()
    eps = {e["id"]: e for e in json.load(open(DATA / "server-calibrated/manifest.json"))["episodes"]}
    recs = []
    for f in sorted(glob.glob(str(DATA / "work/epdump/*.npz"))):
        ep = Path(f).stem; z = np.load(f)
        if int(z["fold"]) not in a.folds:
            continue
        key = hashlib.sha256(("srv:" + ep).encode()).hexdigest()[:20]
        di, dm = DATA / f"work/cache/{key}.img.npy", DATA / f"work/cache/{key}.meta.npz"
        if not (di.exists() and dm.exists()):
            np.save(di, z["gray"])
            K = z["K"]; n = len(z["gray"])
            np.savez(dm, R=z["R"].astype(np.float32), P=z["p"], W=z["v"], fxw=np.full(n, K[0] * 0.4 / 128, np.float32),
                     T_bc=z["T_bc"], times=z["ft"])
        recs.append({"file": key + "_srv.npz", "scene": eps[ep]["scene"], "episode": ep, "fold": int(z["fold"])})
    out = DATA / f"work/server_records_f{''.join(map(str, a.folds))}.json"
    json.dump(recs, open(out, "w"), indent=1)
    print("wrote", out, len(recs), "flights")


if __name__ == "__main__":
    main()
