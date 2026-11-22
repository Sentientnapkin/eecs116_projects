"""Offline sweep of the output-only settings (VERT_SCALE, HORIZ_SCALE) on cached HF runs.
Picks the best pair on the TUNE scenes, reports it on CHECK.  python post_sweep.py libvio_hf_NAME ...
(offline the vertical is the first camera's y axis; the C code uses the measured gravity direction)"""
import glob, json, os, sys, zlib
import numpy as np
H = os.path.dirname(os.path.abspath(__file__))
scenes = {e["scene"] for e in json.load(open(f"{H}/manifest.json"))["episodes"]}
ate = lambda a, b: np.sqrt(np.mean(np.sum((a - b) ** 2, 1)))
VS, HS = [1.0, 0.5, 0.35, 0.25, 0.15, 0.0], [0.9, 1.0, 1.1, 1.2, 1.3]
for lib in sys.argv[1:]:
    tune, check = [], []
    for f in sorted(glob.glob(os.path.expanduser(f"~/ws_proto/cache/{lib}/*.npz"))):
        scene = os.path.basename(f).split("_", 1)[0] if False else os.path.basename(f)[len("native-campaign-"):].rsplit("_", 1)[0][:-len("-0000")]
        assert scene in scenes, scene
        d = np.load(f); grid = np.zeros((len(VS), len(HS)))
        p, q = d["est"][:, :3], d["gt"][:, :3]
        for i, v in enumerate(VS):
            for j, h in enumerate(HS):
                grid[i, j] = ate(p * [h, v, h], q)
        (tune if zlib.crc32(scene.encode()) % 2 == 0 else check).append(grid)
    T, C = np.mean(tune, 0), np.mean(check, 0)
    i, j = np.unravel_index(np.argmin(T), T.shape)
    print(f"{lib:28s} n {len(tune)}/{len(check)}  as is: tune {T[0,1]:.3f} check {C[0,1]:.3f}   "
          f"best on tune: vert {VS[i]} horiz {HS[j]} -> tune {T[i,j]:.3f} check {C[i,j]:.3f}")
