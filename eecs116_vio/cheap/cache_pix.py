"""Cache the sparse pixels a 320x240 guest would read: green channel at every 4th pixel (rows 2::4, cols 2::4) -> (F, 60, 80) uint8.

  python cache_pix.py OUT_DIR ZIP...      -> OUT_DIR/<episode>.npz (key "pix"); frame k = the frame step k receives.
Uses the harness's own conversion (Episode.adapt((320, 240)): INTER_AREA from the stored 640x480).
"""
import os, sys
from multiprocessing import Pool
import numpy as np
from viobench.tools.datasets.storage import read_episode

OUT = sys.argv[1]


def one(path):
    name = os.path.basename(path)[:-4]; dst = f"{OUT}/{name}.npz"
    if os.path.exists(dst): return name, "skip"
    try:
        ep = read_episode(path, frames="lazy")
        _, frames = ep.adapt((320, 240))
        pix = np.stack([np.asarray(f)[2::4, 2::4, 1] for f in frames]).astype(np.uint8)
        np.savez_compressed(dst + ".tmp.npz", pix=pix); os.replace(dst + ".tmp.npz", dst)
        return name, "ok"
    except Exception as e:
        return name, f"ERR {type(e).__name__}: {e}"


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    with Pool(int(os.environ.get("J", 12))) as p:
        for n, s in p.imap_unordered(one, sys.argv[2:]):
            if s != "skip": print(n, s, flush=True)
