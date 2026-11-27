# Stage 2: optimized GSLV

This directory contains the final submitted GSLV build with analytic line Jacobians (server label: `GP + MSCKF w/ GSLV`, submission `41e08d67acd6a988`, November 22, 2026). Only this best Stage 2 option is included.

`solution.c` is the complete C implementation with trained weights embedded. `solution.wasm` is the exact submitted binary. No training, external model files, or datasets are required to build it. It uses the VIOBench ABI v1, WebAssembly SIMD, and libc/libm.

The estimator combines GP/MSCKF visual-inertial odometry, line features, Manhattan constraints, periodic learned velocity updates, a gyro-bias clamp, and analytic line Jacobians with arithmetic optimizations.

## Reproduce

Use CMake >=3.20, wasi-sdk 34 (clang 23.1.0), and the course VIOBench checkout at commit `9b1b07906aff5a3e6f00155e7aecf967d90aa960`.

```bash
export WASI_SDK_PATH=/absolute/path/to/wasi-sdk
export VIOBENCH_NATIVE_DIR=/absolute/path/to/viobench/viobench/solution/runtime/native
./build.sh
```

The script builds `build/solution.wasm`, compares it byte for byte with the submitted binary, and verifies the package checksums. The build uses `-O3` and SIMD without fast-math. Keep the embedded configuration in `solution.c` unchanged.

With the course VIOBench CLI and an episode archive:

```bash
viobench evaluate solution.wasm /absolute/path/to/episode.zip
```

## Recorded validation

The submitted binary SHA-256 is `eb2799cbdc8dd9fa2711cdeda3062447364b6dfd4b05e72e543edd3ffa1a8e6d`.

Recorded private-server result: mean unaligned ATE 0.633 m, median 0.237 m, mean Sim(3) ATE 0.179 m, peak fuel about 4.2M/frame; all 12 episodes completed with zero filled frames. Recorded local holdout mean unaligned ATE: 0.380 m, peak fuel 4.30M/frame. These are separate evaluations.

Prior preflight passed ABI, zero imports, all 738 causality/prefix/repeat checks, and 8 reset checks. Source rebuilds matched the evaluated binary. Private server episodes are not included.

The submission commit should be tagged `submission_stage2`.
