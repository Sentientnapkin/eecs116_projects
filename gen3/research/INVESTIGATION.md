# Technical investigation (2026-11-26) — narrow the research space before big GPU spend
Read research/BRIEF.md first (baseline, eval sets, data, code, rules; §8 work style). Targets explored:
A ≈0.5 m @ ≤1 M peak fuel; C ≈0.15 m @ ≤100 M; D ≈0.05 m @ ≤1 G (exploratory, not assumptions).
Rules for every agent: label every claim MEASURED / EXISTING RESULT / NEW EXPERIMENT / MATH / HYPOTHESIS / UNKNOWN. Never fabricate
expected ATE. Ground truth only for local diagnostics. No submissions, no edits to the frozen baseline (research/baseline/) or other
agents' dirs, v3 TEST split never used. Token-light: write python/bash pipelines that run detached and resumable (nohup setsid,
queue + done markers + results.tsv), then wait with one long until-loop; read only summaries. Output: research/<agent>/REPORT.md
(answers per question, tables, plots as PNG paths, reproduction commands) + a short final message.

## i1 — Scoring, resources, fuel (Q16, Q17, Q14-fuel)
- Exact competition scoring: find the implementation/docs (search eecs116_projects, eecs116_vio, probe/README, results_*.json
  fields, any leaderboard/frontier data, course materials in the repo). How is claimed area computed; credit for multiple frontier
  points; overlap assignment; value of a high-fuel high-accuracy point; one improved solution vs complementary points. Compute
  hypothetical score contributions over a grid of (ATE, peak fuel) incl. Targets A/C/D against the current competitive frontier.
- Authoritative facts: GPUs (types/counts/availability: only 3,5,6,7 usable by us), CPU, RAM, storage, rendering throughput
  (gen3 logs), training infra, competition deadline, submission quota, pretrained/external-data eligibility, module size/memory
  limits, WASM SIMD, precision, our NN inference engine (int16 SIMD exporters), distributed inference across step calls.
- Fuel: measured peak/p95 breakdown of the baseline by component (image conversion, pyramid, detection, tracking, IMU/covariance
  propagation, triangulation, visual updates, net inference, init, recovery, governor overshoot) — use agents/smallnet/tools
  (prof.py, snbench.py, fuelstats.py) and the goats bench pattern; measured fuel of model sizes at ~1, 5, 10, 25, 100, 500, 1000 M
  (e.g. conv stacks via agents/cheap/tools/mknet.py / smallnet exporters), not FLOP estimates.

## i2 — Baseline facts, time-resolved and vertical error attribution (Q1, Q2, Q7, r10 step 1)
- Q1 table: exact config, image resolution, feature/clone counts, update policy, init procedure, net architecture/schedule, gravity
  and bias init, measurement covariances, local-vs-server config differences. Breakdowns by scene, start type, initial speed, FoV,
  exposure, angular velocity, acceleration, path length, tracking quality. Why earlier approaches were abandoned (agents/*/NOTES.md,
  research/single_model/*/NOTES.md, reports/).
- Q2: instrument a copy of the baseline (debug output of state + covariance per frame, or diff vs GT trajectories) and compute
  position/velocity/orientation/gravity(tilt)/bias error at 0.25, 0.5, 1, 2, 5, 10 s and end; share of final error from the start;
  growth law (linear/quadratic/jumps/random walk); local accuracy vs global offset (RPE vs ATE); scale error; velocity error
  autocorrelation; failure concentration; correlation of ATE with sensor/motion/scene variables. Horizontal vs vertical split.
  Plots for good/median/poor flights. Verify the "post-hoc start-error removal doesn't help" finding on this baseline.
- Q7 vertical: true vertical motion, vertical error type (offset/drift/oscillation/under-estimated motion), false vertical motion in
  constant-altitude flight, correlation with tilt error, accel bias, initial vertical velocity; floor/ceiling visibility (from images
  /scene metadata); value estimates for plane/height constraints (oracle runs come from i3).
- Find the previously reported 0.581 m "joint oracle" and 0.813 m "delayed-velocity oracle" (grep NOTES/reports/research) and
  record their baselines, interventions, covariances, replication status.

## i3 — Oracle and noisy-oracle harness (Q3, Q4, Q11, Q12)
- Build ONE harness: offline python writes a per-flight GT side-file (GT pose, differentiated velocity, gravity in the filter frame,
  offline-LS biases, triangulated landmark depths where needed); a copy of the baseline C gets ORACLE_* switches that read it (via a
  host-side mechanism allowed only in diagnostic builds — check evalpool/host for how to pass extra data; a diagnostic host is fine)
  and inject measurements with chosen covariance, frequency, latency, noise type (white / correlated / bias / shared-scale /
  outliers). Everything else identical to the baseline.
- Q3 table (each: intervention, timing, replace vs supplement, covariance, latency, overall + per-scene ATE, paired d + CI, failures):
  true v0, speed only, direction only, gravity, v0+gravity, accel bias, gyro bias, biases throughout, relative rotations, orientation
  throughout, landmark depths, perfect correspondences (if feasible), true velocity first 1 s, every 0.5 s, relative translation every
  0.5 s, vertical velocity every 0.5 s, relative vertical displacement every 0.5 s, altitude vs origin.
- Q4 curves: velocity 0.05–1 m/s, depth 2–40%, gravity 0.1–5°, correspondence 0.1–2 px, relative translation 1–20%, vertical
  displacement 0.02–0.5 m; noise types as above; frequency (every 1/2/5/10/20/40 frames, init-only) and latency (0–16 frames)
  independently. Answer: does 10–20% depth help; correspondence accuracy needed; periodic velocity accuracy needed; value of a
  vertical model; which survive delay.
- Q12: NEES/NIS and consistency of the baseline; can perfect velocity worsen ATE (covariance/latency); clone-relative translation
  fusion; depth priors before landmark elimination; shared depth-scale state; origin-relative correction; fixed-lag smoother value.
- Queue the whole sweep as one script; ≤8 eval workers; use pools/v3val (358) or a fixed stratified 120-flight subset for sweeps,
  full set + 3 replicates to confirm key points.

## i4 — Classical with relaxed compute + frontend diagnostics (Q5, Q6)
- Sweep existing switches far beyond the budget (GOV_B off/huge): image width, 2/5/10× features, clone window 6→12/20/30, track
  lifetime, KLT accuracy, iterations/relinearization; note which need code changes. Try an existing high-accuracy open VIO
  (OpenVINS / VINS-Fusion / Basalt / ORB-SLAM3 inertial) offline on a subset if buildable locally (CPU; licensing OK for diagnostics).
  Separate: unrestricted causal VIO, offline non-causal smoothing (e.g. full-batch BA with GT-free inputs), oracle-assisted.
  Central question: can classical geometry approach 0.1 m on our distribution; if not, which limit (observability, init,
  correspondence quality, sensor errors, estimator design).
- Q6 frontend stats from an instrumented copy: track lifetimes (survival at 5/10/20/40 frames), counts by scene/exposure, parallax
  and triangulated-depth distributions, triangulation and gating rejection rates, tracking failures, subpixel accuracy vs truth
  (project GT-triangulated landmarks), coverage, residual rotation after gyro compensation, accuracy vs resolution / features /
  window. Which of gyro-guided prediction, rotation-compensated flow, 2-pt translation, long-baseline tracking, depth/information-
  aware selection, distant-landmark rotation constraints, blur-aware covariance are already implemented / tried / promising.
  Does a learned tracker add information or just cost?

## i5 — Simulator supervision and reusable geometric dataset (Q8, Q9)
- Inspect gen3/g3.py, the hyperlux/rl_tools renderer, scene assets (gen/conta, catalogs, glb meshes) and HF viobench-stage3. Can we
  get dense metric depth, depth at arbitrary pixels, exact flow, 3-D correspondences, visibility/occlusion, normals, semantics,
  floor/ceiling labels, unblurred frames, sub-exposure poses, true velocities, true biases, meshes? Verify conventions (z-depth vs
  ray distance, frames, flow direction, exposure timing, pose timestamps, intrinsics under resize). Can existing flights be
  re-rendered with extra outputs; raycast depth from meshes + recorded poses; correspondences without RGB; render arbitrary poses;
  reproduce trajectories with other FoV/exposure/texture/lighting/scale; counterfactual initial velocities; new IMU noise
  realisations. Measure cost/throughput with a SMALL test only (GPU 5 or, after gen3/out/GEN_DONE, GPUs 3/6/7; never 0,1,2,4).
  Fallback: sparse depth labels from offline matching + triangulation with GT poses.
- Q9: design + cost a precomputed geometric training set (image windows, intrinsics, IMU + preintegration, tracks, bearings,
  quality, depths/visibility, GT correspondences, MSCKF states/covariances/innovations, GT poses/velocities/gravity/biases,
  metadata): storage, preprocessing throughput, parallelism, I/O, mid-flight window cropping with correct re-initialised frames.
  Build a small prototype shard (≈50 flights) to measure, don't build the full set.

## i6 — Learned-model diagnostics + Target C/D architecture review (Q10, Q13, Q15)
- Q10 for A160ft (and auto_727, smallnet A2_kd, netv2 X/B240): architecture, params, MACs, measured fuel, inputs, resolution,
  context, schedule, objectives, data, validation; speed error, direction error, signed bias, vertical vs horizontal error,
  conditional calibration, held-out-scene generalization, MSCKF integration, known regressions. Input ablations by short GPU 5
  trainings on the existing cache (IMU only, orientation only, single image, 2 frames, longer sequences, +intrinsics, flow only,
  rotation-compensated flow, tracks+IMU, all) — how much is physics vs motion-distribution prior; would speed-only + geometric
  direction beat full-vector regression; is the net near its ceiling (learning curves exist in agents/netv2/NOTES.md).
- Q13/Q15 literature + reasoning (cite papers/implementations: DPVO/DROID, TLIO, RNIN, deep VIO transformers, metric depth models,
  differentiable filters/BA): for architectures A–G assess information extracted, failure modes addressed, evidence for them,
  supervision, generalization risk, causality, inference complexity, plausible peak fuel, distillability to Target C, risks.
  Direct-C vs D-then-distill vs modular components. Explicitly mark what experiments would establish feasibility. Use i3/i4/i5
  REPORT.md files when they appear (read-only).
