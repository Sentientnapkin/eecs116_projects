# i4 REPORT: classical VIO with relaxed compute + frontend diagnostics (Q5, Q6)
Labels: MEASURED (this dir, results.tsv / out/fe_agg.txt), EXISTING (BRIEF/prior work), NEW EXPERIMENT, MATH, HYPOTHESIS, UNKNOWN.
Local ATE = mean unaligned ATE (m). Subset: pools/s80 = fixed 80-flight stratified subset of v3val (32 room / 27 warehouse / 21 forest; 26 hover / 54 mid-flight); v1val = 120 flights.
Base build = baseline "A160ft+Ze0" flags (src.c copy, builds via mk.py). All CIs are paired bootstrap 95% on per-flight differences (n=80, wide). Local is pessimistic vs server (EXISTING).

## 1. Relaxed-compute sweep (Q5)  [MEASURED, NEW EXPERIMENT]
GOV_B=1e12 ("g0") removes the fuel governor. Each config 1 run; key configs 3 replicates (nudged PIXEL_STD/DETECT_MIN_SCORE; replicate means below). Peak = max per-frame fuel.
| config | change vs g0 | mean ATE (s80) | d vs ctl-run (CI) | peak fuel |
|---|---|---|---|---|
| ctl | baseline (governed) | 0.651 (3-rep 0.683) | -- | 3.7 M |
| g0 | governor off | 0.670 (3-rep 0.667) | +0.018 [-0.045,+0.083] | 10.3 M |
| muf | MAX_UPDATE_FEATURES=200 | 0.670 | identical to g0 | 10.3 M |
| gr2 / gr5 / gr10 | grid 14x9 / 22x14 / 32x19 (2/5/10x features) | 0.615 / 0.661 / 0.671 | -0.037 / +0.010 / +0.020 (all n.s.) | 13 / 30 / 52 M |
| c12 | MAX_CLONES=MAX_OBS=12 | 0.601 (3-rep 0.605) | -0.050 [-0.112,+0.011]; reps -0.092 [-0.156,-0.028], -0.092 | 30 M |
| c20 | 20 clones | 0.614 (3-rep 0.627) | -0.037; reps -0.072, -0.058 | 110 M |
| c30 | 30 clones | 0.642 | -0.010 | 368 M |
| c20o8 | 20 clones, MAX_OBS=8 | 0.895 | +0.243 (worse) | 40 M |
| c12e2 | 12 clones, clone every 2 frames | 0.619 | -0.032 | 120 M |
| klt | KLT_R=6, 15 iters, eps .005, 3 levels | 0.656 | +0.005 | 10.6 M |
| it2 / it3 | ITER_UPD=2 / 3 | 0.699 / 0.662 | +0.048 / +0.010 | 12.7 / 14.9 M |
| combo | grid 22x14, 300 update feats, 20 clones, strong KLT | 0.601 (3-rep 0.593) | -0.055; reps -0.105 [-0.187,-0.022], -0.111 [-0.204,-0.022]; v1val 0.507 vs 0.555 (-0.048 [-0.111,+0.023]) | 360 M |
| nonet (LC_ENABLE=0, LV_PERIOD=0: no velocity net) | governed | 1.722 (13 flights >3 m) | +1.07 [+0.56,+1.87] | 3.0 M |
| nonet_g0 | no net, no governor | 2.095 (3-rep; 14-16 flights >3 m) | +1.4 | 7.5 M |
| combo_nonet | combo, no net | 1.912 | +1.26 | 384 M |
(Replicate d columns in results.tsv for _r1/_r2 are paired against the matching baseline replicate.)

Findings
- MEASURED: removing the governor alone does not help (0.667 vs 0.683, n.s.) and costs 2.8x peak. More features (2-10x) do not help; 10x is flat/slightly worse in forest (0.85).
- MEASURED: the only consistently helpful direction is a longer clone window (12-20): about -0.08 m (-11%) with 3 replicates, concentrated in warehouse (0.83 -> 0.64-0.66) while rooms/forest are flat or slightly worse. Window 30 loses the gain. Fuel for c12 is ~30 M peak (8x baseline); combo gets ~-0.09 m (-13%) at ~360 M peak (~100x).
- MEASURED: the velocity net is essential for this MSCKF: without it ATE is 1.7-2.1 m even with 10-100x compute (more compute does not rescue it; combo_nonet 1.91, nonet_g0 2.1). Consistent with EXISTING: no rotor drag, accel carries no velocity info; scale/velocity must come from vision+IMU and is weakly observable at start.
- MEASURED: with the net, relaxing compute by up to 100x lowers local ATE only 0.68 -> 0.59 (best, replicated). Nothing is near 0.1-0.15 m. Extrapolation to C (0.15 m @ 100 M) from these sweeps: not supported by data (UNKNOWN beyond what was swept).
- MEASURED: iterations/relinearization (ITER_UPD 2-3) and KLT accuracy settings give no gain (n.s.).
- MEASURED/UNKNOWN: MAX_UPDATE_FEATURES=200 gave results bit-identical to g0 (cap not binding or switch inactive at these settings); not investigated.
- Code changes needed (not done): true full-history sliding-window BA, relinearized smoothing, more than MAX_CLONES statically sized buffers (compile-time constants exist up to 30 as tested), learned/dense tracker, rotation-compensated/guided tracking beyond what exists.
- NOT RUN (UNKNOWN): external VIO (OpenVINS/VINS-Fusion/Basalt/ORB-SLAM3) offline, offline non-causal batch BA, oracle-assisted variants (oracle harness is i3's remit). EXISTING (BRIEF/memory): server baselines for VINS-Mono/OpenVINS are far worse than our 0.586 m; goats-style EKF 3.3-3.6 m even with oracle velocity.

## 2. Frontend diagnostics (Q6)  [MEASURED; instrumented diag build, AUD_TRK/AUD_STATS, fe_ana.py, 79/80 s80 flights (1 truncated stderr dropped)]
Tracker runs at 320 px width. Table = mean over flights (full per-class output: out/fe_agg.txt).
| metric | all | room | warehouse | forest |
|---|---|---|---|---|
| track survival >=5 / 10 / 20 / 40 / 80 frames | .87/.77/.65/.48/.29 | .82/.68/.51/.31/.10 | .88/.80/.69/.55/.36 | .94/.89/.80/.68/.49 |
| mean track length (frames) | 79 | 35 | 90 | 135 |
| live tracks / frame; frames with <10 live | 29; 36% | 25; 29% | 32 | 32 |
| GT-triangulated depth p10/p50/p90 (m) | 1.8/4.9/10.7 | 0.9/1.8/3.7 | 2.8/7.5/16.3 | 2.1/6.1/14.5 |
| track parallax p10/p50/p90 (deg) | 2.3/14/46 | 3.0/15/41 | 1.9/14/45 | 1.8/12/57 |
| median reproj residual vs GT-triangulation (px@320) | 2.07 | 1.34 | 1.29 | 4.27 |
| gyro-integration residual per frame (px) med / p90 | 0.25 / 0.40 | 0.24 | 0.26 | 0.25 |
| median flow per frame: raw / after GT derotation (px) | 3.8 / 1.2 | 5.6 / 1.8 | 2.6 / 0.7 | 2.7 / 0.8 |
| detections/frame; KLT fail; fwd-bwd reject (per frame) | 5.3; 1.1; 0.75 | 7.5; 1.2 | 4.5; 0.9 | 2.8; 1.2 |
| triangulation / gating rejection rate | 3.0% / 1.9% | | | |
| MSCKF feature rows per frame | 15 | | | |
- Residual by track age (<5,<10,<20,<40,<80,80+ frames): 1.06, 0.80, 1.30, 2.06, 4.27, 10.0 px. HYPOTHESIS: the large late-age residual is mostly track drift/identity slip of long tracks (and GT-triangulation conditioning on very long tracks), not a bias (mean xy bias ~1e-4 px, MEASURED). The residual includes GT/mid-exposure timing and triangulation error, so treat absolute px values as upper bounds (caveat).
- MEASURED: median gyro residual 0.11 deg/frame (0.25 px): rotation is well predicted by the gyro over one frame; the derotated residual flow (0.7-1.8 px) is the translational/ parallax signal. Gyro-guided prediction is therefore already accurate; EXISTING in code: KLT is seeded with gyro-based rotation prediction (verify in src.c; not re-audited here).
- MEASURED: rooms are the hard frontend case (short tracks: 35 frames, close depth ~1.8 m, fast flow) yet have the lowest ATE (0.46); warehouse and forest have long tracks and far depth (p90 16 m) yet higher ATE. HYPOTHESIS: ATE in open scenes is limited by weak translational information at large depth (scale/drift) rather than tracking quality; fits the clone-window gain being warehouse-specific.
- MEASURED correlations with per-flight ATE (Spearman, n=79, ctl run): depth p50/frac_depth>10m +0.51/+0.54, mean track life +0.48, frac frames <10 live tracks +0.40, rows/frame +0.42; rotation rate -0.49/-0.54, flow -0.49, detections/frame -0.46, n_tri -0.36. Tracking error metrics (reproj residual, gyro residual, rejection rates) are weak (|rho|<=0.22). Reading: error follows scene depth/geometry (little parallax per metre of travel), not frontend noise. Correlation, not causal (confounded by scene class).
- Exposure (>35 ms vs <=15 ms): survival similar (>=40: .51 vs .48), median derotated flow 0.87 vs 1.44 px, KLT fails 0.84 vs 1.38 per frame; blur does not visibly degrade tracking statistics here (blur-aware covariance: no evidence of need; not tested directly).
- Hover vs mid-flight starts: frontend stats similar (survival, reproj). Not the source of the start-type difference.
- Learned tracker: UNKNOWN (not tested). MEASURED indirect evidence: improving KLT (more iterations/levels) and 2-10x more features gave no gain, so correspondence precision is not the bottleneck at the sub-pixel level tested; a learned tracker would help only if it adds long-lived tracks in rooms (survival>=40 is 31%) or in low-texture scenes, which clone-window tests suggest matters mainly for warehouse. HYPOTHESIS only.
- Techniques status: gyro-guided prediction EXISTING (see above); rotation-compensated flow, 2-pt translation, long-baseline tracking, distant-landmark rotation constraints, blur-aware covariance: not implemented in this sweep, not tested (UNKNOWN). Manhattan line/vanishing-point constraints EXISTING (linejac). Depth/information-aware selection: grid-based selection only; 10x feature test suggests quantity is not limiting.

## 3. Central question: can classical geometry reach 0.1 m on this distribution?
- MEASURED: with this estimator, up to ~100x compute and the learned velocity net, local ATE reaches 0.59 (best, 3-rep) vs 0.68 control; never below 0.5 m (v1val 0.507). Not close to 0.1 m.
- Likely limiting factors (ordered by evidence): (1) velocity/scale observability: no-net result 1.7-2.1 m regardless of compute (MEASURED); (2) scene depth/parallax (ATE correlates with depth, not tracking noise; MEASURED correlation); (3) heading drift in free-yaw flights (EXISTING: 0.696 free-yaw vs 0.575 normal) ; (4) estimator design: window length helps warehouse only (MEASURED), more iterations/features do not. Initialization and sensor errors are not separated here (UNKNOWN; i2/i3 oracles cover them).
- Not established: whether a full non-causal BA or a strong external VIO would do better (UNKNOWN, not run).

## Reproduce
cd /data/backups/rganapa/Sebastian/gen3/research/i4; python -B run_sweep.py (resumable; configs in CFG; results.tsv); python -B run_fe.py then python -B tools/fe_agg.py > out/fe_agg.txt. Evals: gen3/evals/i4_*__s80.json. Per-flight frontend json: fe/*.json. Builds: builds/*/flags.txt.
Caveats: n=80 subset; single-run CIs wide; combos have peak fuel 30-550 M, unusable for the 1 M budget target (A) but informative for C.
