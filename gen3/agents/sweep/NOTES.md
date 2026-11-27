# sweep agent NOTES (config ablation / sweep on top of F_sp10; CPU only, 20 workers, v3 TEST never used)

## SUMMARY
(in progress)

## Setup
- base.c = copy of agents/priors/gslv_s3ft2.c. mk.py (copy of priors/mk.py, outputs to sweep/builds/NAME).
  `mk.py ref "PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0" base.c` -> sha 40355ed9 == priors F_sp10 (VERIFIED);
  ref_r1 (+PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0) e785ac5b == priors F_sp10_r1, ref_r2 (1.485/990) 47bb1f46 == F_sp10_r2 (VERIFIED).
- Pools: refresh_pools.sh run at start (v3val 749, v1val 210); FROZEN copies of the symlink dirs in sweep/pools/{v3val,v1val}
  so every comparison in this log uses the same 749 v3val flights (0 test files). Eval names evals/sw_NAME__POOL.json.
  The priors agent's per-flight caches for F_sp10/_r1/_r2 (430 flights) were hard-link copied into sw_ref*/ (same sha).
- run.sh POOL NAME "DEFS" ... = build + eval (20 workers, waits while load > 170). sc.py = paired comparison vs sw_ref
  (rep-means with a+b+c), raw + server-weighted with bootstrap CIs for both, peak = max over reps.
- F = PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 (all ablations are F + one change).

## Switch inventory (base.c; effective value in the F_sp10 build; who tested it)
Effective config is set by the "final build" #defines at the top of the file (lines 1-251), which override the defaults
further down. "exact" = speed-only code path, output identical by construction (not swept).
| group | switch (effective) | meaning | tested by |
|---|---|---|---|
| startup prior | PRIOR_MODE=1, START_STD=2.0, START_T=2.0 | iso zero-mean startup velocity prior for START_T s | priors (mode 0/1/3/4, START_STD 1.5/2/2.5), net (iso); sweep: START_T, START_STD x SPEED_STD |
| startup prior | START_MEAN_FWD/X/Y, START_STD_X/Y/Z, SPEED_STD_H/Z, ANISO_ALWAYS, POST_ANISO, START_SHELL_* | modes 2/3/4 only | priors (fwd0, f05, wide, m4) - inert with PRIOR_MODE=1 |
| startup prior | MOVE_TILT_STD 0.15, MOVE_VEL_STD | moving-start tilt/vel sd | priors (t45 hurts, mv20 neutral) |
| startup prior | DET_GYRO 0.2, DET_FORCE 8.8 | moving-start detector | sweep |
| steady prior | SPEED_STD=1.0 (horizontal only!), SPEED_TAU 2 (fixed) | zero-mean velocity prior whole flight | priors (0.5/1/1.5/2); sweep (0.7/1.3 x START_STD) |
| steady prior | INV_VZ=0.3 | vertical velocity sd (overrides SPEED_STD on z) | sweep |
| steady prior | INV_LAT=0.5 | body-lateral velocity ~N(0,0.5^2) after startup | sweep |
| steady prior | AB_VPRIOR=1, AB_THRUST=1, AB_ZUPT=1 | velocity prior / thrust accel-bias pseudo-meas / vision ZUPT | sweep |
| steady prior | INV_HOLD=1 (HOLD_T 1.0) | hover start: gyro=bg, f=R^T g+ba pseudo-meas | sweep |
| steady prior | INV_SHELL, INV_AZ, INV_FADE, INV_HUBER, INV_CRUISE, INV_ZUPTG, INV_BAZ, INV_BGSD, INV_GYV (all 0) | older stage-2 experiments, off | sweep (selected) |
| gate | GATE_MODE=0 (GATE_DISP/PAIRS/SOFT only with mode 1/2) | hover heading-prior release | sweep (GATE_MODE=1) |
| learned net | LC_ENABLE=1, LC_START_EN=1, LC_K=5, LC_SCALE=1.0, LC_FLOOR=0.05, LC_REPLACE=1, LC_SLOW_V, LC_SPD_K, LC_EXTRA_SD | startup net measurement | priors (LC_ENABLE=0, LC_SCALE=3 on old net), net (LC_START_EN=0 on ft2: worse); sweep: LC_SCALE, LC_REPLACE, LC_FLOOR |
| learned net | LV_PERIOD=10, LV_PSCALE=3.0, LV_PLIVE | periodic net re-anchor every 10 frames, sigma x3 | priors/net (LV_PERIOD=0 on OLD net only); sweep |
| learned net | LV_BGC=1, LV_BGMAX=0.021 | gyro-bias clamp | sweep |
| monitor | TC_MON=1, TC_PV_THR=0.25, TC_T0=1.5, TC_GAP=9, TC_MAXANCH=400, TC_RE_SCALE=1.0, TC_RE_FLOOR, TC_POST=1, TC_ROWMAX=30, TC_STARTUP_MON=0, TC_PERIOD=0 | net re-anchor when sqrt(tr Pv) > thr | sweep |
| monitor | LI_GATENET=0.2, LI_PVS=1 | B17 gate-forced ZUPT/hover pv trigger | sweep |
| watchdog | WD* (default off) | goats-style restart | priors (inert) |
| vision | PIXEL_STD 1.5, DETECT_MIN_SCORE 1000 | used for replicate nudges | sweep (1.0/2.0) |
| vision | GRID_X/Y 10x6, MAX_UPDATE_FEATURES 20, MAX_OBS 8, CLONE_EVERY 4, MAX_CLONES 6, MAX_DEPTH 40, KLT_* | tracker/keyframe/budget | sweep (selected) |
| lines | EDGE=1, EDGE_LINE, EDGE_N 32, EDGE_PIX 0.3, EDGE_MYAW=1, EDGE_VERT/HORIZ, EDGE_RMAX | edgelet/line features | sweep |
| map | MAP_MODE=1 (MAP_AGE 100, ZNCC 0.85, ...) | loop-closure-lite map points | sweep |
| iteration | ITER_UPD=2, ITER_TH, ITER_BACK | iterated EKF update | sweep |
| fuel | GOV=1, GOV_B=3.6e6, GOV_UMAX, GC_* | measured-cost governor | linejac (lower budget hurts); sweep |
| initializer | INI_* (not in this source) | goats handover | initializer agent (no gain) |
| exact/speed | F_*, NET_SLICE, NS_*, VKC, EDGE_AJAC/ASIMD, LJ_*, COVPROP, HARDEN, GRAY_G, ... | identical output or fuel scheduling | not swept |

## Results log
### Reference on the frozen 749-flight pool (F_sp10 = sw_ref, sha 40355ed9)
| name | raw | sw | >3m | peak | note |
| ref (r0) | 0.927 | 0.857 | 17 | 4.79M | |
| ref_r1 | 0.904 | 0.844 | 14 | 5.08M | d vs r0 -0.023 [-0.062,+0.020] |
| ref_r2 | 0.877 | 0.815 | 11 | 5.32M | d vs r0 -0.049 [-0.090,-0.009] (!) replicate spread ~0.05 m on 749 flights; peak 5.32M with the new flights |
| REF3 = mean(ref,r1,r2) | 0.902 | 0.839 | 14 | 5.32M | ro/wa/fo 0.496/1.355/0.945, hover/mid 0.970/0.868 |
=> single-run paired CIs vs one reference run understate the chaos noise (a pure replicate gets a CI excluding 0). From here all
   single runs are compared against REF3 (per-flight mean of the 3 reference replicates); screening threshold d < -0.02, then 3 reps.
- Pool composition: rooms 299 (48 hover), warehouse 250 (122 hover; 100 are the new h95* hover flights), forest 200 (81 hover).
  Warehouse hover (server weight 1/6) is the worst cell: 1.46 m on the h95* flights.
- Note DET_FORCE 8.8 < g, but hover flights are unaffected by START_STD/MOVE_TILT (priors notes), so the detector does classify them.
### POOL SWITCH (07:20, coordinator request: disk full, zips outside the keep lists get deleted)
- Frozen pools reduced to gen3/pools/v3val_keep.txt (358 flights, all were in my 749 snapshot) and v1val_keep.txt (120).
  sweep/pools/{v3val,v1val} now hold only those links; pools/*.keep list them; sc.py restricts every comparison to the keep ids
  (cached per-flight results reused; nothing re-run). c_lat0_r1 was restarted on the 358 pool (233 cached).
- ALL numbers below this line are on the 358-flight subset, d vs REF3 (3-rep mean of ref).
| name | flags (F +) | raw | sw | >3m | peak | d raw [CI] | d sw [CI] |
| REF3 | - | 0.933 | 0.870 | 8 | 4.85M | - | - |
| ref r0/r1/r2 | (replicates) | 0.947/0.941/0.910 | 0.877/0.880/0.853 | 9/8/6 | 4.62/4.70/4.85M | +0.015/+0.008/-0.023 | |
| a_edge0 | EDGE=0 (no line features) | 0.946 | 0.882 | 8 | 3.90M | +0.013 [-0.064,+0.080] | +0.012 [-0.041,+0.064] |
| a_lp0 | LV_PERIOD=0 (no periodic net re-anchor) | 0.950 | 0.877 | 7 | 4.80M | +0.018 [-0.011,+0.046] | +0.007 |
| a_tcmon0 | TC_MON=0 (no monitor re-anchor) | 0.971 | 0.904 | 10 | 4.96M | +0.038 [-0.002,+0.077] | +0.034 |
| a_pv0 | TC_PV_THR=0 | 0.936 | 0.866 | 8 | 4.93M | +0.003 [-0.025,+0.032] | -0.004 |
| a_lat0 | INV_LAT=0 (no body-lateral vel prior) | 0.909 | 0.848 | 9 | 4.84M | -0.024 [-0.071,+0.021] | -0.022 [-0.065,+0.015] |
| a_vz0 | INV_VZ=0 (vertical sd = SPEED_STD) | 0.910 | 0.840 | 10 | 4.78M (5.72M on 749) | -0.023 [-0.074,+0.029] | -0.030 [-0.070,+0.007] |
| s_lcs15 | LC_SCALE=1.5 | 0.947 | 0.874 | 11 | 4.95M | +0.014 | +0.004 |
| s_lcs07 | LC_SCALE=0.7 | 0.969 | 0.908 | 12 | 4.78M | +0.036 [-0.000,+0.073] | +0.038 [+0.001,+0.075] |
## FUEL TRADEOFF (coordinator priority 07:30): score = area on log-log (peak fuel/frame vs mean ATE). New best net auto_727:
- base727.c = agents/net/src/g_auto_727.c; mk.py b7_ref "F" base727.c -> 9a468ce9 == net builds/g_auto_727_sp10 (VERIFIED).
- runq.sh pops lines "NAME SRC DEFS" from queue.txt (fuel points first, then the remaining ablation queue). fuel.py = pooled
  per-frame fuel over the 358 keep flights (peak, p99, p95, mean, median per-flight peak) from report/logs/*/fuel.npy.
- GOV_B is the measured-cost governor budget (rows, detection cells, edge detection, map relocalisation, net micro-step units).
### Ablations on base.c (F_sp10 weights), 358 flights, d vs REF3 (F_sp10 3-rep mean 0.933 / sw 0.870); single runs unless "3rep"
| name | change | raw | sw | >3m | peak | d raw [CI] | d sw [CI] |
| lat0 3rep | INV_LAT=0 | 0.923 | 0.859 | 12 | 4.84M | -0.010 [-0.043,+0.024] | -0.011 [-0.045,+0.023] |
| vz0 3rep | INV_VZ=0 | 0.888 | 0.827 | 7 | 5.11M | -0.045 [-0.099,+0.000] | -0.043 [-0.081,-0.009] |
| c_latvz | INV_LAT=0 INV_VZ=0 | 0.859 | 0.817 | 7 | 4.68M | -0.074 [-0.149,-0.011] | -0.053 [-0.107,+0.001] |
| h_hold2 | HOLD_T=2.0 | 0.955 | 0.884 | 9 | 4.62M | +0.022 | +0.014 |
| h_pvs1 | LI_PVS_T0=1.0 | 0.938 | 0.865 | 7 | 4.66M | +0.005 | -0.005 |
| s_sp13 | SPEED_STD=1.3 | 0.932 | 0.866 | 12 | 4.75M | -0.001 | -0.004 |
| s_sp07 | SPEED_STD=0.7 | 0.951 | 0.880 | 11 | 4.92M | +0.019 | +0.010 |
| s_st25 | START_STD=2.5 | 0.910 | 0.857 | 9 | 4.58M | -0.023 [-0.098,+0.031] | -0.012 |
| s_st15 | START_STD=1.5 | 0.924 | 0.866 | 9 | 4.59M | -0.009 | -0.004 |
| a_gate1 | GATE_MODE=1 | 1.093 | 0.958 | 15 | 4.62M | +0.160 [+0.032,+0.327] | +0.088 (bad: warehouse 1.83) |
| a_hold0 | INV_HOLD=0 | 0.960 | 0.888 | 9 | 4.62M | +0.027 [+0.002,+0.055] | +0.018 (hold helps a bit) |
| s_pix20 | PIXEL_STD=2.0 | 1.011 | 0.945 | 11 | 4.71M | +0.078 [+0.034,+0.126] | +0.075 (bad) |
| a_map0 | MAP_MODE=0 | 0.928 | 0.877 | 7 | 4.91M | -0.005 | +0.007 (neutral) |
| a_iter1 | ITER_UPD=1 (no 2nd EKF iteration) | 0.884 | 0.819 | 7 | 4.19M | -0.049 [-0.108,+0.003] | -0.051 [-0.095,-0.013] (and lower peak) |
| a_thr0 | AB_THRUST=0 | 0.928 | 0.863 | 7 | 5.07M | -0.004 | -0.007 (neutral) |
| a_zupt0 | AB_ZUPT=0 (no vision ZUPT, disparity<0.4px) | 0.833 | 0.790 | 5 | 4.62M | -0.100 [-0.152,-0.053] | -0.080 [-0.121,-0.040] (hover 0.963->0.787, warehouse 1.39->1.13) |
=> candidates: AB_ZUPT=0 (largest), ITER_UPD=1, INV_VZ=0 (+INV_LAT=0). Re-testing these on base727 (7a_zupt0, 7a_iter1, 7c_zi, 7c_zilv).

### Fuel map (base727, F + changes, single runs, d vs b7_ref r0 0.906 / sw 0.845, peak 4.80M p95 3.02M)
| name | change | raw | sw | >3m | peak | p95 | mean fuel | d raw [CI] |
| b7_ref | - | 0.906 | 0.845 | 9 | 4.80M | 3.02M | 2.23M | - |
| g_e0 | EDGE=0 | 0.941 | 0.875 | 7 | 3.89M | 3.15M | 2.20M | +0.035 [-0.024,+0.096] |
| g_e0b30 | EDGE=0 GOV_B=3.0e6 | 0.944 | 0.876 | 7 | 3.24M | 2.65M | 1.95M | +0.038 [-0.005,+0.078] |
| g_e0b27 | EDGE=0 GOV_B=2.7e6 | 0.953 | 0.886 | 6 | 2.92M | 2.37M | 1.80M | +0.047 [-0.010,+0.115] |
| g_e0b24 | EDGE=0 GOV_B=2.4e6 | 1.068 | 0.987 | 11 | 2.71M | 2.11M | 1.64M | +0.162 |
| g_e0b21 | EDGE=0 GOV_B=2.1e6 | 1.115 | 1.018 | 14 | 2.37M | 1.87M | 1.49M | +0.209 |
| g_e0b18 | EDGE=0 GOV_B=1.8e6 | 1.277 | 1.175 | 21 | 2.08M | 1.65M | 1.34M | +0.371 |
| g_e0b12 | EDGE=0 GOV_B=1.2e6 | 2.618 | 2.392 | 122 | 1.57M | 1.20M | 1.03M | +1.712 (cliff) |
| g_e0v2b18 | EDGE=0 GOV_VIS=2 GOV_B=1.8e6 | 1.230 | 1.147 | 23 | 2.17M | 1.62M | 1.18M | +0.324 |
| g_e0v2b12 | EDGE=0 GOV_VIS=2 GOV_B=1.2e6 | 1.578 | 1.478 | 40 | 1.63M | - | - | +0.672 |
| g_e0v2b12g85 | + GRID 8x5 | 1.581 | 1.480 | 44 | 1.82M | | | +0.675 |
| g_e0v2b08 | EDGE=0 GOV_VIS=2 GOV_B=0.8e6 | 2.623 | 2.507 | 117 | 1.32M | ~1.0M | | +1.717 |
| g_e0v2b08g85l20 | + GRID 8x5 LV_PERIOD=20 | 2.552 | 2.376 | 114 | 1.32M | | | +1.646 |
| g_e0b24v2 | EDGE=0 GOV_VIS=2 GOV_B=2.4e6 | 1.142 | 1.061 | 16 | 2.69M | | | +0.236 (vis2 worse than vis1 at same peak) |
| g_e0v2 | EDGE=0 GOV_VIS=2 | 1.034 | 0.961 | 12 | 3.82M | 3.11M | 1.92M | +0.128 |
| g_vis2 | GOV_VIS=2 | 0.922 | 0.878 | 7 | 4.88M | 3.09M | 1.98M | +0.016 |
| g_v2b30 | GOV_VIS=2 GOV_B=3.0e6 | 0.966 | 0.905 | 9 | 4.15M | 2.60M | 1.75M | +0.060 |
| g_b30 | GOV_B=3.0e6 (edges on) | 1.219 | 1.032 | 28 | 4.21M | 2.54M | 1.94M | +0.313 (warehouse 2.2) |
| g_b24 | GOV_B=2.4e6 (edges on) | 3.402 | 2.539 | 89 | 3.11M | 2.06M | 1.61M | +2.496 (warehouse diverges ~20 m) |
| g_b18 | GOV_B=1.8e6 (edges on) | 5.482 | 4.444 | 135 | 2.16M | 1.59M | 1.30M | +4.576 |
| g_mc4 | MAX_CLONES=4 | 1.026 | 0.949 | 13 | 4.25M | | | +0.120 |
| g_grid85 | GRID 8x5 | 0.914 | 0.833 | 7 | 5.01M | | | +0.008 |
| g_muf10 | MAX_UPDATE_FEATURES=10 | identical sha 9a468ce9 (inert: overridden) |
| g_um12 | GOV_UMAX=12 | 0.907 | 0.845 | 7 | 4.57M | | | +0.001 |
| g_lp20 | LV_PERIOD=20 | 0.907 | 0.847 | 9 | 5.26M | | | +0.001 |
=> Line features (EDGE) break down whenever GOV_B < 3.6e6 (warehouse diverges): edge tracking/rows take budget first and starve
   point rows. With EDGE=0, GOV_B is a clean knob: knee at ~2.9-3.2 M peak (+0.04-0.05 m); below 2.4 M ATE rises fast, cliff at ~1.6 M.
   Fuel at low budget is ~1 M of fixed cost (pyramid, KLT, prior, net stash), so 1 M peak needs structural cuts (testing grid/KLT).
### KEY RESULT (base727 = auto_727 net, single runs vs b7_ref r0)
| name | change (F +) | raw | sw | >3m | peak | p95 | d raw [CI] | d sw [CI] | ro/wa/fo | hov/mid |
| 7a_zupt0 | AB_ZUPT=0 | 0.778 | 0.735 | 3 | 4.93M | 3.03M | -0.128 [-0.183,-0.082] | -0.110 [-0.162,-0.067] | 0.490/1.064/0.848 | 0.800/0.766 |
| 7a_iter1 | ITER_UPD=1 | 0.890 | 0.835 | 9 | 3.99M | 2.74M | -0.016 [-0.063,+0.037] | -0.010 | 0.520/1.299/0.932 | |
| 7c_zi | AB_ZUPT=0 ITER_UPD=1 | 0.764 | 0.733 | 3 | 3.99M | 2.74M | -0.142 [-0.201,-0.088] | -0.112 [-0.170,-0.058] | 0.532/1.004/0.811 | 0.795/0.748 |
| 7c_zilv = Z | AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 | 0.702 | 0.692 | 3 | 3.73M | 2.72M | -0.204 [-0.273,-0.145] | -0.153 [-0.220,-0.093] | 0.566/0.826/0.750 | 0.674/0.716 |
- Vision ZUPT (median de-rotated clone disparity < 0.4 px -> v = 0 +- 0.02 m/s) fires falsely in stage-3 (wide FoV, far warehouse/forest
  features, slow drift) and locks in wrong velocity; ITER_UPD=1 also cuts peak fuel ~0.8 M (2nd EKF iteration was the spike).
  Rooms get a bit worse with Z (0.49 -> 0.57); the gain is warehouse/forest/hover. Confirming with replicates + v1val, then fuel map on Z.
### CONFIRMED (3 reps each, 358 flights, paired per-flight rep means)
| name | raw | sw | >3m | peak (max over reps) | ro/wa/fo | hov/mid | d raw [CI] | d sw [CI] |
| B7REF3 (b7_ref, _r1, _r2; sha 9a468ce9/d10ab98c/7e44627a) | 0.920 | 0.847 | 10 | 5.35M | 0.482/1.412/0.956 | 1.018/0.870 | - | - |
| Z3 (7c_zilv 32fcbdb6, Z_r1 26ebb911, Z_r2 3b17b98e) | 0.706 | 0.692 | 3 | 3.75M | 0.565/0.838/0.751 | 0.687/0.716 | -0.214 [-0.289,-0.145] | -0.155 [-0.222,-0.096] |
  single reps: Z r0 0.702/0.692, r1 0.708/0.692, r2 0.708/0.691 (replicate spread 0.006 m, much tighter than the reference's 0.025).
| v1val (120) | b7ref_v1 0.653 / sw 0.615 / >3m 0 / 4.44M, ro/wa/fo 0.336/1.025/0.898 -> Z_v1 0.609 / 0.580 / 1 / 3.75M, ro/wa/fo 0.399/0.879/0.751; d -0.044 [-0.107,+0.014], dsw -0.035. No overall regression; rooms +0.06 (same sign as v3val rooms +0.08). |
| 7c_zlv | AB_ZUPT=0 INV_LAT=0 INV_VZ=0 (ITER_UPD 2) | 0.763 | 0.727 | 6 | 4.75M | ro/wa/fo 0.578/0.980/0.765 | d -0.157 vs B7REF3 |
| 7c_ziv | AB_ZUPT=0 ITER_UPD=1 INV_VZ=0 (keep INV_LAT 0.5) | 0.715 | 0.692 | 2 | 3.80M | ro/wa/fo 0.508/0.909/0.784, hov/mid 0.769/0.688 | d -0.204 [-0.275,-0.139], dsw -0.155 |
=> ITER_UPD=1 helps on top of ZUPT-off (wa/fo) AND cuts peak ~0.9 M; INV_LAT=0 trades rooms (+0.06) for hover/warehouse; same sw.
### Sweeps on top of Z (single runs, d vs Z3 = 0.706 / sw 0.692)
| Z_sp15 | SPEED_STD=1.5 | 0.727 | 0.713 | peak 3.89M | d +0.021 [-0.013,+0.053] |
| Z_sp07 | SPEED_STD=0.7 | 0.707 | 0.683 | 3.82M | d +0.001 [-0.029,+0.031] (flat: keep 1.0) |
| Z_lat1 | INV_LAT=1.0 | 0.731 | 0.722 | 3.75M | d +0.025 [-0.022,+0.093] |
| Z_e0 3rep (cc5b1f98 + r1 + r2) | EDGE=0 | 0.693 | 0.664 | 3.76M (p95 2.82M) | d -0.013 [-0.049,+0.022], dsw -0.028 [-0.075,+0.015]; rooms 0.565 -> 0.489 (back to reference), wa 0.887 |
  Z_e0 3rep vs B7REF3: d -0.226 [-0.295,-0.163], dsw -0.183 [-0.243,-0.130]; >3m 10 -> 0.
=> With Z the line features no longer earn their place (they cost rooms 0.08). Z_e0 = best ATE build so far; v1val check queued.
### Fuel map on Z_e0 (EDGE=0) - single runs, d vs B7REF3
| name | GOV_B | raw | sw | >3m | peak | p99 | p95 | mean fuel |
| Z_e0 (3rep) | 3.6e6 | 0.693 | 0.664 | 0 | 3.76M | 3.25M | 2.82M | 2.10M |
| Z_e0b30 | 3.0e6 | 0.742 | 0.715 | 3 | 3.19M | 2.75M | 2.33M | 1.86M |
| Z_e0b27 | 2.7e6 | 0.745 | 0.727 | 2 | 2.93M | 2.49M | 2.09M | 1.72M |
| Z_e0b21 | 2.1e6 | 0.860 | 0.843 | 3 | 2.35M | 1.95M | 1.74M | 1.43M |
| Z_e0b15 | 1.5e6 | 1.265 | 1.260 | 19 | 1.84M | 1.42M | 1.30M | 1.12M |
| Z_e0b24 | 2.4e6 | 0.816 | 0.799 | 3 | 2.63M | 2.22M | 1.89M | 1.56M |
| Z_e0b18 | 1.8e6 | 0.988 | 0.982 | 5 | 2.09M | 1.68M | 1.50M | 1.28M |
| Z_b30 (edges ON) | 3.0e6 | 0.993 | 0.871 | 15 | 3.21M | 2.57M | 2.28M | 1.86M | warehouse 1.58: edges still break under a lower budget |
| Z_vz05 | Z with INV_VZ=0.5 (edges on) | 0.692 | 0.676 | 3 | 3.70M | | | | d vs Z3 -0.014 [-0.044,+0.012] |
### NEW NET PROMOTED (14:02): net_at3_5453_sp10 (src agents/net/src/g_at3_5453.c -> sweep/base5453.c; mk.py n5_ref F -> d323c441 VERIFIED)
| name (3 reps each) | raw | sw | >3m | peak | p95 | ro/wa/fo | hov/mid | d raw [CI] | d sw [CI] |
| N5REF3 (n5_ref d323c441, _r1, _r2 cdfe3304) | 0.885 | 0.812 | 7 | 5.02M | 3.01M | 0.462/1.354/0.931 | 0.987/0.834 | - | - |
| N5ZE03 (n5_Ze0 0c9d8e93, _r1 5372b25f, _r2) | 0.663 | 0.635 | 0 | 3.80M | 2.82M | 0.462/0.854/0.725 | 0.698/0.645 | -0.222 [-0.291,-0.156] | -0.177 [-0.233,-0.126] |
  single reps 0.668/0.669/0.652 (sw 0.636/0.638/0.630).
| v1val (120) | n5ref_v1 0.629 / sw 0.599 / ro 0.316 / peak 4.75M -> n5_Ze0_v1 0.561 / 0.544 / ro 0.347 / 3.74M: d -0.068 [-0.132,-0.016], dsw -0.055 [-0.088,-0.008]. No regression (rooms +0.03). |
### More (single runs). Fuel map on the at3_5453 net (n5 = base5453.c, Z_e0 flags + GOV_B), d vs N5REF3 (0.885 / 0.812)
| name | GOV_B | raw | sw | >3m | peak | p99 | p95 | mean | d raw [CI] | d sw |
| N5ZE03 | 3.6e6 | 0.663 | 0.635 | 0 | 3.80M | 3.25M | 2.82M | 2.10M | -0.222 [-0.291,-0.156] | -0.177 |
| n5Y 3rep (INV_VZ=0.5) | 3.6e6 | 0.666 | 0.639 | 0 | 3.75M | 3.25M | 2.82M | 2.11M | -0.219 | -0.173 (= Z_e0; keep INV_VZ=0) |
| n5_b30 | 3.0e6 | 0.706 | 0.677 | 0 | 3.23M | 2.75M | 2.33M | 1.86M | -0.179 [-0.250,-0.115] | -0.134 |
| n5_b27 | 2.7e6 | 0.731 | 0.711 | 2 | 2.96M | 2.49M | 2.09M | 1.72M | -0.154 [-0.225,-0.087] | -0.101 |
| n5_b24 | 2.4e6 | 0.783 | 0.752 | 2 | 2.67M | 2.22M | 1.89M | 1.56M | -0.102 [-0.173,-0.038] | -0.060 |
| n5_b21 | 2.1e6 | 0.802 | 0.775 | 2 | 2.38M | 1.95M | 1.74M | 1.43M | -0.084 [-0.151,-0.020] | -0.037 |
| n5_b18 | 1.8e6 | 0.985 | 0.978 | 9 | 2.15M | 1.68M | 1.50M | 1.28M | +0.100 [-0.004,+0.199] | +0.166 |
Low end (base727, Z + EDGE=0; d vs N5REF3 is approximate since net differs):
| Zg_e0b21g85 | 2.1e6 GRID 8x5 | 0.826 | 0.799 | 3 | 2.46M | 2.01M | 1.73M | 1.39M | (grid 8x5 ~ neutral at 2.1M) |
| Z_e0b12g64k3 | 1.2e6 GRID 6x4 KLT_ITERS 3 | 1.151 | 1.138 | 11 | 1.95M | 1.31M | 1.14M | 0.94M |
| Zl_b13 | 1.3e6 + GRID 6x4 KLT 3 MAX_CLONES 4 | 1.187 | 1.177 | 11 | 1.94M | 1.30M | 1.13M | 0.86M |
| Z_e0v2b12 | 1.2e6 GOV_VIS=2 | 1.182 | 1.183 | 9 | 1.56M | 1.22M | 1.17M | 0.82M |
| Zl_b10 | 1.0e6 + 6x4/KLT3/MC4 | 1.676 | 1.686 | 34 | 1.67M | 1.04M | 0.89M | 0.75M |
| Zl_v2b09 | 0.9e6 GOV_VIS=2 + 6x4/KLT3/MC4 | 1.712 | 1.692 | 36 | 1.72M | 1.04M | 0.93M | 0.55M |
- PEAK FLOOR: below GOV_B ~1.3e6 the peak no longer follows the budget. Every flight's max is FRAME 0 (initialisation: pyramid +
  full detection + net frame-0 RGB stash), 1.47-1.6 M at GOV_B 1.0e6; LC_ENABLE=0 removes ~0.24 M (stash) -> 1.23 M. A second ungoverned
  spike at frame 8 (first clone-window update) is 1.2-1.35 M. So ~1 M peak is NOT reachable with config flags; it needs code changes
  (spread frame-0 init/detection over frames, defer the stash, cap the frame-8 update). Not attempted (outside a config sweep).
- Ablation leftovers on base727 with plain F (vs B7REF3): LV_PERIOD=5 and START_T=3.0 identical to ref (inert); LV_PSCALE 5 +0.007,
  LV_PSCALE 2 -0.024, START_T 1.0 +0.007, MAX_DEPTH 80 +0.003, LI_GATENET=0 LI_PVS=0 -0.017, LV_BGC=0 -0.035 [-0.084,+0.013],
  PIXEL_STD=1.2 -0.038 [-0.070,-0.005] (all single runs; PIXEL 1.2 and BGC 0 re-tested on top of the final config).
### NEW REFERENCE NET per coordinator: netv2 A160ft (src agents/netv2/src/A160ft.c -> sweep/baseA160.c; mk.py a1_ref F -> c0bb8940 VERIFIED).
  Reference evals: gen3/evals/nv2_A160ft{,_r1,_r2}__v3val.json (A1REF3), nv2_A160ft__v1val.json.
| name (A160ft net, 3 reps) | raw | sw | >3m | peak | p95 | ro/wa/fo | hov/mid | d raw [CI] | d sw [CI] |
| A1REF3 (nv2_A160ft c0bb8940 + _r1 + _r2) | 0.888 | 0.818 | 6 | 5.32M | ~3.0M | 0.477/1.340/0.937 | 0.951/0.856 | - | - |
| A1ZE03 (a1_Ze0 670bc1da, _r1 6d08ae9a, _r2 772a0499) | 0.665 | 0.641 | 0 | 3.77M | 2.82M | 0.476/0.841/0.728 | 0.692/0.652 | -0.223 [-0.285,-0.166] | -0.177 [-0.234,-0.129] |
  reps 0.655/0.665/0.675 (sw 0.631/0.640/0.652). v1val: nv2_A160ft 0.617/sw 0.591/ro 0.317/4.62M -> a1_Ze0_v1 0.556/0.543/ro 0.337/3.76M,
  d -0.062 [-0.119,-0.016], dsw -0.047. No regression.
| a1_b27 (GOV_B 2.7e6) | 0.728 | 0.698 | 1 | 2.97M | 2.09M | 0.507/0.954/0.776 | | -0.160 [-0.218,-0.108] | -0.120 |
| a1_b21 (GOV_B 2.1e6) | 0.828 | 0.809 | 3 | 2.38M | 1.74M | 0.621/1.022/0.897 | | -0.060 [-0.126,-0.001] | -0.009 |
| a1_b13l (1.3e6 + GRID 6x4 KLT_ITERS 3 GC_KLT 3.5e3 MAX_CLONES 4) | 1.179 | 1.153 | 17 | 1.94M | 1.14M | | | +0.290 | +0.335 |
