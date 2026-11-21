# Pushing mean unaligned ATE of a mono+IMU MSCKF far below ~0.78 m (hard cases: rigid offset from bad startup velocity/heading)

Scope note: ~10 web calls only. Several primary sources (OpenVINS docs pages, OpenVINS paper tables) could not be fetched (404 / not reached); numbers from secondary summaries are flagged. Items under "Inferences" are my own reasoning, not sourced.

## Q1. Initialization from non-static starts; which can run late (1-3 s) and re-anchor a running filter

### Takeaway
Modern closed-form/linear initializers (OpenVINS-style dynamic init, Cerezo et al. 2025, VINS-Mono alignment) solve velocity+gravity+biases from a short window with parallax and need no static start; the published 2025 closed-form solver needs ~0.5 s windows and <1 ms. Nothing found describes re-anchoring a running MSCKF directly, but the outputs (v0, g, biases at window start) are exactly what is needed for a replay-from-t=0 scheme.

### Cited Findings
- OpenVINS's InertialInitializer dispatches between a static initializer (platform still, then jerk detected) and a dynamic initializer (when dynamic init enabled and platform moving) based on disparity/IMU checks — [OpenVINS InertialInitializer source](https://docs.ros.org/en/api/ov_init/html/InertialInitializer_8cpp_source.html). I could not confirm the dynamic solver's exact formulation from fetched material.
- Closed-form full VI initialization (Cerezo, Lee, Civera 2025): gyro bias from closed-form relative rotation of first two frames; velocity, gravity, accel bias and point depths from one linear least-squares (SVD); assumes small rotations over the window and roughly constant biases. Observability test = average parallax threshold, then singular-value-ratio stability of the 9x9 (gravity, velocity, accel-bias) Hessian after Schur-marginalizing depths. Adaptive window averages 0.48 +/- 0.27 s on EuRoC (Campos et al. 2.16 s, He et al. 2.5 s). EuRoC velocity RMSE 0.09 m/s vs 0.11 (VINS-Mono), 0.17 (AS-MLE); gravity direction error 0.90 deg vs 1.47 deg (VINS-Mono); total init time 0.96 ms vs 30.94 ms (VINS-Mono). EuRoC only (no TUM-VI) — [Efficient Closed-Form VI Initialization](https://arxiv.org/html/2511.18910v2)
- VINS-Mono init: vision-only SfM, then gyro bias, then velocity/gravity/scale, then gravity refinement with magnitude constraint (2-DOF tangent) — [VINS-Mono](https://arxiv.org/pdf/1708.03852). SfM is unstable in fast motion or few common features — [EDI](https://arxiv.org/pdf/2308.02670); drone-racing work reports init errors show up as roll/pitch error from gravity inferred from short noisy motion — [A2RL finalist](https://arxiv.org/pdf/2602.01860).
- Learned/depth-aided init: monocular learned depth used as init input to cope with low excitation (Google AR) — [arXiv 2204.09171](https://arxiv.org/abs/2204.09171v2); scale-less single-image depth in a closed-form linear init (Merrill, Geneva et al.), with a related result that up-to-scale depth constraints cut init time to ~0.5 s — [NSF PAR](https://par.nsf.gov//servlets/purl/10479088); feed-forward up-to-scale point clouds -> closed-form velocity/gravity/scale then VI-BA — [arXiv 2605.17327](https://arxiv.org/pdf/2605.17327); probabilistic normal epipolar constraint init with scale/gravity refinement — [arXiv 2410.19473](https://arxiv.org/html/2410.19473v2).
- Learned covariance for initialization/calibration (MAC-I^2) and a controlled study on when learned priors help init — [MAC-I2](https://arxiv.org/pdf/2609.07116), [Learned priors study](https://arxiv.org/pdf/2609.13777). Only titles seen; contents not read.

### Inferences
- Late re-anchoring recipe (fits wasm budget): buffer first ~3 s of IMU + tracked features (20 Hz x 60 frames); at t~1.5-3 s run a closed-form linear solve for v0, g-direction refinement, accel bias (single ~9x9 Hessian, ~1 ms-class); then reset filter state at t=0 (or at window start) with the solved v0 and a sane covariance, and replay buffered IMU+tracks once. Cost is a one-off ~(window frames x one filter pass), bounded, not per-frame.
- Your learned CNN velocity is a prior; the linear solve gives an independent, observability-gated measurement; fuse (weight by Hessian) rather than replace. Gate on parallax + singular-value stability as in the paper; if gating never passes, keep the CNN prior.
- Mono scale is ~1 in your bad episodes, so solve with scale fixed/known-ish from IMU; fewer unknowns improves conditioning with only 0.07 rad/s gyro noise.
- Caveat: these solvers assume small rotation and constant bias; with aggressive start-motion and 0.07 rad/s noise, validate on your 4 bad episodes before trusting; published numbers are on EuRoC with much cleaner IMU.

### Gaps
- OpenVINS dynamic-init formulation and thresholds (docs pages 404). No source found on resetting a running MSCKF from a late initializer. No TUM-VI init numbers found. No data on how these solvers behave with gyro noise as high as 0.07 rad/s.

## Q2. Retroactive smoothing of the first seconds (replay, fixed-lag, two-pass)

### Takeaway
I did not find a paper that specifically documents replay-from-t=0 for an MSCKF; the idea follows from the init literature above (init window then filter start). Treat as engineering design, not an evidence-backed result.

### Cited Findings
- (none specific found) Closest: OpenVINS/EuRoC-style systems initialize over a window and start the filter from the solved state — [Efficient Closed-Form VI Initialization](https://arxiv.org/html/2511.18910v2) (window lengths 0.5-2.5 s).

### Inferences
- Two-pass option: run filter forward (cheap), then at t~3 s estimate rigid correction (v0, heading, g) and re-run once from buffered data; total cost ~2x for the first 3 s only. Forward-backward smoothing over the full 60 s is cost-prohibitive for the budget; a rigid-offset correction applied analytically to the already-estimated trajectory is cheaper: since error is a rigid offset set in first seconds, errors in v0 cause p(t)-error ~ dv*t (growing), heading error is a rotation about gravity of the whole trajectory; both can be corrected post hoc if later estimates of those quantities arrive (e.g. from closed-loop visual consistency), but only if outputs are emitted at end (check task output format allows revising past poses — unknown).
- Heading (yaw) is unobservable in VIO; "wrong heading" under unaligned ATE is only a gauge issue if the reference frame is defined by the start pose. If scoring uses the true initial orientation, a yaw prior from a learned head (as in your gp_msckf+heading prior) is the only source; no VIO method can fix it by itself.

### Gaps
- No sourced evidence on fixed-lag/replay cost, or on ablation of re-running from t=0.

## Q3. Consistency fixes (FEJ, OC, RI-EKF, robocentric, InEKF)

### Takeaway
FEJ is the cheapest, best-supported fix (reported significant precision gain on EuRoC in an unofficial OpenVINS log); RI-MSCKF and OC-VINS also improve consistency. These help drift/consistency, not a wrong start velocity.

### Cited Findings
- Li & Mourikis applied FEJ to MSCKF and improved consistency over standard MSCKF — [summary via FEJ-VIRO](https://arxiv.org/pdf/2207.08214); OpenVINS FEJ docs — [OpenVINS FEJ](https://docs.ros.org/en/api/ov_core/html/fej.html).
- OC-VINS projects Jacobians to enforce unobservable directions — [Hesch et al. ISER 2012](https://www-users.cse.umn.edu/~stergios/papers/ISER-2012-OC-VINS-MSCKF.pdf).
- RI-MSCKF clearly beats MSCKF on consistency in 50 Monte Carlo sims; needs no extra computation, unlike OC projection — [Invariant-EKF VINS](https://arxiv.org/pdf/1702.07920). IEKF with FEJ outperforms standard FEJ-EKF (Yang et al., as cited there). EqVIO: symmetry-exploiting filters fix observability mismatch — [EqVIO](https://arxiv.org/pdf/2205.01980).
- Unofficial OpenVINS fork notes: FEJ gives significant precision improvement on mono and stereo EuRoC — [symao/open_vins](https://github.com/symao/open_vins) (unofficial, no numbers captured).

### Inferences
- If your filter lacks FEJ/OC, spurious yaw observability makes the covariance overconfident in heading/velocity, which makes late corrections get under-weighted; this indirectly worsens the rigid-offset cases. Implementation cost in C: FEJ = store first-estimate of position/velocity/orientation per clone and landmark; negligible ops.

### Gaps
- No head-to-head NEES/ATE ablation table (FEJ vs OC vs RI) found; no robocentric-specific numbers.

## Q4. Exploiting simulator structure (dynamics model, drag, gravity, noise)

### Takeaway
A linear rotor-drag term gives a velocity observability/measurement from IMU alone for multirotors and is published to improve accuracy; it directly constrains start velocity in body-horizontal axes.

### Cited Findings
- Adding a linear drag term to velocity dynamics improves estimation accuracy (attributed to Leishman et al.; not verified at the original); partial update for the drag state keeps consistency — [NSF PAR 10135575](https://par.nsf.gov/servlets/purl/10135575).
- Linear propeller drag guarantees bounded velocity error in components orthogonal to shaft — [IMAV 2023](https://www.imavs.org/papers/2023/11.pdf).
- Caveat: reusing the dynamics model with drag depending on estimator state creates a feedback loop that can diverge; HDVIO uses a hybrid point-mass plus learned aerodynamic residual — [HDVIO2.0](https://arxiv.org/html/2504.00969v2). Rotor-speed measurements improve velocity prediction 36.9% (2026 preprint; not applicable without rotor speeds) — [arXiv 2603.00597](https://arxiv.org/pdf/2603.00597).

### Inferences
- Accelerometer on a multirotor measures thrust (body z) plus drag (body x,y ~ -k_d v_xy). So a_x_body, a_y_body mean = -k_d * v_body: a pseudo-measurement of horizontal body velocity. Fit k_d offline from your simulator logs (regress accel x,y vs GT body velocity); then the update is a 2-D linear measurement per IMU window with tiny cost. With 0.28 m/s^2 noise per sample, averaging over ~1 s of N samples needed; value depends on k_d (typical 0.1-0.5 1/s: v=5 m/s gives 0.5-2.5 m/s^2 signal, well above noise after averaging). This could be a direct fix to start velocity in 2 of 3 axes. Unverified for this simulator; check whether sim even models drag (empirical test first).
- Also test simulator structure empirically: controller tilt/thrust relationship (thrust magnitude vs commanded accel), fixed gravity 9.81, yaw-rate limits to build velocity prior; no sources found for the specific simulator.

### Gaps
- No published numbers of ATE gain from drag updates in VIO; no info on this simulator's drag model.

## Q5. Featureless/dark segments

### Takeaway
Practice = health monitoring + IMU-only propagation with honest (growing) covariance, no hard-coded update; no evidence-backed thresholds found.

### Cited Findings
- IMU prediction bypasses the visual module when features are too few (fully or partially, per direction), subject to drift — patent family [US 10962370](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10962370).
- Underwater VIO: health tracking and switch to kinematic/dynamic-model propagation when VIO fails to acquire features — [arXiv 2603.02114](https://arxiv.org/pdf/2603.02114v1) (as described in search summary; not read in full).

### Inferences
- Gate on tracked-feature count and mean innovation/NIS; during outage skip updates and inflate Q for velocity so that on re-acquisition the filter doesn't ignore visual evidence (covariance honesty). A drag pseudo-measurement (Q4) is the natural coasting stabilizer. Dark frames: do not feed corrupted tracks (reject frames by mean intensity/gradient energy).

### Gaps
- No quantitative gating-threshold literature found; learned uncertainty for frame quality not covered beyond MAC-I^2 title.

## Q6. Online calibration and rolling shutter at ~0.2 m ATE

### Takeaway
Probably not first-order: an unofficial EuRoC log reports no obvious gain from online calibration; secondary summary of the OpenVINS paper says simulated bad calibration with online calibration matches true calibration. Only matters if the simulator's extrinsics/time offset differ from the nominal values given.

### Cited Findings
- Online calibration of intrinsics/extrinsics/time offset showed no obvious gain on EuRoC (good calibration) — [symao/open_vins](https://github.com/symao/open_vins) (unofficial).
- Simulation (secondary summary, unverified against the paper): online calibration from poor initial values reaches 0.218 deg/0.139 m vs 0.212 deg/0.134 m with true calibration — [visual-slam-roadmap OpenVINS summary](https://raw.githubusercontent.com/changh95/visual-slam-roadmap/main/level-06-vio-vins/openvins.md); paper: [Geneva et al.](https://udel.edu/~pgeneva/downloads/papers/c10.pdf).

### Inferences
- Simulated scenes likely have no rolling shutter; check if renderer adds time offset; if calibration is exactly known, skip. Do not spend wasm budget here before fixing initialization.

### Gaps
- No rolling-shutter ablation found.

## Q7. Realistic error floor; effect of IMU noise on dead-reckoning

### Takeaway
Good monocular VIO on EuRoC is ~0.1-0.5 m ATE (after SE(3) alignment, 50-130 m trajectories); your 0.13-0.5 m good episodes are already in that band, so remaining gains come from the 4 bad episodes, whose mean-contribution dominates. Unaided IMU dead-reckoning is hopeless at this noise level, so vision must bound it.

### Cited Findings
- Monocular EuRoC MH_01, median RMSE after SE(3) alignment: OpenVINS 0.096 m, VINS-Mono 0.192, ROVIO 0.455, Kimera 1.352 (as reported) — [OpenVIO](https://arxiv.org/pdf/2610.41671).
- MSCKF (monocular) EuRoC: MH01 0.42, MH02 0.45, MH03 0.23, V203 1.13 m; OpenVINS MH01 0.07, MH02 0.14 — [SP-VINS](https://arxiv.org/pdf/2511.18756) (alignment/run details unverified).
- OpenVINS mono-SLAM average on EuRoC Vicon rooms 1.445 deg / 0.079 m (secondary) — [roadmap summary](https://raw.githubusercontent.com/changh95/visual-slam-roadmap/main/level-06-vio-vins/openvins.md). Mono-inertial OpenVINS default 0.139/0.141 (2026 reproduction, units unclear) — [arXiv 2603.21785](https://arxiv.org/pdf/2603.21785).
- Caveat: all published numbers are aligned (SE(3)/yaw) ATE; yours is unaligned, which also charges initial heading/velocity error — so published floors are optimistic for your metric.

### Inferences (my calculation, assumptions stated)
- Assume the quoted 0.07 rad/s and 0.28 m/s^2 are per-sample std at an assumed 200 Hz (rate unknown; check). Then densities: gyro 0.07*sqrt(0.005)=0.0049 rad/s/sqrt(Hz); accel 0.28*sqrt(0.005)=0.0198 m/s^2/sqrt(Hz).
- Gyro random walk: sigma_theta(60 s) ~ 0.0049*sqrt(60) = 0.038 rad (2.2 deg). Tilt error feeds gravity leak: velocity error ~ g*sigma_d*t^1.5/sqrt(3) ~ 13 m/s at 60 s unaided; so vision/gravity must constrain roll/pitch continuously (they do: roll/pitch are observable).
- Accel noise alone: velocity RW 0.0198*sqrt(60)=0.15 m/s; position 0.0198*60^1.5/sqrt(3)=5.3 m unaided (still needs vision), but at 1-3 s horizon: velocity 0.03 m/s; i.e. startup velocity from IMU+vision over 2 s is limited more by observability than by noise.
- Rigid offset from start: a constant velocity error dv gives position error dv*t; 0.5 m/s -> ~15 m at 30 s unless vision corrects (it does, partially), consistent with observed 0.9-2.4 m ATE being a mostly-corrected offset. Heading error delta about gravity rotates the trajectory: ATE ~ delta * path radius; for 5 deg and ~20 m radius ~1.7 m — matches the magnitude of your bad episodes, so check whether bad episodes are heading (rotation-like residual) or velocity.
- Realistic target: mean 0.78 -> ~0.4-0.5 if the 4 bad episodes drop to ~0.3-0.6 and the 8 good stay at ~0.3 (8*0.3+4*0.5)/12=0.37. 

### Gaps
- No Blackbird or TUM-VI numbers retrieved; no published unaligned-ATE benchmark for monocular filters; sampling rate/definition of noise values unknown.

## Prioritized recommendations (all inference from above)
1. Diagnose bad episodes: regress residual into dv0 vs yaw error (simple 2-parameter fit to GT on local set) to decide what to fix.
2. Late closed-form init at t~1.5-3 s (parallax-gated, Hessian-stability gated) + one replay of buffered data; fuse with CNN prior.
3. Test drag pseudo-measurement (empirical k_d from sim logs); cheap and aims at start velocity.
4. FEJ if not already present; covariance inflation on feature outage.
5. Skip online calibration / rolling shutter unless sim shows offsets.
