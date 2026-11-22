# GP + MSCKF fuel reduction (overnight 2026-11-19/20)

Source: `solution.c` here (a copy of the teammate's `classical_vio/gp_msckf/solution.c`; their folder was not touched).
Every change is behind a `#define` that defaults to the original behaviour, so the file builds the original when no flags are given.
Builds: `msckf/build_m.sh NAME FLAG=VAL ...` (with `FLAGS="-O3"`), the same viobench bundle as the submitted wasm.

## Results

Fuel = max fuel per frame in the viobench sandbox (the score's fuel axis). Accuracy = mean unaligned ATE (m).
HF = the public 171-flight server-calibrated set (host build, identical code); "rest" = the 85 flights that start from rest
(like the server's), where the MSCKF is meant to be judged; public = viobench's 10 public episodes (wasm, sandbox).

| build | file | max fuel | public ATE | HF rest mean / median | HF all (171) | flights worse than "never moved" |
|---|---|---|---|---|---|---|
| original (submitted, 1.24 m on the server) | `gp_msckf_original_rebuilt.wasm` | 18.2-21.1M | 0.749 | 0.826 / 0.51 | 2.23 | 27 |
| **A: same accuracy** | `gp_msckf_A_5M.wasm` | **5.2-5.5M** | **0.670** | 0.899 / 0.54 | **1.62** | 20 |
| **B: lower fuel** | `gp_msckf_B_3M.wasm` | **3.0-3.2M** | 0.868 | 0.877 / 0.55 | 1.87 | 24 |
| small t1 | `gp_msckf_small_t1.wasm` | 2.1M | 1.353 | 0.928 / 0.74 | 1.71 | 14 |
| small t6 | `gp_msckf_small_t6.wasm` | 1.4M | 1.493 | 1.267 / 0.95 | 1.99 | 24 |
| small t5 | `gp_msckf_small_t5.wasm` | 1.2M | 1.442 | 1.498 / 1.15 | 2.16 | 22 |
| (ours) v4d, for comparison | `submissions/vio_v4d.wasm` | 4.48M | - | 2.53 / 2.47 | 2.72 | 11 |

The MSCKF is chaotic: a few flights per build blow up to 5-14 m, and *which* flights changes with any change to the
code (the original blows up on Train-63 (13.0 m) and 106366104 (8.0 m)). Means over 85 rest flights move by about
+-0.1 m from that alone; medians and the public set are steadier. A and B also keep the 20-flight sandbox median
(0.62 / 0.66 vs the original's 0.67).

## Flags

- A: `FAST_UPDATE=1 COMPRESS_INFO=1 FAST_FROWS=1 FAST_KLT=1 INT_CORNER=1 DETECT_MAX_CELLS=6 MAX_UPDATE_FEATURES=8 CLONE_BATCH_MAX=8` (+ the default `FAST_PYR=1`), `FLAGS=-O3`
- B: A + `DETECT_STRIDE=4 UPDATE_ROWS_MAX=6 GRID_X=8 GRID_Y=5`
- t1: `FAST_UPDATE=1 COMPRESS_INFO=1 FAST_FROWS=1 FAST_KLT=1 INT_CORNER=1 GRAY_GREEN=1 MAX_UPDATE_FEATURES=5 CLONE_BATCH_MAX=5 GRID_X=6 GRID_Y=4 MAX_CLONES=4 DETECT_MAX_CELLS=3 DETECT_STRIDE=3`
- t6: as t1 with `MAX_CLONES=3 DETECT_MAX_CELLS=2 DETECT_STRIDE=4`; t5: as t1 with `GRID_X=5 GRID_Y=3 MAX_CLONES=3 DETECT_MAX_CELLS=1 DETECT_STRIDE=4`

## What changed (A)

Same math, cheaper (results equal up to rounding; the integer ones are bit-identical):
- `FAST_PYR`: gray image + 2x2 pyramid level with wasm SIMD, identical values (1.27M -> ~0.45M per frame).
- `FAST_KLT`: KLT in 16-bit fixed point SIMD (8 lanes), bilinear weights at 1/16 px; an integer host twin gives identical results.
- `FAST_FROWS` + `COMPRESS_INFO`: per-feature residuals from compact 2x6 Jacobian blocks; the gate covariance as Q (Hx P Hx^T) Q^T;
  the batch information H^T H accumulated per feature and compressed by one Cholesky instead of stacking rows + Householder QR.
- `FAST_UPDATE`: EKF update in whitened form (W = L^-1 HP, P -= W^T W, no back-substitution), row-wise SIMD loops.
- `INT_CORNER`: integer corner sums (identical scores).
Behaviour changes that tested neutral or better:
- `DETECT_MAX_CELLS=6`: score at most 6 empty grid cells per frame (spreads detection; mid-flight starts got much better).
- `MAX_UPDATE_FEATURES=8`, `CLONE_BATCH_MAX=8`: at most 8 features per update.

B adds: 40 tracks (8x5 grid), sparser corner candidates (every 4th pixel), and at most 6 MSCKF rows per frame with the rest
applied over the next frames (`UPDATE_ROWS_MAX`, exact for a linear model but not here: it costs ~0.1-0.2 m on the public set).

## What did not work (measured)
- Covariance propagation every 5/10 IMU samples (`PROP_EVERY`): rest median 0.51 -> 0.77-0.93.
- Gray = green channel (`GRAY_GREEN=1`) or (R+2G+B)/4: fine on HF, worse on the public set (0.87 -> 1.29).
- Cheap per-feature gate without covariance (`CHEAP_GATE`): rest median -> 0.76-1.20.
- 5 clones instead of 6: 4.35M but public 0.876, rest median 0.63. 3 KLT iterations: public 1.165.
- Float32 for the update products (`UPDATE_F32`): only -0.2M.

## Below ~1.1M
Smaller MSCKFs bottom out at ~1.1M max fuel: t7 (15 tracks, 3 clones, 6 rows/frame) 1.13M, t8 (12 tracks) 1.13M, both with
HF all ~2.2-2.3 m (rest 1.5-1.8). The per-frame floor is the IMU (0.12M), the image (~0.12M with green gray) and an EKF update
on a 42-dim state. These still beat v4d (2.72 m HF all, 4.48M) on both axes.

## v4d at 10k fuel
Not reachable at v4d's accuracy with any method I found:
- 10k per frame is about what IMU integration alone costs (8k in our v4 code); reading a 320x240 frame once costs far more.
- Vision-free dead reckoning along the camera heading (the autopilot flies ~along the heading, median cosine 0.98) scores
  3.6-4.7 m on the HF set even with the TRUE orientation and speed, vs v4d's 2.7 m and "never moved" 4.1 m.
- Instead, a small MSCKF (t1/t5 above) beats v4d's accuracy at 1/4 to 1/2 of its fuel.

## Where the fuel goes now (A, worst frames ~5.3M; per-frame regression on logged work counts, R^2 0.99)
fixed per frame ~0.86M (IMU 0.12M, pyramid ~0.45M, small EKF updates), 60 tracks x 13k = 0.8M, detection 6 cells x 73k = 0.44M,
features ~40k each, and the MSCKF update ~41k per row + ~0.9k x rows^2 (rows reach ~29 -> ~2M). The update is already near the
minimum multiply-adds for a 54-60 state; wasm spends ~10 fuel per multiply-add. Getting to 1M at the same accuracy would need a
smaller state or a different filter formulation, which cost accuracy every time it was tried tonight.
