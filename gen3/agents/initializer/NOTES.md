# initializer agent (plan step 3): the other team's stage-2 EKF as GSLV's startup initializer

## SUMMARY (final)
**The handover does not beat the current best build (net agent's s3ft2_iso). No build recommended. Default (INI_MODE=0)
reproduces every reference sha byte for byte.**
- Paired vs s3ft2_iso (v3val, 430 flights; ref 0.904 raw / 0.879 sw, peak 4.71 M; its own replicate r1 gives +0.032 [-0.005,+0.074]):
  - f_n5net (hard handover N=5, net kept, FVMIN=0.5): 0.940 / 0.905, d=+0.036 [-0.001,+0.076], peak 4.95 M; room 0.444 (ref 0.454),
    wh 1.590 (1.454), fo 1.235 (1.209); hover 0.816 (0.801), mid 0.969 (0.928). Same size as replicate noise: neutral at best.
  - f_n10net 1.038 / 0.999, d=+0.134 [+0.080,+0.193]; f_n10 (net off) 1.201 / 1.089, d=+0.297; f_m2n20 (soft feed) 1.122 / 1.027, d=+0.217.
- Their filter alone (solution.cpp to wasm): 3.423 raw / 3.158 sw on 152 flights (GSLV-lj 1.672); rooms 0.663 (better than GSLV-lj's 0.762),
  warehouse 5.30, forest 6.30; peak 0.42 M.
- The early "gain" (i1n10_v05 1.292 vs gslvlj 1.672 on 152 flights) came entirely from turning GSLV's old net off after the
  handover: ablation a3_nonet = LC_ENABLE=0 gives 1.247 by itself. Against net-off GSLV (lc0), handover N=10 is +0.09 / +0.12
  (2 reps) worse. The handover helps rooms in every rebase (-0.01 to -0.07) and hurts warehouse/forest (+0.1 to +0.35).
- Why: in large scenes their velocity at frames 5-40 is as wrong as GSLV's (1.5-2 m/s) but its covariance is tiny (trace
  ~0.002 m2/s2), and attitude is off by up to 6 deg. A velocity sd floor (INI_FVMIN=0.5) is needed (N=40: 2.045 -> 1.787), and shorter N
  is better (60 > 40 > 20 > 10 ~ 5). Gating does not work: their velocity variance "converges" by frame 5 in 64 % of flights, and
  their median inverse depth sits at the 0.5 prior in warehouse/forest. Even an ORACLE rooms-only handover over lc0 is only -0.035
  [-0.073,+0.002]. A colour cue separates forest only.
- Peak fuel: their filter adds about 0.25-0.42 M per frame during the first N frames (mode 1 replaces GSLV there, so the peak is unchanged, 4.4-5.2 M,
  set by chaos later in the flight; mode 2 adds it on top of GSLV but stays <= 5.24 M).
- v1val regression and 3 replicates were not run for a handover candidate because none beats the reference. Replicates were run for
  lc0 vs lc0_n10 (see below).
- Licensing: srcI/ and srcF/ builds contain the other team's vio.cpp/vio.h unmodified; credit them if ever used.


## Setup
- Build tooling: `build.py NAME SRCDIR "DEFINES"` -> builds/NAME/solution.wasm (wasi-sdk, viobench reactor, same flags as
  run_variant.build; C and CXX flags both get the -D list).
- No-change rebuild of linejac/final/gslv_linejac_arith.c (src0/) reproduces the reference sha eb2799cb...  (builds/ref).
- src/gslv.c = GSLV-linejac + INI block (all behind INI_MODE, default 0). With INI_MODE=0 it rebuilds to the same sha
  eb2799cb... (builds/ref_mod), i.e. default off = unchanged GSLV.
- srcI/ = mixed C/C++ build: solution.c (= src/gslv.c) + ini_bridge.cpp + vio.h/vio.cpp, UNMODIFIED copies of the other
  team's /data/backups/rganapa/Sebastian/tmp/goats/submission_stage2 (copy in goats/). NOTE: any submission built from
  srcI contains the other team's code (vio.cpp/vio.h) -- must be credited if ever submitted.
- Their parameters: stage=0.5, seed_px=3, init_tilt=0.45 (parameters.h), rest defaults, depth bank off.

## Switches (src/gslv.c, INI block)
- INI_MODE 1: their filter alone for frames 0..N-1 (its pose is the output); GSLV initialises at frame N from their
  state: GSLV world = R_A W, R_A = align_to_z(-g_W) (yaw kept), R0 = R_A, R = R_A R_their, pos = R_A p, vel = R_A v,
  biases copied; core covariance = J C17 J^T (gravity 2-dof -> world tilt phi = [z]x R_A B dg, which enters TH, TH0,
  P and V). Output is continuous at N (R0^T pos = p_their).
- INI_MODE 2: both from frame 0; at frame N one whitened update of GSLV with their body-frame velocity R^T v and gravity
  direction R^T g/|g| (covariance from their C17, x INI_FINF).
- INI_N, INI_VINF, INI_TINF, INI_BFLOOR, INI_GATEREL (release GSLV's heading prior at handover), INI_NET (GSLV's learned
  velocity net after handover), INI_FINF, INI_FGRAV, INI_NOPRIOR, INI_FVMIN.

## Results (v3val unless noted; paired vs gslvlj)
- baseline gslvlj (refreshed pool, 152 flights): mean 1.672, server-weighted 1.460, median 1.237, >3 m 27, peak 5.10 M.
- ini_goats = their solution.cpp alone (builds/goats, sha 781affb8): mean 3.423, sw 3.158, median 1.908, >3 m 64, peak 0.42 M;
  rooms 0.663 (better than GSLV 0.762), warehouse 5.30, forest 6.30; hover 3.16, mid 3.49. d=+1.751 [+1.322,+2.230].
- i1n40 (INI_MODE=1 N=40), 8-flight mini pool (mid-flight free-yaw): rooms better (0.53/0.30/1.06 -> 0.43/0.45/0.13),
  forest worse (3.65/1.52/2.57 -> 5.85/2.71/5.24), warehouse mixed (4.91/1.71 -> 2.48/2.07). Their velocity at frame 40
  is better than GSLV's on 7/8, but after handover GSLV's velocity error GROWS in forests (fo-552: 0.43 m/s at 40 ->
  2.25 at 100), i.e. the post-handover transient is the problem, not the initial estimate.
- i1n40 variants on mini (8 flights): nonet 2.131, vinf4 2.460, bfl 2.511, gr0 2.382 vs base 2.03 on same 8: all noise-level.
- FULL v3val (152): i1n40_nonet (INI_MODE=1 INI_N=40 INI_NET=0): mean 2.045, sw 1.592, median 1.137, >3m 40, peak 4.36 M;
  rooms 0.624 (vs 0.762), warehouse 3.93 (vs 2.46), forest 2.76 (vs 2.48); hover 0.82, mid 2.33. d=+0.373 [+0.114,+0.649].
- i2n40 (INI_MODE=2 N=40, feed v+g once): mean 2.142, sw 1.692, peak 4.41 M; rooms 0.662, wh 3.93, forest 3.03. d=+0.470 [+0.248,+0.713].
- i1n40_diag (= nonet + stderr diag, identical ATEs): their state at frame 40 vs outcome. rho_med, nis, n_alive, speed do
  NOT separate rooms from warehouse/forest. Gating on their health (no restart and nis<1) leaves 79 flights where
  i1 is 1.181 vs base 1.248 (small). Diagnosis (ana.py/ana2.py vs GT): in open scenes their velocity at frame 20/40 is as
  wrong as GSLV's (1.5-2 m/s) but their velocity covariance is tiny (trace 0.002 m2/s2, sd ~0.03 m/s), so GSLV after
  handover cannot correct it (v error stays ~2.3 m/s through frame 100, GSLV alone recovers to ~0.4 by frame 60). Their
  attitude is also off by up to 6 deg in forests (GSLV ~1.6). => test velocity sd floor (INI_FVMIN) and tilt add (INI_TADD).
- v3val full, INI_MODE=1 N=40 NET=0 unless noted:
  i1n40_v05 (FVMIN=0.5): mean 1.787, sw 1.441, med 1.105, >3m 37, peak 4.36M; room 0.580 wh 3.233 fo 2.518; d=+0.114 [-0.105,+0.344]
  i1n40_v10 (FVMIN=1.0): mean 1.885, sw 1.519, peak 5.20M; room 0.578 wh 3.382 fo 2.735; d=+0.213 [-0.025,+0.460]
  i1n40_v05t (+TADD=0.05): mean 1.857, sw 1.481, peak 4.67M; room 0.605 wh 3.552 fo 2.453; d=+0.185
  i1n40_v10t: mean 1.869, sw 1.521; d=+0.197
  i1n40_v10net (FVMIN=1, NET=1): mean 2.158, sw 1.834; room 0.837 -> GSLV's net after handover hurts; keep NET=0.
  i2n40_v05 (MODE=2, FVMIN=0.5): mean 1.910, sw 1.570, peak 4.53M; room 0.693 wh 3.109 fo 2.865; d=+0.237 [+0.082,+0.397]
  i1n20_v05 (N=20, FVMIN=0.5): mean 1.535, sw 1.274, med 1.022, >3m 19, peak 6.00M; room 0.522 wh 2.757 fo 2.141; hover 0.812 mid 1.705; d=-0.137 [-0.326,+0.072]
  i1n60_v05: mean 1.902, sw 1.543, peak 4.28M; d=+0.230 [+0.018,+0.450]
  i1n40_v03 (FVMIN=0.3): mean 1.744, sw 1.465; d=+0.072
  i1n20_v05t (N=20, FVMIN=0.5, TADD=0.05): mean 1.514, sw 1.269, med 1.117, >3m 27, peak 4.45M; room 0.567 wh 2.634 fo 2.100; d=-0.158 [-0.336,+0.024]
  => shorter N is better (60 < 40 < 20).
  i1n5_v05t: mean 1.336, sw 1.122, med 0.930, >3m 19, peak 5.06M; room 0.462 wh 2.548 fo 1.727; d=-0.336 [-0.550,-0.115]
  i1n10_v05t: mean 1.351, sw 1.152, >3m 17, peak 5.20M; d=-0.321 [-0.497,-0.163]
  i1n10_v05 (no TADD): mean 1.292, sw 1.109, med 0.904, >3m 14, peak 4.38M; room 0.505 wh 2.418 fo 1.617; hover 0.837 mid 1.400; d=-0.380 [-0.555,-0.210]
  i1n15_v05t: mean 1.355, sw 1.175; d=-0.318 [-0.502,-0.140]
  i1n20_v07t: mean 1.556, sw 1.322; d=-0.117.  i1n30_v05t: mean 1.597, sw 1.331; d=-0.075
  => N=5..15 is the sweet spot. Big gain is suspicious (their filter has barely converged at 0.25-0.5 s) ->
     ablations without their filter (INI_MODE=3): a3_full (net off, heading prior released, v=0+-0.5),
     a3_nonet (only net off), a3_rel (only heading prior released).

## Ablation: the gain was GSLV's net being off, not their filter
- a3_nonet (INI_MODE=3, GSLV from frame 0 with lc_active=0 only) = 1.247 / sw 1.076 on 152 -- identical to the priors agent's
  pr_lcoff (LC_ENABLE=0, same numbers). a3_rel (heading prior released, net on): 1.702 (no effect). a3_full (net off,
  prior released, v=0+-0.5): 1.812 (bad: GSLV needs a velocity guess; theirs supplies one).
- vs pr_lcoff on 152: i1n10_v05 d=+0.045 [-0.148,+0.218], i1n5_v05t +0.088, i1n3_v05 +0.070 -> handover neutral vs net-off.

## Rebased on LC_ENABLE=0 (lead request); pools/v3val refreshed to 430 flights
- builds/lc0 = GSLV -DLC_ENABLE=0 (sha cc5f1c97 = priors agent's lcoff). ini_lc0: mean 1.109, sw 1.033, med 0.831, >3m 17,
  peak 5.08M; room 0.582 wh 1.885 fo 1.337; hover 0.797 mid 1.180.
- gslvlj (430): mean 1.524, sw 1.390, >3m 55, peak 5.13M; room 0.706 wh 2.259 fo 2.335; hover 0.920 mid 1.662.
- lc0_n10 (LC_ENABLE=0 INI_MODE=1 INI_N=10 INI_NET=0 INI_FVMIN=0.5) vs lc0: mean 1.201, sw 1.089, >3m 28, peak 5.02M;
  room 0.511 (better) wh 2.092 fo 1.623 (worse); d=+0.092 [-0.001,+0.194].
- vs lc0 (430): lc0_m2n20 (soft: MODE=2 N=20 FINF=4 FVMIN=0.5): mean 1.223 sw 1.100 room 0.547 wh 2.152 fo 1.581, d=+0.115 [+0.039,+0.200]
  lc0_m2n10: mean 1.258 sw 1.152 room 0.666, d=+0.149 [+0.054,+0.242]
  lc0_n5 (hard N=5): mean 1.216 sw 1.101 room 0.499 wh 2.247 fo 1.549, peak 4.99M, d=+0.107 [+0.020,+0.199]
  lc0_h5_30 (health-gated: earliest frame 5, their vvar<0.05, nis<1, no restart, >=8 features; else frame 30): mean 1.236
    sw 1.124 room 0.558 wh 2.231 fo 1.532, peak 4.66M, d=+0.127 [+0.036,+0.220]. Their velocity variance "converges"
    (overconfidently) by frame 5 in 276/430 flights, so the health gate is not informative.
  lc0_n15: mean 1.321 sw 1.171, d=+0.213 [+0.106,+0.320]
  lc0_m2n20g (soft + chi2 gate 12.6 on the 6-dof feed): mean 1.254 sw 1.127, d=+0.145 [+0.075,+0.225]
  lc0_n10d (= n10 + diag; identical ATEs). Scene awareness: their median inverse depth at frame 10 is still the prior 0.5
    in warehouse/forest (p10-p90 0.50-0.50) and 0.41-0.59 in rooms -> no separation. Frame colour separates forest
    (G/avg(R,B) 1.14-1.25 vs ~1.0) but not warehouse vs room. Post-hoc combos vs lc0 (430): ORACLE rooms-only handover
    mean 1.074 sw 0.990 d=-0.035 [-0.073,+0.002] (upper bound, not significant); "not green" rule 1.135 sw 1.021 d=+0.026.
- Replicates (PIXEL_STD=1.515): lc0_r1 mean 1.106 sw 1.012 (vs lc0 r0 1.109/1.033); lc0_n10_r1 mean 1.228 sw 1.103
  room 0.509 wh 2.238 fo 1.587, d=+0.122 [+0.029,+0.213] vs lc0_r1. Two reps agree: handover N=10 is ~+0.1 m worse
  than net-off GSLV overall (rooms -0.06, warehouse +0.2..0.35, forest +0.2..0.3).

## Rebased again on the net agent's s3ft2_iso (new best, 0.904 raw / 0.879 sw on 430, peak 4.71M)
- srcF/ = ../net/src/s3_ft2.c + ini.patch (diff of src/gslv.c vs the arith source; one hunk re-applied by hand after the
  LC_START_EN line). INI_MODE=0 with -DPRIOR_MODE=1 -DSTART_STD=2.0 rebuilds the reference sha 70b4c500 (builds/ft2iso_mod).
- Variants (all PRIOR_MODE=1 START_STD=2.0 INI_FVMIN=0.5): f_n10net (MODE 1, N=10, net kept after handover),
  f_n10 (net off after handover), f_n5net (N=5), f_m2n20 (soft: MODE 2 N=20 FINF=4).
- vs s3ft2_iso (430): f_n10net 1.038/0.999 d=+0.134 [+0.080,+0.193] peak 4.70M (room 0.479 wh 1.748 fo 1.390);
  f_n10 1.201/1.089 d=+0.297 (= lc0_n10: after a handover with net off the prior is irrelevant);
  f_n5net 0.940/0.905 d=+0.036 [-0.001,+0.076] peak 4.95M (room 0.444 wh 1.590 fo 1.235; hover 0.816 mid 0.969);
  f_m2n20 1.122/1.027 d=+0.217 [+0.146,+0.298] peak 4.76M.
  Reference replicate net_s3ft2_iso_r1: d=+0.032 [-0.005,+0.074] -> f_n5net is within noise; the handover cannot beat s3ft2_iso.
