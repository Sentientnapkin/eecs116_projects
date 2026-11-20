# gp_msckf: visual-inertial MSCKF with Gaussian-process IMU biases

A classical visual-inertial estimator written in plain C (libc and libm only, no OpenCV, static memory) and compiled
to a single `wasm32-wasip1` reactor implementing the VIOBench ABI v1. `gp_msckf.wasm` in this folder is the submitted
module; `gp_msckf.wasm.sha256` is its checksum.

| WebAssembly file | Public mean ATE (unaligned) | Public mean Sim(3) ATE | Peak fuel per frame |
|---|---|---|---|
| `gp_msckf.wasm` | 0.749 m | 0.380 m | 18.98M |

Official `viobench evaluate` on the ten public episodes: 10/10 completed, no filled frames, median fuel 9.59M,
p99 16.9M. Per-episode unaligned ATE: 1.176, 0.495, 0.708, 0.580, 1.671, 0.650, 0.596, 0.655, 0.551, 0.411 m.

## How it works

Every step receives one 320 × 240 RGB frame (20 Hz) and the ten IMU samples since the previous frame (200 Hz), and
returns the pose of the camera relative to the first frame and its twist.

| stage | what | why |
|---|---|---|
| IMU propagation | error-state EKF, bias-corrected strapdown integration, block-sparse covariance propagation | accurate over 1–2 s, drifts after (½·a·t²) |
| GP bias states | each IMU bias is a Gaussian process with kernel σ₀² + σ²_rw·min(t, t′) (constant offset + Wiener process), i.e. a random-walk state | biases drift; the state-space form is exact and costs the same every step |
| thrust model | the body x/y specific force of a quadrotor is zero, so its frame mean measures the accelerometer bias | a quadrotor's accelerometer measures thrust, not gravity |
| velocity prior | speed per axis ~0.5 m/s, correlated over 2 s, applied with variance σ²·τ/Δt | velocity is unobservable from the IMU alone; keeps it bounded until vision locks on |
| KLT tracking | 2-level pyramid, 9 × 9 window, inverse compositional, started at the gyro-predicted position | parallax is only ~0.5 px per frame on this ~117° lens |
| grid detection | Shi-Tomasi, one feature per cell of a 10 × 6 grid, scored only in empty cells | cost follows the number of lost tracks |
| MSCKF | the IMU pose is cloned every 4 frames (6 clones ≈ 1.2 s); a track seen in ≥ 3 clones is triangulated, its residuals projected onto the left null space of the feature Jacobian, χ²-gated, stacked, QR-compressed and applied in one EKF update | constrains velocity, tilt and biases from ~1 s of tracks without features in the state |
| vision ZUPT | median de-rotated disparity between consecutive clones < 0.4 px → zero-velocity update | handles hover starts; cannot fire in steady flight, unlike an IMU-based ZUPT |
| spread updates | ended tracks processed every frame, tracks leaving the window spread over the 3 frames before | the score counts the worst frame's fuel |

The state is [orientation, velocity, position, gyro bias, accel bias, frame-0 orientation] plus up to 7 clones; the
frame-0 orientation is kept in the state so the output stays relative to frame 0 while the tilt is refined. All
parameters are documented at the top of `solution.c`.

## Build and check

From the parent directory, with VIOBench installed from a source checkout (bash, CMake and a C toolchain; on Windows
use WSL2, as for the other solutions here):

```bash
viobench bundle gp_msckf -o build/gp_msckf.wasm
viobench check build/gp_msckf.wasm
viobench evaluate build/gp_msckf.wasm
```

The submitted `gp_msckf.wasm` was built with wasi-sdk 34 (clang 23.1.0) against VIOBench `main` of 2026-11-19.

## Development

`JOURNAL.md` records the whole development, one milestone at a time (m1 IMU-only EKF with GP biases → m7 this
solution): the measurements behind every design decision, what was tried and dropped, and the evaluation protocol
(40 windows per build including in-flight starts, paired bootstrap confidence intervals, hold-out split, filter
consistency). Its file paths refer to the development workspace (scripts and frozen milestone copies), which is not
part of this repository.

Further results from that journal:

- In-flight starts (each public episode started 5–40 s in): mean ATE 1.49 m (identity 4.4–5.1 m).
- Held-out third-party episodes calibrated to the course server's longer, faster flights (30 hover starts): mean
  0.76 m (median 0.50 m, identity 4.24 m), peak fuel ~21.6M.

## Known limitations

- The startup of an in-flight episode is the largest error (~0.7–1.3 m offset in the first 5 s).
- The filter is still overconfident (velocity NEES ~4–8 against an ideal ~3).
- Fast flights through textureless views can lose all tracks; the filter then coasts on the IMU and the prior.
