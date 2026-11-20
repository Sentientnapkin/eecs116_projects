# L0 oracle ceiling (IN PROGRESS; ORACLE USES TRUTH, NOT DEPLOYABLE)
Status: reconstructed from crashed run; diagnostic arms (make_arms2.py, run_diag.sh) running. Results in research/results/single_model/oracle_<arm>/report.txt.

## Mechanism (verified from make_arms.py)
- oracle_table.h: per-episode truth (body-frame velocity vb, up vector) keyed by intrinsics (171 unique fx).
- Velocity injection: vel = R_init * vb (+ noise), filter velocity std set to the arm sigma. Tilt arms: R from true up (+noise).
- Noisy arms (vn_s): noise = s * N(0,1) PER AXIS in the filter world frame, deterministic LCG seeded from fx (independent of truth, same draw for every s so noise = s * fixed draw), mean |noise| = 1.67 s (s=1: 1.67 m/s). The filter sigma is set equal to s (consistent). vn arms do not inject tilt (tilt std 0.05, as baseline). Nothing else is injected.
- Baseline in solution.c: INIT_VELOCITY_STD = 1.0 (NOT 0.02), vel = 0; true speed on mid starts ~0.97 m/s (static ~0.06). So vx_1.0 and the baseline have identical covariance; vn_1.0 has a LARGER velocity error (1.67 vs ~0.5 mean over all flights) yet beats the baseline.

## Interim facts (checked)
- Control zero_1.0 (inject v=0, sigma 1.0) reproduces the baseline EXACTLY (search 2.307 / mid 3.764, val 2.032): the injection harness changes nothing else.
- vn noise is independent of truth (corr of vn_1.0 ATE with noise magnitude 0.06, with noise component along travel 0.13 on the 76 visible mid flights), per-axis sigma s, total |noise| mean 1.67 s, seeded per flight by fx, filter sigma = s (consistent). Tilt not injected.
- Mid-flight (visible, n=76) truth speed mean 0.94 m/s; baseline velocity error = speed.
- Per-arm mid results are noisy (n=63, 6 flights >5 m carry ~40 % of the sum): differences below ~0.3 m between arms are within chaos (vx_0.01 1.97 vs vx_0.3 1.22 vs vx_1.0 2.22 is not monotone).

## Results table (search slice folds 0-2 n=119: all mean; static n=56 mean/median; mid n=63 mean/median; val fold 3 n=25 all; val mid n=13)
Baseline: all 2.307, static 0.667/0.50, mid 3.764/1.85, val 2.032, val mid 3.250.
| arm | search all mean | static mean/med | mid mean/med | val all | val mid |
|---|---|---|---|---|---|
| bx_0.1 | 0.840 | 0.703/0.44 | 0.962/0.51 | 0.472 | 0.379 |
| bx_0.3 | 0.829 | 0.692/0.43 | 0.951/0.51 | 0.456 | 0.392 |
| bx_0.6 | 0.895 | 0.750/0.43 | 1.024/0.48 | 0.462 | 0.434 |
| bx_1.0 | 1.116 | 0.833/0.42 | 1.368/0.53 | 0.518 | 0.457 |
| dir_0.3 | 1.065 | 0.618/0.41 | 1.463/0.63 | 0.675 | 0.771 |
| fwd_0.3 | 1.520 | 0.904/0.44 | 2.068/0.79 | 0.855 | 0.861 |
| fwdall_0.3 | 1.523 | 0.940/0.61 | 2.041/0.79 | 0.896 | 0.875 |
| half_0.3 | 1.448 | 0.811/0.48 | 2.015/0.91 | 0.569 | 0.617 |
| mag_0.3 | 1.600 | 0.639/0.43 | 2.454/0.92 | 1.352 | 2.085 |
| mag_1.0 | 1.635 | 0.677/0.40 | 2.486/0.91 | 1.113 | 1.678 |
| neg_1.0 | 1.608 | 0.820/0.43 | 2.309/1.05 | 1.071 | 1.495 |
| tn_0.02 | 1.644 | 0.767/0.48 | 2.424/1.28 | 0.825 | 1.021 |
| tn_0.05 | 1.502 | 0.801/0.51 | 2.124/1.19 | 0.929 | 1.209 |
| tn_0.1 | 1.652 | 0.912/0.47 | 2.310/1.19 | 0.940 | 1.085 |
| tx_0.02 | 1.592 | 0.643/0.42 | 2.435/1.42 | 0.835 | 1.082 |
| tx_0.05 | 1.756 | 0.655/0.49 | 2.734/1.44 | 1.011 | 1.407 |
| tx_0.1 | 1.750 | 0.651/0.43 | 2.726/1.51 | 1.436 | 2.120 |
| vn_0.1 | 1.366 | 0.829/0.52 | 1.844/0.61 | 0.640 | 0.618 |
| vn_0.3 | 1.314 | 0.871/0.52 | 1.708/0.64 | 0.788 | 0.862 |
| vn_0.6 | 1.320 | 0.805/0.49 | 1.778/0.88 | 0.829 | 0.963 |
| vn_1.0 | 1.334 | 0.796/0.49 | 1.813/0.88 | 1.003 | 1.269 |
| vn_1.0_s2 | 1.178 | 0.730/0.52 | 1.576/0.75 | 1.014 | 1.295 |
| vn_1.0_s3 | 1.319 | 0.697/0.49 | 1.873/0.83 | 0.643 | 0.641 |
| vx_0.01 | 1.356 | 0.670/0.45 | 1.965/0.57 | 0.792 | 0.684 |
| vx_0.1 | 1.059 | 0.630/0.43 | 1.441/0.66 | 0.670 | 0.419 |
| vx_0.3 | 0.939 | 0.618/0.41 | 1.224/0.62 | 0.622 | 0.670 |
| vx_0.6 | 1.105 | 0.658/0.43 | 1.503/0.64 | 0.809 | 0.718 |
| vx_1.0 | 1.490 | 0.671/0.41 | 2.218/0.64 | 0.775 | 0.941 |
| vx_3.0 | 2.250 | 0.581/0.47 | 3.733/1.95 | 1.280 | 1.973 |
| zero_0.1 | 2.078 | 0.672/0.44 | 3.327/1.45 | 1.512 | 2.318 |
| zero_0.3 | 1.890 | 0.904/0.44 | 2.768/1.10 | 1.065 | 1.265 |
| zero_1.0 | 2.307 | 0.667/0.50 | 3.764/1.85 | 2.032 | 3.250 |
| zero_3.0 | 2.206 | 0.578/0.47 | 3.653/2.19 | 1.193 | 1.720 |

Arm key: vx_s exact truth velocity, filter sigma s; vn_s truth + N(0,s) per axis (s=1.0 seeds: default 1.81, s2 1.58, s3 1.87 mid); tx/tn_s exact/noisy tilt (sigma s rad); bx_s exact velocity AND tilt (tilt sigma 0.02); zero_s v=0 with sigma s (zero_1.0 = baseline control); mag_s truth speed, random direction; dir_s truth direction, speed 0.97 (truth-gated); fwd_s 0.97 m/s along body +x if truth moving else 0 (fwdall: all flights); half_s 0.5*truth; neg_s -truth. All velocity arms: tilt std 0.05, no tilt injection.

## Answers
(1) Noisy arms verified: noise is real (per-axis N(0,s), |noise| 1.67 s, independent of truth, fixed per flight, filter sigma = s, nothing else injected, control reproduces baseline exactly). The baseline velocity error is ~0.94 m/s (zero start, sigma 1.0); vn_1.0 has error 1.67 m/s yet gets mid 1.58-1.87 over 3 seeds vs 3.76. So the gain is NOT initial-velocity accuracy. Separating arms (mid mean, search):
 - v=0 with sigma 3.0: 3.65 (= baseline); exact truth with sigma 3.0: 3.73 (= baseline). A loose velocity covariance throws away the whole benefit even with a perfect velocity.
 - v=0 with TIGHT sigma 0.3: 2.77 (sigma 0.1: 3.33); i.e. a knowledge-free, 1 m/s-wrong prior, only tightened, recovers ~1.0 m of the 2.5 m gap. Covariance consistency/tightness of the velocity block (and the state prior it constrains) is a major part of the effect.
 - exact truth at sigma 1.0: 2.22, 0.3: 1.22, 0.1: 1.44, 0.01: 1.97 (U shape; 0.3 best; mid n=63 noise is ~0.3).
 - non-zero but WRONG velocity at sigma 1.0 also beats zero: -truth (error 1.9 m/s) 2.31, truth speed with random direction 2.49, noisy 1.6-1.9. So some of the gain is simply "v0 != 0 / nonzero magnitude along some direction with a consistent sigma"; exact direction is worth more: right direction with wrong magnitude (0.97 const) at sigma 0.3 gives 1.46 (near the exact 1.22), random direction with right magnitude at sigma 0.3 (overconfident) 2.45. Constant body-forward 0.97 m/s at sigma 0.3: 2.07 (gated 2.07/ungated 2.04, static gets worse: 0.90-0.94 vs 0.67).
 - Interpretation: direction matters more than magnitude; sigma must be ~0.3 (not 1 and not 3); a heuristic cannot exceed ~2.0 mid without direction.
(2) Needed accuracy: velocity sigma ~0.3 m/s, claimed AND true (vx_0.3 mid 1.22 / all 0.94; sigma 0.6 mid 1.50). Direction error must be small (dir-only ok: 1.46); magnitude error of ~0.5 m/s tolerable (half_0.3 mid 2.02, all 1.45, vs dir 1.46). Learned net target: heading within ~30 deg, speed within ~0.3 m/s, calibrated sigma ~0.3. Gain of wrong-direction priors is mostly the covariance effect (above), ~1.0 m.
(3) Remainder with perfect v and tilt (bx_0.3): search all 0.829 (static 0.692, mid 0.951), val 0.456 (mid 0.39). Visible 144 flights: mid mean 0.86, 4 flights > 3 m (2.3-9.0 m), mean 0.58 without them; static mean 0.66 incl. one 9.8 m and one 3.0 m flight (0.49 without). So with a perfect start about 0.5-0.6 m is the floor from tracking/consistency, plus 2-3 outlier flights (lock-on/tracking failures, not initial state; the static-flight 9.8 m outlier is not startup at all). Exact tilt alone: mid 2.43; exact velocity alone: mid 1.22; both 0.95 (interaction: tilt helps mainly once v is right). Noisy tilt 0.02-0.1 rad mid 2.1-2.4 ~ exact tilt (tilt need not be accurate below ~0.1 rad).
Ceiling vs classical startup (search all 1.33): oracle v only 0.94 (sigma 0.3), v+tilt 0.83; baseline 2.31. Startup prior captures (2.31-1.33)/(2.31-0.94)=72 % of the velocity-oracle gain, 66 % of the v+tilt gain; remaining headroom 0.4-0.5 m search mean, mostly mid. Noisy-v arms with a consistent sigma (1.3-1.4) already match it, which says the classical prior's gain is largely the covariance effect, so a learned velocity net can add at most ~0.4 m and only if it gives calibrated direction and sigma<=0.3.

## Reproduce
python make_arms.py (vx/vn/tx/tn/bx arms), python make_arms2.py (zero/mag/dir/fwd/fwdall/half/neg/vn seeds; also zero_0.3/0.1 via make('zero',s)), then run_diag.sh <arm...> or run_variant --name oracle_<arm> --src research/single_model/oracle/arms/<arm>.c --workers 24. summarize.py prints the table. Per-flight: results/single_model/oracle_<arm>/report.json rows_visible. Oracle only; do not use in submissions.
