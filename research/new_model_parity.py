"""Actual complete changed-input guest parity on a sensor-only replay fixture."""
import argparse
import ctypes as ct
import json
import os
from pathlib import Path
import sys

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent / "native_odometry"))
from replay import Host
from new_input_reference import NewInputReference
from odometry_eval import model_velocities, load_weights, integrate
from viobench.tools.runner.sandbox import Sandbox


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("build", type=Path)
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    cv2.setNumThreads(1); torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    f = dict(np.load(args.fixture, allow_pickle=False))
    camera = json.loads(str(f["camera_json"]))
    sensor = json.loads(args.manifest.read_text())["sensor_config"]
    ref = NewInputReference(sensor, camera, f["frames"][0].shape[:2], f["T_bc"][:3, :3])
    host = Host(args.build); host.init(camera)
    array = lambda dtype: np.ctypeslib.ndpointer(dtype=dtype, flags="C_CONTIGUOUS")
    host.lib.input_features.argtypes = [array(np.uint8), array(np.float32), array(np.float64), array(np.float64)]
    host.lib.input_features.restype = None
    guest = Sandbox(args.build / "odometry.wasm", log_dir=args.out.parent / (args.out.stem + "-wasm"))
    guest.init(camera)
    debug = guest.instance.exports(guest.store)["input_features"]
    shape = (5, sensor["height"], sensor["width"])
    pointers = [guest.alloc(size) for size in (int(np.prod(shape)), 51 * 4, 9 * 8, 13 * 8)]
    reference, native, wasm = {k: [] for k in ("images", "imu", "R")}, [], []
    host_inputs, wasm_inputs, states, fuels, frame_rows = [], [], [], [], []
    offsets = f["packet_offsets"]
    origin = float(f["absolute_times"][0])
    for i, (t, absolute, frame) in enumerate(zip(f["times"], f["absolute_times"], f["frames"])):
        packet = np.ascontiguousarray(f["packets"][offsets[i]:offsets[i + 1]], dtype=np.float64)
        delivered = packet.copy(); delivered[:, 0] += origin
        out = np.zeros(13, dtype=np.float64)
        if host.lib.step(float(absolute), frame, delivered, len(delivered), out):
            raise RuntimeError(f"Native failed frame {i}")
        result = guest.step(float(absolute), frame, delivered)
        debug(guest.store, *pointers)
        wi = np.frombuffer(guest.read(pointers[0], int(np.prod(shape))), np.uint8).reshape(shape).copy()
        wu = np.frombuffer(guest.read(pointers[1], 51 * 4), np.float32).copy()
        wr = np.frombuffer(guest.read(pointers[2], 9 * 8), np.float64).reshape(3, 3).copy()
        ws = np.frombuffer(guest.read(pointers[3], 13 * 8), np.float64).copy()
        hi, hu, hr, hs = np.empty(shape, np.uint8), np.empty(51, np.float32), np.empty((3, 3)), np.empty(13)
        host.lib.input_features(hi, hu, hr, hs)
        im, u, R, _ = ref.step(float(t), frame, packet)
        for key, value in (("images", im), ("imu", u), ("R", R)): reference[key].append(value)
        native.append(out.copy()); wasm.append(np.r_[result.pose, result.twist]); fuels.append(result.fuel)
        host_inputs.append((hi, hu, hr)); wasm_inputs.append((wi, wu, wr)); states.append((hs, ws))
        frame_rows.append({"frame": i, "time": float(t), "python_cpp_pixels_max": int(np.abs(im.astype(int) - hi).max()),
                           "python_cpp_imu_max": float(np.abs(u - hu).max()), "python_cpp_R_max": float(np.abs(R - hr).max()),
                           "cpp_wasm_R_max": float(np.abs(hr - wr).max()),
                           "python_bias": ref.attitude.bias.tolist(), "cpp_bias": hs[:3].tolist(), "wasm_bias": ws[:3].tolist(),
                           "python_counts": [ref.attitude.accepted, ref.attitude.rejected], "cpp_counts": hs[7:9].tolist(),
                           "wasm_counts": ws[7:9].tolist()})
    reference = {k: np.stack(v) for k, v in reference.items()}
    reference.update(v=np.zeros((len(f["times"]), 3)), times=f["times"], T_bc=f["T_bc"])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    py_v = model_velocities(args.run, load_weights(args.run, "best"), reference, device)
    py_p = integrate(py_v, reference)
    cpp_fixed_v = host.predictions(reference)
    native, wasm, states = np.stack(native), np.stack(wasm), np.asarray(states)
    summary = {"frames": len(native), "python_opencv": cv2.__version__, "model_run": str(args.run),
               "python_cpp_position_max_m": float(np.linalg.norm(py_p - native[:, :3], axis=1).max()),
               "cpp_wasm_position_max_m": float(np.linalg.norm(native[:, :3] - wasm[:, :3], axis=1).max()),
               "python_cpp_fixed_input_velocity_max": float(np.abs(py_v - cpp_fixed_v).max()),
               "python_cpp_imu_max": max(r["python_cpp_imu_max"] for r in frame_rows),
               "python_cpp_R_max": max(r["python_cpp_R_max"] for r in frame_rows),
               "cpp_wasm_R_max": max(r["cpp_wasm_R_max"] for r in frame_rows),
               "python_cpp_pixels_max": max(r["python_cpp_pixels_max"] for r in frame_rows),
               "peak_whole_guest_step_fuel": max(fuels), "first_camera_pose": wasm[0, :7].tolist(),
               "rows": frame_rows}
    args.out.write_text(json.dumps(summary, indent=2) + "\n")
    np.savez_compressed(args.out.with_suffix(".npz"), **reference, native=native, wasm=wasm, states=states, fuels=fuels)
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2), flush=True)


if __name__ == "__main__": main()
