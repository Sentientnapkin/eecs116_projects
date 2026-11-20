# Server-12 edge cases, local proxy set, and mitigation tests for the gated gp_msckf build

Scope and conventions. Only aggregate server numbers given by the team were used (per-episode distance, ATE of gp_msckf and of the gated build G, and e7aa5aee's Sim(3)/rotation/velocity figures; identity-pose ATE 4.694 m; VINS-Mono/OpenVINS 0.475/0.553 m). No private episode was opened, downloaded or probed. Everything about the 12 beyond those numbers is labelled INFERENCE. Pool = 726 local flights not in fold 4 (144 of the 171 selected, folds 0-3; 582 of the 711 fresh flights); fold-4 scenes and every sealed_aggregate.json were excluded. Truth is used only to classify local flights. Candidates: base = submitted gp_msckf; f0; G = server gate build (sha ac825145, bit-identical to my e.c defaults); T = tails adopted; M = fgt merged. Local per-flight tables: research/single_model/edge/{sig.json,audit.json,flightstats.json,proxy_out.md,classes.txt,signature.txt}. Code: edge/{stats,audit,sig,analysis,classes,proxy}.py, edge/e.c (+edge.patch).

Fields NOT available to me (the pasted raw JSON is not in the repo; SERVER_RESULT.md has only ATE and the e7aa5aee extras): per-episode rpe, rotation_rmse, velocity_rmse, sim3_scale, final_drift, drift_per_metre, fuel for the other 11 episodes, and the start type, speed profile, fx, texture of any episode. Pasting the raw JSON into a file would let the 12 be matched on rotation/velocity RMSE too.

## Q1. What do the aggregates say about the 12, and what is the e7aa5aee mechanism?

### Takeaway
The server set looks like a mostly mid-flight-start set (INFERENCE: posterior mean mid share about 0.75), distance-matched to our 171 selected flights, and e7aa5aee's signature (scale 0.57, velocity RMSE 1.5 m/s, rotation RMSE 0.235 rad, base 0.918 m) is the "startup heading prior over-states a slow or ambiguous start, metric scale inflates, rotation compensates" mode that G inherits from f0, not a tilt runaway.

### Cited Findings
- Server distances: 39.5-80.4 m, mean 59.6, sd 11.9 (SERVER_RESULT.md numbers in the brief). Pool path length (sidecar audit.travel_m): selected static 54.7, selected mid 57.2, fresh static 44.9, fresh mid 45.7 m (edge/audit.py). Only 7 pool flights exceed 70 m, so slots at 72.7, 74.0, 80.4 m are matched to flights 11-19 m shorter (proxy.py reports max distance error per slot).
- Identity-pose ATE 4.694 vs pool zero-motion ATE (sidecar zero_motion_ate_m) selected static 3.89, mid 4.35, fresh 3.1 (audit.py). Server flights are somewhat more extended than even the selected mid flights.
- Old gp_msckf had 3 of 12 episodes above 5 m (11.3, 7.97, 8.68) and mean 3.226 (median 1.244). In the pool the base build exceeds 5 m on 1.4% of static flights and 10.5% of mid flights (classes.txt/proxy_out.md); fresh REPORT.md gives 1.1% static / 8.5% mid.
- G fixed those three (0.307, 0.299, 1.09) and regressed e7aa5aee 0.918 -> 7.70; the other 11 average 0.657 m (SERVER_RESULT.md). Sim(3) scale 0.572 means the estimate must be shrunk by 0.57, i.e. the trajectory is 1.75x over-extended (metrics.py umeyama: scale maps estimate to truth). Rotation RMSE 0.235 rad (13.5 deg), max 0.308 (ratio 1.31), velocity RMSE 1.52 m/s against a mean true speed of about 74/60 = 1.2 m/s, Sim(3) ATE 3.67 (aligned error is half the unaligned one), final drift 6.7 m (0.090 x 74).
- Pool flights whose G metrics are closest to that signature (edge/signature.txt): flat-scene flights 26329 (scale 0.2-0.5), and slow or ambiguous mid starts 151-09, 151-00, 168-00, 169-01. Of 25 pool flights with G scale < 0.75 and ATE > 3 m, 20 are mid starts, 13 have true start speed < 0.6 m/s, and only 5 had base < 2 m (G-specific regressions).
- The ones where G is worse than base by > 1.5 m (17 of 726; 8 by > 3 m): 157-11 (base 0.50 -> 9.12, scale 0.17, start 0.47 m/s straight ahead), 150-00 (0.37 -> 7.52, scale 0.20, start 0.18 m/s), 169-01 (1.48 -> 7.21), 102344457-01 (0.42 -> 3.82), 168-00 (0.25 -> 3.15), 102816114-00 (0.37 -> 3.13, start 0.08 m/s), 3-01 (1.11 -> 3.65). Mostly slow starts (true |v0| < 0.6 m/s, 8 of 17). Mid starts with v0 < 0.3 m/s: G ATE > 3 on 13.6% vs base 13.6%; with v0 in 0.3-0.6: G 3.0% vs base 9.1%; v0 > 1.2: G 9.5% vs base 36.9% (signature.txt).
- Gate numbers: at the 0.45 s decision the gate releases the prior on only 3 of 63 mid starts, 55 of 56 static (gate/NOTES.md); the f0 prior is 0.9 m/s along the camera axis (START_MEAN_FWD 0.9 in gate.c) for START_T = 2 s.

### Inferences
- INFERENCE (start mix): the likelihood of "at least 3 base episodes above 5 m and base mean 3.226 +- 0.6" in random 12-draws rises monotonically with the mid share (0.0008 at all static, 0.060 at 50% mid, 0.162 at all mid); with a uniform prior the posterior mean mid share is 0.75 and the mass below 0.3 is 6%. So the server set is probably mostly or entirely mid starts. This is not proof; the 3 tails could also be a hard texture scene (flat scenes give base tails on static flights too).
- INFERENCE (long/fast): no per-episode speed is available. Within the pool the correlation of G ATE with path length is 0.06, so 74-80 m flights are not predicted to be intrinsically worse. e7aa5aee's own 7.7 m / 74 m = 0.104 m/m is in the pool band of G failures (0.08-0.17 for the scale<0.5 flights).
- INFERENCE (mechanism, e7aa5aee): scale 0.57 + velocity RMSE comparable to the mean speed + moderate, roughly constant rotation error (max/rms 1.3, so no late runaway; a tilt/gravity runaway would give a rotation error growing with time and a large Sim(3) residual) fits a startup speed error that is never corrected by vision: the prior injects 0.9 m/s forward while the true start is slow or lateral, scale locks to about 1.75x and the filter absorbs the inconsistency in attitude (about 13 deg). Plain gp_msckf (0.918) was fine on the same episode, which fits "prior-specific". Distinct from the wrong-direction lock-out of tails/NOTES.md (negative-depth triangulation flood), which in the pool gives scale near 1 and rotation error small to moderate; on e7aa5aee the aggregate cannot separate these two, and T's patch did not rescue the nearest pool analogues (151-09, 169-01 stay 6.4 and 7.3 m under T).
- INFERENCE (episodes): 8950399d (39 m, 11.3 -> 0.307), 89f8c99e (7.97 -> 0.299) and cd6dc704 (8.68 -> 1.09) look like wrong-direction/fast mid starts that the prior rescues (base tails, G fixes). 1c6e73f3, 726458d9, dd7a737e (base and G both about 0.1-0.3 m) look like benign hover or well-behaved starts. 78ed493f (0.72 -> 0.97) and f7c2546f (0.74 -> 1.48, shortest at 41.5 m) are mild regressions, consistent with the noise on the pool (G worse than base by 0.25-0.75 m is common). The Sim(3) ATE of G is mean 0.574, so most error elsewhere is metric/scale or alignment (unaligned vs aligned) rather than shape.

### Gaps
- Start type, speed, rotation content, texture and fx of each episode are unknowable from the aggregates; rotation/velocity RMSE of the 11 non-regressed episodes were not available to me (need the raw JSON).
- The pool has no flights above 80 m and few above 70 m.

## Q2. Proxy set and what 12-draws say about the server number

### Takeaway
Under the matched draws, G's 12-episode mean has median 0.9-1.2 m and P(at least one episode above 5 m) of 0.4-0.55 (mid share 0.5-1.0); the observed 1.244 m with one 7.7 m episode is a typical draw (percentile 59-74 of the G draws), and the chaos-replicate spread of a single build is as large as the difference between our candidates.

### Cited Findings
Proxy construction: for each server slot (distance d_i) the 60 pool flights (non-fold-4, selected + fresh) with the nearest path length; draw one per slot; start type drawn with a fixed mid share p_mid (0, 0.5, 1.0) because it is unknown. 30000 draws each (edge/proxy.py, proxy_out.md). Whole-pool (n=726) means: base 1.395, f0 0.841, G 0.842, T 0.824, M 0.828.

12-draw distribution of the mean (30000 draws), p_mid = 0.5:
| cand | mean | p5 / p50 / p95 | P(mean >= 1.244) | P(any ep > 5 m) | P(>=2 eps > 5) |
|--|--|--|--|--|--|
| base | 1.790 | 0.76 / 1.64 / 3.35 | 0.72 | 0.71 | 0.33 |
| f0 | 1.009 | 0.50 / 0.90 / 1.87 | 0.27 | 0.39 | 0.08 |
| G | 1.035 | 0.50 / 0.94 / 1.91 | 0.29 | 0.43 | 0.10 |
| T | 0.975 | 0.50 / 0.86 / 1.85 | 0.20 | 0.23 | 0.03 |
| M | 0.990 | 0.50 / 0.88 / 1.88 | 0.22 | 0.29 | 0.04 |
p_mid = 1.0: base 2.757 (P any>5 0.88), f0 1.188 (0.46), G 1.242 (0.54, P(mean>=1.244) 0.44), T 1.255 (0.36), M 1.286 (0.45). p_mid = 0.0: all about 0.83 (G P(any>5) 0.30, T 0.09: T helps flat-scene statics).
- Conditioned on the server base aggregate (ABC: base 12-mean 3.226 +- 0.6 and >= 3 base episodes > 5 m; p_mid 0.5): base 3.18; f0 1.48; G 1.50 (P(any>5) 0.74, P(>=2) 0.32); T 1.17 (0.27, 0.04); M 1.19. The observed G 1.244 sits below the conditioned mean (about 1.5) and at the 35th-45th percentile.
- Where 1.244 falls in unconditioned G draws: percentile 85 (p_mid 0), 74 (0.5), 59 (1.0); base 3.226 falls at 100 / 95 / 75. P(exactly one G episode > 5 m) = 0.32 at p_mid 0.5.
- Chaos: replicate means of the SAME build G on the whole pool: 0.842 / 0.902 / 0.905 (search slice 1.028 / 1.223 / 1.293; >10 m flights 1 / 4 / 3). Replicate-averaged (G3) whole-pool 0.883.
- Fresh-pool means (REPORT.md of the fresh agent, 711 flights): base 1.221, f0 0.812, G 0.813, tails 0.835, merged 0.834. My non-fold-4 recomputation: T 0.824 vs G 0.842 pool-wide, but paired T - G = -0.018 [-0.095, +0.060], 16 flights worse and 20 better by > 1.5 m: no evidence that T generalises better or worse in mean, but T lowers the count of > 5 m draws in the proxy (0.23 vs 0.43) because it fixes flat scenes and several wrong-direction starts while adding new tails (T worse than G by > 1.5 m on 160-00 (0.72 -> 13.0), 0-02, 166-02 static, 176-06).

### Inferences
- INFERENCE: the server number for any of our candidates is dominated by whether a draw contains a > 5 m episode (ex-worst-episode mean is about 0.7-0.9 for all f0-family builds; one 7 m episode adds about 0.6 to the 12-mean). The plausible range for a G-like build is 0.5-2.3 m (5-95%); 1.244 is unremarkable and the 0.976 local prediction was a near-median draw of a bimodal distribution.
- INFERENCE: P(>5 m episode) 0.43-0.54 for G means a second submission of G-like builds would hit a similar regression with roughly even odds on a different episode; reducing P(any > 5 m) is the lever (T 0.23, my combined arm below 0.43-0.51 depending on mid share).
- VINS/OpenVINS scoring 0.475/0.553 on the 12 (aggregate) says the 12 are not intrinsically hard for visual-inertial estimators; our tails are caused by the heading prior/lock-out classes, not by degenerate scenes. Per-flight VINS/OpenVINS are available only for the 171 selected flights, so they could not be used as a matching variable on the fresh flights.

### Gaps
- Start-type mix unknown (mid-share sweeps provided). Pool lacks 70-80 m flights. Matching on rotation/velocity RMSE not possible (fields missing). Draws assume equal weight and independent slots; scene overlap between selected and fresh flights is not modelled (bootstrap CIs for paired contrasts resample scenes).

## Q3. Edge-case catalog

### Takeaway
The dominant, measurable classes are (a) slow or ambiguous mid starts where the 0.9 m/s heading prior over-states speed, (b) reverse/lateral starts (axis angle > 90 deg), (c) flat/dark scenes, (d) fast starts; yaw rate, tilt and intrinsics are not separable from the pool statistics available. Table: whole non-fold-4 pool, mean ATE (m) per candidate (research/single_model/edge/classes.txt).

### Cited Findings
| class (truth used for labelling only) | n | base | f0 | G | T | M | G >3 m | G >5 m | G worse than base by >1.5 |
|--|--|--|--|--|--|--|--|--|--|
| static (hover) start | 363 | 0.61 | 0.60 | 0.60 | 0.59 | 0.59 | 6 (2%) | 4 (1%) | 1 |
| mid, v0 < 0.3 m/s | 59 | 1.42 | 1.09 | 1.15 | 1.14 | 1.21 | 14% | 5% | 5 |
| mid, v0 0.3-0.6 | 99 | 1.35 | 0.83 | 0.80 | 0.72 | 0.70 | 3% | 1% | 3 |
| mid, v0 0.6-1.2 | 121 | 2.42 | 1.10 | 1.10 | 1.10 | 1.11 | 11% | 6% | 5 |
| mid, v0 1.2-1.8 | 59 | 2.76 | 0.87 | 0.87 | 0.83 | 0.83 | 5% | 2% | 1 |
| mid, fast start v0 >= 1.8 | 25 | 4.73 | 2.39 | 2.39 | 2.53 | 2.53 | 20% | 12% | 2 |
| mid moving, axis <45 deg | 34 | 1.51 | 1.24 | 1.25 | 1.05 | 1.05 | 6% | 6% | 1 |
| mid moving, 45-90 | 104 | 2.92 | 1.04 | 1.04 | 0.97 | 0.98 | 10% | 3% | 3 |
| mid moving, 90-135 (lateral/back) | 137 | 2.09 | 0.93 | 0.92 | 0.97 | 0.95 | 6% | 3% | 6 |
| mid moving, >= 135 (reverse) | 29 | 2.28 | 1.64 | 1.64 | 1.59 | 1.59 | 14% | 10% | 1 |
| flat_fraction > 0.2 (textureless) | 9 | 4.33 | 3.85 | 3.85 | 1.64 | 1.88 | 44% | 33% | 0 |
| dark_fraction > 0.2 | 8 | 4.30 | 2.81 | 2.81 | 2.57 | 2.57 | 38% | 12% | 1 |
| path < 40 m | 167 | 0.99 | 0.73 | 0.73 | 0.73 | 0.73 | 4% | 2% | 4 |
| path >= 65 m (long) | 25 | 1.51 | 0.71 | 0.71 | 0.70 | 0.69 | 0 | 0 | 0 |
(axis angle = angle between mean true velocity over the first 0.45 s and the camera axis; fresh REPORT.md gives 17.6% of f0 flights above 3 m for starts more than 135 deg off the axis vs 6-8% elsewhere, consistent with the 14% here at >=135 deg.)

- Pool-wide G failure signature split (edge/signature.txt): scale < 0.75 and ATE > 3 m: 25 flights (20 mid, 13 slow starts); flat scene 26329 flights 8.0/8.5/5.9/4.9 m under G (T: 2.4/3.3/1.8/3.2).
- Mitigations tested are in Q4; effect on the classes: slow-start over-speed (SPD patch) fixes 150-00 (7.52 -> 0.44), 102816114-00 (3.13 -> 0.19), 157-11 (9.12 -> 3.86), 151-03 (12.5 -> 4.7), 176-07; reverse starts (strict flow override) fix 102344457-01 (3.82 -> 0.88), 123-00 (4.14 -> 0.73), 178-01 (3.39 -> 0.74), 150-03, 155-06, 176-07 (3.30 -> 0.61). Cheap but harmful: GATE_DISP 3.0 (pool +0.065 [+0.016,+0.126]), START_T 1.0 (search 1.255 vs 1.028, 9 flights > 5 m), contrast-adaptive thresholds alone (pool +0.016, adds 2 flights > 10 m).

### Inferences / classes with no usable evidence
- High yaw rate: every pool flight saturates (truth yaw rate max 62 deg/s median; the config cap is the generator's MAX_YAW_RATE 2.0 rad/s); no variation to test. Vertical, tilt: my truth-derived tilt and vertical-share columns did not follow the intended conventions (tilt_max came out 130-180 deg), so no conclusion is drawn on tilt (the briefing says 24 deg max measured; pool starts at near zero tilt). Frame-0 IMU window difference: f0's detector margin (static max |f| 8.69 vs 8.8; gate/NOTES.md) is covered by G's vision gate (gate s3/s4: static 0.872 -> 0.659 in the always-moving-detector world); not re-tested here. Intrinsics: sidecars list fov 120 with fov_range 15 for all flights (the guest reads fx per episode, e7aa-type variation is therefore represented), but I did not extract per-flight fx, so there is no fx-conditioned result. IMU bias outliers: not separately tested (|dba| < 0.15 in tails/NOTES.md).
- INFERENCE: the cheapest wins are classes (a) and (b), both are startup-velocity classes, consistent with the oracle experiments in tails/NOTES.md (velocity direction at start is the lever).

### Gaps
- No pool flight reproduces e7aa5aee's long 74 m + scale 0.57 + rotation 0.235 profile exactly; closest neighbours given above.

## Q4. Mitigation experiments (on G; search slice for selection, then the whole proxy pool)

### Takeaway
Base for all arms: edge/e.c = final/fgt.c with TAILS_DET 0, TAILS_KLT 0, VI_MODE 0 by default, which is bit-identical to the server G wasm (sha ac825145; search 1.028, val 0.543). Per instruction (G is the base; T/merged do not generalise) mitigations are switchable defines. Best combined arm CMBX = EDGE_SPD=1 + VI_MODE=1 + VI_COSMAX=-0.26. It improves search 1.028 -> 0.944, pool-wide 0.842 -> 0.786 and, replicate-averaged, 0.883 -> 0.830 (paired -0.053 [-0.081,-0.028] vs G3; 16 flights better and 1 worse by >1 m), but it does NOT remove the P(any > 5 m episode) problem (0.40-0.51 per 12-draw vs G 0.43-0.54). Not adopted yet (no preflight/causality/determinism run).

### Cited Findings
Arms (edge/run.sh; search = folds 0-2, n=119; val = fold 3 only for the finalist; "pool" = non-fold-4 selected + fresh, edge/run_fresh_e.py, tables ftable_*.json):
| arm | change (all #ifndef defines in e.c) | search mean (>5/>10) | val | pool mean (>3/>5/>10) | paired vs G, pool [95%] |
|--|--|--|--|--|--|
| g0 (= G) | defaults | 1.028 (4/0) | 0.543 | 0.842 (38/19/1) | = |
| spd1 | EDGE_SPD=1: at clone 4 compare flow speed to filter speed; if |v| > 1.8 v_flow + 0.25 scale v to flow speed, drop heading prior | 1.027 (4/0) | 0.529 | 0.823 (37/16/0) | -0.020 [-0.054,+0.013]; 2 worse / 4 better |
| spd2 | same, ratio 1.4, abs 0.15 | 1.054 (5/0) | | 0.830 (38/16/0) | -0.013 [-0.047,+0.024] (5 worse / 6 better; more side effects, e.g. 151-00 2.88 -> 6.23) |
| gd3 | GATE_DISP 3.0 (release more slow starts) | 1.033 (4/0) | | 0.907 (43/22/3) | +0.065 [+0.016,+0.126] REJECT |
| st1 | START_T 1.0 | 1.255 (9/1) | | not run | REJECT on search |
| ta | contrast-adaptive thresholds only (T part A) | 0.960 (2/0) | | 0.858 (39/19/2) | +0.016 [-0.054,+0.096] no gain on pool |
| vb | VI_MODE 1 with VI_COSMAX -0.26 (T part B only for reverse starts > 105 deg off axis) | 0.945 (4/0) | | 0.818 (34/18/1) | -0.024 [-0.046,-0.006]; 1 worse / 8 better |
| cmb (invalid) | EDGE_SPD + vb, guard bug (sp_cap blocked when vi_ok = 2): numerically identical to vb | | | | superseded |
| cmbx | EDGE_SPD=1 + VI_MODE=1 + VI_COSMAX=-0.26 (guard fixed: sp_cap runs unless vi_ok == 1) | 0.944 (4/0) | 0.529 | 0.786 (32/15/0) | -0.056 [-0.090,-0.026]; 1 worse / 12 better |
Chaos replicates (PIXEL_STD 1.515/DETECT_MIN_SCORE 1010 and 1.485/990), search means: G 1.028/1.223/1.293; vb 0.945/1.139/1.146; cmbx 0.944/1.133/1.153. Pool means: G 0.842/0.902/0.905, vb 0.818/0.879/0.865, cmbx 0.786/0.862/0.841. > 5 m counts: G 19/21/19, cmbx 15/20/15; > 10 m: G 1/4/3, cmbx 0/4/2. Val (n=25): G 0.543/0.571/0.521, cmbx 0.529/0.569/0.518 (no flight above 5 m). Static flights: cmbx static is bit-identical to G in replicate 0 (0.605); mid pool mean 1.080 (G) vs 0.968 (cmbx).
Proxy 12-draws, mean of 12-mean / P(any > 5 m) with p_mid 0.5 -> 1.0: G 1.035 / 0.43 -> 1.242 / 0.54; cmbx 0.997 / 0.40 -> 1.167 / 0.49; replicate-averaged G3 1.086 / 0.46 -> 1.348 / 0.56 vs cmbx3 1.044 / 0.43 -> 1.264 / 0.51; T 0.975 / 0.23 -> 1.255 / 0.36. Under the server-base ABC conditioning (p_mid 0.5): G 1.500 / 0.74, cmbx 1.445 / 0.73, T 1.173 / 0.27.

### Inferences
- INFERENCE: the speed-consistency patch is the correct response to the e7aa5aee signature (it fixes the slow-start over-speed flights) but it also breaks a few flights (102815859-00 0.32 -> 4.81, 159-01 0.24 -> 3.83, 150-01 0.91 -> 1.76); the flow-speed estimate (log-correlation 0.87, median error 0.16 m/s per tails/NOTES.md) is too noisy to trigger safely at 1.8x. Net effect is small and not significant alone.
- INFERENCE: the strict-reverse variant of T's flow override captures most of T's gains on reverse starts without adding T's new tails (pool > 10 m: 1 vs 2; but replicate 1 has 4 flights > 10 m for every G-family arm), so the >10 m tail count is mostly chaos in this family, not the patches.
- INFERENCE: neither arm lowers the 12-draw probability of a > 5 m episode materially; T remains better on that metric in the proxy (0.23-0.36) while having a similar mean; a combination of T part A (flat scenes, which drives T's low P(>5) at p_mid = 0) with cmbx is the untested next step (ta alone: pool +0.016).

### Gaps
- cmbx has not been through the preflight (ABI, determinism, causality, reset, no filled frames); peak fuel not checked; replicate means differ from G by less than the replicate spread of G alone (0.842-0.905), so a decision to ship should require a fresh-seed check. cmbx was chosen on search plus pool; the pool includes the fresh flights that other agents used as validation, so those are no longer clean holdout. Only val (3 replicates) was used as a final check; no sealed data touched.
- Patch: research/single_model/edge/edge.patch (diff of e.c vs final/fgt.c); only the EDGE_SPD block and the three default changes (TAILS_DET/TAILS_KLT/VI_MODE to 0) differ.
