# Simulator / benchmark structure study (public code + our own generated pool)

Date 2026-11-20. Scope: exploitable STRUCTURE of how episodes are generated and scored, to find priors/constraints for the gp_msckf estimator.
Sources read: public VIOBench repo (VB = /dev/shm/sebastian-vio/viobench: docs/*.md, tools/datasets/{simulation,regularize,episode}.py, tools/runner/{metrics,score,leaderboard}.py, tools/abi/config.py, episodes/__init__.py), the
simulator venv (venv-sim .../site-packages: hyperdrone 0.1.10 python layer + the vendored C++ headers under hyperlux/_vendor/rl-tools/include/rl_tools/rl/environments/{hyperdrone,l2f}
= HD / L2F below), our generator (research/gen*, native_campaign.py, configs/server_*.json), public episodes (baselines/public-raw, public data), our pool gen/raw-fast/bench.
Upstream web check: github.com/jonas-eschmann/viobench is public (README only mirrors the local docs; nothing about stage2/mid-flight); github.com/rl-tools/rl-tools has no page text on hyperdrone/hyperlux. No further online docs found.
RULES kept: nothing private was downloaded/opened/probed (episodes/__init__.py read as text only: hashes only, no scene/seed/settings info); no sealed_aggregate.json, no fold-4 scenes (all pool draws skip fold 4 via the
sha256(catalog:scene)%5 rule), no holdout set, no git, no estimator evaluations run. Scripts and small result pickles: research/single_model/simstruct/ (t1..t10, load.py).
Truth tests use 48-80 flights (T1/T2), 363 mid-start flights (T3,T5-T7,T10), 150+150 first windows (T4), all from gen/raw-fast/bench (our K/K2-override pool, NOT the server's unknown settings).

## 1. Planner and flight dynamics (HD/tasks/visual_inertial_localization/*.h)
* Task: `visual_inertial_localization` world; the drone is an x500 quadrotor (mass 2.0 kg, J=0.0217, rotor tau 0.03 s, L2F/parameters/dynamics/x500_sim.h) flown by a neural RAPTOR position policy
  (GRU 16, controllers/raptor/raptor.h, checkpoint conta:b6bd082c..; outputs motor commands). Dynamics step = IMU step 5 ms.
* Route: roadmap (<=160 nodes) = collision-free scene annotation positions + Halton fill (bases 2,3,5) with z in [zmin-0.3, zmax+0.3] (planning_operations_cpu.h:60-98), edges <= CONNECTION_DISTANCE
  (default 4.0 m), spacing >= ROADMAP_SPACING (0.65). Route = random walk on the graph, NUM_WAYPOINTS = 0.8/s x duration (simulation.py:44,66; public CLI default 48), weight
  exp(3*alignment with current direction) * novelty^2 * distance/(1+0.2 d^2), no immediate backtracking (:314-355). Spawn node in the largest connected component (:136-141).
  3-D route (z varies). Collision radius 0.45 + tracking margin 0.25 (:53).
* Trajectory family: per-segment degree-5 Bezier (min-jerk-like control points, `trajectory_operations_generic.h:262-286`) between consecutive waypoints; interior waypoint velocity = tangent (in+out) x
  min(0.7 cruise, d/dur) x (1+alignment)/2, ZERO if turn sharper than 120 deg (alignment<=-0.5) -> a stop (planning :163-186). Duration per segment from max(1.875 d/vmax, sqrt(6d/(0.65 amax)), cbrt(60 d/(0.5 jmax))),
  then stretched until certified bounds speed<=cruise, |a|<=0.65 MAX_ACCELERATION, |j|<=0.5 MAX_JERK, collision free (fit_trajectory :188-216).
* Defaults (visual_inertial_localization.h:84-95): cruise U(0.45,0.8) m/s per flight, MAX_ACCELERATION 0.7, MAX_JERK 2.0, MAX_YAW_RATE 0.8, PHASE_ACCELERATION 0.2, PHASE_JERK 0.5.
  Public set (default planner, hold 1 s): path 13.7-19.9 m per 60 s (measured on the 10 public episodes). Course-server episodes: 39.5-80.4 m, mean 59.6 m (configs/server_observed.json) => the
  server planner is NOT the public default (3-4x faster); exact server overrides unknown. Our pool uses override sets K (cruise 3-4.5, accel 6, jerk 30, yaw 2, spacing 1, connection 6) / K2 (4-6, 8, 40) chosen to match path length only.
* Speed profile: time-warp "phase" (tracking_operations_cpu.h:70-105): segment time advances at phase_rate in [0,1], phase accel <= min(0.2, 0.35 amax/cruise_max, ..) = 0.2 /s, jerk <= 0.5 /s^2 (with the K/K2 overrides too).
  pace target = clamp((0.9*0.25 - tracking_error)/(0.4*0.25)) x max(0,cos(heading_err))^2: the reference slows to a halt when the position error >0.325 m or the heading is >90 deg off the reference direction.
  Reference velocity fed to the policy = bezier velocity x phase_rate, position error clipped to 1 m, velocity error clip 2 m/s (raptor.h POSITION_CLIP/VELOCITY_CLIP). => speed is tracking-limited: measured mean 0.84 m/s,
  p99 2.6, max 3.8-4.1 in the K/K2 pool although cruise is 3-6.
* Yaw policy: target yaw chases atan2 of the REFERENCE velocity (fallback: direction to next waypoint when |v|<1e-3), rate-limited by MAX_YAW_RATE, target may lead the actual yaw by at most YAW_ERROR_LIMIT 0.25 rad
  (raptor/operations_generic.h:86-93). Decoupled roll/pitch: none (yaw only). MEASURED consequence (T2): yaw rate is bang-bang: |w_z| ~0.63-0.73 rad/s whenever the heading is turning (p50 0.63, p99 0.73, max 0.90),
  independent of MAX_YAW_RATE (0.8 vs 2.0) because of the 0.25 rad error limit; heading follows velocity direction with a ~0.3-0.5 s lag (median |vel dir - yaw(t+0.3 s)| 5 deg), 13.5% of moving time (hs>0.5) has |heading-velocity|>90 deg.
* Measured envelope (T2, 80 flights, 25 ms smoothing, t>1.5 s): |a_h| p50/p90/p99 0.68/2.0/3.5 m/s^2 (certified reference bound 0.65*MAX_ACC = 3.9 (K) / 5.2 (K2)); |jerk| p99 13.6; tilt p50/p99/max 4/20/33 deg;
  horizontal speed p99 2.6; |w| p90 0.87 rad/s. The health NOTES envelope (119 flights): |vz| p99 1.0, |z-z0| p99 2.0, max 2.9; per-flight max distance from start p50/p90/p99 4.8/8.0/12.8 m (tailcap: no safe containment radius <22 m).
* Stops/hovers: hover_fraction (<0.1 m/s) ~3-4% of the time (T2: frac<0.1 = 4.2%, <0.3 = 18%): stops only at sharp (>120 deg) waypoints or when pace is gated.
* Quadrotor attitude link (flatness): thrust is along body +z only (rotor_thrust_directions {0,0,1}; no drag, no wind: disturbances {0,0}; `60_dynamics.h`). Measured (T2): angle between body z and (a-g) = 0.01/0.02/0.05 deg
  (p50/p90/p99). So tilt = atan(|a_h|/(g+a_z)) EXACTLY, and the specific force in body axes is (0,0,|a-g|) exactly: f_x,f_y = 0 (truth rms 0.007 m/s^2 = finite-difference noise). solution.c already uses
  f_x,y = bias (THRUST_MODEL). The accelerometer therefore carries ZERO tilt information at any time (also at rest the drone is level, so alignment from the first window gives tilt 0 and the true start tilt is
  hidden): at a crop the true tilt vector = -a_h/g (corr(up_c,x ; a_c,x) = -1.00, corr(up_c,z ; a_c,z) = -1.00 on 363 starts).

## 2. Start conditions
* Public generator (simulation.py): every flight begins at the spawn pose = origin, level, at rest (HD preset `init` guided: max_position/angle/velocity = 0, presets.h:~96-106); `hold_seconds` 1.0 s hover (INITIALIZATION_HOLD_STEPS=200,
  tracking_operations_cpu.h:96); then the route. There is NO mid-flight start anywhere in the public code. TASK.md: guest is not told "whether an episode starts at rest or in flight". Mid-flight starts in our work =
  native_campaign.crop_episode (our construction; crop ~U(3,40) s on a 0.05 s grid, hover 0.2 s). Server mid-share (~75 %) is an inference from old-build failure counts (single_model/edge/NOTES.md), not documented.
* Static-start timeline (T2, 40 flights, truth): speed <0.08 m/s and tilt <1.1 deg for t<2.0 s; speed first exceeds 0.1 m/s at t = 2.75/2.86/3.02 s (p5/50/95), 0.3 at 3.3 s, 0.5 at 3.6 s; speed p50 0.15 at 3 s, 0.87 at 4 s.
  => at rest for ~2.7 s (hold 1 s + slow phase ramp). Frame-0 IMU window (T4, 150 static + 150 mid): static |f| p5/50/95 = 8.18/8.41/8.62 m/s^2 (rotor spin-up: z force ramps 8.0 -> 9.8 over ~0.1 s; THE FIRST TWO ROWS ARE IDENTICAL
  in 100% of static starts, 0% of mid crops: regularize.py:imu_windows holds the first sample for the slot before t=0.005) vs mid 9.22/9.87/10.49; |mean gyro| static 0.02/0.06/0.10 vs mid 0.19/0.65/0.97. Rule "|f|<8.8" classifies 100%/98.7%
  (static/mid); "gyro<0.2 & fz<9.4" 100%/100%. (Valid for our crops; a server that crops differently could differ.)
* What the guest gets at step 0 (ABI.md:83-96, regularize.py, episode.py:imu_window): t0 = 0.045 s (mid-exposure of frame 0 = render at step 9; 1 sub-frame, exposure 5 ms), 10 IMU rows in (t0-0.05, t0] (rows stamped 0.0..0.045 after
  regularize; the first is a duplicate of the sample at 0.005 when the flight starts at sim t=0), config {width,height,fx,fy,cx,cy,T_cam_imu}. T_cam_imu = body(FLU)->camera: cam x=-body y, cam y=-body z, cam z=+body x; camera looks along body +x, NO
  tilt (R_BODY_CAMERA_FORWARD, config.py:12; mount rotation/offset randomisation 0), zero lever arm. IMU frame = body FLU frame.
* Truth reference (episode.py:97-130, metrics.py:91-94): T_c0_ck = inv(T_wc,0) T_wc,k at the frame (mid-exposure) times; twist by +-5 ms central difference in camera-k axes; ATE = sqrt(mean_k |p_est,k - p_gt,k|^2), computed
  as the norm of delta=inv(T_gt) T_est translation (rotation-invariant, so frame choice is irrelevant); frame 0 error is 0 by definition.
* Start-state distribution of our crops (T3, 363 mid flights, camera-0 axes x right, y down, z fwd): speed pct 10/25/50/75/90/99 = 0.21/0.40/0.77/1.15/1.67/2.45 (mean 0.84); velocity mean (-0.01,-0.02,+0.49), std (0.50,0.34,0.64), axes ~uncorrelated;
  corr(speed, crop time) 0.02 (no dependence on crop time); 3-D angle between optical axis and velocity (speed>0.3): median 30 deg, 16% >90; tilt deg pct 10/50/90/99 = 1.0/4.6/12.9/21.3;
  up-vector in camera axes mean (0.004,-0.991,0.023), std (0.074 roll-comp, 0.015, 0.110 pitch-comp), heavy-tailed (kurtosis 8.5 / 4.6); start accel std (0.72,0.50,1.08) m/s^2 cam axes.

## 3. IMU model (L2F/operations_generic/70_post_integration.h, 30_sample_initial_state.h; HD/presets.h:116-127; VB tools/abi/config.py DEFAULT_IMU)
* accel = R(next)^T((v_next - v)/dt - g) + b_a + n_a ; gyro = w_next + b_g + n_g ; sampled once per 5 ms step, stamped at the step end; no latency, no scale factor, no saturation, no misalignment, no sample-and-hold beyond the step.
* n_g ~ N(0, 0.07 rad/s) and n_a ~ N(0, 0.28 m/s^2) PER SAMPLE at 200 Hz (comment in presets.h: "noise density * sqrt(rate)"). Bias: turn-on uniform(+-0.02 rad/s) gyro, (+-0.2 m/s^2) accel per axis; random walk increment sigma*sqrt(dt)
  per sample with sigma 0.0006 rad/s/sqrt(s) (gyro), 0.001 m/s^2/sqrt(s) (accel); g = (0,0,-9.81).
* MEASURED (T1, 48 flights, truth from the 200 Hz ground truth): per-sample noise std gyro (0.0701,0.0700,0.0700), accel (0.2806,0.2804,0.2798); gyro bias estimates in the first second: std (0.010,0.012,0.013) (uniform +-0.02 => 0.0115 plus 0.005 meas);
  accel x,y bias estimate std (0.134,0.124) (uniform +-0.2 => 0.115 plus 0.02 meas); bias drift over 59 s: gyro 0.0085 observed vs 0.0070 (2-mean noise) + 0.0046 (walk) => consistent; accel xy 0.032 vs 0.029 expected.
* COMPARISON with solution.c (lines 54-59, 62-63): GYRO_NOISE 0.07, ACCEL_NOISE 0.28, GYRO_BIAS_MAX 0.02, ACCEL_BIAS_MAX 0.2, GYRO_BIAS_WALK 0.0006, ACCEL_BIAS_WALK 0.001, s0 = max/sqrt(3): ALL EXACT, no mismatch. q_th=(0.07 dt)^2,
  q_v=(0.28 dt)^2 per step are the correct per-sample discretisation (dt=0.005). Therefore the autoloop's GYRO_NOISE 0.056 (-0.09 on search) is NOT recovering a different true noise; it is a filter-consistency/tuning
  effect (e.g. overstated gyro uncertainty relative to a vision update that is itself over-confident or gated; sample-and-hold of w at step end gives a small systematic, not white, integration error). Treat as a tunable, not as a simulator fact; check it on fresh before trusting.
* Non-identifiabilities that ARE exact: accel z bias is confounded with thrust (only observable at hover from g=9.81 exactly); at static start the first ~100 ms of f_z is a rotor spin-up transient (8.0 -> 9.8 m/s^2) - do not read it as bias/tilt.

## 4. Camera / exposure / lighting
* Pinhole, no distortion, square pixels, cx=W/2-0.5 (config.py:25-29); stored 640x480, guest may take 320x240 area-averaged (intrinsics rescaled). FOV (horizontal) = 120 + U(-15,15) deg per episode (simulation.py:59; HD world.h:81, operations_cpu.h:396) => fx@320
  = 66-123 px; public set measured 105.0-131.2 deg; our pool measured 105.4-134.4 deg (fx 67-122). Per task statement the server's fx is 97-123 px (FOV 105-117.5 deg): at 12 episodes P(all <=118 deg under U(105,135)) ~ 3e-5, so the server FOV
  draw is narrower than the public default (base/range changed) - our pool has ~30% flights with fx<97 that the server did not show.
* nominal_camera (simulation.py:161-172): ONE render per IMU step (exposure_seconds = 0.005), 8-bit quantisation, no motion blur (ENABLE_MOTION_BLUR false), no rolling shutter, no image noise, no auto-exposure,
  BRIGHTNESS_RANDOMIZATION_RANGE = 0 ("photometry is handled by the ISP stage", not present in the public tree; the header comment refers to viobench.tools.datasets.generate.camera which is absent here), anti-aliasing off, shading `High`.
  Public episodes: exposure_seconds 0.005 for all 10. TASK.md says the shutter type "is not given", so the private episodes MAY use another camera plug-in (cannot be verified without data). Darkness comes from the scene lighting itself
  (pool dark_fraction 0.4-0.7%, flat/textureless ~2-4%).

## 5. Private evaluation set (what public code says)
* episodes/__init__.py: `public` = 10 ProcTHOR-Train-1 flights (seeds 0-2, 4 instances/round, default planner, static start); `private` = 14 neutrally labelled episodes (hashes only); `private_stage2` = 12 episodes with hashes
  004c5894 1c6e73f3 21494468 726458d9 78ed493f 8950399d 89f8c99e a61ad08d cd6dc704 dd7a737e e7aa5aee f7c2546f (hash prefixes only; used here only to label our server-result numbers, nothing fetched). Descriptions "private_stage2/episode-NNNN.zip"
  contain no scene id, seed, crop fraction or planner settings. Nothing in code/docs defines "stage2" (instructor-chosen set; server README: sets are presets of hashes; default timeout 24 min per episode).
* Only reported facts (server pages, configs/server_observed.json): 12 episodes, distance travelled 39.5-80.4 m (mean 59.6), mean zero-motion extent 4.694 m (= RMS distance from start; the identity-pose ATE anchor).

## 6. Metric (VB tools/runner/metrics.py, docs/TASK.md, STUDENT_GUIDE.md:211-231)
* Headline: ate = sqrt(mean_k |p_est,k - p_gt,k|^2) per episode, position of T_c0_ck, NO alignment; arithmetic mean over the selected episodes with EQUAL weight per episode (not per frame, not squared across episodes) => an outlier episode adds linearly
  (e7aa5aee 7.70 m = 52% of the 12-episode mean 1.244). Sim(3) ATE, RPE (1 s pairs), rotation/velocity RMSE are diagnostics only.
* Fill rule: from the first failed step (error, non-finite, zero quaternion, trap, out of fuel) all remaining frames get p=(0,0,0), q=(0,0,0,1), zero twist and are scored (error = |p_gt|; so a failed episode scores about its truth RMS distance from the start, mean 4.7 m on server-like flights;
  p90 7.5 m). A completed-but-diverged estimate can be worse than this (3 old server tails 8-11 m), i.e. the zero fill is a cap of ~extent for flights whose est. error exceeds it; but containment radii < 22 m clip real flights (tailcap/NOTES.md).
* Score (leaderboard in STUDENT_GUIDE): log-space area gain between the baseline frontier and the submission point, floors 1 fuel and 0.001 m, reference rectangle = [1.2 x step_fuel] x [1.2 x mean ATE of the fastest eligible baseline];
  percentage of that log rectangle; best single submission counts. Equal proportional improvements of ATE or fuel count equally (log axes).
* Fuel: max over all attempted frames (including failing step) across episodes; per-step limit 2e10, init 2e11.

## 7. Falsification tests (all truth/IMU only on our pool; scripts in simstruct/)
T1 (t1_imu.py): IMU model exact (section 3). T2 (t2_kin.py/t2_report.py, pkl deleted for size): kinematics/flatness/yaw. T3/T3r (t3_start.py, t3_report.py): start-state distribution. T4 (t4_first.py): frame-0 window signature.
T5-T10 (t5_gyro_pred.py ... t10_regime.py): gyro-conditioned velocity structure.

### T8/T9 NEW LAW: coordinated-turn lateral velocity (continuous, whole flights, 80 flights, 5-fold CV across flights)
body lateral velocity (FLU y, left) v_y = 0.993 s x w_z x |v_h| ; R2 = 0.84, residual rms 0.187 m/s (raw rms 0.467; constant-zero model R2 0 = the current PRI_LAT prior N(0,0.5^2) and "lateral prior" family).
Regime split of v_y residual: |w_z|<0.15 rad/s (heading holds): rms 0.059 (raw 0.049); 0.15-0.45: 0.177; >=0.45 (saturated turn): 0.217 (raw 0.594).
Mechanism: heading chases the velocity direction at <=0.65 rad/s; while it turns, the velocity points to the SIDE the heading is turning toward (sign(v_y)==sign(w_z) in 156/156 moving saturated-turn starts); angle(vel dir - heading) ~ 1.5 s x w_z (rms resid 33 deg vs raw 54 deg).
Forward speed: v_x R2 0.36 (const) -> 0.63 using (w_z, sat=min(|w_z|/.65,1), w_y).
### T6/T7/T10: start-velocity prior conditioned on the FIRST-WINDOW gyro (mean of the 10 rows; 363 mid starts, 5-fold CV)
Regimes: aligned |w_z|<0.15 (24%): speed p50 0.94, heading-vs-velocity angle p50 1 deg, 1% >90 deg / backward; mid 0.15-0.45 (18%): 6 deg, 6%; saturated >=0.45 (58%): 49 deg, 26% backward/>90 deg.
Linear model vc = [0.022 -0.004 .944] + w_z[-0.643 -0.027 -0.015] + sat[-0.047 -0.029 -0.702] + w_x[-0.895 0.186 0.087] + w_y[0.079 -0.027 -0.744]  (camera-0 axes x,y,z; w_* = gyro body FLU axes; coefficients printed by t7).
CV rmse per axis (x,y,z): adopted prior mean (0,0,0.9): 0.497/0.336/0.761 (3D rms 0.969); constant fitted mean: 0.498/0.338/0.642 (0.880); gyro-conditioned: 0.323/0.339/0.510 (0.693).
Heteroscedastic Gaussian NLL per start: adopted (0,0,.9;.5,.35,.6) -0.49; conditional -1.79. Calibration of the conditional model: mean z^2 (1.12,1.07,1.06), frac |z|>2 (5.8%,5.8%,7.2%) vs adopted (0.99,0.92,1.61) forward axis overconfident (z^2 1.61).
Per regime 3D rmse adopted -> conditional: aligned 0.67 -> 0.54 (sigma_x only 0.05!), mid 0.71 -> 0.61, saturated 1.13 -> 0.77; p90/p99 of |v err|: 1.40/2.38 -> 1.12/1.75. Roll comp of velocity also correlates with w_x (-0.42) and forward speed with w_y (-0.47).
Tilt cannot be predicted from the first window (CV rmse of up-vector comps 0.072/0.110 vs 0.074/0.111 constant; R2 <= 0.08). Truth start tilt vector: Gaussian roll-comp 0.074 rad, pitch-comp 0.110 rad (cam axes);
tilt-vector NLL: iso sigma .05 -2.37, .10 -3.70, .15 -3.39 (adopted MOVE_TILT_STD), .20 -2.99, anisotropic (.074,.110) -3.79 (best; heavy tails kurtosis 8.5/4.6, 6% |roll|>0.15, 17% |pitch|>0.15).

## 8. Ranked proposals (exploitable priors/constraints), each with the cheap test and what is still unproven
1. Gyro-regime-conditioned start-velocity prior (extends PRIOR_MODE=3). Replace mean (0,0,0.9) cam-axes, sigma (0.5,0.35,0.6) by the conditional model of T7/T10 (mean from w_z, sat, w_x, w_y; sigma per regime: x 0.05/0.14/0.40, y ~0.33, z 0.40/0.45/0.57).
   Evidence: truth NLL -0.49 -> -1.79, 3D rmse 0.97 -> 0.69, wrong-direction (backward) mass 26% only in the saturated regime and then always on the side of sign(w_z). The oracle study says direction matters more than magnitude and sigma 0.3 is needed;
   this gives lateral sigma 0.05-0.14 for 42% of starts and a signed lateral for the rest. Risk: coefficients fitted on our K/K2 pool (server planner differs, speeds likely similar since tracking-limited); regime thresholds 0.15/0.45 are tied to the 0.65 rad/s yaw saturation (a property of
   the policy, not of the overrides) so they should transfer. Test: run_variant on search+val (fresh for confirmation), 3 replicates; do NOT touch holdout. Expected: removes most of the residual "wrong-direction startup" failures (b6fix: 12 of 33 bad fresh flights).
2. Continuous "coordinated-turn" lateral-velocity pseudo-measurement, all times: v_y,body = 0.99 w_z |v_h| with sigma 0.06 (|w_z|<0.15) / 0.18 / 0.22 (and vertical-free). Replaces the PRI_LAT N(0, 0.5) prior (c2 block; -0.46 search on its own, +/- on top of the startup prior). Residual rms 0.19 vs 0.47: 2.5x tighter.
   Cheap test: replay est. velocity vs this law on pool traces; then run_variant. Caution: use filter's w_z = gyro - b_g and |v_h| from the filter state (a wrong |v_h| scales the constraint - keep inflated sigma or gate), expect benefit mostly in scale/bias observability during turns.
3. Anisotropic start-tilt prior in camera axes: roll-comp sigma 0.074, pitch-comp 0.110 (instead of isotropic 0.15), heavy-tailed (consider Student-t / 2-component: 6% |roll|>0.15). NLL -3.39 -> -3.79; tilt ~ -a_h/g exactly so it is the prior on the start horizontal acceleration (std 0.72/1.08 m/s^2).
   Note the startup NOTES found tilt .10/.20 not better than .15 within chaos noise: expect <= 0.1-0.2 m, needs 3 replicates.
4. Static-start exact ZUPT (detector: first two IMU rows identical, or |f|<8.8: 100%/98.7%): for t<2.0 s truth speed <0.08 m/s, tilt <1.1 deg, level; hold velocity at 0 sigma 0.03 and tilt sigma 0.01-0.02 until the pace of motion exceeds (speed first >0.1 at 2.75-3.0 s), gyro bias from the mean (400 samples -> 0.003 vs prior 0.0115), accel biases similarly;
   skip the first ~100 ms f_z spin-up (8.0 -> 9.8). Static mean ATE is 0.47-0.67 so upside is small and filter-dependent (it currently starts with sigma_v 1.0).
5. Bounded-acceleration/tilt prior from the planner: |a_h| certified <= 0.65 MAX_ACC, empirically p99 3.5 m/s^2, tilt p99 20 deg: only useful as soft weak limits (hard limits already failed in health C6). Low priority.
6. Metric-level: zero-fill caps a failed episode at its truth RMS distance (~4.7 m avg); not exploitable without a failure detector and a safe radius (tailcap says none). The mean of per-episode RMSE (equal weight) means one tail episode is linear in the score: keep investing in tail robustness (the 7.7 m episode).
7. Data/tuning pool mismatch (not a prior): server FOV 105-118 deg (fx 97-123) vs pool 105-134; reweight or regenerate if fx-sensitive effects (startup prior, texture) are tuned on the pool. Server planner is 3-4x faster than public defaults but tracking-limited; its true overrides are unknown.

## 9. Open items / caveats
* The start-velocity law uses OUR crop construction. If the server crops differently (e.g. random hover/in-flight state without the planner's regime mix) the gyro conditioning would not transfer; the aligned/saturated yaw behaviour (|w_z| in {~0, ~0.65}) is a property of the autopilot and should hold for any in-flight state of this planner.
* 363/80 flight samples of a K/K2 override pool; the server's real planner parameters are unknown (public-default planner would give ~3x slower flights; the yaw saturation and the heading-chase law are independent of speed).
* We did not run the estimator; all numbers are truth-only conditional statistics.
* private_stage2: only hashes; no scene/seed/crop information exists in public code.
