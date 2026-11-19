"""Isolated OpenCV5.1 dependency builds to match the newest model's training backend."""
import argparse
import json
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("kind", choices=("native", "wasm")); p.add_argument("--jobs", type=int, default=24)
a = p.parse_args()
root = Path("/dev/shm/sebastian-vio")
src = root / "new-model-opencv510-src"
pin = subprocess.check_output(["git", "-C", str(src), "rev-parse", "HEAD"], text=True).strip()
assert pin == "e4f78fbcf1a773fbed69e14500e8b734963eb585"
build = root / ("new-model-opencv510-" + a.kind)
cmd = ["cmake", "-S", str(src), "-B", str(build), "-G", "Ninja",
       "-DCMAKE_MAKE_PROGRAM=/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/ninja",
       "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_LIST=core,imgproc,geometry,features,flann,video",
       "-DBUILD_SHARED_LIBS=" + ("OFF" if a.kind == "wasm" else "ON"), "-DCPU_DISPATCH=",
       "-DCMAKE_CXX_FLAGS=-ffp-contract=off"]
disabled = ("BUILD_TESTS", "BUILD_PERF_TESTS", "BUILD_EXAMPLES", "BUILD_JAVA", "BUILD_opencv_apps",
            "BUILD_opencv_python3", "BUILD_opencv_python_bindings_generator", "BUILD_opencv_dnn",
            "WITH_IPP", "WITH_ITT", "WITH_OPENCL", "WITH_TBB", "WITH_OPENMP", "WITH_PTHREADS_PF",
            "WITH_EIGEN", "WITH_LAPACK", "WITH_FFMPEG", "WITH_GTK", "WITH_QT", "WITH_JPEG",
            "WITH_PNG", "WITH_WEBP", "WITH_OPENEXR", "WITH_PROTOBUF", "WITH_HARFBUZZ")
cmd += ["-D" + key + "=OFF" for key in disabled]
cmd += ["-DOPENCV_DISABLE_THREAD_SUPPORT=ON"]
if a.kind == "wasm":
    sdk = root / "viobench/viobench/solution/build/toolchain/wasi-sdk"
    emulation = "-D_WASI_EMULATED_PROCESS_CLOCKS -D_WASI_EMULATED_SIGNAL -D_WASI_EMULATED_MMAN -D_WASI_EMULATED_GETPID"
    cmd += [f"-DCMAKE_TOOLCHAIN_FILE={sdk}/share/cmake/wasi-sdk-p1.cmake",
            "-DCMAKE_C_FLAGS=-msimd128 " + emulation,
            "-DCMAKE_CXX_FLAGS=-msimd128 -ffp-contract=off -fwasm-exceptions -mllvm -wasm-use-legacy-eh=false " + emulation]
logs = Path(__file__).resolve().parent / "results/loop/new-model-wasm"
logs.mkdir(parents=True, exist_ok=True)
(logs / (a.kind + "-opencv510-command.json")).write_text(json.dumps({"source_commit": pin, "configure": cmd}, indent=2) + "\n")
with (logs / (a.kind + "-opencv510-build.log")).open("w") as log:
    subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True)
    subprocess.run(["cmake", "--build", str(build), "--parallel", str(a.jobs)], stdout=log, stderr=subprocess.STDOUT, check=True)
print(build, "complete", flush=True)
