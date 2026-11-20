# Startup package (C1 tilt/velocity widening, C2 priors, C3 fast lock-on) for gp_msckf

Status: FINAL (recommended build = adopted.c / adopted.patch). Sources: `orig.c` (= submitted solution.c, verified identical), `v.c`/`v2.c`/`v3.c`
(orig + #define switches; every arm is a -D flag, defaults reproduce the original). Reports: research/results/single_model/startup_<arm>/report.txt.
Search slice = folds 0-2 (n=119: 56 static, 63 mid); val = fold 3 (n=25). Fold 4 never read.

IMPORTANT reference: `startup_base` (v.c with no flags, rebuilt) scores search 2.215 / val 1.963, not the submitted 2.307 / 2.032
(rebuild/toolchain difference, paired d=-0.09 [-0.30,+0.03]; not significant, but it means arm deltas vs the submitted baseline include ~-0.09 of
free drift; compare arms against startup_base too). Static flights are bit-identical across all arms (motion detector leaves hover starts alone), static
mean 0.678 vs submitted 0.667 (the +0.011 is the same rebuild offset).

## Arms (search slice vs submitted baseline 2.307 / mid 3.764)
| arm | change | search mean | med | mid | >5 / >10 m | paired d [95% CI] | val mean / mid |
|---|---|---|---|---|---|---|---|
| base (rebuild) | none | 2.215 | 0.80 | 3.58 | 17 / 6 | -0.09 [-0.30,+0.03] | 1.96 / 3.22 |
| c1_t10 | moving-start tilt sigma 0.10 | 2.071 | 0.80 | 3.31 | 14 / 5 | -0.24 [-0.65,+0.14] | 1.24 / 1.82 |
| c1_t15v15 | tilt .15, vel sigma 1.5 | 2.152 | 0.89 | 3.46 | 17 / 4 | -0.15 [-0.51,+0.15] | 1.90 / 3.09 |
| c1_t20 | tilt .20 | 1.984 | 0.82 | 3.15 | 15 / 3 | -0.32 [-0.87,+0.13] | 1.31 / 1.96 |
| c1_t20v20 | tilt .20, vel 2.0 | 2.330 | 0.93 | 3.80 | 20 / 5 | +0.02 [-0.46,+0.51] | 1.33 / 2.00 |
| c1_t30 | tilt .30 | 2.217 | 0.93 | 3.59 | 19 / 3 | -0.09 [-0.63,+0.37] | 1.93 / 3.16 |
| c1_v20 | vel sigma 2.0 | 2.325 | 0.90 | 3.79 | 17 / 6 | +0.02 [-0.31,+0.31] | 1.29 / 1.91 |
| c2a_s10 | isotropic velocity-prior sigma 1.0 for 2 s | 1.865 | 0.74 | 2.92 | 13 / 4 | -0.44 [-0.99,+0.01] | 1.01 / 1.38 |
| c2a_s20 | same, sigma 2.0 | 1.846 | 0.74 | 2.89 | 12 / 4 | -0.46 [-0.93,-0.09] | 1.18 / 1.71 |
| c2b_aniso | horizontal 1.0 / vertical 0.3 (world) for 2 s | 1.961 | 0.68 | 3.10 | 13 / 3 | -0.35 [-0.69,-0.04] | 1.74 / 2.79 |
| c2c_head | heading-aware prior (below) | **1.327** | 0.57 | **1.90** | 9 / **0** | **-0.98 [-1.73,-0.41]** | **0.63 / 0.65** |
| c2e_gate | chi2 gate 11.34 on the zero-mean prior | 2.215 | 0.80 | 3.58 | 17 / 6 | = base | = base |
| c3_fast | first 40 frames: clone every 2, min obs 2, tri eig 1e-6 | 2.055 | 0.79 | 3.28 | 14 / 7 | -0.25 [-0.73,+0.15] | 1.28 / 1.90 |
| c3_tri8 | c3 with tri eig 1e-8 | 2.012 | 0.79 | 3.20 | 14 / 6 | -0.29 [-0.80,+0.13] | 1.28 / 1.91 |
| c3_chi25 | c3 + chi2 z 2.5 in the fast window | see report | | | | | val mid 1.82 |

(CIs are vs the submitted baseline; subtract ~0.09 for the like-for-like comparison.)

## Heading prior (PRIOR_MODE=3) as built by the previous agent
When the first IMU window shows motion (|mean gyro| > 0.2 rad/s or |specific force| > 8.8 m/s^2; hover starts untouched), the initial velocity is set to
mean 0.65 m/s along the camera optical axis (z_c) with camera-frame sigmas (x 0.5, y 0.35, z 0.75) and the same distribution is applied as a whitened
pseudo-measurement every frame instead of the zero-mean speed prior for the first START_T=2 s. After 2 s the original zero-mean prior resumes.

## Truth check of the assumption "the drone faces its direction of travel" (heading_stats.py, truth only, search mid n=63)
Start velocity (0-1 s) in the camera frame: mean forward 0.49 m/s of speed 0.98 m/s; std (x 0.54, y 0.34, z 0.81). Angle between camera axis and velocity:
median 66 deg, 19/63 flights above 90 deg (moving backwards). So heading is a weak predictor, not a reliable one. ATE by angle bin (base -> head):
0-30 deg 5.82 -> 2.09 (n=16); 30-60 2.81 -> 1.45 (13); 60-90 1.36 -> 1.25 (15); 90-180 3.97 -> 2.57 (19). By forward speed: < 0 (backward) 5.17 -> 3.21 (n=12);
0-0.3 2.25 -> 1.51; 0.3-0.7 1.69 -> 0.71; 0.7-1.2 2.98 -> 1.72; > 1.2 6.86 -> 2.91. Helps in every bin, including flights flying backwards
(smaller gain), i.e. it is not just exploiting the facing-forward statistic.

## Sensitivity of the heading prior (search slice, mean ATE; all PRIOR_MODE=3, others default: fwd 0.65, sx .5, sy .35, sz .75, T 2 s)
Reference c2c_head 1.327 (>5 m 9, >10 m 0). Run-to-run neighbours differ by +-0.2-0.3 (the system is chaotic on the bad flights), so treat differences below ~0.3 as noise.
| arm | change | search | >5/>10 | paired vs base |
|---|---|---|---|---|
| h_t1 / h_t4 | duration 1 s / 4 s | 1.489 / 1.543 | 11/1, 13/1 | -0.73 / -0.67 (both exclude 0) |
| h_f0 | mean 0 (camera-axis covariance only) | 1.800 | 13/2 | -0.42 [-0.78,-0.10] |
| h_f03 | mean 0.3 | 1.953 | 13/3 | -0.26 (ns) |
| h_f10 | mean 1.0 | 1.302 | 9/2 | -0.91 |
| h_m90 | mean 0.9, sz 0.6 | 1.270 | 7/1 | -0.95 [-1.56,-0.42] |
| h_back | mean -0.65 along the camera axis (deliberately wrong) | 1.742 | 12/3 | -0.47 [-1.09,+0.06] |
| h_lat | mean 0, +0.65 along camera x (wrong) | 1.560 | 8/1 | -0.66 [-1.31,-0.09] |
| h_sx03 / sx08 | lateral-x sigma .3 / .8 | 1.475 / 1.387 | 9/1, 9/3 | -0.74 / -0.83 |
| h_sy02 / sy06 | y sigma .2 / .6 | 1.499 / 1.307 | 12/2, 7/2 | -0.72 / -0.91 |
| h_sz05 / sz10 | forward sigma .5 / 1.0 | 1.442 / 1.631 | 8/1, 12/2 | -0.77 / -0.58 |
| h_tilt15 | default + tilt .15 | 1.479 | 7/2 | -0.74 |
| h_fast | default + C3 fast lock-on | 1.349 | 9/2 | -0.87 |
| h_tilt15_fast | both | 1.532 | 12/3 | -0.68 |
| h_m90_aniso | m90 + C2b anisotropy after 2 s | 1.862 | 13/5 | +0.59 worse than m90 [+0.21,+1.07] |
| **h_m90_t15** | **mean 0.9, sz 0.6, tilt .15** | **1.033** | **4/0** | **-1.27 vs submitted [-2.00,-0.71]; -0.24 vs h_m90 [-0.54,-0.02]** |
| n_t10 / n_t20 | m90_t15 with tilt .10 / .20 | 1.261 / 1.366 | 4/1, 7/2 | worse than m90_t15 |
| n_f10 / n_f08 | m90_t15 with mean 1.0 / 0.8 | 1.212 / 1.271 | 6/0, 10/0 | worse |
| n_fast | m90_t15 + C3 | 1.381 | 11/3 | worse (C3 rejected) |
| n_t4 | m90_t15, 4 s | 1.168 | 7/0 | worse |

Findings. (1) Every parameterisation of the prior beats base (1.27-1.95 vs 2.215), including deliberately wrong ones (backward 1.74, lateral 1.56, zero mean 1.80),
so most of the gain is NOT the heading assumption: it is replacing the tight zero-mean velocity pseudo-measurement by a prior whose mean is non-zero and whose
scale matches the true start speed (~1 m/s, the filter used to start at 0.02 m/s). The gain grows with the mean (0 -> 1.80, 0.65 -> 1.33, 0.9-1.0 -> 1.27-1.30) and
with a correct direction (forward 1.27 vs backward 1.74 vs lateral 1.56 at similar sigma), so the heading information adds roughly 0.3-0.5 m on top. (2) Truth check: only half of the
start speed is along the camera axis and 30 % of mid flights move backwards (>90 deg off axis); even there ATE improves (5.17 -> 3.21 for backward-moving starts).
(3) Mechanism: removes the biggest shared error (initial velocity = true speed, 51 % of the 2 s error), which in turn stops the tilt/velocity runaway and the lock-out (flights >10 m: 6 -> 0-1).
(4) Static starts: untouched by construction (motion detector), static mean 0.678 identical to base in every arm, no new >10 m flights (best arm 0).
(5) Risk, stated honestly: the 0.9 m/s forward mean and the sigmas are tuned on this simulator's start-speed distribution (mean 0.98 m/s on mid starts; server flights are
longer/faster, ~60 m vs ~17 m path, so real start speeds may be higher, and a vehicle starting mid-air at a different speed or with a lateral velocity gets a mean that is off by ~1 m/s, which the
sigmas (0.5/0.35/0.6 m/s) do not cover: the lateral/backward tests show this costs ~0.5 m of the gain but does not make things worse than base). The tilt widening (.15) on top of the heading prior is
NOT robust: neighbours (.10, .20, and fwd .8/1.0) are no better than h_m90 (1.27), so m90_t15 at 1.03 is partly a favourable draw; expect ~1.2-1.3 on fresh flights. Of the other arms:
C2b anisotropy and C3 fast lock-on hurt on top of the heading prior (rejected), C2a/C1 widening are subsumed (rejected), C2e gate is inert.

## Val (fold 3, n=25; finalists only: c2c_head, h_m90, h_m90_t15)
c2c_head 0.631 (mid 0.654); h_m90 0.528 (mid 0.455); h_m90_t15 0.524 (mid 0.447); base 1.963 / 3.215 (submitted 2.032 / 3.250). Val is consistent with search, no contradiction.

## Recommended build
`adopted.c` (= v3.c with defaults PRIOR_MODE=3, START_MEAN_FWD=0.9, START_STD_Z=0.6, MOVE_TILT_STD=0.15; all else off) and `adopted.patch` (unified diff vs orig.c = submitted solution.c).
Built and re-evaluated as `startup_adopted`: search 1.033 (median 0.54, >5 m 4, >10 m 0), mid 1.348, static 0.678, paired vs submitted -1.274 [-2.00,-0.71]; val 0.524.
For combining with other patches the minimal pieces are: motion detector + `moving` flag in init, the camera-axis Gaussian initial velocity, and the PRIOR_MODE==3 branch of the velocity prior update (v.c diff vs orig.c shows exactly these; the C3/C2a/C2b switches in adopted.c are inactive and can be deleted).
Helper scripts: compare.py, pair.py (paired bootstrap between arms), heading_stats.py, runq.sh/launch.sh (arm queues).
