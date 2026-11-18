"""Compare PyTorch, native C++, and metered WebAssembly on frozen development inputs."""
import argparse
import ctypes as ct
import json
import os
from pathlib import Path
import sys

import cv2
import numpy as np
import torch
from viobench.tools.datasets.storage import read_episode
from viobench.tools.runner.engine import Engine
from viobench.tools.runner.sandbox import Sandbox

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import Flight
from odometry_data import load_row
from odometry_eval import integrate, load_weights, metrics, model_velocities
from pairs import digest
from streaming import Inputs


class Host:
    def __init__(self, build):
        self.lib = ct.CDLL(str((build / "host.so").resolve()))
        array = lambda dtype: np.ctypeslib.ndpointer(dtype=dtype, flags="C_CONTIGUOUS")
        u8, f32, f64 = (array(dtype) for dtype in (np.uint8, np.float32, np.float64))
        self.lib.host_weights.argtypes = [f32]
        self.lib.host_weights.restype = None
        self.lib.init.argtypes = [ct.c_char_p, ct.c_uint32]
        self.lib.step.argtypes = [ct.c_double, u8, f64, ct.c_int32, f64]
        self.lib.host_features.argtypes = [u8, f32, f64]
        self.lib.host_features.restype = None
        self.lib.host_net_step.argtypes = [u8, f32, f32]
        self.lib.host_net_step.restype = None
        self.lib.host_reset_net.argtypes = []
        self.lib.host_reset_net.restype = None
        self.weights = np.fromfile(build / "weights.f32", dtype="<f4")
        self.lib.host_weights(self.weights)

    def init(self, camera):
        config = json.dumps(camera).encode()
        if self.lib.init(config, len(config)):
            raise RuntimeError("Host init failed")

    def predictions(self, row):
        self.lib.host_reset_net()
        out = np.empty((len(row["times"]), 3), dtype=np.float32)
        for im, imu, v in zip(row["images"], row["imu"], out):
            self.lib.host_net_step(im, imu, v)
        return out.astype(np.float64)


def ate(estimate, row):
    return metrics(estimate, row["cam_gt"], row["times"])["ate"]


def max_abs(a, b):
    return float(np.max(np.abs(a - b)))


def position_delta(a, b):
    return float(np.linalg.norm(a - b, axis=1).max())


def write_row(rows, row):
    rows.append(row)
    print(json.dumps(row, allow_nan=False), flush=True)


def prepared(args, host, manifest, weights):
    from viobench.tools.abi.config import default_guest_config
    rows = []
    host.init(default_guest_config())
    for record in manifest["datasets"]["development"]:
        row = load_row(args.manifest.parent.parent / "shards", record)
        py_v = model_velocities(args.run, weights, row, "cpu")
        cpp_v = host.predictions(row)
        py_p, cpp_p = integrate(py_v, row), integrate(cpp_v, row)
        vel_delta, pos_delta = max_abs(cpp_v, py_v), position_delta(cpp_p, py_p)
        write_row(rows, dict(scene=record["scene"], crop_s=record["crop_s"], shard=record["file"],
                             frames=len(cpp_v), pytorch_ate=ate(py_p, row), cpp_ate=ate(cpp_p, row),
                             velocity_delta_max_mps=vel_delta, position_delta_max_m=pos_delta,
                             passed=vel_delta <= .0002 and pos_delta <= .002))
    return rows


def raw_roster(manifest):
    records = manifest["records"]
    if any(r["split"] != "dev" or not r["flight_id"].startswith("dev-") for r in records):
        raise ValueError("Use the campaign development manifest")
    for catalog in ("procthor", "hssd-val"):
        matches = [r for r in records if r["catalog"] == catalog and r["seconds"] == 30]
        first = min(r["flight_id"] for r in matches)
        crops = sorted((r for r in matches if r["flight_id"] == first), key=lambda r: r["crop_s"])
        if [r["crop_s"] for r in crops] != [0, 5]:
            raise ValueError(f"Unexpected crops for {first}")
        yield from crops


def raw(args, host, sensor, weights):
    engine = Engine()
    rows = []
    records = raw_roster(json.loads(args.campaign_manifest.read_text()))
    for r in records:
        name, crop = r["flight_id"], r["crop_s"]
        archive = args.raw_dev / (name + ".zip")
        if digest(archive) != r["parent_sha256"]:
            raise ValueError(f"Archive digest mismatch: {archive}")
        episode = read_episode(archive)
        first = int(np.searchsorted(episode.frame_times, episode.frame_times[0] + crop - 1e-8))
        flight = Flight(archive, crop=crop, stop=601)
        camera = flight.K
        python = Inputs(sensor, camera, (240, 320), flight.T_bc[:3, :3])
        wasm = Sandbox(args.build / "odometry.wasm", engine, log_dir=args.build / f"{name}-{crop}")
        wasm.init(camera)
        host.init(camera)
        shape = (5, sensor["height"], sensor["width"])
        images = np.empty(shape, dtype=np.uint8)
        imu = np.empty(51, dtype=np.float32)
        rotation = np.empty((3, 3), dtype=np.float64)
        cpp_out, wasm_out = np.empty((flight.F, 13)), np.empty((flight.F, 13))
        ref_images, ref_imu, ref_rot, fuel = [], [], [], []
        image_max = np.zeros(5, dtype=int)
        changed_pixels = np.zeros(5, dtype=np.int64)
        imu_delta, rotation_delta = 0., 0.
        for i, (t, img, packet) in enumerate(zip(flight.ft, flight.frames, flight.win)):
            img, packet = np.ascontiguousarray(img), np.ascontiguousarray(packet)
            # Send the harness's original timestamps and packet to the ABI.
            # The reference Flight supplies the reset-relative training inputs.
            absolute_t = episode.frame_times[first + i]
            delivered = np.ascontiguousarray(episode.imu_window(first + i), dtype=np.float64)
            cpp_out[i].fill(np.nan)
            if host.lib.step(absolute_t, img, delivered, len(delivered), cpp_out[i]):
                raise RuntimeError(f"Host step failed at frame {i} of {name}/{crop}")
            host.lib.host_features(images, imu, rotation)
            result = wasm.step(absolute_t, img, delivered)
            wasm_out[i] = np.r_[result.pose, result.twist]
            fuel.append(result.fuel)
            im, u, R, _ = python.step(t, img, packet, "triple_derot")
            image_max = np.maximum(image_max, np.abs(im.astype(np.int16) - images).max(axis=(1, 2)))
            changed_pixels += np.count_nonzero(im != images, axis=(1, 2))
            imu_delta = max(imu_delta, max_abs(imu, u))
            rotation_delta = max(rotation_delta, max_abs(rotation, R))
            ref_images.append(im)
            ref_imu.append(u)
            ref_rot.append(R)
        row = dict(images=np.stack(ref_images), imu=np.stack(ref_imu), R=np.stack(ref_rot),
                   v=flight.v_body, times=flight.ft, cam_gt=flight.cam_gt, T_bc=flight.T_bc)
        py_p = integrate(model_velocities(args.run, weights, row, "cpu"), row)
        state_delta = max_abs(cpp_out, wasm_out)
        write_row(rows, dict(flight=name, crop_s=crop, frames=flight.F, pytorch_ate=ate(py_p, row),
                             cpp_ate=ate(cpp_out[:, :3], row), wasm_ate=ate(wasm_out[:, :3], row),
                             max_pixel_delta_by_plane=image_max.tolist(),
                             changed_pixels_by_plane=changed_pixels.tolist(), imu_delta_max=imu_delta,
                             attitude_delta_max=rotation_delta, state_delta_max=state_delta,
                             python_cpp_position_delta_max_m=position_delta(py_p, cpp_out[:, :3]),
                             cpp_wasm_position_delta_max_m=position_delta(cpp_out[:, :3], wasm_out[:, :3]),
                             init_fuel=wasm.init_fuel, peak_step_fuel=max(fuel), peak_frame=int(np.argmax(fuel)),
                             wasm_linear_memory_bytes=wasm.memory.data_len(wasm.store),
                             failed_frames=0, filled_frames=0,
                             passed=imu_delta <= .00002 and rotation_delta <= 1e-8 and max(image_max) <= 1
                             and state_delta <= .002))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "manifest", "build", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--campaign-manifest", type=Path)
    parser.add_argument("--raw-dev", type=Path)
    parser.add_argument("--mode", choices=("prepared", "raw"), required=True)
    args = parser.parse_args()
    if args.mode == "raw" and not (args.campaign_manifest and args.raw_dev):
        parser.error("raw replay needs --campaign-manifest and --raw-dev")
    if args.output.exists():
        parser.error("output already exists")
    torch.set_num_threads(int(os.environ.get("ODO_CPU_THREADS", "3")))
    cv2.setNumThreads(1)
    manifest = json.loads(args.manifest.read_text())
    weights = load_weights(args.run, "best")
    host = Host(args.build)
    rows = (prepared(args, host, manifest, weights) if args.mode == "prepared" else
            raw(args, host, manifest["sensor_config"], weights))
    stats = {k: float(np.mean([r[k] for r in rows])) for k in rows[0] if k.endswith("_ate")}
    passed = all(r["passed"] for r in rows)
    report = dict(seed=json.loads((args.run / "config.json").read_text())["seed"],
                  checkpoint_sha256=digest(args.run / "best.safetensors"), summary=stats, passed=passed, rows=rows)
    if args.mode == "raw":
        wasm = args.build / "odometry.wasm"
        report.update(wasm_sha256=digest(wasm), wasm_bytes=wasm.stat().st_size)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(stats), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
