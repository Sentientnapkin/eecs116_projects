# Track specs (from the user's research plan, 2026-11-26). Read the SHARED REQUIREMENTS at the bottom too.

## r1 — Gyro-compensated optical flow and translation direction
Get accurate translation/velocity DIRECTION from feature correspondences + gyro-integrated relative rotations.
Implement and compare: (1) gyro-guided feature tracking (predict feature positions from rotation); (2) rotation-compensated
optical flow; (3) exact finite-frame epipolar geometry with known relative rotation; (4) 2-point translation-direction RANSAC;
(5) weighted 3x3 eigenvalue translation-direction estimate; (6) robust IRLS and alternative outlier rejection; (7) confidence from
residual statistics, eigenvalue separation, spatial coverage, parallax; (8) sign disambiguation from positive depth; (9) temporal
baselines: consecutive frames vs longer-baseline correspondences.
Constraint: n = cross(R_21 b_1, b_2), nᵀ t_21 = 0 (b = calibrated bearings, R_21 from gyro + camera-IMU calibration).
Care: camera vs IMU velocity/frames, gyro bias and rotation uncertainty, camera-IMU lever arm, forward/backward/sideways/diagonal
motion, near-zero translation, wide FoV, motion blur, low-parallax warehouse/forest.
First standalone vs GT: angular error, sign accuracy, confidence calibration, failure rate. Compare with the CNN's direction and
oracle direction diagnostics. Then use the direction to constrain/correct the learned initial velocity. Share your direction
estimator code (C + python) in research/r1/lib/ for r2/r9.

## r2 — Metric initial velocity from visual direction + inertial acceleration
v_i = v_0 + Δv_i (IMU), P_i = I − d_i d_iᵀ, P_i v_0 = −P_i Δv_i; accumulate, weighted LS for v_0.
Implement (a) direction-based estimator consuming r1-style directions (build your own minimal direction estimator if r1's is not
ready), (b) standalone finite-displacement estimator: substitute integrated inertial position into raw epipolar constraints over
finite intervals (do not treat inter-frame displacement as instantaneous velocity).
Investigate windows 2,3,5,10,20,30,40 frames; frame-pair baselines; gravity and accel-bias sensitivity; confidence-weighted fusion
with the learned velocity; correcting only geometrically observable components; robustness to near-constant velocity and purely
longitudinal acceleration; incremental sufficient statistics. Oracle gravity/biases first, then estimated ones.
Measure: initial |v| error, direction error, current position error, conditioning, latency, downstream ATE. Never force-replace the
existing estimate when poorly conditioned.

## r3 — Direct joint visual-inertial initialization (v0, g, b_a)
Initial IMU frame as reference: p(t) = t v_0 + ½t² g + α(t) − B(t) b_a, α(t)=∫(t−τ)R(τ)a_m(τ)dτ, B(t)=∫(t−τ)R(τ)dτ;
x=[v_0,g,b_a], F(t)=[tI, ½t²I, −B(t)], p(t)=F(t)x+α(t); lever arm p_C(t)=p(t)+R(t)r_IC; for corresponding bearings rotated
into the reference frame: n_ijᵀ(p_C,j − p_C,i) = 0 → linear Ax=b.
Investigate 3-D (fixed g, b), 6-D (v_0, g), 9-D (+b_a) solvers; gravity-magnitude constraint; gyro-bias correction / bounded
outer refinement; Manhattan gravity priors; learned velocity priors; bias regularization; robust losses; uncertainty and
observability checks; numerically stable accumulation and small solvers; conditioning after unit scaling and priors.
Literature: direct and rotation-translation-decoupled VI init, closed-form init (Martinelli, Kaiser), landmark elimination.
Decide whether it beats the current init standalone and fused with the net; how early useful metric estimates appear.

## r4 — Learned metric depth + geometry-based velocity
flow_i = (1/Z_i) A_i v (translational flow is analytic given depth). Compare: coarse metric depth maps (8x8, 16x12, 32x24), sparse
depth at tracked features, global/effective scene depth, relative depth + learned global scale, metric inverse depth, per-feature
depth uncertainty, floor-plane / camera-height where applicable. Evaluate instantaneous-flow velocity recovery and exact
finite-frame translation from predicted 3-D landmarks + tracked bearings; uncertainty weighting, robust regression, shared depth
errors, systematic scale bias, FoV conditioning.
START WITH ORACLE DEPTH (ceiling). No depth maps are stored: use GT poses + tracked features to triangulate oracle feature depths
offline (and ask the orchestrator before any re-rendering with the simulator). Then train learned variants: depth / inverse-depth
error, global scale error, initial |v| and direction error, velocity uncertainty calibration, downstream ATE, WASM fuel.
Prioritize generalization to unseen scenes, FoVs, exposures, regimes. (r11 covers model design/other targets — coordinate via notes.)

## r5 — Depth-aware feature management and rotation estimation
Select/weight MSCKF features by geometric information, not only corner strength + grid. Separate: near high-parallax landmarks for
translation/scale; distant landmarks for rotation and gyro bias; long-lived tracks for temporal consistency; features that
constrain currently uncertain state directions. Implement/compare: depth-aware selection; parallax-aware track selection;
information-based ranking (measurement Jacobians + state covariance); marginalized-landmark information; explicit rotation-only
constraints for distant features; robust visual rotation corrections; gyro-bias estimation from long-lived low-parallax tracks;
per-feature covariance from track quality, depth, blur. Don't misclassify near-epipole low-parallax features as distant.
Goal: same or better ATE with fewer feature updates → lower peak fuel. Use existing MSCKF infrastructure. (The anchors agent is
sweeping clone-window/track-length switches — don't duplicate plain switch sweeps.)

## r6 — Multi-view flow magnitude and landmark-eliminated initialization
Recover metric speed under longitudinal acceleration where direction alone is insufficient. Preliminary diagnostic: does the change
of rotation-compensated flow magnitude + IMU acceleration reveal speed change (don't assume constant depth/projection).
Principled multi-view: min over x and landmarks Σ ||(I − d_ik d_ikᵀ)(P_k − p_C,i(x))||², p_C,i(x) from the integrated IMU model
(as r3); eliminate each landmark (Schur complement / null-space). Investigate multi-view constraints with shared landmark geometry,
efficient elimination, bearing-space vs normalized reprojection residuals, depth-dependent weighting, conditioning for distant
landmarks, comparison vs pairwise epipolar init (r2/r3), metric scale under longitudinal acceleration, incremental bounded updates.
Establish whether it gives stronger metric constraints than r2 and r3.

## r7 — Motion blur as a motion measurement
Inspect the simulator's blur generation first (gen3/g3.py and the hyperlux camera: exposure averaged over 5 ms sub-renders in
linear light). Investigate directional gradient statistics, patch autocorrelation, blur direction/length estimation, spatially
varying rotational vs translational blur, exposure estimation using the gyro, first-frame hover vs moving classification,
first-frame translation direction (sign ambiguity), blur-derived velocity priors with depth, blur-aware feature covariance and
tracking confidence. Classical and small learned models (privileged labels offline). Determine whether exposure and motion can be
disentangled. Treat blur as an uncertain supplemental observation. Standalone accuracy first, then VIO integration.

## r8 — Exposure and effective timestamp
Determine whether camera timestamps correspond to exposure start/mid/end or another convention (episode.json says
"timestamp": "mid_exposure" — verify against the renderer, gen3/g3.py, and the frame/IMU timestamps). Relationship between
exposure, angular velocity, visual rotation and gyro-integrated rotation. Investigate fixed offset, per-episode offset,
exposure-dependent offset, VI rotational consistency across candidate offsets, joint gyro-bias + offset estimation, blur-aware
measurement models, pose interpolation at effective observation times. Oracle experiments with known timing. Quantify effect on
tracking, init, downstream ATE. Don't add a correction if the sim is already synchronized. Strictly causal.

## r9 — Multi-hypothesis initial velocity
Small posterior over initial speed/velocity/regime instead of committing to one net prediction: discrete 8–32 speed hypotheses,
Gaussian-mixture prior, hover vs moving hypotheses, speed hypotheses along a geometric direction (r1), light particle estimator,
delayed commitment. Don't run a full MSCKF per hypothesis unless justified; share tracks, IMU integration, accumulated geometric
constraints. Score hypotheses with pairwise epipolar consistency, multi-view reprojection, inertial dynamics, learned depth,
the net's velocity, physical priors. Keep uncertainty when uninformative. Compare posterior mean, MAP, mixture-based filter init,
conservative fallback. Focus: catastrophic init failures and worst-episode ATE.

## r10 — Origin-anchored initial-state refinement
Do init errors get permanently embedded after early clones are marginalized? Build a light mechanism to improve the current pose
relative to the episode origin when new info on v_0, g, biases arrives: retain selected early clones, a few long-lived anchor
landmarks, a secondary initial-state estimator, bounded early-window smoothing, fixed-lag init refinement, controlled reset or
bounded replay, explicit propagation of initial-state uncertainty, correcting current position as well as velocity.
δp(t) ≈ t δv_0 + ½t² δg − B(t) δb_a — but account for intervening corrections/correlations; no double counting. Outputs must stay
strictly causal (can't revise past poses). Evaluate vs the existing sliding window on unaligned ATE.

## r11 — Small learned models for missing geometric information
Which learned quantity gives the largest marginal benefit inside the classical estimator: initial metric speed (vs full 3-D v),
metric/effective depth, relative depth + global scale, hover-vs-moving probability, velocity uncertainty and multimodal
distributions, gravity direction + confidence, bias priors (if inferable), feature measurement uncertainty, track reliability,
exposure/blur, motion excitation/observability, init confidence. Compare tiny standalone models vs a shared light encoder with
multiple heads; inputs incl. intrinsics, IMU statistics, geometric feature measurements, rotation-compensated flow. Uncertainty-aware
losses, mixture density, distillation, quantization, integer-friendly architectures. Evaluate multiple deployment budgets against the
actual score (smallest isn't automatically best). Coordinate with r4 (r4 = depth→velocity geometry; r11 = model design, other
targets, uncertainty, accuracy-vs-fuel). Existing net tooling: agents/netv2, agents/smallnet.

## SHARED REQUIREMENTS (all tracks)
- Oracle ceiling first where applicable (true v_0, speed, direction, gravity, biases (offline LS estimate), relative rotations,
  feature depths, timing, perfect correspondences) — does solving the subproblem actually improve ATE? Privileged info never at
  inference.
- Standalone measurement accuracy before modifying the MSCKF; then compare frozen baseline / baseline+change / standalone / oracle /
  ablations.
- Report: mean, median, worst-episode ATE; per scene and motion regime; early trajectory error at several horizons; initial |v| and
  direction error; gravity error; failure rate; MAX per-frame fuel and its distribution; score estimate (BRIEF §2).
- Native/python prototypes are fine for speed; confirm promising results in the actual WASM build.
- Strict causality, no wasm imports, bounded complexity (iterations, features, hypotheses), no compute spikes (spread work).
- Identical episodes and seeds; absolute and relative changes vs baseline; no cherry-picking; report regressions; separate genuine
  geometric information from dataset-specific learned priors; judge generalization (classes, FoV, exposure, start type).
- Deliverables: the 11 items in BRIEF §7. Recommendation: integrate / refine / abandon, with exact code paths and commands.
