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
mkdir "$work/stage3"
for module in solution.py vision.py fusion.py; do
  git show "9239c1b:$workspace/solution/$module" > "$work/stage3/$module"
done
viobench bundle "$work/stage3" --runtime "$runtime" -o "$work/fused.wasm"

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

## Stage 5: 116_traditional_combination

The visual front end tracks up to 100 corners from a keyframe using consecutive Lucas–Kanade hops. Starting at four hops (200 ms at 20 Hz), it de-rotates the current bearings using the integrated gyro and fits a translation axis with two-track RANSAC and an SVD refit. The fit requires at least 0.5° of median inlier parallax and a well-conditioned set of epipolar planes. The EKF retains the keyframe pose and its cross-covariance, then uses at most one translation-axis measurement per keyframe. The camera still operates at 320 × 240.

Run the host comparison above against the current solution. For the WebAssembly comparison, reuse the same runtime and label the new build separately.

```sh
viobench bundle "$workspace/solution" --runtime "$runtime" -o "$work/116_traditional_combination.wasm"
viobench check "$work/116_traditional_combination.wasm"
(cd "$work" && viobench evaluate 116_traditional_combination.wasm)
```

All ten public episodes completed in WebAssembly with no filled frames.

| Metric | Stage 1 IMU only | Stage 3 EKF | Stage 5 |
| --- | ---: | ---: | ---: |
| Mean Sim(3) ATE (m) | 2.153 | 2.806 | 2.512 |
| Maximum fuel per frame | 6,458,348 | 183,960,828 | 141,367,669 |
| Mean unaligned ATE (m) | 1,377.553 | 5.593 | 4.662 |
| Mean linear velocity RMSE (m/s) | 70.376 | 0.656 | 0.621 |

In a separate host replay, Stage 5 supplied 2,169 translation axes and the EKF accepted all of them. The median unsigned axis error against ground truth fell from 52.2° in Stage 3 to 6.8° in Stage 5. The median Stage 5 track spanned four frame intervals and 7.8 cm of actual camera travel. The host diagnostic uses ground truth only to score each estimated axis.
