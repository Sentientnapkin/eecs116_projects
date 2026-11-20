# Health checks (C5) and flight-envelope priors (C6)  -- FINAL

Source: `health2.c` = original `solution_orig.c` plus switchable blocks (all default 0 = original behaviour; HC_LOG only prints to stderr). `diff solution_orig.c health2.c` shows exactly the change. `health.c` is the earlier version (no HC_REC, no PRI_*). Arms run by `run.sh`/`run2.sh` via `batch1/2/3.sh` (results `arm_<name>.txt`, full reports in `research/results/single_model/health_<name>/`).
Slices: search = folds 0-2 (n=119: 63 mid, 56 static), val = fold 3 (n=25).

## C6 envelope (truth, SEARCH slice, 119 flights; finite-difference velocity smoothed 0.2 s; z relative to start)
Percentiles 50/90/95/99/99.9/max, all flights:

| quantity | p50 | p90 | p95 | p99 | p99.9 | max |
|---|---|---|---|---|---|---|
| speed (m/s) | 0.81 | 1.88 | 2.22 | 2.77 | 3.28 | 4.13 |
| abs vertical vel (m/s) | 0.12 | 0.51 | 0.67 | 1.01 | 1.40 | 1.97 |
| horizontal speed | 0.74 | 1.85 | 2.18 | 2.74 | 3.25 | 4.12 |
| tilt (deg) | 4.7 | 13.4 | 16.3 | 21.2 | 27.0 | 34.6 |
| abs z - z0 (m) | 0.38 | 1.12 | 1.43 | 2.03 | 2.58 | 2.91 |
| abs body lateral vel vb_y | 0.13 | 0.83 | 1.27 | 2.00 | 2.70 | 3.45 |
| abs body forward vel vb_x | 0.57 | 1.63 | 2.01 | 2.66 | 3.20 | 4.12 |

RMS: vz 0.30, horizontal speed 1.10, vb_y 0.52, vb_x 0.96 m/s; per-flight std of z 0.39 (p50) / 0.74 (p90) / 0.94 (max); per-flight max |z-z0| p50 1.08, p90 1.89, max 2.91; per-flight max speed p50 2.84, max 4.13; mean speed 0.93; mean path 56 m (server ~60 m). Static and mid starts have the same envelope (differences < 0.1). Body slip angle when moving (>0.3 m/s): median 12 deg, p75 47 deg (the plan's 24-flight sample said median 6, p75 15, p90 33; here lateral is far less negligible, rms vb_y/vb_x = 0.54).

Differences from the plan's 24-flight numbers: the plan used speed limit 3.5, vertical speed 1.5, tilt 40 deg, height std 0.52 (hard limits). On 119 flights speed exceeds 3.5 m/s in max-case 4.1 (p99.9 3.3), |vz| exceeds 1.5 in about 0.05% of samples (max 1.97), tilt max is 34.6 (40 never exceeded), height std per flight p50 0.39 but p90 0.74, max 0.94 and max |z-z0| 2.9, i.e. a 0.52 std is the median not a bound. The vertical-position prior sigma 0.8 therefore is tight for the top decile. Hard limits at 3.5/1.5 clip real motion in a few percent of flights, which is why they regressed (see arms table).
Scripts: `envelope.py` (builds `envelope.pkl`), `/data/.../tmp/env_stats.py` output reproduced above; `est_envelope.py <run>` compares estimated vs true envelope; `trips.py <run>` counts trip logs per flight.

## Arms (search mean 2.307 / mid 3.764 / static 0.667 / val 2.032 / val mid 3.250 for baseline)
See table below (filled from reports). Verdict column applies the adoption rule.

Baseline (submitted): search 2.307 (static 0.667, mid 3.764), val 2.032. Arms `v3head*` are on top of the heading-aware startup prior (`../startup/v3.c`, PRIOR_MODE=3; reference `v3head` = 1.327 search, reproduces startup_c2c_head). Their source is `hv3.c` (health blocks merged into startup v3.c; `hc_frame` / `cur_z` renamed to avoid clashes). Delta CIs are vs the submitted baseline. Selection used search only; val columns were printed by the shared tool for every arm and not used to choose.

| arm | search mean | median | d [95% CI] | mid | static (d) | >5 / >10 m | val mean | val mid |
|---|---|---|---|---|---|---|---|---|
| c1 | 1.682 | 0.82 | -0.624 [-1.206,-0.170] | 2.578 | 0.674 (+0.008) | 13 / 0 | 1.087 | 1.549 |
| c2 | 1.672 | 0.80 | -0.635 [-1.187,-0.172] | 2.564 | 0.667 (+0.001) | 10 / 1 | 1.010 | 1.382 |
| c3 | 1.728 | 0.82 | -0.578 [-1.138,-0.140] | 2.621 | 0.724 (+0.057) | 9 / 0 | 1.343 | 2.013 |
| c4 | 1.726 | 0.85 | -0.581 [-1.075,-0.134] | 2.741 | 0.584 (-0.083) | 10 / 2 | 1.099 | 1.600 |
| lim1 | 5.265 | 0.83 | +2.959 [+1.492,+4.725] | 9.352 | 0.668 (+0.002) | 23 / 16 | 5.020 | 9.006 |
| lim1reset | 2.349 | 0.84 | +0.042 [-0.453,+0.543] | 3.816 | 0.698 (+0.031) | 17 / 6 | 1.825 | 2.840 |
| lim2tight | 5.131 | 0.80 | +2.825 [+1.673,+4.283] | 9.087 | 0.681 (+0.014) | 26 / 21 | 2.911 | 4.670 |
| nis309 | 2.217 | 0.83 | -0.089 [-0.307,+0.009] | 3.596 | 0.667 (+0.000) | 17 / 5 | 1.572 | 2.365 |
| plat035 | 1.863 | 0.81 | -0.444 [-0.921,-0.020] | 2.911 | 0.684 (+0.017) | 15 / 2 | 1.115 | 1.537 |
| plat05 | 1.842 | 0.69 | -0.464 [-0.936,-0.067] | 2.958 | 0.587 (-0.080) | 11 / 4 | 1.156 | 1.689 |
| plat07 | 1.789 | 0.75 | -0.517 [-0.923,-0.208] | 2.847 | 0.599 (-0.068) | 11 / 4 | 1.739 | 2.783 |
| pvh08 | 2.568 | 0.71 | +0.261 [-0.120,+0.610] | 4.279 | 0.643 (-0.024) | 21 / 10 | 1.212 | 1.718 |
| pvz03 | 1.988 | 0.85 | -0.319 [-0.758,+0.077] | 3.248 | 0.570 (-0.097) | 17 / 2 | 1.181 | 1.709 |
| pz08 | 2.165 | 0.81 | -0.142 [-0.487,+0.225] | 3.486 | 0.678 (+0.012) | 17 / 5 | 1.089 | 1.540 |
| recspd22 | 1.803 | 0.88 | -0.503 [-1.113,-0.015] | 2.598 | 0.910 (+0.243) | 12 / 2 | 1.088 | 1.394 |
| rectri04 | 1.766 | 0.88 | -0.540 [-1.085,-0.115] | 2.682 | 0.736 (+0.070) | 11 / 2 | 1.583 | 2.383 |
| recused7 | 1.924 | 1.08 | -0.383 [-0.935,+0.095] | 2.780 | 0.961 (+0.294) | 11 / 1 | 1.800 | 2.503 |
| recv035 | 1.888 | 0.83 | -0.418 [-0.941,+0.008] | 2.885 | 0.767 (+0.101) | 16 / 3 | 1.433 | 2.125 |
| recv035z3 | 1.791 | 0.83 | -0.516 [-1.051,-0.091] | 2.682 | 0.789 (+0.122) | 16 / 1 | 1.298 | 1.864 |
| starve | 2.037 | 0.82 | -0.270 [-0.568,-0.033] | 3.250 | 0.672 (+0.005) | 15 / 4 | 1.219 | 1.697 |
| v3head | 1.327 | 0.57 | -0.980 [-1.732,-0.412] | 1.904 | 0.678 (+0.011) | 9 / 0 | 0.631 | 0.654 |
| v3head_c2 | 1.294 | 0.55 | -1.013 [-1.749,-0.393] | 1.851 | 0.667 (+0.001) | 8 / 1 | 0.674 | 0.736 |
| v3head_nis309 | 1.340 | 0.56 | -0.967 [-1.715,-0.389] | 1.928 | 0.678 (+0.011) | 9 / 0 | 0.631 | 0.654 |
| v3head_plat05 | 1.318 | 0.55 | -0.988 [-1.676,-0.451] | 1.986 | 0.568 (-0.099) | 12 / 2 | 0.682 | 0.742 |
| v3head_pvz03 | 1.393 | 0.61 | -0.914 [-1.644,-0.316] | 2.124 | 0.570 (-0.097) | 7 / 1 | 0.656 | 0.699 |
| v3head_rectri04 | 1.392 | 0.58 | -0.914 [-1.643,-0.361] | 1.960 | 0.754 (+0.087) | 9 / 1 | 0.602 | 0.602 |
| v3head_recv035z3 | 1.389 | 0.57 | -0.917 [-1.663,-0.320] | 1.906 | 0.809 (+0.142) | 8 / 1 | 0.794 | 0.906 |
| v3head_starve | 1.384 | 0.59 | -0.923 [-1.634,-0.374] | 2.011 | 0.677 (+0.011) | 9 / 1 | 0.631 | 0.656 |

Arm definitions (defines on health2.c): lim1 HC_LIM=1 (hard pseudo-measurement limits speed 3.5, |vz| 1.5, tilt 40); lim1reset +HC_RESET=1; lim2tight limits 3.0/1.2; nis309 HC_NIS_Z=3.09 (gate stacked update); starve HC_STARVE=1 (no accepted vision update for 1.5 s -> velocity prior std x0.6); pz08 PRI_Z_STD=0.8 (height vs start); pvz03 PRI_VZ_STD=0.3; pvh08 PRI_VH_STD=0.8; plat035/05/07 PRI_LAT_STD (body lateral velocity ~ N(0,s^2), tau 2 s: soft non-holonomic); recv035 HC_REC=1 HC_REC_VSTD=0.35 (trigger sqrt(trace Pv)>0.35 after 3 s; response soft reset: inflate v by 1 m/s and roll/pitch by 0.1 rad, relax per-feature gate for 2 s); recv035z3 same with relaxed z=3.0; recspd22 trigger |v|>2.2 m/s before 10 s; rectri04 trigger triangulation-failure rate >0.4 per second; recused7 trigger <7 features used per second; c1 = plat05+pvz03+starve; c2 = c1+pz08; c3 = c1 with starve scale 0.4; c4 = plat05+pvz03+pz08 (no starve); a0_log = logging only (identical to baseline).

## Findings
1. Hard plausibility limits fail (lim1, lim2tight: +2.9 / +2.8 m, 16-21 flights >10 m). The envelope above explains it: real flights reach 4.1 m/s and |vz| 2.0, so 3.5 / 1.5 clip real motion in 18/25 search flights (vmax/vzmax fire on 18 and 25 flights, 3781/2837 frame trips) and the pseudo-measurement fights vision. The soft reset on the same trips (lim1reset) is neutral (+0.04). Tilt limit never fires (max tilt 34.6 deg, 40 limit).
2. NIS gate on the stacked update (z 3.09): fires on 6 flights (7 times), -0.09 ns. NIS monitor log (z 3.09) alone: 5-6 flights; harmless but weak. Keep as log.
3. Starvation mode: fires on 47/119 flights (16 static, 31 mid; includes 16 of the 17 baseline >5 m flights; 118 entries, 5107 starved frames). -0.27 [-0.57,-0.03], static unchanged. Strongest of the single health checks and the only trigger that is specific to the failures.
4. Recovery (soft reset + relaxed gate) triggers: help mid starts (-0.9..-1.1 mid) and cut >10 m flights to 1-3, but cost static (+0.07 to +0.29; reset fires on 46-69 flights incl. 12-25 static ones) so they violate the static rule (+0.05). Best trade rectri04 (static +0.07, ci [-0.02,+0.18]) still misses; recspd22 and recused7 worse.
5. Envelope priors: lateral velocity prior (plat05/plat07) is the best single prior: -0.46/-0.52 sig, static -0.08/-0.07 sig better; vertical velocity 0.3 -0.32 ns (static -0.10); height prior 0.8 -0.14 ns; horizontal velocity 0.8 worse (+0.26). Combined c2 (plat05+pvz03+starve+pz08): search 1.672 [-0.64: -1.19,-0.17], mid 2.564, static 0.667, >10 m 1 (baseline 6), val 1.010 (mid 1.38).
6. On top of the heading-aware startup arm (v3head 1.327): none of the checks adds a significant gain. v3head_c2 1.294 (d vs v3head about -0.03, ns; mid 1.85; >5/>10 m 8/1), v3head_plat05 1.318 (static -0.10 but 2 flights >10 m), pvz03 1.393, starve 1.384, rectri04 1.392 (static +0.09), recv035z3 1.389 (static +0.14), nis309 1.340. The startup prior already removes most runaways, so recovery has little left to fix, and the checks overlap with it. Overlap is the main finding: C5/C6 gains (-0.64 alone) are mostly the same gains as the startup prior (-0.98).

## Recommendation
- If the heading-aware startup arm is adopted: take it alone; optionally add the c2 block (`adopted_v3head_c2.c`, `adopted_on_startup_v3.patch`) for a -0.03 (not significant) search gain and one fewer >5 m flight; its static is unchanged, so it does no harm, but it fails the 'CI excludes zero' rule as an increment. Keep HC logging.
- If startup is not adopted: adopt c2 (`adopted_c2.c`, `adopted.patch` vs solution_orig.c = submitted solution.c): search 1.672 vs 2.307, CI excludes zero, static +0.001, >10 m 1 vs 6, val 1.010 vs 2.032 not contradicted.
- Do not adopt: hard limits, soft reset triggers (static penalty), pvh08, nis gate.
Defaults in `adopted_c2.c` are HC_STARVE 1, PRI_LAT_STD 0.5, PRI_VZ_STD 0.3, PRI_Z_STD 0.8 (identical code to the evaluated arms). Per-flight trip counts: `trips.py <run> [N]`. Trip log lines on stderr: "HC <kind> n= f= t= a= b=" and periodic "HC sum" lines.
