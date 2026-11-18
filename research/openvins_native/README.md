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
