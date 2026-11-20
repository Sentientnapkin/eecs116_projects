# Structural odometry pipelines: ready for experimental scoring

Four standalone C++17/Wasm guests have been built from the canonical **N2 kf_grid_native seed217** packed weights. No retraining or dataset scoring was performed. The frozen source and original binaries are unchanged. New code lives here; the build script patches an isolated copy of `native_odometry/` under the output directory.

| Guest | New integration behavior |
| --- | --- |
| `struct_control` | None. Rebuild is byte-identical to the frozen seed217 guest. |
| `struct_manhattan` | Persistent room-axis observations gradually correct heading around estimated gravity. |
| `struct_direction` | Calibrated two-view geometry gradually rotates predicted camera velocity toward the observed translation direction. |
| `struct_combined` | Both corrections, with direction geometry using the corrected orientation. |

The learned model receives exactly the existing kf_grid input policy in every variant. These are controlled integration ablations, not new trained model families or a new OpenVINS smoother.

## Files ready now

- [Reviewable readiness index, hashes and validation results](../results/eval/structural-pipelines/ready.json).
- Local build: `research/artifacts/structural-pipelines-v5/`.
- Each of `control/`, `manhattan/`, `direction/`, `combined/` contains `odometry.wasm`, `host.so`, canonical `weights.f32`, model config and official ABI check log.
- The build directory contains `source/`, `build.json`, `geometry.json`, `validation.json`, `ready.json` and `score.sh`.

Nothing was copied into the live `/baselines/queue` watcher. That watcher can start scoring automatically, so add these guests only when the scoring dataset is frozen and ready.

## Manhattan implementation

LSD detects long line segments at 5 Hz, with at most 96 segments retained. For pixel endpoints `p1,p2`, `K^T (p1 × p2)` is the calibrated interpretation-plane normal. The estimated camera attitude rotates that normal into the initial body frame. Its intersection with the gravity-horizontal plane yields a candidate horizontal world direction. Raw pixel slopes are never interpreted as yaw.

Gravity is estimated from a qualifying 0.8-second IMU window: near-1g mean acceleration, low mean gyro and bounded acceleration/gyro variance. The resulting axis is fixed for the episode. This preserves the arbitrary initial yaw gauge and avoids assuming that initial body Z is gravity. Sustained linear acceleration or sensor bias can still corrupt this gravity estimate; qualification is evidence, not a guarantee of stillness.

A deterministic search groups directions modulo 90 degrees. Acceptance requires at least eight supporting lines, both perpendicular axis families, support in four image regions, at least 55% agreement and three consecutive stable observations. The first stable room orientation defines the reference. Later observations correct drift with gain 0.15, a 0.5-degree maximum step and a 10-degree innovation gate. This version maintains one room frame; it does not implement Atlanta-world room switching. Vertical lines alone do not activate it.

## Direction implementation

At 2 Hz, a grid frontend detects up to 160 corners, tracks them forward/backward using gyro-predicted KLT and checks spatial coverage. Essential-matrix RANSAC and cheirality select correspondences. With rotation fixed to the estimator, a bearing-normal eigenproblem recovers translation direction; majority positive-depth support chooses its sign. Gates include 30 inliers, five occupied image cells, two-pixel residual flow, eigenvalue separation and at least 70% depth-sign agreement. Additional RANSAC saves/restores the OpenCV RNG so it does not disturb the base input path.

The direction is compared with the predicted camera displacement over the same interval. Displacements below 5 cm and disagreements over 45 degrees are rejected. Accepted corrections use 25% of the angle, capped at 10 degrees, with 0.5-second decay and a one-second expiry. They rotate current and subsequent camera velocity while preserving its magnitude; past emitted positions are never rewritten. Camera/IMU lever-arm velocity is included. Gyro angular twist remains the base sensor estimate; it does not include the derivative of the structural yaw adjustment.

## Checks completed

- All four actual Wasm guests pass the official ABI check against VIOBench `9b1b079`.
- Native geometry contracts pass: calibrated yaw correction sign/convergence, spatial and vertical-line rejection, gravity acceptance/rejection, translation direction/sign and zero-parallax rejection.
- A projected 3D point-cloud image pair activates the real KLT/essential frontend; the velocity correction turns toward the recovered direction and preserves speed.
- Four 70-frame synthetic Wasm streams produce finite states and identity first-camera poses. Independent 45-frame replays match each full stream's prefix exactly; native resets reproduce their first output exactly.
- The rendered room activates the actual Manhattan frontend in native and Wasm. Maximum synthetic native/Wasm component difference is approximately `5.96e-8`.
- Direction-only rejects the stationary/rotation-only room stream and matches the control within `1e-12`.

Synthetic peak fuel/frame was 1.071B control, 1.175B Manhattan, 1.275B direction and 1.360B combined. These are synthetic observations, not expected dataset maxima. Accuracy and actual full-roster fuel remain unmeasured. The frozen base's unresolved long visual-backend parity issue remains; these checks do not resolve it or qualify a course submission.

## Score when the dataset is ready

Run from the repository root:

```bash
/data/backups/rganapa/Sebastian/venv-teacher/bin/python \
  research/structural_pipelines/score.py \
  --episodes /path/to/frozen-episode-zips \
  --out /path/to/new-structural-results \
  --workers 8
```

The runner verifies guest hashes and the clean pinned evaluator, records the SHA256 of every episode before scoring, and refuses to reuse an output directory with different inputs. It runs all four guests on the same episodes using the existing metered evaluator. For an interrupted run, the same command resumes completed reports. Final outputs include per-flight results, full mean unaligned ATE, reported peak fuel and the guest-by-episode matrix. Compare paired flights, failures, filled frames and duration/domain/motion groups alongside the mean. Any future tuning should use development data rather than this final comparison set.

## Rebuild and validate

Use a fresh output directory, existing toolchain and OpenCV 5.1 builds. No new dependencies or weights are downloaded:

```bash
export TMPDIR=/dev/shm/sebastian-vio/tmp
export PYTHONPATH=/dev/shm/sebastian-vio/viobench
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
BUILD=research/artifacts/my-structural-build
$PY -B research/structural_pipelines/build.py --out "$BUILD"
$PY -B research/structural_pipelines/check_geometry.py "$BUILD"
$PY -B research/structural_pipelines/validate.py "$BUILD"
$PY -B research/structural_pipelines/package.py "$BUILD"
```

The final step creates `ready.json` and updates the small tracked readiness index; it does not run dataset scoring, enqueue guests, publish or submit. Older incomplete development builds remain separate from the ready suite.
