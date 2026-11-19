"""Compare trained inertial refinement to host C and optionally measure Wasm parity and fuel.

Run from research with python -m refine_c.check.
"""
import argparse
from _ctypes import dlclose
import ctypes
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

import numpy as np
from safetensors.torch import load_file
import torch

from odometry_models import OdometryNet
from .export_weights import export


ROOT = Path(__file__).resolve().parent


def compare(refiner, cfg, inputs, wasi_cc=None):
    count = sum(item.shape[-1] for item in inputs[:3]) + 9
    initial, context, imu, rotation = inputs
    frames = torch.cat((context, initial, imu, rotation.flatten(-2)), dim=-1).numpy()
    with torch.no_grad():
        expected, _ = refiner(*inputs, None)
    expected = expected[-1].numpy()

    with TemporaryDirectory(prefix="refine-parity-") as directory:
        path = Path(directory)
        export(cfg, {key: value.numpy() for key, value in refiner.state_dict().items()}, path/"weights.h")
        sources = ["-std=c99", "-O3", "-Wall", "-Wextra", "-Werror", "-I", str(path), "-I", str(ROOT),
                   str(ROOT/"refine.c"), str(ROOT/"parity.c"), "-lm"]
        library = path/"refine.so"
        subprocess.run(["cc", "-shared", "-fPIC", *sources, "-o", str(library)], check=True)
        host = ctypes.CDLL(str(library))
        native = np.empty_like(expected)
        try:
            host.refine_frame.restype = ctypes.POINTER(ctypes.c_float)
            host.refine_reset.restype = host.refine_frame_step.restype = None
            buffer = np.ctypeslib.as_array(host.refine_frame(), shape=(count+3,))
            for stream, estimates in zip(frames, native):
                host.refine_reset()
                for i, frame in enumerate(stream):
                    buffer[:count] = frame
                    host.refine_frame_step()
                    estimates[i] = buffer[count:]
        finally:
            # On NFS a loaded library keeps a .nfs file alive after unlink.
            dlclose(host._handle)
        np.testing.assert_allclose(native, expected, atol=2e-6, rtol=1e-5)
        report = {"frames": int(np.prod(native.shape[:-1])), "native_max_abs_m_per_s": float(abs(native-expected).max())}

        if wasi_cc:
            import wasmtime
            wasm = path/"refine.wasm"
            exports = ["refine_frame", "refine_frame_step", "refine_reset"]
            subprocess.run([str(wasi_cc), "-nostartfiles", "-Wl,--no-entry",
                            *[f"-Wl,--export={name}" for name in exports],
                            *sources, "-o", str(wasm)], check=True)
            config = wasmtime.Config()
            config.consume_fuel = True
            engine = wasmtime.Engine(config)
            store = wasmtime.Store(engine)
            store.set_fuel(10_000_000)
            guest = wasmtime.Instance(store, wasmtime.Module.from_file(engine, str(wasm)), []).exports(store)
            ptr = guest["refine_frame"](store)
            memory = guest["memory"]
            offset = ptr + count*4
            actual = np.empty_like(expected)
            peaking = 0
            for stream, estimates in zip(frames, actual):
                guest["refine_reset"](store)
                for i, frame in enumerate(stream):
                    memory.write(store, frame.astype("<f4").tobytes(), ptr)
                    budget = 1_000_000_000
                    store.set_fuel(budget)
                    guest["refine_frame_step"](store)
                    peaking = max(peaking, budget-store.get_fuel())
                    estimates[i] = np.frombuffer(memory.read(store, offset, offset+12), dtype="<f4")
            np.testing.assert_allclose(actual, expected, atol=2e-6, rtol=1e-5)
            report.update(wasm_max_abs_m_per_s=float(abs(actual-expected).max()), wasm_peak_fuel=peaking)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("shard", type=Path, help="A development replay shard")
    parser.add_argument("--wasi-cc", type=Path)
    args = parser.parse_args()
    cfg = json.loads((args.run/"config.json").read_text())["model"]
    torch.set_num_threads(4)
    model = OdometryNet(cfg).eval()
    model.load_state_dict(load_file(args.run/"best.safetensors"))
    with torch.no_grad(), np.load(args.shard, allow_pickle=False) as row:
        length, imu, rotation = len(row["imu"]), [], []
        context, initial = [], []
        state = None
        for start in range(0, length, 16):
            frames = slice(start, start+16)
            images = torch.from_numpy(row["images"][frames])[None]
            u = torch.from_numpy(row["imu"][frames])[None]
            R = torch.from_numpy(row["R"][frames]).float()[None]
            head, state, _ = model.head(images, u, state, R)
            context.append(head)
            initial.append(model.output(head))
            imu.append(u)
            rotation.append(R)
        inputs = [torch.cat(parts, 1) for parts in (initial, context, imu, rotation)]
    print(json.dumps(compare(model.refiner, cfg, inputs, args.wasi_cc)))


if __name__ == "__main__":
    main()
