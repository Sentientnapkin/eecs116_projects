# OpenVINS / MSCKF estimator tricks for gp_msckf: catalogue and measured effect

All numbers: mean unaligned ATE (m). Base = B6 (research/single_model/frontend/adopted_fbh.c) unless "old base" (G+C1, inventive/adopted.c) is named. Fresh = 711 flights (primary arbiter), search = folds 0-2 (n=119, 3 chaos replicates vs B6 replicates 0.950/0.943/0.900), val = fold 3 (n=25). Fold 4, private episodes and the holdout set were not touched. Code: research/single_model/openvins_tricks/ (oy.c = switchable blocks on adopted.c, ob.c = same blocks on B6, ob_arms.patch = diff vs B6, NOTES.md, logs log_*). Results: research/results/single_model/oy_*, ob_*, fresh_ob_*.

## 1. What OpenVINS does that a basic MSCKF does not (from the pinned OpenVINS 2.7 source in viobench-provided-openvins/host-build and its example config)

### Takeaway
Most OpenVINS "tricks" are consistency devices (FEJ, anchored inverse-depth, SLAM landmarks) or front-end/initialisation machinery. The ones that are cheap and structural for our plain-C filter are FEJ/observability constraint, baseline-ratio feature gate, mid-point integration, and chi2/noise settings.

### Cited findings (source = OpenVINS code or docs read locally/online)
- FEJ: Jacobians (propagation F and measurement H) are evaluated at first estimates; IMU first estimate = predicted state x_{k|k-1}, set in Propagator.cpp ("replace imu estimate and fej with propagated values"); clone FEJ = IMU FEJ at cloning; for MSCKF features p_FinG_fej is simply the current triangulation (UpdaterMSCKF.cpp: `feat.p_FinG_fej = (*it2)->p_FinG`); H uses clone Rot_fej/pos_fej (UpdaterHelper.cpp). Docs: https://docs.openvins.com/fej.html (says FEJ keeps the 4-dof unobservable subspace from gaining spurious information, at the cost of linearisation error; cites FEJ2/OC as alternatives).
- Feature gating (FeatureInitializerOptions.h): min_dist 0.10 m, max_dist 60 m, max_baseline ratio 40 (feature distance / max perpendicular baseline), max_cond_number 1e4 on the 3x3 ray matrix, LM refinement max 5 runs, lambda 1e-3. Ours: depth 0.2-40 m, eigenvalue ratio 1e-6 (cond 1e6), no baseline-ratio gate.
- MSCKF gate: chi2 of the null-space projected residual, per-dof 95% table (`chi_squared_table[rows]`) times chi2_multiplier (1.0 in the provided example), noise sigma_pix (provided example 0.5 px; EuRoC 1.0; ours 1.5 px). Measurement compression and isotropic R after compression, as ours.
- Provided example (examples/native/openvins/solution.cpp make_options): max_clone_size 11 (clone every frame), do_fej true, RK4 integration, 50 SLAM landmarks, ZUPT by disparity only (zupt chi2 multiplier 0, zupt_only_at_beginning), static init window 0.8 s with disparity < 1.5 px, dynamic init (Ceres MLE, 6 poses, min 5 deg).
- ZUPT in OpenVINS (https://docs.openvins.com/update-zerovelocity.html): synthetic a=0, w=0 measurement with chi2 test (noise inflated 50-100x in real data) plus a disparity test; our vision ZUPT (median de-rotated disparity < 0.4 px) is the disparity variant.
- Time offset: OpenVINS can calibrate camera-IMU dt online. Here the ABI states frame timestamps are mid-exposure and IMU rows are exact (docs/ABI.md); no offset exists to calibrate, not tested empirically (labelled: unverified beyond the spec).

### Inferences
- Our regime (1.2 s window, ~1 m/s, 2 m depths, large startup corrections) differs from EuRoC; transfer of FEJ is not guaranteed.

## 2. Measured effect (the earlier-attempt bug hunt and the arms)

### Takeaway
No OpenVINS trick improved B6 under the adoption rule (fresh mean improvement >= 0.03 with CI excluding zero). FEJ cannot be adopted: the position part of FEJ is destructive. The earlier FEJ attempt had no Jacobian bug; the degradation is real.

### Findings (measured)
- Jacobian correctness: with OX_DIAG the relative size of H n for the yaw null vector built from the current poses is 1e-16 on every sampled flight, i.e. the analytic clone Jacobians (after left-null-space projection) are exactly consistent; built from the first-estimate (cloning-time) poses it is 3e-4..5e-3. The earlier texture.c FEJ arm computed the residual at the current estimate (correct) and the Jacobian at the first estimate; I found no bug.
- Chaos floor: OX_OC=2 (project with the current-pose null vector, a mathematical no-op at 1e-16) moved search mean 0.845 -> 0.909 on the fgt base and individual flights by up to +3.9 m (178-01 0.70 -> 4.60); only 27/119 flights stayed within 0.02 m. Roundoff-level perturbations flip discrete gates/KLT decisions; single-run differences below ~0.2 (search) are not evidence.
- Old base (G+C1, search 3 replicates, ref 1.079): FEJ H+F (pre-update first estimate) +1.54 [+0.93,+2.30], val +0.68; same delayed to t>3 s +0.65; FEJ in F only +0.04 [-0.07,+0.17] (neutral); OC with first-estimate null vector +0.08 [-0.05,+0.20], val +0.07 [+0.02,+0.11]; OC+FEJ-F +0.13.
- B6 (fresh n=711, ref 0.618; search 3-rep ref 0.931):
| arm | fresh mean (d [95% CI]) | fresh >5 / >10 m | search 3-rep d [CI] | val | verdict |
|---|---|---|---|---|---|
| ctrl (port, no switch) | 0.618 (0) | 8 / 0 | 0 | 0.441 | reproduces B6 exactly |
| OC (yaw null vector at first-estimate poses, OX_OC=1) | 0.703 (+0.085 [+0.043,+0.126]) | 12 / 1 | +0.152 [+0.037,+0.299] | 0.461 | reject |
| FEJ attitude only (R first estimate, position current) | 0.644 (+0.026 [-0.010,+0.056]) | 9 / 1 | +0.079 [-0.036,+0.190] | 0.575 | reject (neutral/worse) |
| FEJ position only (p first estimate, R current) | 1.858 (+1.24 [+1.03,+1.50]) | 69 / 26 | +1.26 [+0.86,+1.70] | 1.103 | reject, destructive |
| FEJ H+F (full, OpenVINS-style) | 1.862 (+1.244 [+1.03,+1.48]) | 70 / 31 | +1.41 [+0.94,+1.95] | 0.970 | reject, destructive |
| baseline-ratio gate 40 (OX_BLR=40, OpenVINS fi_max_baseline) | 0.655 (+0.036 [+0.008,+0.062]) | 5 / 0 | +0.033 [-0.06,+0.16] | 0.454 | reject (fewer >5 m flights 8 -> 5, peak fuel 24.5 -> 22.4 M; mean worse) |
| mid-point attitude for acceleration (OX_MID=1) | 0.644 (+0.026 [-0.010,+0.066]) | 6 / 2 | +0.049 [-0.04,+0.14] | 0.418 (-0.023 [-0.039,-0.007]) | reject |
- Old-base search arms (3 replicates, ref 1.079): OX_BLR=40 -0.032 [-0.17,+0.09] (mid -0.09, >3 m flights 13->10); OX_BLR=20 +0.069 (val +0.20); TRI_MIN_EIG 1e-4 (OpenVINS cond 1e4) +0.008; CHI2_Z 2.0 +0.178 [+0.012,+0.403]; separate update noise 1.0 px (gate 1.5) +0.091; MAX_CLONES 8 +0.011 (static -0.07 [-0.18,+0.02]).
- Mechanism of the FEJ failure: attitude-only FEJ is harmless, position FEJ is catastrophic. In H, the feature in the clone frame is u = R^T(p_f - p_c). p_f is triangulated from the current clone positions, but p_c is replaced by the first-estimate position; velocity/position corrections inside the 1.2 s window (tens of cm, larger at startup) shift u by a sizable fraction of the 1-3 m feature depth, so the Jacobian and the null-space projection of H_f no longer match the residual. OpenVINS avoids this because its first estimates and its landmark are consistently chained over longer, better-conditioned trajectories; re-triangulating the feature at the first-estimate poses (texture fej2, +2.55 on the old baseline) did not fix it either.
- OC variant: projecting H off the yaw null vector built at first-estimate poses changes H by only 0.03-0.5%, yet the result is consistently worse in search (+0.08..+0.15) and fresh (+0.085). Our F is not made Phi-consistent (no OC-modified F), so the constraint is applied against a covariance that does not carry the matching null space; no benefit, small real cost.

### Inferences
- Position NEES excess (4x static, 14x mid) is not a yaw/position spurious-information problem fixable by FEJ/OC in this window length; the NEES excess is startup transients (earlier NOTES) and parameter-like.
- Baseline-ratio gating removes some bad late flights (>5 m: 8 -> 5 on fresh, fewer tails) but raises the mean slightly; it could be an option if tails rather than mean matter (not adopted: rule requires mean improvement).

### Gaps
- Not tested: OC with a Phi-modified propagation (Hesch OC-MSCKF); per-feature noise by depth; ZUPT chi2 variant; online time-offset (none exists per ABI); fast starts >1.8 m/s, flat/dark and reverse-start mechanisms (left to the other agents' analyses); Joseph form/symmetrisation (OX_SYM switch exists, not run: P update is written symmetrically already).
- Parameter-like hints for the autoloop (old base, search only, not significant): none beat the base; CHI2_Z above 1.645 and larger update noise hurt.

## 3. Adopted patch
None. ob_arms.patch (research/single_model/openvins_tricks/ob_arms.patch) contains the switchable blocks (all default off, bit-identical to B6) for reproducing the arms.
