# Stage 4 benchmark

Run these commands from the repository root with VIOBench installed. Both versions use the same public episodes and 320 × 240 inputs. The comparison reads the Stage 1 estimator from Git and uses the current solution for the fused run.

```sh
python "Final Project/traditional_vio/benchmark.py" > /tmp/traditional-vio-host.jsonl
```

Pass `--max-episodes 1` for a quick check. Each JSON line contains VIOBench trajectory and twist metrics for both estimators, plus the number of frame pairs with usable visual motion and the number used to correct the estimate. Host timing measures local Python execution.

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

For the WebAssembly comparison, extract the Stage 5 solution and reuse the same runtime.

```sh
mkdir "$work/stage5"
for module in solution.py vision.py traditional_combination.py; do
  git show "0ecb9fc:$workspace/solution/$module" > "$work/stage5/$module"
done
viobench bundle "$work/stage5" --runtime "$runtime" -o "$work/116_traditional_combination.wasm"
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

## VIOBench KLT + IMU example

Using the same runtime and ten public episodes, the unmodified `python/klt_imu` example completed every frame. It scored 2.042 m mean Sim(3) ATE, 141,887,507 peak fuel per frame, 152.697 m mean unaligned ATE, and 7.541 m/s mean linear velocity RMSE. It uses a half-second initialization and replaces the IMU displacement direction with the visual direction when available, preserving the predicted distance. It then blends that displacement divided by the time interval into velocity.

```sh
viobench bundle "Final Project/viobench/viobench/solution/examples/python/klt_imu" --runtime "$runtime" -o "$work/viobench_klt_imu.wasm"
(cd "$work" && viobench evaluate viobench_klt_imu.wasm)
```

On the first public episode, a host call-count profile showed 2,398 Lucas–Kanade passes in both Stage 3 and Stage 5. Stage 3 ran 1,199 corner detections and 1,199 calls each to `findEssentialMat` and `recoverPose`. Stage 5 ran 260 corner detections and 308 SVD refits. These counts explain where Stage 5 avoids work, while the peak fuel values above come from the WebAssembly runs.

## Stage 6: direct keyframe correction

Stage 6 reuses Stage 5's 320 × 240 keyframe tracking and gyro-aided translation fit. It resolves the axis sign by checking that at least 70% of inlier features triangulate in front of both cameras. A valid update replaces the direction of the predicted camera displacement while retaining its IMU-derived length. The estimator then blends the corrected displacement divided by the keyframe interval with its predicted velocity using the example's 50/50 weight. The camera lever arm is accounted for in both conversions. The first-frame gravity initialization is the same as Stage 5, with no half-second calibration delay. The direct variant carries no EKF covariance or online bias estimates.

```sh
mkdir "$work/stage6"
for module in solution.py vision.py traditional_combination.py; do
  git show "e11ac0b:$workspace/solution/$module" > "$work/stage6/$module"
done
viobench bundle "$work/stage6" --runtime "$runtime" -o "$work/116_traditional_combination_stage6.wasm"
viobench check "$work/116_traditional_combination_stage6.wasm"
(cd "$work" && viobench evaluate 116_traditional_combination_stage6.wasm)
```

Both the smoke test and all ten public WebAssembly episodes passed with no filled frames. The host replay applied 2,159 direct visual corrections.

| Metric | IMU only | VIOBench KLT + IMU | Stage 5 EKF | Stage 6 direct |
| --- | ---: | ---: | ---: | ---: |
| Mean Sim(3) ATE (m) | 2.153 | 2.042 | 2.512 | 1.713 |
| Maximum fuel per frame | 6,458,348 | 141,887,507 | 141,367,669 | 132,473,107 |
| Mean unaligned ATE (m) | 1,377.553 | 152.697 | 4.662 | 212.038 |
| Mean linear velocity RMSE (m/s) | 70.376 | 7.541 | 0.621 | 13.002 |
| Mean fitted scale | 0.00373 | 0.08503 | 1.31920 | 0.04058 |

Stage 6 improved Sim(3) ATE on eight of ten episodes versus IMU only, seven versus the bundled KLT + IMU example, and nine versus Stage 5. The direct update inherits the IMU's displacement magnitude, so inertial drift can become excess travel along a visually plausible path. The scale fit can absorb much of that excess travel. Stage 5 remains the stronger metric estimator.

## Stage 7: hard position redirection with a Kalman velocity update

Stage 7 retains Stage 6's signed visual direction, keyframe tracker, and hard position update. Each accepted measurement redirects the camera displacement to the signed visual direction while preserving the predicted length. The velocity update instead uses the two components of the predicted average camera velocity perpendicular to the visual axis. Their expected value is zero. A three-state Kalman filter models the covariance shared by the interval-average and end velocities under white acceleration noise. It weights the constraint using track geometry and adds no independent measurement of along-axis speed. Position and attitude are outside this filter.

```sh
mkdir "$work/stage7"
for module in solution.py vision.py traditional_combination.py; do
  git show "90b4b1b:$workspace/solution/$module" > "$work/stage7/$module"
done
viobench bundle "$work/stage7" --runtime "$runtime" -o "$work/116_traditional_combination_stage7.wasm"
viobench check "$work/116_traditional_combination_stage7.wasm"
(cd "$work" && viobench evaluate 116_traditional_combination_stage7.wasm)
```

Stage 7 passed the WebAssembly smoke test and completed all ten public episodes with zero filled frames. Synthetic tests checked that redirection preserves displacement length, the velocity update responds to measurement uncertainty, and a rendered keyframe interval triggers both corrections.

| Metric | Stage 6 direct | Stage 7 Kalman velocity |
| --- | ---: | ---: |
| Mean Sim(3) ATE (m) | 1.713 | 1.572 |
| Maximum fuel per frame | 132,473,107 | 133,412,127 |
| Mean unaligned ATE (m) | 212.038 | 614.936 |
| Mean linear velocity RMSE (m/s) | 13.002 | 68.094 |
| Mean fitted scale | 0.04058 | 0.00950 |

Stage 7 improved the aligned error on six episodes. Its direction constraint leaves along-axis speed unmeasured, and the hard position update keeps the predicted length. The 50/50 blend in Stage 6 provided more damping on these flights.

## Stage 8: consecutive-frame corner matching

Stage 8 detects fresh corners in the previous image and matches them to the current image with forward and backward KLT on each pair. It advances the reference pose and image every step, including when matching fails. It keeps Stage 7's 320 × 240 resolution, gyro de-rotation, signed translation fit, minimum 0.5° parallax, hard position redirection, and Kalman velocity correction.

```sh
mkdir "$work/stage8"
for module in solution.py vision.py traditional_combination.py; do
  git show "1343e7b:$workspace/solution/$module" > "$work/stage8/$module"
done
viobench bundle "$work/stage8" --runtime "$runtime" -o "$work/116_traditional_combination_stage8.wasm"
viobench check "$work/116_traditional_combination_stage8.wasm"
(cd "$work" && viobench evaluate 116_traditional_combination_stage8.wasm)
```

Stage 8 passed the WebAssembly smoke test and completed all ten public episodes without filled frames. The host replay recorded 408 visual updates versus 2,159 in Stage 7. Synthetic checks confirmed an immediate correction on a valid pair, fresh corner detection for every pair, and recovery after a blank frame.

| Metric | Stage 7 keyframes | Stage 8 consecutive frames |
| --- | ---: | ---: |
| Mean Sim(3) ATE (m) | 1.572 | 2.155 |
| Maximum fuel per frame | 133,412,127 | 146,527,025 |
| Mean unaligned ATE (m) | 614.936 | 1,314.982 |
| Mean linear velocity RMSE (m/s) | 68.094 | 69.841 |

## Stage 9: 400 ms keyframes

Stage 9 takes Stage 7's tracker, gyro-aided signed translation fit, hard position redirection, and Kalman velocity correction. It attempts one fit after eight frame hops (400 ms at 20 Hz), then starts a new keyframe whether the fit passes or fails. It starts a new keyframe sooner if too few tracks survive. The estimator still returns a state on every frame.

```sh
viobench bundle "$workspace/solution" --runtime "$runtime" -o "$work/116_traditional_combination_stage9.wasm"
viobench check "$work/116_traditional_combination_stage9.wasm"
(cd "$work" && viobench evaluate 116_traditional_combination_stage9.wasm)
```

Stage 9 passed the WebAssembly smoke test and completed all ten public episodes without filled frames. The host replay applied 1,137 visual corrections versus 2,159 with Stage 7. Synthetic checks confirmed an eight-hop correction and a fresh keyframe after both successful and unsuccessful fits.

| Metric | Stage 7 adaptive keyframes | Stage 9 400 ms |
| --- | ---: | ---: |
| Mean Sim(3) ATE (m) | 1.572 | 1.607 |
| Maximum fuel per frame | 133,412,127 | 132,754,468 |
| Mean fuel per frame | 76,233,888 | 72,433,174 |
| Mean unaligned ATE (m) | 614.936 | 653.533 |
| Mean linear velocity RMSE (m/s) | 68.094 | 68.481 |
