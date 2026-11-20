# Fresh-flight validation (711 flights not in the 171 selected set)  -- IN PROGRESS

Pool: tmp/fresh_pool (symlinks to gen/raw-fast/bench zips minus selected/; 711 = 360 static 'fast-*' + 351 mid 'fastmid-*' approx; tags.json from sidecars).
Note: 101 distinct (catalog,scene) in fresh; many scenes also occur in the selected set (flights differ: seed/path, scenes not held out). 
Runner: research/single_model/fresh/run_fresh.py (+chain.sh); PNG cache off; ~3 flights/s with 32 workers (much cheaper than the 24 s CPU estimate).
Per-flight tables: research/single_model/fresh/table_<cand>.json/.csv ; outputs research/results/single_model/fresh_<cand>/.
Candidates: base (submitted gp_msckf.wasm), f0, gate (G, server wasm), tails (T), fgt (fgt_merged, sha 73c81ced).
Truth convention (verified on one flight): ground_truth_state = p(3) world, q(4) xyzw, v(3) BODY frame (R(q) v == dp/dt, err 8e-4), w(3); at frame 0 q=identity.
T_body_camera: camera z (optical axis) = body +x, so angle(v_body, +x) is the camera-axis angle.

## RESULTS (all 5 candidates + 2 GATE_DEBUG builds done; full detail in REPORT.md, tables table_<cand>.json/csv, analyze.py)
Fresh n=711 (356 static, 355 mid; 101 scenes, many shared with the selected set, so scene-disjoint it is not; flights are new).
mean / median / p90 / max | >3 / >5 / >10 m:
base  1.221 / 0.51 / 2.92 / 22.6 | 67 / 34 / 6
f0    0.812 / 0.44 / 1.46 / 12.5 | 36 / 16 / 1
gate  0.813 / 0.44 / 1.46 / 12.5 | 37 / 17 / 1
tails 0.835 / 0.44 / 1.44 / 16.0 | 34 / 20 / 3
fgt   0.834 / 0.43 / 1.44 / 16.0 | 35 / 21 / 3
Paired scene-bootstrap vs base: f0 -0.409 [-0.57,-0.28]; gate -0.408; tails -0.386 [-0.55,-0.24]; fgt -0.386. Between f0/gate/tails/fgt all CIs span 0 (tails-f0 +0.023 [-0.05,+0.10]).
Gains are real (all in mid starts: base 1.87 -> f0 1.05); static unchanged (0.57). Tails patch does not generalize: it helps dev/hssd groups (mid dev 1.22 -> 1.08/1.05) but adds new >10 m tails (130-00 16.0, 160-00 13.0, 3 total >10 vs 1) on seen/clean procthor.
Wrong direction (mid, angle to camera axis): >135 deg is the worst bin for every build (>3 m: base 20.6%, f0 17.6%, tails/fgt 14.7%, n=34); 0-135 bins 6-8% for f0. Tails reduce 135-180 only marginally; the 0.26-cos flow override is not a cure.
Gate: releases prior on 24 (G) mid flights, all with start speed <0.5 (max 0.46), never on a >0.5 m/s flight; fgt releases one at 0.62 m/s (100-00: 0.77 -> 4.22). G regresses vs f0 on only 2 flights (151-04 1.46->5.50, 3-01 1.03->3.65), improves 1; G ~= f0 (+0.001).
Detector vs sidecar: mid 355/355 moving; static 355/356 not moving, 1 false 'moving' (fast-ProcTHOR-Train-157-07, |f|=8.816 > 8.8; the gate released it). Static |f| max 8.816, 6 static >8.7: thin margin confirmed. 30 mid detected by force only, 5 by gyro only, 16 mid with true speed <0.1 m/s.
Frame-0 truth: v is body-frame; camera axis = body +x.

## CORRECTION (frame convention) -- supersedes the angle numbers above
The truth states are in the CAMERA frame (estimate.tum header: "camera k in camera 0 frame"), so the optical axis is +z of the truth velocity, not body +x.
Verified on 151-03, 64-01, 130-00: with states taken as camera-frame poses, IMU specific force reproduced from truth (R_cam T_body_camera^T f - a) gives a constant gravity vector (|g| 9.8-10.0, residual std 0.13-0.16); taken as body frame the residual is 5+ m/s^2 and |g| nonsense.
The first run (truth_feats_WRONGAXIS_bodyx.json) used body +x; truth_feats.json/REPORT.md are recomputed with +z. Earlier statements "v is body frame, camera axis = body +x" and the n=34 / 17.6% bin are WRONG.
Corrected, mid flights by angle(true start v, optical axis), >3 m rate (n): 
0-45 (182): base 19.2%, f0 6.0%, G 6.0%, T 4.9%, fgt 5.5% | 45-90 (100): base 7.0%, f0 5.0%, G 6.0%, T 6.0%, fgt 6.0% |
90-135 (55): base 21.8%, f0 16.4%, G 16.4%, T 14.5%, fgt 14.5% | 135-180 (18): base 38.9%, f0 27.8%, G 27.8%, T 22.2%, fgt 22.2%.
Conclusion: the wrong-direction effect survives and is cleaner (>90 deg: f0 ~19% >3 m vs 5.7% for <90, n=73 vs 282), but the worst bin 135-180 has only n=18; the tails patch reduces the >3 m rate in the >90 bins modestly (f0 14/73 -> T 12/73) while adding catastrophic outliers (16 m, 13 m) in the other bins.
Gate-release analysis unchanged (released flights all <0.5 m/s except fgt 100-00 at 0.62, angle now 38 deg).
Restricted to start speed >0.5 m/s (angle well defined), mid, n / >3 m count (base, f0, G, T, fgt) and f0 mean: 0-45 n=130: 32,8,8,6,7 (f0 0.89); 45-90 n=48: 7,5,5,5,5 (1.30); 90-135 n=31: 11,8,8,6,6 (2.16); 135-180 n=6: 4,4,4,2,2 (3.45).
