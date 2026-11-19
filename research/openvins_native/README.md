# Native OpenVINS paired replay

This C++ runner uses upstream OpenVINS commit `6948812` with ROS and ArUco disabled. It replays one calibrated monocular stream and its timestamped IMU from the local VIOBench campaign. Both arms use identical inputs, upstream options, and calibration. The `try_zupt` flag also controls the upstream static initializer's jerk requirement.

Use OpenCV 4, Eigen, Boost, Ceres and a recent compatible C++ runtime. On the GPU host the upstream build needed `-DCMAKE_CXX_FLAGS="-include cassert"` because some source files relied on a transitive assert include. The local dependency prefix also supplied libstdc++ at link and runtime. For a compatible prefix:

```bash
cmake -S "$OPENVINS_SOURCE/ov_msckf" -B "$OPENVINS_BUILD" -G Ninja \
  -DENABLE_ROS=OFF -DENABLE_ARUCO_TAGS=OFF -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="$DEPS" -DCMAKE_CXX_FLAGS="-include cassert"
cmake --build "$OPENVINS_BUILD" --target ov_msckf_lib --parallel
cmake -S openvins_native -B "$WRAPPER_BUILD" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$DEPS" \
  -DCMAKE_CXX_FLAGS="-include cassert" -DCMAKE_EXE_LINKER_FLAGS="-L$DEPS/lib" \
  -DOPENVINS_SOURCE="$OPENVINS_SOURCE" -DOPENVINS_BUILD="$OPENVINS_BUILD"
cmake --build "$WRAPPER_BUILD"
LD_LIBRARY_PATH="$DEPS/lib" OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python -B openvins_eval.py --runner "$WRAPPER_BUILD/openvins_replay" \
  --raw-dev "$RAW_DEV" --records "$CAMPAIGN_RECORDS" --baseline "$BD0_BASELINE" \
  --work-dir "$REPLAY_SCRATCH" --output results/eval/openvins/campaign-dev-30s.json --workers 16
```

A replay starts with a fresh estimator and delivers IMU observations no later than the current image. The pre-initialization pose is zero. After initialization, the first valid estimate and the gyro increment from the first camera frame set the output gauge. Failed frames hold the last valid estimate. The evaluator verifies frame times and truth against the paired prepared shards. The denominator is all 120 crops in each arm.

The first wrapper omitted fields normally initialized by the upstream YAML loader, which invalidated its scores. The calibrated rerun explicitly uses identity gyro/accelerometer intrinsics and zero gyro gravity sensitivity. It scored 2.843 m with stationary updates off (no initialization on any crop) and 2.837 m with them on (57 crops with an estimate). Nominal/static and moving-start ATE were 2.726 / 2.960 m off and 2.709 / 2.964 m on. Both arms recorded one OpenCV exception, and their partial trajectories were retained. B-D0 scored 1.353 m on the same roster. Neither arm passed the development gate for Wasm fuel measurement.

[Per-replay results](../results/eval/openvins/campaign-dev-30s.json)

## Initialization and stationary-update diagnostics

Run the same replay command with `--diagnose` and a separate output path to log upstream initialization decisions and add the inertial-only stationary arm. Run with `--initialization-only` and a separate output path to retain the still-start initializer while rejecting every post-initialization stationary update. Both are diagnostic arms on the unchanged campaign-dev roster.

| Arm | Overall ATE (m) | Static ATE (m) | Moving ATE (m) | Initialized static / moving |
| --- | ---: | ---: | ---: | --- |
| Stationary updates off | 2.843 | 2.726 | 2.960 | 0 / 0 |
| Stationary updates on | 2.837 | 2.709 | 2.964 | 47 / 10 |
| Inertial-only stationary update | 2.881 | 2.798 | 2.965 | 47 / 10 |
| Still-start initialization only | 9.254 | 13.816 | 4.691 | 47 / 10 |

- The off/on instrumentation reproduced the original per-crop ATE exactly. With stationary updates off, 117 of 120 crops had a dynamic-initialization attempt rejected for rotation below the 45-degree threshold. Dynamic feature shortage was reported on 103 crops, and the static initializer reported low IMU excitation on 71. Reasons overlap and can recur on each crop.
- The default stationary arm processed 19,490 valid frames with truth speed above 0.2 m/s. It applied a stationary update to 17,548 of them (90.0%). With the visual disparity shortcut disabled it still updated 17,474 (89.7%). Accepted stationary updates skip the ordinary clone and visual-update path.
- Suppressing all post-init stationary updates preserved the initialization times and valid-frame masks. ATE increased from 2.837 to 9.254 m. The MSCKF reached its update stage on 29,000 frames and used at least one feature on 11,116 (38.3%). The worst crop was 352.31 m with usable MSCKF features on 37 of 573 update-stage frames. This distinguishes the startup failure from poor visual support after startup. All arms retain one native OpenCV exception.

[Logged decisions and inertial-only control](../results/eval/openvins/campaign-dev-diagnostics.json) · [Initialization-only control](../results/eval/openvins/campaign-dev-initialization-only.json)
