# CPU and WebAssembly inference for B-D0-ssm-x3

This opt-in C++17 path exports the best EMA weights from the PyTorch SSM checkpoint. It implements the three shared-weight residual CNN passes, normalized local correlation, IMU branch, projection, selective SSM, rolling gyro calibration, image history warps, and camera-frame pose and twist. The VIOBench v1 reactor accepts the standard 320×240 RGB feed. The model consumes 128×96 images. Inference and calibration use fixed-size reusable buffers. The host library exposes additional entry points for numerical comparison.

## Build and replay

From `research/` in the teacher environment, with the packaged VIOBench 0.0.1 runtime and a local VIOBench wasi-sdk. Use a fresh build directory for each checkpoint. For seeds 218 and 219 use the corresponding `B-D0-ssm-x3-s218-gpu` or `B-D0-ssm-x3-s219-gpu` run.

```bash
export CUDA_VISIBLE_DEVICES="" TMPDIR=/dev/shm
export XDG_CACHE_HOME="$PWD/results/loop/native-deploy/cache"
RUN=/path/to/runs/B-D0-ssm-x3-gpu
MANIFEST=data/hub-cache/B-D0-ssm-x3-gpu/manifests/teacher-full.json
BUILD=results/loop/native-deploy/bd0-217
SDK=/path/to/wasi-sdk
RAW_DEV=/path/to/campaign/raw/dev

python -B native_odometry/export.py "$RUN" "$MANIFEST" "$BUILD" --wasi-sdk "$SDK"
python -B -m viobench check "$BUILD/odometry.wasm"
python -B native_odometry/test_guest.py "$BUILD" "$MANIFEST"
python -B native_odometry/replay.py "$RUN" "$MANIFEST" "$BUILD" "$BUILD/prepared.json" --mode prepared
python -B native_odometry/replay.py "$RUN" "$MANIFEST" "$BUILD" "$BUILD/raw.json" --mode raw \
  --campaign-manifest data/native-campaign/dev-records.json --raw-dev "$RAW_DEV"
```

Omit `--wasi-sdk` when building for prepared CPU replay alone. The three reference checkpoints were exported with GCC 11.4 and WASI SDK 34 (Clang 23.1), with SIMD128 for WebAssembly and floating-point contraction disabled. The generated weight blob is little-endian FP32. Run the host library on an architecture supported by the local `-march=native` build. The experiment and tolerances are recorded under `deployment` in [experiments.json](../configs/experiments.json).

Prepared evaluation replays each entire shard with a fresh recurrent state. Both velocity streams use the reference Python integration, isolating model math. Raw evaluation passes the same adapted RGB and absolute timestamp packets to both binaries through the VIOBench ABI. Python builds the corresponding reset-relative feature stream separately. The raw run measures all 13 state components, the camera position trajectory, peak per-step fuel and initialization fuel. Successful runs require every frame to produce a finite state. The archived original D0 development flights were unavailable for raw replay on this machine. The fuel and raw ATE sample uses two frozen campaign-dev parents and two crop origins per parent.

## Arithmetic and fuel

The exported SSM has **1,286,355 FP32 parameters** and **356.20 M MACs/frame** in the convolutions, dense layers and valid correlation dot products. The three CNN passes account for 354.34 M MACs/frame. These counts exclude normalization, activations, pooling, SSM elementwise updates, sensor preprocessing and integration. The last residual block alone accounts for 155.71 M MACs/frame across the three image planes.

The archived 32×24 EMA uses the two-convolution visual encoder and 32-dimensional embedding in `learned_probe.py` and `seq_heads.py`. With a three-plane input that architecture has 20,175 stored parameters and 175,328 convolution/dense MACs/frame. With five planes it has 20,575 parameters and 252,128 MACs/frame. These are architecture estimates because the exact archived EMA weight bundle was unavailable. They count the deployed encoder's serialized auxiliary head, which contributes no inference MACs. The historical replay reports 16.93 M peak fuel/frame for the previous EMA on its own roster. See [the historical fuel report](../ROBUSTNESS.md).

## Verified results

ATE is unaligned trajectory RMSE in metres, averaged equally across replays.

| Seed | Prepared dev PyTorch / C++ ATE | Raw campaign-dev sample WASM ATE |
| --- | ---: | ---: |
| 217 | 1.0535 / 1.0535 | 0.4477 |
| 218 | 1.1202 / 1.1202 | 0.6144 |
| 219 | 1.1112 / 1.1112 | 0.9139 |
| Mean | 1.0950 / 1.0950 | 0.6587 |

- **Prepared development, 42 replays and 21,900 frames.** The largest per-component velocity delta was 0.626 µm/s. Maximum trajectory separation was 0.418 µm.
- **Raw campaign-dev sample, 12 replays and 6,600 frames.** The C++ image planes and IMU features were bitwise identical to Python. The maximum attitude element delta was 7.22 × 10⁻¹⁵. Maximum C++–WASM trajectory separation was 0.122 µm. Every frame produced a finite state.
- **Fuel and artifact.** Peak was 1,074,754,835 fuel/frame and initialization used 100,800–101,187 fuel. Each WASM artifact was 5,229,373 bytes and used 64 MiB of linear memory. Peak fuel was 63.5× the historical EMA on its separate roster. This artifact serves as the FP32 parity reference. The CNN accounts for 99.5% of counted MACs.
- **Regression checks.** The VIOBench ABI check, synthetic RGB/lever-arm/reset regression, 16 causal tests and 11 CPU odometry tests passed. The CUDA-only checkpoint test was skipped.

[Versioned per-replay results, hashes and runtime versions](../results/eval/native-deploy/b-d0-cpp-fp32.json)

## Convolution SIMD pilot

`--wasm-kernel simd-8x32` uses an 8×32 SIMD128 tile to reuse each weight splat and activation load across more outputs. `--wasm-kernel simd-8x32-k2` additionally unrolls two sequential K iterations. The kernels preserve each lane's FP32 accumulation order with contraction disabled. Shapes outside the wider tile use the existing path. With no option the exporter uses the original 4×16 tile. `--wasm-kernel scalar` builds the scalar path without SIMD128.

To reproduce the bounded comparison, build both candidates and the default control for seed 217, run `python -B -m viobench check "$BUILD/odometry.wasm" --frames 32` on each, and run the synthetic regression above for each build. For the selected variant, replay each seed with these additional options. `CONTROL` is the original 4×16 artifact for that seed.

```bash
python -B native_odometry/replay.py "$RUN" "$MANIFEST" "$BUILD" "$BUILD/matched-raw.json" --mode raw \
  --campaign-manifest data/native-campaign/dev-records.json --raw-dev "$RAW_DEV" \
  --control-wasm "$CONTROL/odometry.wasm" \
  --control-report results/eval/native-deploy/b-d0-cpp-fp32.json
```

The matched replay verifies the checkpoint and control WASM hashes. It meters both guests on each of the same delivered observations and checks the control peaks against the verified report. Each frame's full pose and twist are compared.

| Seed 217 synthetic screen | Peak step fuel |
| --- | ---: |
| Original 4×16 | 1,074,754,459 |
| 8×32 | 956,583,271 |
| 8×32, K unrolled by two | 861,235,039 |

The unrolled variant advanced to raw replay. The regenerated default artifact matched the original byte for byte. The scalar artifact passed the five-frame ABI smoke and the RGB, lever-arm and reset regression.

On all 12 matched campaign-dev replays across seeds 217–219, the selected kernel reduced peak step fuel by **19.87%**, from **1,074,754,835** to **861,235,415**. All 13 output components were bitwise identical over 6,600 frames. Mean unaligned ATE stayed at 0.658690 m, with zero failed or filled frames. Initialization fuel matched on every replay (100,800–101,187), and the WASM artifact grew by 4,896 bytes. The optimized kernel remains opt-in.

[Versioned synthetic and matched raw results](../results/eval/native-deploy/b-d0-cpp-fp32-convolution-pilot.json)
