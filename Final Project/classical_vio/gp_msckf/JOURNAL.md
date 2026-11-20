> This journal was written in the development workspace; file paths in it (solutions/..., scripts/..., build/...) refer to that workspace, which is not part of this repository. The submitted solution is `solution.c` / `gp_msckf.wasm` in this folder (milestone m7).

# Solution journal

One entry per milestone (a real change to the pipeline, e.g. adding vision or porting to C), with what changed,
why, how to reproduce it and the results. Small tuning steps are folded into their milestone. Each milestone's code
is frozen in `solutions/history/<milestone>/`; the working copy is `solutions/ekf_gp/`.

## Environment

| | |
|---|---|
| viobench | `main` of github.com/jonas-eschmann/viobench, downloaded as a zip on 2026-11-19 (no git, so no commit hash) |
| OS | Windows 11, no WSL |
| Python | 3.13.14 in `.venv` (`python -m venv .venv`, `.venv\Scripts\python -m pip install -e .`) |
| packages | numpy 2.5.5, opencv-python-headless 5.1.0.95, wasmtime 50.0.1, conta 0.0.8, hyperdrone 0.1.10; cmake 4.4.5, ninja 1.13.2 (`.venv\Scripts\python -m pip install cmake ninja`) |
| wasm toolchain | wasi-sdk 34 for Windows (clang 23.1.0): `wasi-sdk-34.0-x86_64-windows.tar.gz` from github.com/WebAssembly/wasi-sdk/releases/tag/wasi-sdk-34, sha256 `cccb5c32β€¦71d8f`, extracted to `build\toolchain\wasi-sdk` |
| data | `viobench.episodes.public`: 10 episodes of 60 s (1200 frames), HyperDrone in ProcTHOR-Train-1, IMU preset x500_fpv_imu (the `DEFAULT_IMU` of `viobench/tools/abi/config.py`), 1 s hover at the start; cached in `~/.cache/conta` |

Metrics: **ATE** = unaligned position RMSE in frame-0 coordinates, mean over episodes with equal weight (the
benchmark's headline). Host runs (`viobench debug`, `scripts/tune_imu.py`) give accuracy only. **Fuel** needs a
`.wasm` and `viobench evaluate`; on Windows only native C/C++ solutions can be built (wasi-sdk), Python ones need Linux.

Private episodes are expected to be harder and to start in flight, so every milestone is also measured with
`--skip 5` (each public episode started 5 s in, ground truth re-referenced to the new first frame).

## Evaluation protocol (from m6 on)

Tuning and scoring on the same 10 episodes invites overfitting, and per-episode ATE spreads 0.4β€“5 m, so a 10-episode
mean is uncertain by roughly Β±0.2β€“0.3 m. From m6 on, decisions use `scripts/robust_eval.py`:

- 40 windows: each public episode started at 0, 5, 15 and 30 s (starts > 0 are in-flight starts);
- per window: ATE, Sim(3) ATE and scale, error 5 s in (startup offset), rotation error at the end, and with a
  `DEBUG_COV=1` build the NEES of output velocity and position (about 3 when the claimed covariance is honest);
- paired difference between two builds with a 95 % bootstrap interval resampling episodes, per offset and for
  episodes 0β€“4 vs 5β€“9 (hold-out check). A change is adopted only if the interval excludes 0 and it has a physical
  reason; settings are derived from data or physics where possible, not swept.

**First use: m6 noise settings (pixel Οƒ 1.5, prior 5) vs the earlier ones (1.0, 3):**

| | B β’ A | 95 % interval |
|---|---|---|
| all 40 windows | β’0.074 m | [β’0.233, +0.067], not significant |
| start 0 / 5 / 15 / 30 s | +0.025 / β’0.177 / +0.143 / β’0.287 m | only 30 s significant |
| episodes 0β€“4 / 5β€“9 | β’0.219 / +0.071 m | inconsistent halves: overtuning |

The sweep's "β’9 %" came mostly from the windows it was tuned on.

**Consistency:** NEES velocity median 12 (m6) / 16 (earlier), position 160 / 344, against an expected ~3: the filter
is overconfident (velocity Οƒ ~2Γ— too small, position ~7β€“10Γ—).

**Error breakdown (m6):**

| start | ATE | error at 5 s | Sim(3) ATE | scale | rotation at end |
|---|---|---|---|---|---|
| 0 s (hover) | 1.059 | 0.143 | 0.481 | 0.998 | 5.5Β° |
| 5 s | 1.893 | 1.528 | 0.547 | 1.004 | 4.2Β° |
| 15 s | 1.994 | 1.092 | 0.576 | 1.113 | 3.6Β° |
| 30 s | 1.714 | 1.276 | 0.477 | 1.072 | 4.0Β° |

The shape is good everywhere (~0.5 m after alignment); the in-flight penalty (~0.8 m ATE) is an offset built up in
the first 5 s. Likely cause, a modelling error: both velocity priors are applied as independent measurements at
20 Hz, so the startup prior Οƒ 0.5 m/s acts like Οƒ β‰ 0.1 m/s after one second, pulling an in-flight start toward
"not moving" and making the filter overconfident.

## m7: one physically scaled velocity prior (`history/m7_msckf_c_prior`, working copy `solutions/msckf_c`)

**Change** (`PRIOR_MODE 1`): the startup prior (Οƒ 0.5 m/s until lock-on) and the after-lock prior (Οƒ 5) are replaced
by one prior "speed per axis ~ Οƒ_s, correlated over Ο„", applied every frame with variance `Οƒ_sΒ² Ο„ / Ξ”t`, so the
frames within one Ο„ carry the information of a single Οƒ_s measurement (before: independent measurements at 20 Hz).
Values are physical bounds, not fitted: Οƒ_s 0.5 m/s per axis (β‰ 0.9 m/s total; public flights mean 0.33, max 0.7),
Ο„ 2 s. Pixel Οƒ 1.5 is kept from m6 (not significant either way).

**Selection** (40 windows, offsets 0/5/15/30; paired vs m6, 95 % bootstrap over episodes):

| prior (per-frame Οƒ) | mean ATE | worst | wins | vs m6 | NEES v / p |
|---|---|---|---|---|---|
| m6 (0.5 then 5) | 1.665 | 3.75 | | | 12 / 160 |
| **Οƒ 0.5, Ο„ 2 (3.2)** | **1.389** | **3.48** | 30/40 | **β’0.276 [β’0.514, β’0.080]** | 8 / 84 |
| Οƒ 1, Ο„ 1 (4.5) | 1.418 | 3.45 | 27/40 | β’0.247 [β’0.544, +0.016] | 8 / 58 |
| Οƒ 1, Ο„ 2 (6.3), the planned value | 1.519 | 4.82 | 26/40 | β’0.146 [β’0.460, +0.212] | 8 / 46 |
| Οƒ 1, Ο„ 5 (10) | 1.554 | 6.35 | 27/40 | β’0.111 [β’0.587, +0.338] | 6 / 34 |
| Οƒ 2, Ο„ 2 (12.6) | 1.692 | 9.55 | 26/40 | +0.027 [β’0.503, +0.646] | 6 / 31 |

Not flat in prior strength: weaker priors let some in-flight windows diverge, so the filter still relies on the prior
while vision locks on (an open weakness, not tunable away).

**Confirmation on fresh windows** (offsets 10/20/40, not used for the choice; 30 windows):

| | vs m6 | halves 0β€“4 / 5β€“9 | worst (m6 5.05) | NEES v / p (m6 17 / 309) |
|---|---|---|---|---|
| **Οƒ 0.5, Ο„ 2 (adopted)** | **β’0.304 [β’0.487, β’0.137]** | β’0.322 / β’0.286, both significant | 3.99 | 8 / 125 |
| Οƒ 1, Ο„ 1 | β’0.385 [β’0.646, β’0.114] | β’0.513 / β’0.256 (second n.s.) | 3.97 | 8 / 72 |

Two settings of similar strength both win, so the gain is not one lucky value. Οƒ 0.5, Ο„ 2 was the value committed to
before the confirmation run.

**Results m7** (70 windows, fuel max ~20.8 M, median ~9.6 M; scores on the assumed baselines):

| | m6 | **m7** |
|---|---|---|
| hover start (offset 0) | 1.059 m | **0.749 m** |
| in-flight starts (offsets 5/10/15/20/30/40, mean) | 1.775 m | **1.491 m** |
| score at the in-flight ATE | 3.46 % | **4.04 %** |

The filter is still overconfident (velocity NEES ~8, position ~80β€“125 vs ~3 expected), and the in-flight startup
offset (~0.7β€“1.3 m after 5 s) remains the main error.

**Reproduce:**

```powershell
.\scripts\build_variant.ps1 ref_m6 "PRIOR_MODE=0 DEBUG_COV=1"
.\scripts\build_variant.ps1 m7 "DEBUG_COV=1"
.venv\Scripts\python scripts\robust_eval.py build\variant_ref_m6.wasm build\variant_m7.wasm
.venv\Scripts\python scripts\robust_eval.py build\variant_ref_m6.wasm build\variant_m7.wasm --offsets 10 20 40
```

## External check: server-calibrated episodes (held-out, after m7)

Data: `SentientNapkin/viobench-server-calibrated` on the Hugging Face Hub, a third-party draft (licence "other"):
171 generated episodes in the official format, flights calibrated to the course server's reported path lengths
(~60 m vs 18 m public; e.g. median speed 0.85 m/s, p90 1.8 m/s), half of them mid-flight starts. Used only as a
held-out test, never for tuning. `scripts/eval_external.py` downloads in batches of 5, checks sha256 against the
manifest, runs the builds in the sandbox, saves `build/external.json` and deletes the batch.

**First 30 in manifest order** (all hover starts: the manifest lists its 85 hover starts first; identity 4.238 m):

| build | mean ATE | median | worst | fuel max | paired vs m6 [95 %] |
|---|---|---|---|---|---|
| m6 | 0.757 | 0.349 | 7.733 | 21.1 M | |
| **m7** | 0.760 | 0.498 | 8.038 | 21.6 M | +0.003 [β’0.089, +0.083], same |
| Οƒ 1, Ο„ 1 | 0.867 | 0.468 | 11.03 | 21.1 M | +0.110 [β’0.094, +0.380] |
| Οƒ 1, Ο„ 2 | 1.288 | 0.428 | 23.84 | 21.1 M | +0.531 [β’0.100, +1.663] |

- m7 generalizes to the faster flights on hover starts (median < 0.5 m, mean 0.76 m vs identity 4.24, flat fuel);
  m6 and m7 are equal here, consistent with m7's gain coming from in-flight starts.
- Velocity NEES ~3.7 on these flights: close to honest.
- Heavy tail: `fast-106366104_174226329-00` (manifest flag *textureless*, fast flight up to 2.2 m/s) fails for every
  build (m7 8.04 m, identity 6.52 m). Weaker priors make the tail much worse, supporting m7's prior strength.
- Mid-flight starts not yet tested on this set (manifest positions 86β€“171).

## Submission package (m7, cleaned)

`solutions/submission/solution.c`: the m7 filter only (no research switches, no parked VI init), fully documented;
README alongside. Verified bit-identical to the m7 research build on 4 windows (`scripts/compare_two_wasm.py`: max
difference 0.0). Submission file `dist/gp_msckf.wasm` (70 KB) with its sha256 in `dist/gp_msckf.wasm.sha256`.

Official `viobench evaluate` on the public set: **mean ATE 0.749 m, fuel per frame max 18,982,624** (median 9.59 M,
p99 16.9 M), 10/10 completed, no filled frames.

## Tools

| script | what it does |
|---|---|
| `scripts/synthetic_check.py` | solutions on the analytic scenes of `tests/vio_scene.py` (noisy IMU, known biases); no download |
| `scripts/tune_imu.py` | settings sweep of an IMU-only solution on the public episodes, frames not decoded; `--skip S` for in-flight starts, `--solution DIR` picks the version, identity printed as reference |
| `scripts/build_native.ps1` | Windows replacement for `runtime/native/build.sh`: C/C++ solution directory β†’ `build\<name>.wasm` with wasi-sdk (no OpenCV) |

Fuel, the benchmark's way (works on Windows for native solutions):

```powershell
.\scripts\build_native.ps1 <solution dir>                    # -> build\<name>.wasm
.venv\Scripts\viobench check build\<name>.wasm               # a few synthetic frames: errors, fuel per step
.venv\Scripts\viobench evaluate build\<name>.wasm -o build\report-<name>   # all 10 public episodes: ATE + fuel/frame
```

`viobench` prints a `PermissionError ... stderr.txt` traceback on Windows when it cleans up a temp folder; it is
harmless (the results are unaffected).

## m0: baselines (repo examples)

```powershell
.venv\Scripts\viobench debug viobench\solution\examples\python\minimal
.venv\Scripts\viobench debug viobench\solution\examples\python\dead_reckoning
.venv\Scripts\viobench debug viobench\solution\examples\python\klt_imu --max-episodes 1
```

| solution | mean ATE, normal start | mean ATE, `--skip 5` | Sim(3) ATE | documented fuel/frame |
|---|---|---|---|---|
| identity (`minimal`) | 4.892 m | 5.066 m | 2.7β€“4.3 m | 0.09 M |
| `dead_reckoning` | 7.329 m | β€“ | 0.8β€“2.4 m | 4.0 M |
| `klt_imu` | episode 0 only: 482.3 m (scale blow-up) | β€“ | 2.0 m | 50β€“130 M, p95 500 M |

Per-episode identity ATE: 7.78 8.44 2.81 5.66 3.36 3.88 5.63 3.81 3.78 3.78.

Toolchain check: `cpp_minimal` built with `scripts/build_native.ps1` and evaluated on episode 0 gives ATE 7.780 m
(identical to the Python identity) at **113 fuel/frame**, flat. The examples README's "2.2 M, reads every pixel once"
is stale: the current `solution.cpp` never reads the frame.

## m1: IMU-only error-state EKF with GP bias states (`history/m1_imu_ekf`)

**Pipeline.** Error-state EKF, 18 error states `[dΞΈ, dv, dp, db_g, db_a, dΞΈ0]` (local angle errors; `dΞΈ0` is a
clone of the frame-0 orientation so the output stays relative to frame 0 while tilt is refined).

1. *Init (frame 0)*: roll/pitch from the mean specific force of the first IMU window (world z = up, world yaw = body
   yaw: gauge), `p = 0`, `v = 0` with Οƒ 1 m/s, biases 0 with the GP prior variance `maxΒ²/3` (uniform initial bias).
2. *Propagate (every IMU sample)*: bias-corrected strapdown integration; `P β† F P Fαµ€ + Q`.
3. *GP bias prior*: kernel `Οƒ0Β² + Οƒ_rwΒ² min(t, t')` (constant + Wiener), i.e. a random-walk state with
   `Q_b = Οƒ_rwΒ² Β· 200 Β· dt` (random walk read as per-sample std); option `BIAS_KERNEL = "ou"` (MatΓ©rn-Β½,
   `b' = e^(-dt/Ο„) b`, `Q = Οƒ0Β²(1 - e^(-2dt/Ο„))`).
4. *Updates (every frame, Ο‡Β² gate at 99 %, Joseph form)*:
   - tilt: `mean(f) = R_hatαµ€(-g) + b_a`, Οƒ 1 m/sΒ² (approximate: a quadrotor's accelerometer measures thrust);
   - weak velocity prior `v ~ N(0, 3Β²)` per frame (bounds IMU-only drift);
   - ZUPT in the opening phase: implemented but **off** (`USE_ZUPT = False`), see below.
5. *Output*: `T_c0_ck = T_cam_imu Β· [R0αµ€R, R0αµ€p] Β· T_imu_cam`; twist in camera axes with the lever arm.

**Reproduce:** `.venv\Scripts\python scripts\tune_imu.py --solution solutions\history\m1_imu_ekf` (and `--skip 5`).

**Results** (mean ATE over 10 episodes):

| | normal start | in-flight start (`--skip 5`) |
|---|---|---|
| identity | 4.892 m | 5.066 m |
| **m1** | **4.892 m** | **5.064 m** |
| with opening-phase ZUPT | 4.939 m | 5.279 m (up to +0.97 m on one episode) |
| without velocity prior | 9.660 m | 8.919 m |
| other settings (tilt Οƒ, OU kernel, random-walk units, prior Οƒ 1β€“6) | 4.887β€“4.896 m | 5.062β€“5.070 m |

The ZUPT recovers the gyro bias well on synthetic data (error 0.021 β†’ 0.005 rad/s in 2 s) but pins the velocity to
0 when an episode starts in flight, so it is off.

**Conclusion.** IMU-only, velocity is unobservable: the filter lands exactly at identity's ATE, at more fuel, so m1
adds no frontier area by itself. Its bias and covariance machinery is the backbone for vision.

### Why IMU-only cannot beat identity (analysis after m1)

- *Scoring* (`scripts/score.py`, the server's `area_gains`): the ATE axis spans ~8.7 log-units, fuel ~24; a point at
  identity's ATE gains nothing, so ATE is the lever (e.g. 2 m @ 0.12 M β‰ 5 % of the box, 0.5 m @ 1 M β‰ 11 %).
- *No rotor drag* (`scripts/analyze_drag.py`): body x/y specific force is pure bias + white noise (corr with body
  velocity < 0.08), so the accelerometer gives no velocity information; it does measure b_a,xy directly.
- *Oracle drift* (`scripts/imu_limits.py`): true start state and true biases, pure integration: 0.04 m after 1 s,
  1β€“2 m after 5 s, 4β€“8 m after 10 s, 37β€“74 m after 30 s (Β½Β·aΒ·tΒ², a β‰ 0.08 m/sΒ²). Over 60 s the best IMU-only
  position estimate is "near the start", which is identity.
- *Bias random walk*: measured drift (0.020 rad/s peak-to-peak with 2 s smoothing) is mostly smoothing noise; it fits
  the per-βs (density) reading of the config, not the per-sample one. To switch when vision lands.
- *Sweep* of the thrust model (`USE_THRUST_MODEL`), velocity prior Οƒ 0.5β€“3 m/s and a position prior Οƒ 3β€“10 m:
  every variant 4.889β€“4.894 m (normal start) and 5.064β€“5.069 m (`--skip 5`), i.e. no change.
- *Trajectory prior* (`scripts/trajectory_prior.py`): flights have no consistent direction relative to frame 0
  (mean final position [-0.08, 0.03, 0.93] m, spread [3.3, 0.3, 4.8] m; altitude is held, vertical RMS 0.3β€“0.7 m).
  Predicting the mean trajectory of the other episodes, scaled Γ—0.25, gives 4.835 m leave-one-out (β’1.2 %), with
  per-episode swings of Β±0.5 m: too small and too dataset-specific to use.
- *Fuel*: shaving the filter's 0.12 M changes nothing while its ATE equals identity's (zero area at any fuel), and
  is negligible next to vision later.

## m2: m1 ported to C (`history/m2_imu_ekf_c`, working copy `solutions/ekf_gp_c`)

**Change.** The m1 filter (ZUPT off) in plain C: fixed-size arrays, `T_cam_imu` read from the config with a minimal
JSON scan, nothing allocated after `init`. Two fuel optimizations, both exact:

- *propagation*: `F` is the identity except five 3Γ—3 blocks (`TH-TH = dRαµ€`, `TH-BG = -dt I`, `V-TH = -dt R[a]Γ—`,
  `V-BA = -dt R`, `P-V = dt I`), so `F P Fαµ€` is done as a row pass and a column pass over the TH, V, P blocks only;
- *update*: `P β† P - K (P Hαµ€)αµ€` over the nonzero columns of `H`, upper triangle mirrored, instead of the dense
  Joseph form. The dense code stays behind `-DDENSE_COVARIANCE`.

**Reproduce:**

```powershell
.\scripts\build_native.ps1 solutions\history\m2_imu_ekf_c
.venv\Scripts\python scripts\compare_wasm.py build\m2_imu_ekf_c.wasm solutions\history\m1_imu_ekf --episodes 2
.venv\Scripts\viobench evaluate build\m2_imu_ekf_c.wasm
```

**Results.** Matches the Python m1 frame by frame (max difference 1e-13 over 2 episodes). `viobench evaluate`,
10 public episodes:

| | mean ATE | fuel/frame max (median) |
|---|---|---|
| identity (`cpp_minimal`) | 4.892 m | 113 |
| m2, dense port | 4.892 m | 700,643 (700,521) |
| **m2** | **4.892 m** | **122,466 (122,344)** |

Fuel is flat (p99 = max). Per-episode ATE 7.78 8.44 2.80 5.66 3.35 3.88 5.63 3.81 3.78 3.78; rotation error 7.5β€“35.6Β°.

**Conclusion.** The filter backbone costs ~0.12 M fuel/frame, negligible next to vision (OpenVINS: 33 M). As a
submission it sits at identity's ATE with 1,000Γ— its fuel, i.e. strictly worse than identity: the gain has to come
from vision. Rotation error (up to 36Β°) is the first thing to watch once vision feeds in velocity.

## m3: visual-inertial MSCKF, Python prototype (`history/m3_msckf_py`, working copy `solutions/msckf`)

**Image data first** (`scripts/track_stats.py`, OpenCV KLT at 320Γ—240): corners are plentiful (80 of 80 every
frame) despite large plain walls; the lens is very wide (fx 97β€“123 px, ~117Β° horizontal, varies per episode);
tracks: median 2β€“5 frames but 22β€“30 % live past 20 frames; translational parallax (rotation removed with ground
truth) 0.4β€“0.5 px after 1 frame, 3β€“4 px after 10, 5β€“7 px after 20. So two-frame methods (klt_imu) see only noise,
and the estimator needs a ~1 s window.

**Pipeline** (on top of m1's error-state EKF with GP bias states):

1. *Tracking*: gray image, pyramidal KLT (15Γ—15, 3 levels), forward-backward check (0.5 px), topped up to 60
   corners per frame (`goodFeaturesToTrack`, quality 0.01, min distance 10 px).
2. *Clones*: every 4 frames the IMU pose (R, p) is cloned into the state (6 error dims, covariance augmented with
   `J = [I on dΞΈ; I on dp]`); 6 clones kept (24 frames β‰ 1.2 s). Only clone-frame observations are stored.
3. *MSCKF update*: a feature with β‰¥ 3 clone observations is used once, when its track ends or when its oldest clone
   leaves the window: linear triangulation (ray-matrix eigenvalue check) + 3 Gauss-Newton steps, depth 0.2β€“40 m;
   residuals `z - Ο€(R_cαµ€(p_f - p_c))` (Οƒ 1 px), Jacobians `β‚/β‚dΞΈ_c = JΟ€ R_bcαµ€ [R_cαµ€(p_f - p_c)]Γ—`,
   `β‚/β‚dp_c = -JΟ€ R_bcαµ€ R_cαµ€`; projected onto the left null space of the feature Jacobian (QR); per-feature Ο‡Β² gate
   (95 %, Wilson-Hilferty); one stacked update, QR-compressed when taller than the state.
4. *Vision ZUPT*: at each clone, median de-rotated disparity (gyro rotation) of features seen in the last two clones;
   below 0.4 px β†’ `v = 0` (Οƒ 0.02 m/s). Cannot fire in steady flight, unlike an IMU ZUPT.
5. *Backbone changes*: bias random walk per βs, thrust model on (body x/y specific force = b_a,xy), gravity tilt
   update off; velocity prior Οƒ 3 m/s, and Οƒ 0.5 m/s until vision has locked on (100 features used).

**Development steps** (mean ATE over the 10 public episodes; `scripts/eval_vision.py`, timeline in
`scripts/diagnose.py`):

| step | normal start | in-flight (`--skip 5`) | finding |
|---|---|---|---|
| identity | 4.892 | 5.066 | |
| first prototype | 3.462 (7/10 < identity) | 3.801 | without the velocity prior it diverges (750 m) |
| + vision ZUPT | 1.916 (10/10) | 2.848 | the opening hover gave no parallax, velocity drifted 0.43 m/s in 1 s, then every feature failed triangulation (893 of 893) |
| triangulation cutoff 1e-3 β†’ 1e-6 | **1.061** (10/10) | 2.715 (9/10) | 1e-3 rejected ~75 % of tracks on this wide lens (2,000 failures vs 700 used per episode); 1e-7 = 1e-6 |
| + initial velocity prior Οƒ 0.5 until lock | 1.201 (10/10) | **2.205** (10/10) | in flight the accelerometer gives no tilt (it points along thrust), velocity drifted to 3 m/s before vision locked, leaving a 5 m offset |

Tried and not kept: no velocity prior (diverges on 3β€“6 episodes), velocity prior Οƒ 10 (1.37 / 3.25 m), 10 clones
(5.35 m), initial tilt Οƒ 0.1 (2.45β€“2.61 m in flight).

**Reproduce:** `.venv\Scripts\python scripts\eval_vision.py --solution solutions\history\m3_msckf_py` and `... --skip 5`.

**Fuel: not measured** (Python solutions cannot be built on Windows). Estimate for a C port of this exact design:
20β€“35 M at the worst frame, dominated by KLT (forward-backward, 4 levels, 15Γ—15) and the batched update every 4th
frame (max-fuel spike). Planned reductions for the C port: no forward-backward check, 1β€“2 pyramid levels with a
gyro-predicted start, 9Γ—9 window, corner detection only in empty grid cells, updates spread over frames.

**Open:** in-flight starts still cost ~1 m more than hover starts; a closed-form visual-inertial initialization
(velocity and gravity from the first ~1 s) is the proper fix.

*Parked after m3:* a closed-form VI initialization (linear in v0 and g, features eliminated by Schur complements;
`USE_VI_INIT`, off in `solutions/msckf`). Checked against ground truth (`scripts/check_vi_init.py`) and a
synthetic unit test (`scripts/test_vi_init_synthetic.py`): exact on noise-free data, but the linear ray equations
are biased toward zero scale under pixel noise (0.1 px: |v0| 0.46 β†’ 0.03 m/s); refining on the image reprojection
error is the fix, left unfinished (the public episodes all start from a hover). The private set is expected to start
in flight, so m3's startup velocity prior stays.

## m4: m3 in C (`history/m4_msckf_c`, working copy `solutions/msckf_c`)

**Change.** The m3 filter, unchanged, in C without OpenCV. Own image front end:

- gray `(77 R + 150 G + 29 B + 128) >> 8`; 3-level pyramid of 2Γ—2 means;
- pyramidal inverse-compositional KLT (translation), 11Γ—11 window, β‰¤ 10 iterations per level, start at the
  gyro-predicted position (`K R_rel Kβ»ΒΉ`), drop if mean |I β’ T| > 25 or the template Hessian is weak; **no**
  forward-backward check (compile switch `KLT_FB`; the MSCKF Ο‡Β² gate handles outliers);
- Shi-Tomasi (3Γ—3 block of central differences) on a 10Γ—6 grid, one feature per cell (β‰¤ 60), scored only in empty
  cells at stride 2, threshold 1000 (β‰ OpenCV quality 0.01 on these frames: per-frame best corner 93kβ€“104k);
- MSCKF exactly as m3: null-space projection by 3 Householder reflections on `[Hf | Hx | r]`, per-feature Ο‡Β²,
  stacked update QR-compressed to the state size, `P β† P β’ (HP)αµ€ Sβ»ΒΉ HP`.

One porting bug found with on-stderr counters (`scripts/diagnose_wasm.py`): the triangulation Gauss-Newton used
`JΟ€ R_wc` instead of `JΟ€ R_wcαµ€`, which made the updates push velocity to 1β€“4 m/s (episode 0: 28 m error after 30 s).

**Reproduce:**

```powershell
.\scripts\build_native.ps1 solutions\history\m4_msckf_c
.venv\Scripts\python scripts\eval_wasm.py build\m4_msckf_c.wasm            # sandbox, same fuel metering as evaluate
.venv\Scripts\python scripts\eval_wasm.py build\m4_msckf_c.wasm --skip 5   # in-flight start
```

**Results** (10 public episodes, fuel from the sandbox):

| | mean ATE | worst | fuel/frame max | median | p99 |
|---|---|---|---|---|---|
| normal start | **0.988 m** (identity 4.892) | 2.260 | 55.3 M | 14.4 M | ~41 M |
| in-flight (`--skip 5`) | **2.434 m** (identity 5.066) | 5.192 | 56.1 M | 14.5 M | ~41 M |

All 10 episodes beat identity in both. Score (`scripts/score.py` logic, assumed Python baselines): 4.7 % of the box
at the normal-start ATE, 2.0 % at the in-flight ATE.

**Where the fuel goes:** ~14 M every frame, nearly all KLT (60 features Γ— 3 levels; the template alone takes 605
bilinear samples per feature-level, and every sample recomputes its integer position and weights); every 4th frame
(clone) adds ~30β€“40 M for the MSCKF batch (gating `H0 P H0αµ€` per feature, QR compression of a few hundred rows,
a 60-dimensional update). The max-fuel metric is set by the clone frames.

## m5: fuel cuts on m4 (`history/m5_msckf_c_fuel`, working copy `solutions/msckf_c`)

**Profile first** (`scripts/profile_fuel.ps1`: builds with components switched off via `PROFILE_SKIP`, fuel from
`scripts/fuel_stats.py` on the first 30 s of episode 0): clone frames 30.8 M median / 52.8 M max, other frames
11.2 M; the MSCKF batch adds 19.5 M median (up to 41 M) on clone frames, KLT ~8.3 M per frame, the rest ~2.8 M.

**Changes** (in order; episode-0 fuel per frame, median / max):

| change | median | max | exact? |
|---|---|---|---|
| m4 | ~14 M | 52.8 M | |
| KLT: one bilinear patch read per template (gradients by differences inside it) and constant weights per iteration | | | yes |
| MSCKF spread over frames (`SPREAD_UPDATES`): ended tracks every frame (β‰¤ 20), tracks about to lose the oldest clone in thirds on the 3 frames before it leaves; QR compression and update restricted to the clone columns (the rows are zero on the core) | 14.0 M | 22.5 M | yes (same estimator, processed earlier) |
| per-feature gating over the observing clones' columns only | 13.9 M | 22.3 M | yes |
| tracker: 2 pyramid levels, 9Γ—9 window, β‰¤ 5 iterations, 0.1 px stop on the coarse level | **9.4 M** | **18.7 M** | no |

Tried, not kept: per-frame cap of 8 ended tracks (no effect: fewer end per frame); 5 clones (max 14.8 M; see below).
Variants are built with `scripts/build_variant.ps1 <name> "DEFINE=value ..."`.

**Results** (10 public episodes, sandbox fuel; score with the server's area code against the assumed Python
baselines identity 0.09 M / 4.892 m and dead_reckoning 4 M / 7.329 m):

| | normal start | in-flight (`--skip 5`), worst | fuel max | median | score (in-flight ATE) |
|---|---|---|---|---|---|
| m4 | 0.988 m | 2.434 m, 5.19 | 56.1 M | 14.5 M | 2.04 % |
| exact changes only (3 levels, 11Γ—11) | **0.907 m** | 2.127 m, 3.51 | 24.5 M | 14.0 M | |
| **m5** (fast tracker, 6 clones) | 1.034 m | **2.070 m, 3.11** | 20.2 M | 9.6 M | **2.94 %** |
| fast tracker, 5 clones | 1.067 m | 2.143 m, 4.49 | 15.4 M | 9.0 M | 2.93 % |

Spreading the updates also improved accuracy (tracks are used as soon as they end, at fresher linearization points).
m5 keeps 6 clones: the same score as 5 clones with a clearly better worst case, which matters for a harder private
set. With the in-flight priority, m5 trades 0.13 m at normal starts for the best in-flight ATE and the least fuel.

**Reproduce:**

```powershell
.\scripts\build_native.ps1 solutions\history\m5_msckf_c_fuel
.venv\Scripts\python scripts\eval_wasm.py build\m5_msckf_c_fuel.wasm --skip 5
.venv\Scripts\python scripts\eval_wasm.py build\m5_msckf_c_fuel.wasm
```

**Remaining fuel** (~9.4 M median): KLT ~5 M, gray/pyramid/detection/IMU ~2.8 M, MSCKF updates the rest; the max
(~19β€“20 M) comes from frames that process the third of tracks leaving the window.

## m6: noise tuning; VI initialization tried in C and left off (`history/m6_msckf_c_tuned`)

**Why these levers:** the score's exchange rate at m5's in-flight point (server area code): halving ATE +2.36
points, halving fuel +0.28; doubling fuel pays for itself at about a 9β€“10 % ATE reduction.

**Noise sweep** (`scripts/sweep.ps1`, compile-time variants, in-flight start, reference m5 2.070 m):

| setting | mean ATE | worst |
|---|---|---|
| pixel Οƒ 0.5 / 0.7 / 1.0 / **1.5** / 2.0 px | 2.370 / 2.063 / 2.070 / **1.875** / 2.015 | 4.34 / 3.45 / 3.11 / 3.65 / 3.89 |
| velocity prior after lock-on Οƒ 2 / 3 / **5** m/s | 2.017 / 2.070 / **1.926** | 3.49 / 3.11 / **2.92** |
| Ο‡Β² gate 95 % β†’ 99 % | 2.024 | 4.00 |
| startup velocity prior Οƒ 0.3 / 1.0 (0.5 kept) | 2.417 / 2.066 | |
| lock-on after 300 features (100 kept) | 2.060 | |
| **pixel Οƒ 1.5 + velocity prior 5** | **1.893** | **2.90** |
| + Ο‡Β² 99 % / pixel Οƒ 2.0 + prior 5 / pixel 1.5 + prior 8 | 2.016 / 1.986 / 2.007 | |

A larger pixel Οƒ helps: the filter was overconfident in single tracks. The combination is kept for its worst case.

**VI initialization** (for in-flight starts):

- *Python* (`solutions/msckf`, `USE_VI_INIT`): the refinement now uses variable projection (each inverse depth
  re-fitted by 1-D Gauss-Newton at every candidate v0/g; LM steps accepted only if that cost drops). Synthetic test
  (`scripts/test_vi_init_synthetic.py`): v0 error 0.04 m/s and gravity 0.10Β° at 0.3 px noise (linear only:
  0.50 m/s, 1.4Β°). Real data (`scripts/check_vi_init.py`): no longer biased toward zero (estimates 0.08β€“0.58 vs true
  0.10β€“0.56 m/s) but 0.06β€“0.30 m/s and ~1Β° error. End-to-end in-flight: **1.875 m with vs 2.205 m without**.
  Reference copy: `history/m6_msckf_c_tuned/python_vi_init_reference/solution.py`.
- *C* (`USE_VI_INIT`, off by default): window records per track, preintegration with `β‚Ξ±/β‚b_a`, linear 9Γ—9 solve
  with a b_a prior, reprojection refinement on β‰¤ 30 longest tracks at every 2nd frame (camera poses precomputed per
  solve: an attempt costs ~18β€“20 M, first version 33β€“36 M). It rarely succeeds on the first window (episode 2:
  accepted at 4.8 s instead of 1.2 s; earlier attempts diverge). Not caused by tracker outliers (same with
  `KLT_FB=1`) nor by size (same with 60 tracks, every frame, 15 iterations); a capped robust cost made it worse
  (from v0 = 0 every feature looks like an outlier). Most likely the C tracks: ~30 tracks last β‰¥ 8 frames in the
  window vs ~65 with OpenCV. End-to-end in C:

| C build | in-flight | normal start | fuel max |
|---|---|---|---|
| **VI init off (m6)** | **1.893 m** | 1.059 m | **19.5 M** |
| VI init on | 1.933 m | 1.013 m | 24.8 M |

**Results m6** (10 public episodes, sandbox fuel): in-flight **1.893 m** (worst 2.90), normal start **1.059 m**
(worst 1.69), fuel max 19.5 M, median 9.7 M. Score on the assumed baselines: **3.26 %** at the in-flight ATE
(m5 2.94 %), 5.27 % at the normal-start ATE.

**Reproduce:**

```powershell
.\scripts\build_native.ps1 solutions\history\m6_msckf_c_tuned
.venv\Scripts\python scripts\eval_wasm.py build\m6_msckf_c_tuned.wasm --skip 5
.venv\Scripts\python scripts\eval_wasm.py build\m6_msckf_c_tuned.wasm
```

**Re-validated with the robust protocol (below): the noise tuning is not a significant improvement.**

**Open:** the in-flight gap (1.89 vs 1.06 m) remains. Longer, cleaner C tracks for the VI window (e.g. more
features during the first seconds, or the forward-backward check only until initialized) are the likely way to make
the C VI init match Python's.

