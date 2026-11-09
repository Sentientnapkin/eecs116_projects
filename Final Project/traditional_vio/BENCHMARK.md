# Stage 4 benchmark

Run these commands from the repository root with VIOBench installed. Both versions use the same public episodes and 320 × 240 inputs. The comparison reads the Stage 1 estimator from Git and uses the current solution for the fused run.

```sh
python "Final Project/traditional_vio/benchmark.py" > /tmp/traditional-vio-host.jsonl
```

Pass `--max-episodes 1` for a quick check. Each JSON line contains VIOBench trajectory and twist metrics for both estimators, plus the number of frame pairs with usable visual motion and the number accepted by the EKF. Host timing measures local Python execution.

## WebAssembly accuracy and fuel

The runtime build needs temporary paths without spaces. Build one runtime and use it for both submissions.

```sh
work=$(mktemp -d /tmp/traditional-vio.XXXXXX)
workspace="Final Project/traditional_vio"
TOOLCHAIN="$work/toolchain" BUILD="$work/runtime" bash "$workspace/runtime/python/build.sh"
runtime="$work/runtime/dist/runtime.wasm"

mkdir "$work/imu"
git show "8fe28cd:$workspace/solution/solution.py" > "$work/imu/solution.py"
viobench bundle "$work/imu" --runtime "$runtime" -o "$work/imu.wasm"
viobench bundle "$workspace/solution" --runtime "$runtime" -o "$work/fused.wasm"

viobench check "$work/imu.wasm"
viobench check "$work/fused.wasm"
(cd "$work" && viobench evaluate imu.wasm && viobench evaluate fused.wasm)
```

Compare mean Sim(3) ATE and maximum fuel per frame in the two evaluation reports. Check unaligned ATE, fitted scale, and twist errors for the metric output.

## Initial host results

Stage 1 (`8fe28cd`) vs. Stage 3 (`9239c1b`) across all 10 public episodes, using Python 3.11, NumPy 2.4.6, and OpenCV 5.0.0.93. Error metrics are means of the per-episode RMSE values.

| Metric | IMU only | Fused |
| --- | ---: | ---: |
| Sim(3) ATE (m) | 2.153 | 2.850 |
| Unaligned ATE (m) | 1,377.553 | 5.921 |
| Linear velocity RMSE (m/s) | 70.376 | 0.721 |
| Angular velocity RMSE (rad/s) | 0.123 | 0.122 |
| Rotation RMSE (rad) | 0.463 | 0.479 |
| Mean fitted scale | 0.00373 | 1.06049 |

The visual front end supplied 1,134 measurements across 11,990 consecutive frame pairs (9.5%). The EKF applied 1,132. Both solutions produced valid states for all 12,000 frames. Fusion improved unaligned ATE on all ten episodes and Sim(3) ATE on one.

## WebAssembly results

Both five-frame smoke tests passed. Both bundles then completed all 10 public episodes with zero filled frames under Wasmtime 50.0.1. The guest uses NumPy 2.3.4 and OpenCV 4.12.0. RMSE values in the table are means across episodes.

| Metric | IMU only | Fused |
| --- | ---: | ---: |
| Sim(3) ATE (m) | 2.153 | 2.806 |
| Maximum fuel per frame | 6,458,348 | 183,960,828 |
| Unaligned ATE (m) | 1,377.553 | 5.593 |
| Linear velocity RMSE (m/s) | 70.376 | 0.656 |
| Angular velocity RMSE (rad/s) | 0.123 | 0.122 |
| Rotation RMSE (rad) | 0.463 | 0.436 |
| Mean fitted scale | 0.00373 | 1.20864 |

Fusion improved unaligned ATE on all ten episodes and Sim(3) ATE on three. Sim(3) alignment shrank the IMU-only trajectories substantially, with fitted scales ranging from 0.00069 to 0.00956. The lower aligned error can therefore coexist with substantially worse metric pose and velocity. The fused estimator used 28.5 times as much peak fuel and remained under the benchmark's 20 billion fuel per frame limit.
