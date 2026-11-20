# Fundamentally different state-estimation formulations and learning paradigms for monocular+IMU drone odometry (2026)

Scope note: web research was limited (about 15 tool calls). Arxiv IDs marked VERIFIED were opened on arxiv.org/abs in this session; IDs marked UNVERIFIED came only from search snippets. Most abstracts gave no numbers, so quantitative claims are few. Project context numbers come from reports/Drone VIO ATE approaches.md. The "Local diagnostic" numbers are my own computation (script: /data/backups/rganapa/Sebastian/tmp/claude-1000/-data-backups-rganapa-Sebastian-eecs116-projects/b6c1eecc-bd43-4dc8-9783-b32fe49af7c1/scratchpad/decomp.py and decomp2.py), read-only on repo data.

## Q1. What does our own saved data say the learned model's error actually is? (changes which paradigm to pick)

### Takeaway
On 40 of the 171 selected flights, the learned guests (N2 kf-input s217, B-D0) barely beat "stay at origin": they under-predict speed by about 2.6x and shrink the trajectory extent, so the dominant error is amplitude collapse (regression to the mean), not yaw alone. VINS-Mono on the same 40 flights has mean ATE 0.45 m. A paradigm that fixes only yaw would leave most of the error.

### Cited Findings
- Local diagnostic (my computation, first 40 flights alphabetically in bench-fast/selected, estimate.tum from each guest's report/logs vs truth zips, truth converted to camera0 frame via T_imu_cam and expressed relative to the first estimate pose). Reproduces official scores approximately (N2 3.65 vs official 3.51 on 171; VINS-Mono 0.45; B-D0 3.80 vs 3.84):
  - N2 s217: mean unaligned ATE 3.65 m; error of a constant-origin (zero motion) estimate 4.23 m; best-fit global scale factor 1.64 (estimate should be scaled UP); mean speed estimated 0.35 m/s vs true 0.91 m/s; bounding-box diagonal of estimate 4.18 m vs truth 11.40 m; estimated path length 21 m vs true ~55 m.
  - Full rotation (Kabsch, no scale) alignment only lowers N2 mean ATE 3.65 to 3.40 and B-D0 3.80 to 3.43; origin-scale-only alignment lowers N2 to ~3.2 (both are crude, not Sim(3)). So neither global rotation (yaw+tilt) nor global scale explains most of it.
  - VINS-Mono: ATE 0.45, speed 0.93 m/s, extent 11.66 m, i.e. correct amplitude.
- Project report: learned error Spearman 0.88-0.93 with identity-pose error; oracle perfect yaw cut true-velocity-through-gyro dead-reckoning from 0.967 to 0.209 m (so yaw matters when velocity is perfect) — /data/backups/rganapa/Sebastian/eecs116_projects/reports/Drone VIO ATE approaches.md
- Environment: episodes have 200 Hz IMU noise std gyro 0.07, accel 0.28 (large), biases random walk; camera 122 deg HFOV pinhole 640x480 raw (episode.json in truth zips).

### Inferences
- The learned velocity head likely suffers MSE-style shrinkage on fast (0.9 m/s avg, 3-6 m/s cruise segments) flights it was not trained on (training flights <=33 m path). Any paradigm should therefore be judged on speed/amplitude fidelity, not just yaw. Falsify with per-flight regression of estimated vs true speed (slope) on all 171 flights; if slope is ~0.4 everywhere, the cheapest win is a training-distribution/loss fix (or scale-calibrated metric head), independent of paradigm.
- Caveat: only 40 flights, sorted order, includes mid-start flights; the frame convention was reverse-engineered and only checked by score reproduction.

### Gaps
- No yaw/scale/amplitude decomposition on all 171 flights; no Sim(3) or 4-DoF-with-gravity alignment done properly (needs gravity-aligned start frame).

## Q2. Ranked candidates (mechanism, evidence, why it could help, wasm, GPU fit)

### Takeaway
Ranking for mean unaligned ATE under wasm/causal constraints: (1) learned-covariance differentiable filter wrapped around the existing geometric VIO plus learned velocity (guard as a trained estimator), (2) multi-hypothesis yaw/scale tracking over the learned velocity net, (3) learned-prior initialization for VINS/OpenVINS (kills catastrophic tails), (4) simulator-trained long-context SSM/transformer with amplitude-aware loss (our current family, fixed), (5) test-time self-supervision, (6) equivariant/invariant filter rewrites, then speculative ones. Nothing found shows a formulation that by itself reaches 0.5 m unaligned; the evidence in the literature is mostly aligned ATE, pedestrians, or EuRoC.

### Cited Findings
Tier A (try first)
1. Differentiable filter / learned-covariance fusion, trained end to end on unlimited sim data.
   - Mechanism: embed EKF/ESKF update in the graph; learn measurement (displacement/velocity) and its covariance through posterior-position loss. Wagstaff et al. differentiable KF with IMU process model + network relative-pose measurement, self-supervised, recovers metric scale, no divergence on degraded EuRoC — [arXiv 2203.07207, VERIFIED](https://arxiv.org/abs/2203.07207). DFIO (Nov 2026): joint training of displacement and covariance heads through differentiable measurement updates; 13.2% lower mean abs translation error vs TLIO, 39.6% lower 1 s RTE (pedestrian data; no ATE/yaw reported) — [arXiv 2611.13517, VERIFIED](https://arxiv.org/abs/2611.13517).
   - Library: Theseus (differentiable nonlinear least squares, GPU, implicit differentiation) — [arXiv 2207.09442, found via search, abstract summarized by search not opened](https://arxiv.org/abs/2207.09442); differentiable factor-graph smoothers — [arXiv 2105.08257, snippet only](https://arxiv.org/pdf/2105.08257).
   - Why it helps us: the report's untried item 1 (NLL fusion). Train the gating on sim: output covariance of VINS/OpenVINS/N2 so the filter downweights failing sources; directly optimizes the raw-mean metric including tails (loss on unaligned ATE, can use log or heavy-tail-weighted).
   - Wasm: only inference (small covariance heads + 15-state ESKF) ships; high. GPU: heavy training, parallel over flights, good fit.
   - Falsify: on existing per-flight trajectories of N2, VINS-Mono, OpenVINS (all 171), fit a tiny classifier on trajectory-only features (speed vs N2, innovation, init time) with leave-scene-out CV; compare with oracle-min and the repo's post-hoc gate. Kill if CV gate mean >2.0 m.
2. Multi-hypothesis yaw/scale tracking.
   - Mechanism: keep K yaw offsets (or K scale values) of the learned velocity-through-attitude path, weight by a learned visual/IMU likelihood, resolve later (delayed decision is not causal for output, but a mixture or MAP-so-far output is). Particle/multi-hypothesis filtering is shown to beat a single filter on VO-vs-prior-map, though sometimes picking a wrong hypothesis — [TAROS 2021 paper, snippet](https://lcas.lincoln.ac.uk/wp/wp-content/uploads/2021/09/p1.11-TAROS2021paper11.pdf). I found no VIO paper using learned-likelihood multi-hypothesis for yaw (searched once).
   - Why: targets the oracle-yaw gap (0.967 to 0.209 m) but, per Q1, only part of the error.
   - Wasm: K=16-64 particles of a cheap state, fine. GPU: train likelihood.
   - Falsify: with truth, add synthetic yaw offsets to N2 trajectories and test whether a visual two-view rotation likelihood (existing kf_grid features) can separate them; kill if best-of-K selection with the real likelihood does not cut yaw error by 30%.
3. Learned/foundation-model-assisted VIO initialization.
   - Feed-forward 3D model gives metric scale, velocity, gravity by a closed-form linear solve; success >90%, needs under 1.2 s vs 3-4 s — [arXiv 2605.17327, VERIFIED](https://arxiv.org/abs/2605.17327). Learned monocular depth priors in VI initialization improve conditioning in low excitation — [ECCV 2022, arXiv 2204.09171, snippet](https://arxiv.org/pdf/2204.09171). Learned covariance for init/calibration: MAC-I2 — [arXiv 2609.07116, UNVERIFIED](https://arxiv.org/pdf/2609.07116). Caution: a controlled study found a learned prior in VINS changed mean APE only -0.2% on KITTI, and online extrinsic updates worsened APE 45-52% — [arXiv 2609.13777, VERIFIED](https://arxiv.org/abs/2609.13777).
   - Why: project shows OpenVINS mean 0.98 m if init within 3 s vs 168 m otherwise; init failures are the tail.
   - Wasm: a small CNN/MLP init head (N2 itself already supplies v0, gravity direction); a depth foundation model is too heavy for wasm fuel (2e10/step) so prefer N2-provided velocity seeds. Falsify: instrument the 17 OpenVINS flights >10 m and replace estimated v0 by N2 velocity over the first 3 s offline.

Tier B
4. Long-context end-to-end Mamba/SSM/transformer VIO.
   - Evidence is thin: MambaVO (visual), MambaIO (inertial pedestrian, 8-15% lower errors, secondary summary) — [arXiv 2412.20082 snippet](https://arxiv.org/pdf/2412.20082), [arXiv 2511.15645 snippet](https://arxiv.org/html/2511.15645v1); SS-VIO (KITTI, ResearchGate only). No paper found on long-context Mamba VIO explicitly. Our own SSM model is already this class and shows amplitude shrinkage; gains must come from loss/data (full-trajectory loss, 60 m flights, speed-matched data), not architecture (project: architecture swaps inside seed noise).
   - Falsify: cheap per-flight speed-slope check (Q1); then fine-tune on the 882 pool windows with full-length loss on a held-out split.
5. Test-time training / self-supervised online adaptation.
   - RIO: rotation-equivariance self-supervision + uncertainty-gated TTT; >25% gain in several scenarios; 9.29% on RoNIN, 17.04% on RIDI (secondary snippet) — [arXiv 2111.11676, VERIFIED abstract](https://arxiv.org/abs/2111.11676). UL-VIO: BatchNorm-only test-time adaptation with inertial-referred pseudo labels, <1M params, ~1% KITTI error cost — [arXiv 2409.13106, VERIFIED](https://arxiv.org/abs/2409.13106). Adaptive VIO: online continual learning with VI-BA — [arXiv 2405.16754, VERIFIED](https://arxiv.org/abs/2405.16754). Self-supervised LoRA adaptation of IMU model — [arXiv 2608.25427, snippet UNVERIFIED](https://arxiv.org/html/2608.25427).
   - Why: could fix per-flight speed shrinkage (e.g. adapt a scale head against IMU double-integration consistency over short windows). Wasm: backprop on BatchNorm/scalar parameters is feasible in C++ but costs fuel and parity risk. Falsify: offline, optimize a single per-flight scale/gain on N2 velocities to match accelerometer-integrated velocity over 2 s windows; kill if scale error vs the oracle best-fit scale does not drop below 20%.
6. Equivariant/invariant filters (EqVIO, MSCEqF, InEKF + learned bias).
   - EqVIO with SOT(3) landmark symmetry for monocular — [arXiv 2205.01980 (journal), 2104.03532 (ICRA21), via search](https://arxiv.org/abs/2205.01980); authors' own claim of state-of-the-art among EKF VIO on EuRoC, no independent replication seen. MSCEqF — [arXiv 2311.11649, VERIFIED](https://arxiv.org/abs/2311.11649). Learned IMU bias inside invariant MSCKF, preserves symmetry, robust when vision is lost — [arXiv 2505.06748, VERIFIED, no numbers](https://arxiv.org/abs/2505.06748).
   - Why limited: better consistency and large-linearization-error tolerance help initialization transients, not amplitude shrinkage or textureless failure; yaw is still unobservable from IMU+camera without a reference. Wasm: EKF-class, light, feasible (EqVIO C++ exists). Falsify: run only if init-linearization is the proven failure cause in the 17 OpenVINS tail flights.

Tier C (speculative / low priority for this setting)
7. Learned dense/deep BA (DPVO, DROID-SLAM, DBA-Fusion; DBA-Fusion RAL 2024 combines deep DBA with IMU in a factor graph) — [arXiv 2403.13714, VERIFIED, no numbers](https://arxiv.org/abs/2403.13714); DEIO reports DBA-Fusion failing on several sequences where DPVO does not (secondary, search snippet) — [arXiv 2411.03928, snippet](https://arxiv.org/html/2411.03928). Not wasm-feasible at inference; use as teacher only.
8. Physics-informed dynamics as process model: HDVIO, point-mass model + learned aerodynamics from thrust+IMU history, up to 33% better motion estimation — [arXiv 2306.11429, VERIFIED](https://arxiv.org/abs/2306.11429). Needs thrust input (not in our ABI per project notes); simulator drag unknown.
9. Continuous-time GP/B-spline: GP-based IMU preintegration for asynchronous event-inertial (GPO) — [arXiv 2412.08909, snippet](https://arxiv.org/abs/2412.08909); survey — [arXiv 2411.03951, snippet](https://arxiv.org/pdf/2411.03951). Benefit is asynchronous/high-rate sensors; ours is synchronous 20 Hz camera, so little expected gain; costlier solve.
10. Diffusion/flow posterior over trajectories: found only IMU-bias diffusion (EuRoC) — [arXiv 2505.11763, snippet](https://arxiv.org/pdf/2505.11763) and VeloBins velocity-bin uncertainty for aerial inertial odometry — [arXiv 2608.29720, UNVERIFIED](https://arxiv.org/pdf/2608.29720). No full-trajectory posterior for VIO found. Cheap relevant variant: replace regression head by binned/mixture head to avoid mean-collapse (directly addresses Q1 shrinkage) — falsify by checking whether per-frame velocity predictions are bimodal at fast segments.
11. Analysis-by-synthesis / simulator as likelihood / render-and-compare: no reliable literature found in my searches; the simulator (OptiX) is not available in wasm, so only as a training-time teacher (e.g., render-based consistency losses). Gap.
12. Learned trajectory/planner prior: no paper found on a learned ego-motion prior regularizing VIO (search returned human-motion and planning diffusion priors only: [Motion Planning Diffusion, arXiv 2308.01557](https://arxiv.org/abs/2308.01557), [Human Motion Diffusion as a Prior, arXiv 2303.01418](https://arxiv.org/abs/2303.01418), both snippets). Our flights come from a roadmap planner with known speed range; a prior over speed profile (amplitude) is the realistic piece.
   - Falsify using saved truths: compute speed-profile statistics (mean speed per segment) of the 171 truths; test whether a speed-scaling rule using the prior (rescale estimate speed to prior mean) lowers N2 ATE; cheap and also exploits the planner's cruise speed range. Kill if gain <5%.
13. Event-camera/optical-flow-only photometric velocity: no evidence for a 20 Hz RGB setting; the learned velocity model already uses correlation volumes (optical-flow-like).

### Inferences
- The most promising non-incremental direction is not a new estimator but making the estimator aware of its own error (learned covariance + differentiable filter) and attacking init transients with learned seeds; both are cheap in wasm and use H100s for training only.
- Because the learned model's error is amplitude collapse, a heavy-tail/mixture or binned velocity head and a scale-consistency adaptive step (IMU-integrated velocity as anchor) may beat any yaw-focused fix; yaw multi-hypothesis then handles the remaining 0.2-1 m.
- Published numbers are not comparable to ours (aligned ATE, pedestrian, EuRoC/KITTI), so treat gains as directional only.

### Gaps
- No verified numbers for EqVIO/MSCEqF on drone data; abstracts for 2505.06748, 2403.13714, 2405.16754 had none.
- No papers found for simulator-in-the-loop likelihood, planner-prior regularization, or full-trajectory diffusion VIO; may exist but searches did not surface them.
- 2026 IDs marked UNVERIFIED (2609.07116, 2608.29720, 2608.25427) were not opened; 2105.08257, 2207.09442, 2412.08909, 2411.03951, 2411.03928, 2412.20082, 2511.15645, 2505.11763, 2308.01557, 2303.01418, 2204.09171 were seen in search results only (the Theseus and EqVIO details come from search summaries).
- RIO's author attribution in a search summary ("Cao et al.") conflicts with the arXiv abs page (Zhou, Cao, Zeng, Wang); use the abs page.

## Q3. Cheap falsification experiments on existing data (read-only), in priority order

### Takeaway
Five offline experiments using saved estimate.tum files (under /data/backups/rganapa/Sebastian/baselines/bench-fast/selected/<guest>/<flight>/report/logs/*/estimate.tum, estimate frame = camera0 at first frame) and truth in gen/raw-fast/selected/*.zip (IMU-frame ground truth, convert with T_imu_cam in episode.json) decide which paradigm deserves GPU time within hours.

### Cited Findings
- Available guests with 171 flights each: b_d0, bd0_kfgrid, bd0_velfusion, dead_reckoning, n2_kfgrid, n2_kfinputs_s217/s218/s219, openvins, sp5_combined/direction/manhattan, vins_mono (directory listing). Python note: the venvs lack scipy; numpy exists in /data/backups/rganapa/Sebastian/venv-teacher.
- E1 (amplitude): regress estimated vs true speed over all 171 flights and all guests; if slope for learned guests is ~0.4, prioritize loss/head fixes and TTT scale anchor. Kill criterion for "yaw dominates": 4-DoF alignment gain <15% (already about 7% on 40 flights).
- E2 (gate): oracle-min and cross-validated gate over N2/VINS/OpenVINS (project stage 0).
- E3 (speed-prior rescale): rescale N2 speeds by the planner-prior mean speed; measure ATE.
- E4 (yaw multi-hypothesis): inject yaw offsets, test separability with the existing kf_grid features.
- E5 (init seeding): on the 17 OpenVINS tail flights, test whether replacing early velocity with N2 velocity avoids takeover transients.

### Inferences
- E1 and E2 take minutes of CPU and decide between "fix learned head" and "learned guard"; run them before any GPU training.

### Gaps
- E1 was run only on 40 flights in this session (Q1); full-pool results not computed.
