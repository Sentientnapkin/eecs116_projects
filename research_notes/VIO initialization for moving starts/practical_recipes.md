# Practical recipes for VIO/INS moving-start initialization (open-source VIO + embedded flight stacks)

Scope: what real systems do in the first 0.5-2 s when the filter starts while the vehicle is already moving. Target: embedded EKF/MSCKF, monocular 20 Hz camera, 200 Hz IMU, drone, tight per-frame budget. Sources were checked on 2026-11-26 against GitHub `master`/`main` branches unless noted. Research budget was limited to about 20 tool calls, so several systems are listed under Gaps.

## OpenVINS: static vs dynamic initializer (defaults, thresholds, covariances)

### Takeaway
OpenVINS (rpng/open_vins, ov_init) ships a static initializer by default and an opt-in dynamic initializer (`init_dyn_use: false` in the EuRoC config). The dynamic initializer is a linear solve for features, velocity and gravity under a gravity-magnitude constraint, with biases assumed known or zero. A short Ceres MLE follows, then the recovered covariance is inflated by 10-100x. If dynamic init is disabled and the platform is moving, OpenVINS refuses to initialize; it never falls back to a static init.

### Cited Findings
- **Header defaults** (`InertialInitializerOptions.h`):
  - Window and features: `init_window_time=1.0` s, `init_imu_thresh=1.0` (accel variance), `init_max_disparity=1.0` px, `init_max_features=50` (exits if <15).
  - Dynamic init on/off and poses: `init_dyn_use=false`, `init_dyn_num_pose=5` (needs >=4), `init_dyn_min_deg=45.0`.
  - MLE: `init_dyn_mle_max_iter=20`, `init_dyn_mle_max_time=5.0` s, `init_dyn_mle_opt_calib=false`.
  - Inflation: ori 10, vel 10, bg 100, ba 100.
  - Other: `init_dyn_min_rec_cond=1e-15`; bias guesses `init_dyn_bias_g/a = [0,0,0]`.
  - Source: [OpenVINS InertialInitializerOptions.h](https://raw.githubusercontent.com/rpng/open_vins/master/ov_init/src/init/InertialInitializerOptions.h)
- **Shipped EuRoC config** (`config/euroc_mav/estimator_config.yaml`), which overrides the header defaults:
  - Window and features: `init_window_time: 2.0`, `init_imu_thresh: 1.5`, `init_max_disparity: 10.0` ("dependent on resolution"), `init_max_features: 50`.
  - Dynamic init on/off and poses: `init_dyn_use: false`, `init_dyn_num_pose: 6` (evenly spaced in the window), `init_dyn_min_deg: 10.0`.
  - MLE: `init_dyn_mle_max_iter: 50` ("zero to skip the MLE"), `init_dyn_mle_max_time: 0.05` s, `init_dyn_mle_max_threads: 6`, `init_dyn_mle_opt_calib: false` ("not recommended").
  - Inflation: `init_dyn_inflation_ori: 10`, `_vel: 100`, `_bg: 10`, `_ba: 100`.
  - Other: `init_dyn_min_rec_cond: 1e-12`.
  - ZUPT: `try_zupt: false`, `zupt_max_velocity: 0.1`, `zupt_noise_multiplier: 10`, `zupt_max_disparity: 0.5`, `zupt_only_at_beginning: false`.
  - Source: [OpenVINS euroc estimator_config.yaml](https://raw.githubusercontent.com/rpng/open_vins/master/config/euroc_mav/estimator_config.yaml)
- **Routing logic in `InertialInitializer.cpp`:**
  - Window start is `newest_cam_time - init_window_time - 0.10`.
  - The window is split at its midpoint, and average disparity is computed for each half. Each half needs at least 15 features.
  - `is_still` means both halves have disparity below `init_max_disparity`. `has_jerk` means the older half is still and the newer half is moving.
  - The static path runs if `(has_jerk && wait_for_jerk) || (is_still && !wait_for_jerk)` and `init_imu_thresh > 0`. The dynamic path runs if `init_dyn_use && !is_still`. Otherwise init fails with "platform moving too much" or "no accel jerk detected".
  - Dynamic init is not available on Android builds because Ceres is not included.
  - Source: [OpenVINS InertialInitializer.cpp](https://raw.githubusercontent.com/rpng/open_vins/master/ov_init/src/init/InertialInitializer.cpp)
- **Dynamic initializer internals (`DynamicInitializer.cpp`):**
  - Poses are taken every `init_window_time/(num_pose+1)` s. It needs at least 8 valid features. The feature gate is `0.75*init_max_features`, although the log message says 0.95.
  - It integrates gyro over the window and fails if total rotation is below `init_dyn_min_deg`. The accel norm is only logged, not used as a gate.
  - Biases are not estimated in the linear stage; they are fixed to the config guesses.
  - Linear stage: unknowns are features, v_I0 and g_I0. Features and velocity are projected out, leaving a 6x6 companion-matrix polynomial in a Lagrange multiplier for the constraint `|g| = gravity_mag`. It picks the real root whose |g| is closest and requires `||g|-9.81| <= 1e-3`.
  - Ceres MLE: `DENSE_SCHUR` with `DOGLEG`, Cauchy loss with scale 1.0.
  - MLE priors: first-pose yaw and position std 1e-5, gyro-bias std 0.05, accel-bias std 0.10, extrinsic rotation/translation std 0.001/0.01.
  - Covariance comes from `ceres::Covariance` at the newest pose. It is then inflated per block (position is not inflated) and position is reset to 0.
  - Source: [OpenVINS DynamicInitializer.cpp](https://raw.githubusercontent.com/rpng/open_vins/master/ov_init/src/dynamic/DynamicInitializer.cpp)

### Inferences
- The OpenVINS recipe for a moving start is: about 2 s of data, 6 poses, at least 10 deg of rotation, a <=50 ms MLE, and covariance inflation of x10 on orientation/bg and x100 on velocity/ba.
  - Inflating velocity and accel bias by two orders of magnitude is how they keep the first EKF updates consistent with an overconfident Ceres covariance.
  - A 20 Hz mono drone filter can copy the inflation factors directly even if it uses a cheaper linear-only solve (set MLE iterations to 0).
- The 10-deg rotation gate and the gravity-magnitude constraint are the main defences against scale collapse.
  - Near-pure translation at constant velocity leaves the linear system ill-conditioned. OpenVINS simply waits in that case.
- Gyro bias is treated as known (zero) at init. On a cheap IMU, a large gyro bias over a 2 s window corrupts the rotation used for preintegration.

### Gaps
- I did not fetch the OpenVINS initialization paper and its success-rate numbers (Geneva/Huang, "Linear and nonlinear VIO init", circa 2023 OpenVINS docs). I also did not fetch the StaticInitializer internals (how `init_imu_thresh` is applied to accel variance).

## Other open-source VIO systems: how they initialize and whether a moving start is supported

### Takeaway
VINS-Mono/Fusion and ORB-SLAM3 initialize from motion by design: visual SfM over a sliding window is aligned to IMU preintegration. Both need parallax but no stillness. MSCKF-VIO (KumarRobotics) is static-only: it averages the first 200 IMU messages as gravity and gyro bias. OpenVINS is static by default, with dynamic init opt-in.

### Cited Findings
- **VINS-Mono `initialStructure()`:**
  - It runs only once the window is full (`frame_count == WINDOW_SIZE`) and more than 0.1 s has passed since the last attempt.
  - IMU excitation check: the std of per-frame average acceleration must reach 0.25, otherwise it logs "IMU excitation not enouth!". The `return false` is commented out, so the check is non-blocking.
  - Relative pose needs more than 20 correspondences and `average_parallax*460 > 30`, i.e. about 30 px at a 460 px virtual focal length. On failure it logs "Not enough features or parallax; Move device around".
  - It then runs global SfM and PnP for each frame (at least 6 points). `visualInitialAlign()` follows: gyro bias, then gravity, velocity and scale.
  - Source: [VINS-Mono estimator.cpp](https://raw.githubusercontent.com/HKUST-Aerial-Robotics/VINS-Mono/master/vins_estimator/src/estimator.cpp)
- **MSCKF-VIO (KumarRobotics):**
  - `imuCallback` buffers until 200 IMU messages, then calls `initializeGravityAndBias()`. Mean gyro becomes `gyro_bias`. Mean accel becomes gravity, with the norm used as gravity magnitude. Orientation comes from `FromTwoVectors`. Accel bias is not set.
  - Feature callbacks are ignored until then. This implicitly assumes the platform is still.
  - Initial covariance diagonals: gyro bias 1e-4, velocity 0.25, accel bias 1e-2, extrinsic rotation 3.0462e-4 (about (1 deg)^2), extrinsic translation 1e-4. Position and orientation start at 0. Initial velocity is 0.
  - Source: [msckf_vio.cpp](https://raw.githubusercontent.com/KumarRobotics/msckf_vio/master/src/msckf_vio.cpp)
- **ORB-SLAM3 inertial-only initialization:**
  - Initialization is posed as MAP estimation that accounts for IMU noise. On EuRoC it initializes in under 4 s "at almost any point along the trajectory", with 5.3% average scale error (Campos et al., ICRA 2020). Source: [arXiv 2003.05766](https://arxiv.org/abs/2003.05766)
  - Earlier work (Campos et al. 2019) found the closed-form Martinelli-Kaiser solution gave 32.9-156.7% scale error on EuRoC V1 sequences. Two VI-BA rounds reduced this to 8.8-24.5%. Source: [arXiv 1908.10653](https://arxiv.org/pdf/1908.10653) (figures from the search-result snippet, not verified in the PDF).
- A Robocentric VIO paper describes the static recipe: gyro bias from the mean of stationary IMU readings, accel bias after removing gravity. Source: [arXiv 1805.04031](https://arxiv.org/pdf/1805.04031)
- A keyframe-based structureless filter (2020) claims to start at standstill or in motion without special-casing stationary periods or using ZUPT. Source: [arXiv 2012.15170](https://arxiv.org/pdf/2012.15170)

### Inferences
- MSCKF-VIO's 200 messages at 200 Hz is 1 s of averaging. Started in flight, the mean accel includes vehicle acceleration, so tilt error is about atan(a_horiz/g). For example, 1 m/s^2 gives about 5.8 deg.
  - Its velocity prior of 0.25 (std 0.5 m/s) around v=0 would also be wrong for a drone already moving at a few m/s.
- VINS-Mono's 30 px parallax requirement at 20 Hz typically needs a few hundred ms of lateral motion. Its excitation check is advisory only.
- For a 20 Hz mono MSCKF, the cheapest robust option is the OpenVINS-style linear solve: features, v0 and g, with known gyro bias, over 1-2 s and about 5-6 poses. Skip the MLE and inflate the resulting covariance.

### Gaps
- Not verified from source in this pass:
  - **ROVIO/ROVIOLI:** recalled as initializing attitude from the first accel sample, with velocity 0 and a large velocity covariance.
  - **Basalt:** recalled as initializing attitude from the first accel and relying on the optimizer.
  - **Kimera-VIO:** recalled as supporting ground-truth, IMU-static or online visual-inertial init.
  - **SVO2/SVO Pro:** recalled as relying on the VINS-style or ORB-SLAM3-style init in its backend.
  - **OKVIS2:** recalled as starting from accel tilt and using the optimizer.
  - **DM-VIO:** recalled as using delayed marginalization plus a photometric BA (PBA) with an explicit scale variable and a gravity-direction prior, starting from visual-only.
  - I could not fetch these within budget; treat them as unverified.
- **ORB-SLAM3 specifics:** the init window length, keyframe count and the 5 s / 15 s VI-BA refinement schedule (recalled as about 10 keyframes over about 2 s) could not be extracted. The PDF could not be parsed (no pdftotext available).

## PX4 EKF2 and ArduPilot EKF3: in-motion alignment, initial variances, bias-learning delays

### Takeaway
Neither flight stack does a true in-motion alignment. PX4 EKF2 refuses tilt init unless the low-passed accel norm is within 0.8-1.2 g and gyro is below 15 deg/s, then assumes the vehicle is static. ArduPilot EKF3 waits 1000 ms, takes a single accel sample as gravity (zero yaw), and starts with accel and gyro bias learning inhibited. Both recover from tilt error through the filter, using a nonzero initial attitude variance.

### Cited Findings
- **PX4 `initialiseTilt()`** (PX4-Autopilot main, `src/modules/ekf2/EKF/ekf.cpp`):
  - Accel and gyro are low-pass filtered from delta-vel/dt and delta-ang/dt.
  - Init is rejected if `accel_norm < 0.8g` or `> 1.2g`, or if `gyro_norm > 15 deg/s`.
  - Otherwise attitude is set from the filtered accel vector aligned to (0,0,-1). There is no explicit minimum sample count; it retries every IMU update.
  - Source: [PX4 ekf.cpp](https://raw.githubusercontent.com/PX4/PX4-Autopilot/main/src/modules/ekf2/EKF/ekf.cpp)
- **PX4 `initialiseCovariance()`:**
  - Attitude: tilt variance is `EKF2_ANGERR_INIT^2` (floored at 0.01). Yaw variance starts at 0.
  - Velocity: without GNSS, horizontal variance is 0.5^2, and vertical is 1.5^2 times horizontal.
  - Position without GNSS: horizontal variance is `EKF2_NOAID_NOISE^2`.
  - Biases: gyro bias variance is `EKF2_GBIAS_INIT^2`, accel bias variance is `EKF2_ABIAS_INIT^2`.
  - Source: [PX4 covariance.cpp](https://raw.githubusercontent.com/PX4/PX4-Autopilot/main/src/modules/ekf2/EKF/covariance.cpp)
- PX4 docs:
  - The EKF goes through tilt, then yaw, then height alignment before normal mode.
  - The GSF yaw estimator can reset yaw after takeoff if navigation is lost ("the main 24-state EKF will align it's yaw to the GSF estimate").
  - `EKF2_ABIAS_INIT` is described as related to the sensor's turn-on bias.
  - Sources: [PX4 EKF2 tuning (main)](https://docs.px4.io/main/en/advanced_config/tuning_the_ecl_ekf.html); [PX4 preflight checks v1.14](https://docs.px4.io/v1.14/en/flying/pre_flight_checks)
- **ArduPilot EKF3 `InitialiseFilterBootstrap()`:**
  - It waits 1000 ms after the first call, then sets tilt from a single accel sample: `pitch=asin(ax)`, `roll=atan2(-ay,-az)`, yaw=0.
  - The source comments say "This assumes measured acceleration is dominated by gravity", "TODO we should average accel readings over several cycles" and "TODO - in-flight restart method".
  - Initial attitude variance is `sq(0.1)` rad^2 per axis (about 5.7 deg std). `tiltErrorVariance` starts at `sq(2*pi)`.
  - Bias learning starts inhibited: `inhibitDelVelBiasStates = inhibitDelAngBiasStates = true`.
  - Accel-bias axes are treated as observable only when their gravity component exceeds 0.8. XY biases stay unobservable "until the vehicle accelerates horizontally in flight". All axes are inhibited when the vehicle is on the ground and moving.
  - Gyro-bias variance is clamped to `sq(0.175*dt)`.
  - Source: [ArduPilot AP_NavEKF3_core.cpp](https://raw.githubusercontent.com/ArduPilot/ardupilot/master/libraries/AP_NavEKF3/AP_NavEKF3_core.cpp)

### Inferences
- A practical flight-stack pattern for moving starts:
  1. Gate tilt init on |a| ≈ g (±20%) and low rotation rate.
  2. Low-pass the accel.
  3. Give tilt a variance of about (0.1 rad)^2 and let velocity or position aiding correct it.
  4. Hold bias states frozen (inhibited) until the filter has settled and the axes are excited.
- For a drone in cruise, |a| ≈ g often holds, so the PX4 gate passes even though the specific force includes drag or tilt-induced components. Tilt error is then roughly the horizontal acceleration divided by g, which is why the initial tilt variance must not be too small.

### Gaps
- I could not retrieve exact numeric defaults for `EKF2_ANGERR_INIT`, `EKF2_GBIAS_INIT`, `EKF2_ABIAS_INIT`, the `EKF2_ABL_*` limits, the `EKF2_EV*` gates or the PX4 LPF time constant. The parameter reference page was truncated.
  - Recalled but unverified: ANGERR_INIT 0.1 rad, GBIAS_INIT 0.1 rad/s, ABIAS_INIT 0.2 m/s^2.
- The ArduPilot conditions that set `tiltAlignComplete` were not in the fetched portion.

## Aerospace in-motion alignment (velocity-aided, coarse-to-fine, OBA)

### Takeaway
The aerospace answer to a moving start is optimization-based alignment (OBA). It integrates the velocity/attitude equations over a window and solves for the initial attitude as a Wahba/quaternion problem using external velocity or position. This is a coarse alignment that needs no prior attitude, followed by Kalman fine alignment.

### Cited Findings
- Wu & Pan (IEEE TAES 49(2):1006-1023, 2013) present in-flight coarse alignment from GPS velocity and position, using velocity/position integration formulae. It needs no prior attitude, and a KF does fine alignment afterwards. Sources: [arXiv 1207.1550](https://arxiv.org/pdf/1207.1550); [citation via Cambridge](https://www.cambridge.org/core/product/2E342BE1284C33290859829AF6BBC490)
- The OBA framework originates in Wu, Wu, Hu & Hu (2011), "Optimization-Based Alignment for Inertial Navigation Systems: Theory and Algorithm", *Aerospace Science and Technology*. Chang, Li & Li (2016, TAES) compare and extend OBA methods. Sources: [Cambridge (Xue et al. 2017, J. Navigation)](https://www.cambridge.org/core/journals/journal-of-navigation/article/inmotion-alignment-algorithm-for-vehicle-carried-sins-based-on-odometer-aiding/2E342BE1284C33290859829AF6BBC490); [arXiv 1411.5869](https://arxiv.org/pdf/1411.5869.pdf)
- An odometer-aided OBA with a unit-quaternion constraint was published in Sensors in 2018. Source: [PMC6069107](https://pmc.ncbi.nlm.nih.gov/articles/PMC6069107)
- A patent on in-motion accelerometer initialization reports that initializing as if stationary while actually moving makes position error diverge, plateauing above 1 km horizontal. Source: [USPTO 11187719](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11187719)

### Inferences
- For VIO, the analogue of the "external velocity" is the visual up-to-scale velocity or the feature constraints. The OpenVINS linear dynamic init is essentially an OBA with visual aiding: it integrates the IMU over the window and solves for gravity in the body frame together with v0.
- A cheap embedded variant follows from this:
  - Integrate the gyro to get relative rotations R_k.
  - Integrate R_k·a_k dt.
  - Fit gravity and v0 by least squares against any velocity or displacement source, such as a learned velocity, or VO up to scale with a scale unknown.
  - The result is a 3-7 unknown linear solve per window, which is negligible compute.

### Gaps
- No numeric accuracy or convergence-time figures for OBA were extracted; only abstracts and reference lists were read.

## Tricks for consistent early covariance and failure modes (scale collapse, wrong gravity, heading)

### Takeaway
Real systems use a few tricks:
- Inflating the initial covariance: OpenVINS uses x10-x100. PX4 and ArduPilot set tilt to about 0.1 rad.
- Inhibiting or freezing bias states early: ArduPilot inhibits both bias states, and OpenVINS fixes biases in the linear solve.
- Refusing to initialize until there is enough excitation or parallax: OpenVINS requires at least 10 deg of rotation, and VINS-Mono requires 30 px parallax with more than 20 correspondences.
- Gating gravity-from-accel on |a| ≈ g and low gyro: PX4 uses 0.8-1.2 g and 15 deg/s.

Yaw is unobservable, so it is fixed by a tight prior (OpenVINS MLE uses 1e-5) or by starting yaw at 0 with zero variance (PX4, ArduPilot).

### Cited Findings
- Inflation: OpenVINS config multiplies orientation by 10, velocity by 100, gyro bias by 10 and accel bias by 100. Source: [OpenVINS config](https://raw.githubusercontent.com/rpng/open_vins/master/config/euroc_mav/estimator_config.yaml)
- Bias freezing or delay: in ArduPilot EKF3 both bias states start inhibited, and horizontal accel bias is learned only after horizontal acceleration. Source: [ArduPilot EKF3 core](https://raw.githubusercontent.com/ArduPilot/ardupilot/master/libraries/AP_NavEKF3/AP_NavEKF3_core.cpp)
- In OpenVINS dynamic init, biases are fixed in the linear stage and given weak priors in the MLE (std 0.05 for gyro, 0.10 for accel). Source: [OpenVINS DynamicInitializer.cpp](https://raw.githubusercontent.com/rpng/open_vins/master/ov_init/src/dynamic/DynamicInitializer.cpp)
- Delaying until excitation or parallax: OpenVINS `init_dyn_min_deg` (10 deg in the config, 45 in the header). VINS-Mono requires parallax above 30 px at f=460 and retries every 0.1 s. Sources: [OpenVINS config](https://raw.githubusercontent.com/rpng/open_vins/master/config/euroc_mav/estimator_config.yaml); [VINS-Mono estimator.cpp](https://raw.githubusercontent.com/HKUST-Aerial-Robotics/VINS-Mono/master/vins_estimator/src/estimator.cpp)
- Gravity under acceleration:
  - PX4 gates on 0.8-1.2 g and 15 deg/s, then assumes static. Source: [PX4 ekf.cpp](https://raw.githubusercontent.com/PX4/PX4-Autopilot/main/src/modules/ekf2/EKF/ekf.cpp)
  - ArduPilot explicitly assumes "acceleration is dominated by gravity". Source: [ArduPilot EKF3 core](https://raw.githubusercontent.com/ArduPilot/ardupilot/master/libraries/AP_NavEKF3/AP_NavEKF3_core.cpp)
  - OpenVINS instead solves gravity jointly with velocity under |g| = 9.81. Source: [OpenVINS DynamicInitializer.cpp](https://raw.githubusercontent.com/rpng/open_vins/master/ov_init/src/dynamic/DynamicInitializer.cpp)
- Scale collapse: closed-form init gave 32.9-156.7% scale error on EuRoC V1 before BA (Campos 2019), whereas MAP inertial-only init gave 5.3% (Campos 2020). Sources: [arXiv 1908.10653](https://arxiv.org/pdf/1908.10653); [arXiv 2003.05766](https://arxiv.org/abs/2003.05766)
- Heading: PX4 starts with zero yaw variance and relies on mag, EV or the GSF yaw estimator to align or reset yaw after takeoff. Sources: [PX4 covariance.cpp](https://raw.githubusercontent.com/PX4/PX4-Autopilot/main/src/modules/ekf2/EKF/covariance.cpp); [PX4 EKF2 docs](https://docs.px4.io/main/en/advanced_config/tuning_the_ecl_ekf.html)

### Inferences
- Synthesized recipe for a 20 Hz mono / 200 Hz IMU drone MSCKF at a moving start:
  1. **Tilt.** Low-pass the accel for 0.5-1 s and accept it only if |a| is within ±20% of g and |ω| < 15 deg/s. Better, solve g and v0 jointly with a linear OpenVINS-style system over 1-2 s (6 poses at 20 Hz is easy).
  2. **Covariance.** Set tilt σ ≈ 0.1 rad. Inflate velocity by about x100 relative to any solver covariance, or use σ ≈ 0.5-1 m/s if there is no solver. Fix yaw and position with tiny variance, since they are gauge freedoms.
  3. **Biases.** Freeze bias states, or give them a tiny process noise, until the attitude covariance has shrunk. Learn horizontal accel bias only after horizontal excitation (the ArduPilot logic).
  4. **Vision updates.** Accept vision updates with a relaxed chi^2 gate, or inflate pixel noise, for the first frames. Require minimum parallax or rotation before trusting depth or scale.
- Failure modes to expect:
  - Tilt error of about a_horiz/g when gravity is taken from accel under acceleration.
  - Scale or velocity divergence under near-constant-velocity translation with little rotation.
  - Overconfident covariance after a solver init. This is why OpenVINS inflates by up to x100.

### Gaps
- I found no cited source for explicit "inflate-then-shrink" time schedules or "relaxed chi^2 for first N frames" in these codebases; that recipe step is inference only.
- The PX4 EV gate and delay defaults were not retrieved.

## Benchmarks comparing initializers on mid-sequence starts

### Takeaway
The standard protocol is exhaustive: launch an initialization at many points along every EuRoC sequence, rather than at random offsets. Campos et al. 2020 (ORB-SLAM3 inertial-only init) is the reference benchmark. Later papers reuse it (learned-depth priors) or sample 20 s segments every 5 s (DOGE).

### Cited Findings
- Campos et al. (ICRA 2020):
  - Initialization in under 4 s at almost any trajectory point, with 5.3% average scale error. Source: [arXiv 2003.05766](https://arxiv.org/abs/2003.05766)
  - A search snippet says initializations were launched every 0.5 s, giving 2,248 trials, and that VI-BA from the same guesses scored 13.82% against 11.69% for inertial-only. These figures were not verified in the PDF; the snippet table was garbled. Source: [arXiv 2003.05766 PDF](https://arxiv.org/pdf/2003.05766)
- The learned monocular depth priors paper (2022) uses the same exhaustive protocol at 10 Hz. It produced 1,078 (inertial-only), 1,545 (baseline) and 1,547 (proposed) successful initializations out of 1,680 attempts. Source: [arXiv 2204.09171](https://arxiv.org/pdf/2204.09171) (counts from the search snippet)
- DOGE (2024) samples 20 s segments every 5 s on each EuRoC sequence and compares against VINS-Mono and DRT-VIO. Source: [arXiv 2412.08135](https://arxiv.org/pdf/2412.08135)
- XR-VIO (2025) compares VINS-Mono init with ORB-SLAM3 inertial-only init (4- and 5-keyframe configurations) on scale, ATE, gravity error and success rate. Source: [arXiv 2502.01297](https://arxiv.org/pdf/2502.01297)
- EDI (2023) is an ESKF-based disjoint initialization compared against VINS-Mono's loosely coupled linear init and a nonlinear-optimization init. Source: [arXiv 2308.02670](https://arxiv.org/pdf/2308.02670)
- A probabilistic normal epipolar constraint init (2024) is another recent EuRoC init comparison. Source: [arXiv 2410.19473](https://arxiv.org/html/2410.19473v2)

### Inferences
- To benchmark our moving-start init, copy the Campos protocol: start every 0.5 s along each flight and report success rate, scale error, gravity error and ATE at fixed horizons. This directly matches the mid-flight starts in our task.

### Gaps
- I found no paper that explicitly uses random offsets. The OpenVINS team's own mid-sequence init evaluation was not located.
- Per-method numbers for DOGE, EDI and XR-VIO were not extracted.
