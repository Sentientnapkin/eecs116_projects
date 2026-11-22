"""Dump every episode zip in a directory to the epdump npz format (run with the vio_eval python).

  vio_eval/Scripts/python dump_dir.py --src C:/Users/alexa/vio_data/proxy --out C:/Users/alexa/vio_data/work/proxydump
Keys as disp_teacher/dump_eps.py (gray128, ft, R, p, v, T_bc, K) plus imu (raw rows) and start (crop offset, s).
"""
import argparse, json
from pathlib import Path
import cv2
import numpy as np
from viobench.tools.datasets.storage import read_episode
from viobench.tools.geometry import interpolate_poses, poses_to_matrices


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--src", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for z in sorted(Path(a.src).glob("*.zip")):
        dst = out / f"{z.stem}.npz"
        if dst.exists():
            continue
        meta = json.loads(z.with_suffix(".json").read_text()) if z.with_suffix(".json").exists() else {}
        ep = read_episode(str(z))
        cam, frames = ep.adapt((320, 240))
        gray = np.stack([cv2.resize(cv2.cvtColor(np.asarray(f), cv2.COLOR_RGB2GRAY), (128, 96), interpolation=cv2.INTER_AREA) for f in frames])
        ft = ep.frame_times; gt = ep.ground_truth
        M = poses_to_matrices(interpolate_poses(gt[:, 0], gt[:, 1:8], ft))
        Md = poses_to_matrices(gt[:, 1:8]); vd = np.gradient(Md[:, :3, 3], gt[:, 0], axis=0)
        v = np.stack([np.interp(ft, gt[:, 0], vd[:, i]) for i in range(3)], 1)
        np.savez_compressed(dst, gray=gray, ft=ft, R=M[:, :3, :3], p=M[:, :3, 3], v=v, T_bc=ep.T_body_camera,
                            K=np.array([cam["fx"], cam["fy"], cam["cx"], cam["cy"]]), imu=np.asarray(ep.imu),
                            fold=-1, start=float(meta.get("crop_start_s", 0.0)))
        print("dumped", z.stem, len(gray), flush=True)


if __name__ == "__main__":
    main()
