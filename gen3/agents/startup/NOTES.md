# startup agent NOTES (first 0.5-3 s of GSLV + auto_727 net; CPU only, <=14 workers, no v3 TEST, no git/uploads)

## SUMMARY
WHAT HELPED (only one thing): V0M=1 - use the net's HEAD 0 (body velocity at the anchor frame; GSLV only used head K = frame 5)
as a second velocity measurement on a stochastic clone of V taken at the anchor frame (the 3 zero-padding error states 21..23, so no
state growth and essentially no fuel: one extra 3-row update per net landing). Effect consistent in sign on 3 nets, size shrinks as
the net improves, raw-mean CIs touch 0:
- auto_727 (5 reps, v3val 358): 0.912 -> 0.873, d raw -0.040 [-0.087,+0.002], d srv-w -0.040 [-0.079,-0.006]; mid 0.863 -> 0.829,
  hover 1.010 -> 0.960; >2 m 24 -> 22, >3 m 9 -> 8. v1val (3 reps) 0.648 -> 0.637, d -0.012 [-0.044,+0.020].
- at3_5453 (3 reps): 0.885 -> 0.859, d -0.026 [-0.071,+0.011], srv-w -0.025 [-0.058,+0.005]; v1val -0.013 [-0.038,+0.013].
- nv2_A160ft (3 reps): 0.888 -> 0.866, d -0.022 [-0.071,+0.024], srv-w -0.025 [-0.062,+0.007]; mid 0.856 -> 0.806, hover 0.951 -> 0.986,
  >3 m 6 -> 3; v1val ~+0.01 (neutral).
- pooled over the 3 nets: -0.029 [-0.072,+0.004]; rooms -0.051 [-0.092,-0.016]. Early errors (mid-flight, 727): velocity error at
  frame 40 0.458 -> 0.377 m/s, position error at frame 40 0.547 -> 0.458 m.
- Peak fuel: unchanged in kind (V0M adds ~nothing per frame); per-run peaks 4.4-5.4 M are set by chaos later in the flight, same range
  as the base replicates (base 4.53-5.35 M). Neither base nor V0M meets <= 4.2 M on every flight.
BEST BUILD (on the current reference net A160ft): builds/a1_v0m/solution.wasm, sha256 b6cc85eaaaee6f3c32010caf0a34a0cd6fc1cfea16bf428fcf44bdb8fb013fe2,
  source gslv_stA160.c (= agents/netv2/src/A160ft.c + startup.patch), flags -DPRIOR_MODE=1 -DSTART_STD=2.0 -DSPEED_STD=1.0 -DV0M=1.
  Same change on other nets: builds/v0m (auto_727, gslv_st.c, sha b8102cfd...), builds/n5_v0m (at3_5453, gslv_st5453.c, sha a93be5ad...).
  All new code is behind #ifndef switches; default flags reproduce 9a468ce9 / d323c441 / c0bb8940 exactly.
WHAT DID NOT HELP (all on top of V0M, v3val, single run within the V0M replicate spread 0.852-0.889 unless noted):
  tilt sd 0.10 / 0.25; LC_SCALE 1.2; chi2 gate 11.345 on net updates; START_STD 4 (weaker zero-velocity pull); V0_SCALE 1.5;
  net landing earlier (NS_BOOST 0.6/1.2 M extra budget while pending); accel-bias freeze (INV_BAZ 0.05) and gyro-bias freeze (INV_BGSD
  0.005, worse); re-anchor sigma LV_PSCALE 1.5/2/6, no periodic re-anchors, re-anchors from 0.5 s; extra early net anchors (ST_EARLY);
  early MSCKF updates from live tracks before the window fills (ST_ETRK: 3 reps, +0.001 vs V0M); vision rows while the net is pending
  (ST_NOHOLD: much worse, 0.71 -> 1.36 on mid40). Not applicable: FEJ reset (GSLV has no FEJ), drag pseudo-measurement (simulator has
  NO rotor drag: body-xy specific force vs body velocity slope -0.005, corr 0.03).
KEY FINDINGS:
- Net calibration (literature's first number): the startup net is honest. Mid-flight starts: head K err 0.314 m/s, chi2_3 > 11.345 on
  0.4 % (nominal 1 %), z-rms 0.96; head 0 0.317 m/s, 2.1 %, 0.99; periodic re-anchors 0.40 m/s, 3.6 %, 1.04 (filter inflates those x3).
  Recalibration / gating has no room. (GT twist in ground_truth_state is camera-LOCAL; earlier drafts of this log misread it.)
- The remaining startup error is TILT: frame-0 gravity = mean specific force = thrust axis (no drag), so the initial horizontal
  acceleration is read as gravity: tilt error 6.5 deg mean / 15 deg p90 at frame 5 on mid-flight starts, still 3.1 deg at 1 s, ~1 deg
  only after ~2 s (vision). The net's velocities cannot fix it (0.3 m/s over 0.25-0.5 s ~ 5-10 deg resolution, no better than the prior),
  and vision cannot start before the net has fixed velocity/scale. No tested lever shortened this.
- Startup net lands at frame ~13 (NET_SLICE over ~9 frames of budget); no MSCKF rows before frame ~17 (NS_HOLD + window).
- What-if: removing the position error at frame 10-60 from the rest of the trajectory does NOT lower the local mid-flight mean ATE
  (0.837 -> 0.87-0.97); locally, start position offsets are not the dominant ATE term, later drift is. Locally hover flights (warehouse hover
  1.44 m, 4/6 of warehouse server weight) fail later in the flight, not at the start.

## Setup
- gslv_ref.c = net/builds/g_auto_727_sp10/src/solution.c (priors/gslv_s3ft2.c + auto_727 weights). gslv_st.c = my working copy.
- mk.py NAME "DEFS" [src] -> builds/NAME/solution.wasm (same toolchain as priors/mk.py). run.sh POOL NAME.. -> evals/st_NAME__POOL.json (14 workers, load wait).
- Reference flags B = PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0. `mk.py st0 B` on gslv_st.c -> sha 9a468ce9 == g_auto_727_sp10 (VERIFIED after every edit).
- tools/early.py (per-flight early pos/vel errors), tools/dbgview.py (per-frame debug vs GT), tools/netcal.py (net calibration vs GT from LCO lines).
- Debug switch ST_DBG=N: per-frame SD lines (frames <= N) + LCO line (all 12 net outputs) per net application, to stderr.txt.

## Diagnosis (baseline net_auto_727_sp10, v3val 358)
- mean 0.906; hover 1.043 (n=120) vs mid-flight 0.837 (n=238) locally (hover warehouse 1.44 dominates; those fail LATER, not at the start:
  their p100 ~0.4 m, v<0.1 m/s in the first 5 s).
- Mid-flight: vel error v5/10/20/40/60 = 1.23/1.07/0.67/0.46/0.32 m/s; position error at frame 20 already 0.3-0.7 m.
- Per-frame on wa-9300407 (ATE 4.5): startup net lands at frame 13 (NET_SLICE spread; gov ~3.5 M/frame); NO MSCKF rows before frame 17.
  Before the net the estimated acceleration is (true a(t) - true a(0)): frame-0 tilt is align_to_z(mean f) and the simulator has no rotor
  drag (accelerometer = thrust along body z), so the frame-0 horizontal acceleration is read as gravity (tilt error = a_h(0)/g,
  e.g. 2 m/s^2 -> 12 deg). Net at frame 13 fixes position via the VK clone (0.63 -> 0.21 m) but not the tilt.
- Drag check (literature item 8): per-frame body-xy specific force vs GT body velocity, 14k frames: slope -0.005 / +0.004, corr 0.03
  -> NO drag in the simulator; drag pseudo-measurement dropped.
- The net (lv3.py) has two heads: head 0 = body velocity at the anchor frame, head K = at anchor+5. GSLV used only head K.

## Switches added (gslv_st.c, all default off -> 9a468ce9)
- V0M=1: clone V into the zero-padding states 21..23 at every lc_begin (anchor frame), apply head 0 as a body-velocity measurement on it
  when the net lands (after the head-K update); V0_SCALE (sigma mult), V0_REANCH (0: startup only). Head0 - headK through the IMU
  propagation constrains tilt (= the literature's "gravity + v0 least-squares from net velocities and integrated IMU", done inside the EKF).
- LC_GATE: chi2 gate on the net updates.

## Results log
### Net calibration vs GT (tools/netcal.py on st_dbg = reference + ST_DBG; v3val 358). GT twist in ground_truth_state is CAMERA-LOCAL
### (body velocity = T_body_camera @ v_gt; verified against the training targets vb of agents/net/cache/val and the python net, which
### reproduces the C outputs exactly). Re-anchor anchor frame = frame_no + 1. Literature's "first number": chi2_3 > 11.345 exceedance.
| anchors | head | n | err m/s | chi2>11.345 (nominal 1 %) | 3-sigma cover/axis | z-rms |
| startup mid-flight | head0 (v at frame 0) | 238 | 0.317 | 2.1 % | 99.6 % | 0.99 |
| startup mid-flight | headK (v at frame 5) | 238 | 0.314 | 0.4 % | 100 % | 0.96 |
| startup hover | headK | 120 | 0.089 | 0.8 % | 100 % | 0.77 |
| periodic re-anchors | head0 / headK | 9703 | 0.388 / 0.402 | 3.5 / 3.6 % | 99.1 % | 1.03 / 1.04 (filter uses sigma x LV_PSCALE 3) |
(full table: ana/netcal_st_dbg.txt)
- => the net is well calibrated at startup and at re-anchors (z-rms ~1); recalibration / chi2 gating (literature item 2) has no room.
  The startup measurement is not the problem; what the filter does with it before and after is.
- No FEJ in GSLV (literature item 4 not applicable).
### Batch 1 (v3val 358, paired vs net_auto_727_sp10; sc.py)
| name | flags (+B) | raw | srv-w | d raw [CI] | d srv-w [CI] | hover | mid | b/s/f | >1/2/3 m | peak |
| net_auto_727_sp10 | B | 0.906 | 0.845 | - | - | 1.043 | 0.837 | 0.845/0.734/0.929 | 114/26/9 | 4.80M |
| st_dbg | B ST_DBG=60 | identical ATEs to reference (debug prints only) |
| v0m | V0M=1 | 0.852 | 0.787 | -0.054 [-0.105,+0.005] | -0.058 [-0.103,-0.009] | 0.939 | 0.809 | 0.893/0.626/0.918 | 111/21/7 | 4.60M |
| v0s | V0M=1 V0_REANCH=0 | 0.855 | 0.785 | -0.051 [-0.110,+0.015] | -0.060 [-0.115,+0.003] | 0.952 | 0.806 | 0.990/0.602/0.855 | 103/23/7 | 4.86M |
| base_r1 | B PIXEL_STD=1.515 DETECT_MIN_SCORE=1010 | 0.931 | 0.851 | +0.025 [-0.035,+0.099] | +0.006 | 0.990 | 0.901 | | 113/30/9 | 5.35M |
| base_r2 | B PIXEL_STD=1.485 DETECT_MIN_SCORE=990 | 0.922 | 0.845 | +0.016 [-0.039,+0.081] | -0.000 | 1.022 | 0.871 | | 109/25/8 | 4.90M |
| v0m_r1 | V0M=1 + r1 | 0.866 | 0.795 | -0.040 [-0.091,+0.009] | -0.050 [-0.094,-0.000] | 0.963 | 0.817 | 0.841/0.641/0.966 | 116/25/5 | 4.89M |
| v0m_r2 | V0M=1 + r2 | 0.889 | 0.819 | -0.017 [-0.075,+0.048] | -0.026 | 0.964 | 0.851 | 0.950/0.626/0.988 | 113/21/11 | 5.08M |
| v0m_t25 | V0M=1 MOVE_TILT_STD=0.25 | 0.878 | 0.806 | -0.028 | -0.039 | 0.939 | 0.848 | | 110/24/6 | 5.03M |
| v0m_t10 | V0M=1 MOVE_TILT_STD=0.10 | 0.868 | 0.802 | -0.038 | -0.043 | 0.939 | 0.832 | | 111/21/6 | 4.60M |
| v0m_lcs12 | V0M=1 LC_SCALE=1.2 | 0.904 | 0.819 | -0.001 | -0.026 | 0.973 | 0.870 | | 109/28/11 | 5.07M |
| v0m_ps6 | V0M=1 LV_PSCALE=6 (re-anchor sigma x6) | 0.857 | 0.792 | -0.049 | -0.054 | 0.953 | 0.809 | | 109/23/7 | 4.84M |
| v0m_lp0 | V0M=1 LV_PERIOD=0 (no periodic re-anchors) | 0.867 | 0.803 | -0.039 | -0.043 | 0.953 | 0.823 | | 121/19/8 | 5.00M |
| v0m_g | V0M=1 LC_GATE=11.345 | 0.868 | 0.805 | -0.038 | -0.040 | 0.932 | 0.836 | | 110/23/10 | 4.66M |
- 3-rep paired (rep.py, per-flight mean over r0/r1/r2): base 0.920 / sw 0.847 -> v0m 0.869 / sw 0.800: d raw -0.051 [-0.104,+0.001],
  d srv-w -0.047 [-0.090,-0.009]; hover 1.018 -> 0.955, mid 0.870 -> 0.825; >2 m 26 -> 20; peak max 5.35 -> 5.08 M.
- tilt sd 0.10/0.25, LC_SCALE 1.2, chi2 gate, re-anchor sigma x6 or no re-anchors: all within the v0m replicate spread (0.852-0.889).
### Batch 2 (v3val 358, vs net_auto_727_sp10; all + B V0M=1)
| v0m_nb12 | NS_BOOST=1.2e6 (more net micro-steps per frame while startup net pending) | 0.877 | 0.802 | -0.029 | -0.043 | 0.985 | 0.822 | | 111/24/7 | 4.95M |
| v0m_nb6 | NS_BOOST=0.6e6 | 0.866 | 0.800 | -0.040 | -0.045 | 0.988 | 0.804 | 0.807/0.643/0.957 | 108/24/6 | 4.69M |
| v0m_baz05 | INV_BAZ=0.05 (accel bias ~frozen) | 0.885 | 0.814 | -0.021 | -0.031 | 1.021 | 0.816 | | 114/23/8 | 4.97M |
| v0m_bg5 | INV_BGSD=0.005 (gyro bias ~frozen) | 0.916 | 0.840 | +0.010 | -0.005 | 0.998 | 0.874 | | 112/36/6 | 5.00M |
| v0m_ss4 | START_STD=4.0 (weaker zero-mean startup pull) | 0.867 | 0.802 | -0.039 | -0.043 | 0.939 | 0.831 | | 114/23/5 | 5.06M |
| v0m_s3 | V0_SCALE=1.5 | 0.860 | 0.796 | -0.046 | -0.049 | 1.004 | 0.787 | 0.869/0.594/0.908 | 115/26/5 | 4.45M |
=> none separates from v0m (rep spread 0.852-0.889). Bias freezing (literature item 3) does not help (gyro freeze hurts).
### Early-error / tilt diagnostics
- early.py, v0m vs base (mid-flight, 238): pos err p20/40/60/100 0.428/0.547/0.583/0.630 -> 0.398/0.458/0.487/0.544 m;
  vel err v20/40/60 0.667/0.458/0.320 -> 0.622/0.377/0.280 m/s. Hover unchanged early (0.31 vs 0.33 at frame 100).
- tools/tilt.py (SG debug lines: filter's world-up in body vs GT ep.ground_truth body pose), pools/mid40 (40 random mid-flight starts):
  tilt error (deg) at frame 5/10/13/15/20/30/40/60: base 6.5/6.2/5.1/4.6/3.5/1.8/1.3/0.9 (p90 at 5: 14.9 deg);
  v0m 6.5/5.9/4.8/4.5/3.1/1.7/1.2/0.8. => the frame-0 tilt (thrust axis taken as gravity) is wrong by ~6.5 deg mean / 15 deg p90
  and is only fixed by vision after ~1.5 s. This is the main startup error left.
- Not effective at removing it: extra early net anchors (ST_EARLY=3: one more anchor at frame ~11; tilt at 30/40 unchanged,
  mid40 ATE +0.05), FAST_FRAMES (inactive in the GOV vision path; same wasm).
- ST_ETRK=40 (update with live tracks seen in >=3 clones on clone frames during the first 2 s): tilt 13/20 4.8/3.1 -> 4.3/2.6 deg; mid40 ATE 0.710 -> 0.694.
- ST_NOHOLD=1 (vision rows while the startup net is pending): very bad (mid40 0.71 -> 1.36): vision before velocity is known locks in a bad scale.
- What-if (early.py, baseline): subtract the position error at frame k from every later frame. Mid-flight mean ATE 0.837 ->
  0.965 / 0.922 / 0.916 / 0.875 for k = 10/20/40/60 (better on only 117/238 flights at k=60); hover 1.043 -> 1.025.
  => locally the start POSITION offset is not a systematic ATE driver (later drift is as large and often cancels it); the
  start matters through the state it hands on (velocity/tilt/scale), which is what v0m improves.
### Batch 3 (v3val 358, vs net_auto_727_sp10; all + B V0M=1)
| v0m_et40 | ST_ETRK=40 (early track updates until the clone window fills; identical to ST_ETRK=80) | 0.846 | 0.782 | -0.060 [-0.113,-0.004] | -0.063 [-0.106,-0.015] | 0.939 | 0.799 | 0.826/0.649/0.921 | 118/22/6 | 5.04M |
| v0m_et40n2 | ST_ETRK=40 ST_ETRK_N=2 | 0.861 | 0.804 | -0.045 | -0.041 | 0.939 | 0.821 | | 111/22/7 | 4.69M |
| v0m_ps2 | LV_PSCALE=2.0 | 0.858 | 0.786 | -0.048 | -0.059 | 0.961 | 0.807 | | 122/21/6 | 4.60M |
| v0m_ps15 | LV_PSCALE=1.5 | 0.860 | 0.791 | -0.046 | -0.054 | 0.953 | 0.813 | | 112/20/7 | 5.05M |
| v0m_tt05 | TC_T0=0.5 (periodic re-anchors from 0.5 s) | 0.861 | 0.794 | -0.045 | -0.051 | 0.939 | 0.822 | | 107/23/8 | 4.83M |
### Replicates (v3val 358 and v1val 120; rep.py = per-flight mean over r0/r1/r2, paired bootstrap)
| set | v3val raw | v3val srv-w | d raw [CI] | d srv-w [CI] | hover | mid | >1/2/3 | peak max |
| base (727 sp10) x3 | 0.920 | 0.847 | - | - | 1.018 | 0.870 | 111/26/10 | 5.35M |
| v0m x3 | 0.869 | 0.800 | -0.051 [-0.104,+0.001] | -0.047 [-0.090,-0.009] | 0.955 | 0.825 | 108/20/8 | 5.08M |
| v0m_et40 x3 | 0.870 | 0.802 | -0.050 [-0.102,+0.000] | -0.045 [-0.086,-0.004] | 0.955 | 0.827 | 105/22/7 | 5.10M |
(v0m_et40 r1 0.876, r2 0.887; vs v0m x3: +0.001 [-0.019,+0.023] -> early track updates add nothing.)
| v1val set | raw | srv-w | d raw [CI] | d srv-w [CI] | hover | mid | peak max |
| base x3 | 0.648 | 0.612 | - | - | 0.590 | 0.666 | 4.69M |
| v0m x3 | 0.637 | 0.599 | -0.012 [-0.044,+0.020] | -0.013 [-0.041,+0.020] | 0.552 | 0.662 | 4.80M |
| v0m_et40 x3 | 0.650 | 0.620 | +0.002 | +0.008 | 0.552 | 0.680 | 4.75M |
=> v1val: no regression (slightly better). v1val singles: v0m 0.635 / r1 0.628 / r2 0.647; base 0.653 / 0.626 / 0.666.
### Net promoted meanwhile: net_at3_5453_sp10 (g_at3_5453_sp10, sha d323c441). gslv_st5453.c = its source + startup.patch
### (diff gslv_ref.c -> gslv_st.c); `mk.py n5_st0 B gslv_st5453.c` reproduces d323c441 (VERIFIED). Re-validating V0M on it (n5_*).
### 5 replicates on auto_727 (r3: PIXEL_STD 1.53 DMS 1020, r4: 1.47/980)
| base x5 | 0.912 | sw 0.842 | hover 1.010 mid 0.863 | >1/2/3 110/24/9 | peak max 5.35M |
| v0m x5 | 0.873 | sw 0.802 | d raw -0.040 [-0.087,+0.002], d srv-w -0.040 [-0.079,-0.006] | hover 0.960 mid 0.829 | 104/22/8 | 5.39M |
(singles: base 0.906/0.931/0.922/0.893/0.909; v0m 0.852/0.866/0.889/0.860/0.896)
### Re-validation on at3_5453 (promoted net; n5_* builds from gslv_st5453.c)
| v3val | base x3 (net_at3_5453_sp10, r1, r2) 0.885 / sw 0.812 | n5_v0m x3 0.859 / sw 0.787 | d raw -0.026 [-0.071,+0.011], d srv-w -0.025 [-0.058,+0.005] |
|  | hover 0.987 -> 0.962, mid 0.834 -> 0.807, >1/2/3 114/22/7 -> 109/21/5, peak max 5.02 -> 4.84M |
| v1val | base x3 0.632 / sw 0.599 | n5_v0m x3 0.619 / sw 0.584 | d raw -0.013 [-0.038,+0.013] |
### Re-validation on nv2_A160ft (coordinator's reference; a1_* builds from gslv_stA160.c = agents/netv2/src/A160ft.c + startup.patch;
### `mk.py a1_st0 B gslv_stA160.c` reproduces c0bb8940 VERIFIED)
| v3val | base x3 (nv2_A160ft, _r1, _r2) 0.888 / sw 0.818 | a1_v0m x3 0.866 / sw 0.793 | d raw -0.022 [-0.071,+0.024], d srv-w -0.025 [-0.062,+0.007] |
|  | hover 0.951 -> 0.986 (worse), mid 0.856 -> 0.806, >1/2/3 115/25/6 -> 112/20/3, peak max 5.32 -> 5.16M |
| v1val | base (single) 0.617 / sw 0.591 | a1_v0m 0.620 / 0.637 / 0.631 (mean 0.629), sw 0.600/0.596/0.586 | ~+0.01, neutral |
### Pooled over the three nets (per-flight mean of the per-net rep-mean differences, v3val 358)
all -0.029 [-0.072,+0.004]; mid-flight -0.037 [-0.101,+0.011]; hover -0.013 [-0.035,+0.008]; room -0.051 [-0.092,-0.016];
warehouse -0.038 [-0.156,+0.046]; forest +0.015 [-0.007,+0.038].
