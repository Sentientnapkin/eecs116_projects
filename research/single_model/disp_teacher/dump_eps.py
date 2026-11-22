"""Dump server-calibrated episodes to compact npz for offline teacher checks (run with the vio_eval python).

  vio_eval/Scripts/python dump_eps.py --ids a b c   (or --all-visible)
Per episode: gray128 [n,96,128] (OpenCV RGB2GRAY + INTER_AREA from the guest's 320x240), frame times, truth body
pose (R_wb, p) at frame times, true world velocity, T_body_camera, K at 320x240, imu rows.
"""
import argparse, hashlib, json
from pathlib import Path
import cv2
import numpy as np
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import interpolate_poses, poses_to_matrices

DATA = Path("C:/Users/alexa/vio_data")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--ids", nargs="*"); ap.add_argument("--all-visible", action="store_true")
    a = ap.parse_args()
    eps = json.load(open(DATA / "server-calibrated/manifest.json"))["episodes"]
    fold = lambda e: int(hashlib.sha256((e["catalog"] + ":" + e["scene"]).encode()).hexdigest()[:8], 16) % 5
    sel = [e for e in eps if (a.all_visible and fold(e) != 4) or (a.ids and e["id"] in a.ids)]
    out = DATA / "work/epdump"; out.mkdir(parents=True, exist_ok=True)
    for e in sel:
        dst = out / f"{e['id']}.npz"
        if dst.exists():
            continue
        ep = read_episode(str(DATA / "server-calibrated" / e["file"]))
        cam, frames = ep.adapt((320, 240))
        gray = np.stack([cv2.resize(cv2.cvtColor(np.asarray(f), cv2.COLOR_RGB2GRAY), (128, 96), interpolation=cv2.INTER_AREA) for f in frames])
        ft = ep.frame_times
        gt = ep.ground_truth
        M = poses_to_matrices(interpolate_poses(gt[:, 0], gt[:, 1:8], ft))
        Md = poses_to_matrices(gt[:, 1:8]); vd = np.gradient(Md[:, :3, 3], gt[:, 0], axis=0)
        v = np.stack([np.interp(ft, gt[:, 0], vd[:, i]) for i in range(3)], 1)
        np.savez_compressed(dst, gray=gray, ft=ft, R=M[:, :3, :3], p=M[:, :3, 3], v=v, T_bc=ep.T_body_camera,
                            K=np.array([cam["fx"], cam["fy"], cam["cx"], cam["cy"]]), fold=fold(e),
                            start=float(e.get("start_offset_s", 0)))
        print("dumped", e["id"], len(gray), flush=True)


if __name__ == "__main__":
    main()
