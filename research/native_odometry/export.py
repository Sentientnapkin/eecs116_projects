"""Export a supported FP32 SSM checkpoint and build its C++ host and WASI binaries."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess

import numpy as np
from safetensors.numpy import load_file
import viobench

SOURCE = Path(__file__).resolve().parent


def export(run, manifest, output, wasi_sdk):
    model = json.loads((run / "config.json").read_text())["model"]
    sensor = json.loads(manifest.read_text())["sensor_config"]
    width, height = (model[key] for key in ("width", "height"))
    channels = model["channels"]
    stride = [2 if i < 3 else 1 for i in range(len(channels))]
    embedding, layers, states = (model[key] for key in ("embedding", "layers", "states"))
    radius, correlation = model["correlation_radius"], model["correlation"]
    if (model["head"] != "ssm" or any(model.get(k) for k in ("blind", "imu_blind", "attitude_input"))
            or min(width, height, embedding, layers, states) <= 0 or radius < 0
            or width >= 320 or height >= 240 or not channels or any(c <= 0 or c % 4 for c in channels)):
        raise ValueError("Unsupported model configuration for this FP32 SSM port")
    if ((width, height) != (sensor["width"], sensor["height"]) or sensor["policy"] != "rolling"
            or sensor["portable_pixels"] != "remap" or not sensor["ordered_packet"]
            or sensor.get("reliability") or sensor.get("rotation_method")
            or sensor["baselines"] != [.25, 1.] or sensor["startup_seconds"] != 1.):
        raise ValueError("Unsupported sensor configuration")
    tensors = load_file(run / "best.safetensors")
    packed = []

    def take(prefix, shape):
        tensor = tensors.pop(prefix)
        if tensor.shape != shape or tensor.dtype != np.float32 or not np.isfinite(tensor).all():
            raise ValueError(f"Invalid tensor {prefix}, expected finite FP32 {shape}")
        packed.append(tensor.reshape(-1))

    def affine(prefix, n, inputs=None):
        take(prefix + ".weight", (n,) if inputs is None else (n, inputs))
        take(prefix + ".bias", (n,))

    cin, w, h = 1, width, height
    cnn_macs = 0
    for i, (c, s) in enumerate(zip(channels, stride)):
        prefix = f"visual.cnn.{i}"
        w, h = (w - 1) // s + 1, (h - 1) // s + 1
        take(prefix + ".body.0.weight", (c, cin, 3, 3))
        affine(prefix + ".body.1", c)
        take(prefix + ".body.3.weight", (c, c, 3, 3))
        affine(prefix + ".body.4", c)
        cnn_macs += h * w * c * (cin + c) * 9
        if cin != c or s != 1:
            take(prefix + ".skip.weight", (c, cin, 1, 1))
            cnn_macs += h * w * c * cin
        cin = c
    if w % 4 or h % 3:
        raise ValueError("Feature map must split evenly into the 3x4 pooling grid")
    offsets = (2 * radius + 1) ** 2
    visual = (3 * cin + 2 * offsets * correlation + 2) * 12
    affine("visual.sensor.0", 64, 51)
    affine("visual.sensor.2", 64, 64)
    affine("visual.projection.0", embedding, visual + 64)
    affine("visual.projection.1", embedding)
    for i in range(layers):
        prefix = f"temporal.{i}"
        affine(prefix + ".norm", embedding)
        affine(prefix + ".input", 2 * embedding, embedding)
        affine(prefix + ".parameters_in", embedding + 2 * states, embedding)
        take(prefix + ".log_rate", (embedding, states))
        take(prefix + ".skip", (embedding,))
        affine(prefix + ".output", embedding, embedding)
    affine("output.0", embedding)
    affine("output.1", 128, embedding)
    affine("output.3", 3, 128)
    if tensors:
        raise ValueError(f"Unexpected tensors: {sorted(tensors)}")
    weights = np.concatenate(packed).astype("<f4", copy=False)
    output = output.resolve()
    output.mkdir(parents=True)
    weights.tofile(output / "weights.f32")
    config = dict(WIDTH=width, HEIGHT=height, BLOCKS=len(channels), CHANNELS=channels, STRIDES=stride,
                  EMBEDDING=embedding, LAYERS=layers, STATES=states, CORRELATION=int(correlation),
                  RADIUS=radius, STARTUP_SECONDS=sensor["startup_seconds"], BASELINES=sensor["baselines"],
                  WEIGHTS=len(weights))
    (output / "model_config.h").write_text("#pragma once\n" + "".join(
        f"#define ODO_{key} " + (", ".join(map(str, value)) if isinstance(value, list) else str(value)) + "\n"
        for key, value in config.items()))
    corr_macs = sum((w - abs(dx)) * (h - abs(dy)) for dx in range(-radius, radius+1) if abs(dx) < w
                    for dy in range(-radius, radius+1) if abs(dy) < h) * cin * 2 * correlation
    counts = dict(parameters=len(weights), cnn_macs=3*cnn_macs, correlation_macs=corr_macs,
                  dense_macs=64*(51+64)+embedding*(visual+64)
                  + layers*embedding*(4*embedding+2*states)+128*(embedding+3))
    (output / "counts.json").write_text(json.dumps(counts, indent=2) + "\n")

    abi = Path(viobench.__file__).parent / "solution/runtime/native"
    flags = ["-std=c++17", "-O3", "-ffp-contract=off", "-Wall", "-Wextra", "-Werror",
             "-I", str(output), "-I", str(abi), str(SOURCE / "guest.cpp")]
    subprocess.run([*shlex.split(os.environ.get("CXX", "c++")), *flags, "-march=native", "-fPIC", "-shared",
                    "-o", output / "host.so"], check=True)
    if wasi_sdk:
        assembly = output / "weights.S"
        assembly.write_text('.section .rodata.odo_weights,"",@\n.globl odo_weights\n.p2align 4\n'
                            'odo_weights:\n.incbin "weights.f32"\n.size odo_weights, .-odo_weights\n')
        subprocess.run([wasi_sdk.resolve() / "bin/clang++", *flags, "-msimd128", "-mexec-model=reactor",
                        "-Wl,--initial-memory=67108864", "-Wl,--strip-debug", "weights.S",
                        "-o", "odometry.wasm"], cwd=output, check=True)
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "manifest", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--wasi-sdk", type=Path, help="Path to a VIOBench wasi-sdk installation")
    args = parser.parse_args()
    print(json.dumps(export(args.run, args.manifest, args.output.resolve(), args.wasi_sdk)))


if __name__ == "__main__":
    main()
