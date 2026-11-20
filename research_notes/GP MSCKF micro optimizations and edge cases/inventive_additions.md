# Inventive additions to gp_msckf (gate build G as base)

Base/reference: final/submit/gate.c (G). Search = folds 0-2 (n=119), val = fold 3 (n=25); fold 4 never opened. Fresh = 711 never-tuned flights (fresh/tags.json), scored with inventive/fresh_run.py (writes only inventive/ and results/single_model/inv_fresh_*).
Source: `inv_g.c` = gate.c + switchable blocks (all #ifndef, default 0 = gate.c exactly; `inv_gbase_r0` reproduces G: 1.028/0.543). `adopted.c` = inv_g.c with INV_HOLD=1, INV_VZ=0.3, INV_LAT=0.5; `adopted.patch` = `diff -u final/submit/gate.c adopted.c`.
(First arms were run on fgt.c = inv.c; fgt is not used as base any more because the fresh run shows tails/fgt do not generalize.)
Tools: run.sh, rep.sh (3 chaos replicates: PIXEL_STD/DETECT_MIN_SCORE 1% nudges), cmp.py (-r: 3-replicate mean vs inv_gbase), summ.py, flt.py, fresh_run.py, smooth_test.py.

## Reference noise
G replicates (search): 1.028 / 1.223 / 1.293 (mean 1.181; mid 1.34/1.70/1.84, static 0.678/0.687/0.675). Static is nearly deterministic, mid is chaotic: single runs of mid-affecting arms must be compared to the replicate mean (mid 1.63), not to r0.

## Idea list (22) and verdicts
Targets: S static tails/floor, W wrong-direction starts, D dark/flat, L long-flight drift, F 0.5-0.6 m floor. Size = lines of C; fuel cost negligible unless noted.
| # | idea | rationale (physical) | target | size | result |
|---|---|---|---|---|---|
| a | HOLD: first 0.4-1.0 s of hover starts: gyro window mean = bg, specific force = R^T g + ba as pseudo-measurements (frames before 0.4 s skipped: truth |w| decays 0.12->0.03 rad/s) | at rest the gyro reads bias, accel reads gravity | S/F | 25 | ADOPTED. search static 0.678 -> 0.622 (static is deterministic, r1/r2 0.687/0.675), err@2 s 0.13 -> 0.04 m; fresh static -0.071 [-0.151,+0.008] |
| j | tighter initial bias sd (accel 0.06, gyro 0.006) | known sim ranges | S | 1 | static 0.621 but sd < true uniform sd (0.115): overconfident, redundant with HOLD; rejected |
| b1 | speed hinge |v|<=2.0 | over-extension tails | 8 | rejected: 1.115 (mid 1.50, >5 m 7) |
| b2 | speed shell |v|~0.9+-0.5 after 3 s | weak vision | 8 | rejected: 1.215, static 0.643 |
| c | body lateral velocity N(0,0.5^2) (non-holonomic, slip RMS 0.52) | planner faces travel direction | W/L | 8 | ADOPTED with vz: see C1 |
| i/vz | world vertical velocity prior sd 0.3 (|vz| RMS 0.30) | planner altitude hold | L | 1 | ADOPTED with lat |
| d | gyro->initial lateral velocity: v_x(cam) = 0.73 (w_y - w_z) from the first IMU window (truth regression on search mid, LOO resid 0.34 vs 0.50, forward axis not predictable) | yaw lag / bank coupling, wrong-direction help | W | 12 | rejected: 3 replicates 1.209 vs 1.181 (mid 1.68 vs 1.63), more >5 m in rep 0 |
| e/f | vertical-acceleration pseudo-measurement a_z = (R(f-ba))_z - g ~ 0 (tilt/ba_z link) | level flight | tilt | 10 | rejected: 1.360, 2 flights >10 m (ba_z/tilt confounded, noisy) |
| g | starvation / cov-scheduled prior | | | | not re-run: health NOTES (starve -0.27 alone, ~0 on top) |
| h | startup prior fade (mean decays over 1 s after 2 s) | smooth release | | 4 | rejected: 1.155 (mid 1.58 vs 1.63 mean: neutral), notes: START_T 1/4 already worse |
| k | cruise-direction prior after startup (camera-axis mean 0.4) | planner cruise | | 8 | rejected: mid 1.615 (= ref mean), static unchanged |
| l | remove extrinsic transforms | pure permutation | fuel only | | not tested (no accuracy effect) |
| m | causal output smoothing (EMA) | jitter | | 0 C | rejected offline on saved tracks: raw 0.845, EMA .5 0.848, .3 0.860, .15 0.922; second-difference jitter only 2.5 cm |
| n | iterated EKF / relinearize | large corrections | | 30+ | not implemented (needs prior-mean shift bookkeeping) |
| o | Huber down-weight of features with chi2 in (gate, 4 gate) instead of reject | soft gating | | 5 | rejected: 1.375, static 0.84, val 0.75 |
| p | heading-aligned anisotropic prior | | | | = c + vz (body lateral + world vertical) |
| q | restart on persistent NIS | | | | rejected in health (static +0.07) |
| r | ZUPT also asserts gyro = bias | rest | S | 6 | rejected: static 0.696 (rest detection can include slow rotation) |
| s | MAX_DEPTH 12 m (indoor) | far features low parallax | | 0 | rejected: 1.216 (mid 1.68, >10 m 1) |
| t | yaw-lag lateral prior from yaw rate (corr with w_z) | | W | | the truth check (v_x vs w_y 0.71) led to d; fails in the filter |
| u | accel-bias z prior from long-window thrust | | | | merged into e |
Not done: wrong-direction-specific fix; ideas a-d only reduce the lateral part; flow sign (VI) was already shown not to generalize (fresh/REPORT.md).

## Arms table (search, single run unless stated; ref G reps 1.028/1.223/1.293)
| arm | search | static | mid | >5 / >10 | val |
|---|---|---|---|---|---|
| inv_gbase_r0/r1/r2 | 1.028/1.223/1.293 | 0.678/0.687/0.675 | 1.339/1.700/1.844 | 4,7,9 / 0,2,1 | .543/.571/.521 |
| hold | 1.001 | 0.622 | 1.339 | 4/0 | .487 |
| gyv (3 reps) | 1.131 (mean 1.209) | 0.678 | 1.533 | 6/0 | .665 |
| az | 1.360 | 0.649 | 1.991 | 8/2 | .584 |
| vz 0.3 | 1.064 | 0.570 | 1.503 | 3/0 | .554 |
| lat 0.5 | 1.018 | 0.568 | 1.418 | 4/0 | .554 |
| shell1 / shell2 | 1.115 / 1.215 | 0.684 / 0.643 | 1.498 / 1.723 | 7/0, 7/1 | |
| fade 1.0 | 1.155 | 0.678 | 1.580 | 7/1 | |
| huber 4 | 1.375 | 0.841 | 1.850 | 7/1 | .749 |
| cruise 0.4 | 1.174 | 0.678 | 1.615 | 6/0 | |
| zuptg | 1.036 | 0.696 | 1.339 | 4/0 | .517 |
| bias init tight | 1.129 | 0.621 | 1.581 | 5/0 | |
| depth 12 | 1.216 | 0.693 | 1.681 | 6/1 | |
| vz+lat | 1.051 | 0.584 | 1.466 | 3/0 | .559 |
| **C1 = hold+vz+lat, 3 reps** | 1.070/1.042/1.126 (mean 1.079 vs 1.181) | 0.595 vs 0.680 | 1.510 vs 1.627 | 3,3,4 / 0,0,1 vs 4,7,9 / 0,2,1 | .540/.563/.509 (0.537 vs 0.545) |
C1 paired (3-rep means, search): all -0.102 [-0.256,+0.040], static -0.085 [-0.270,+0.074], mid -0.118 [-0.316,+0.076]; val -0.008 (not contradicted).

## Fresh (711 flights, G 0.813 -> ...)
| build | all | static | mid | >5 | >10 |
|---|---|---|---|---|---|
| G | 0.813 | 0.573 | 1.054 | 17 | 1 |
| hold | 0.777 (d -0.036 [-0.076,+0.002]) | 0.502 (-0.071 [-0.151,+0.008]) | 1.054 (identical by construction) | 16 | 1 |
| vz+lat | 0.787 (-0.026 [-0.089,+0.041]) | 0.581 (+0.008) | 0.995 (-0.059 [-0.163,+0.039]) | 10 | 0 |
| **C1 (adopted)** | **0.733 (-0.080 [-0.144,-0.022])** | **0.471 (-0.102 [-0.171,-0.041])** | 0.995 | **8** | **0** |
Search-slice static gains of vz/lat (-0.11) did not reproduce on fresh statics (+0.008); their fresh value is the mid tail reduction (>5 m 14 -> 7).

## Adopted: C1 (adopted.c / adopted.patch vs gate.c)
1. HOLD (hover starts only: `moving`=0): while t - t_start < 1.0 s, after 0.4 s, and while the frame-mean |gyro| < 0.12 rad/s and ||f|-g| < 1 m/s^2: pseudo-measurements gyro_mean = b_g (noise 0.07^2/n) and f_mean = R^T[0,0,g] + b_a (noise 0.28^2/n; Jacobian [R^T g]x on tilt, I on b_a). Assumption: the first second of a hover start is rest (a hold) and gravity is 9.81. Fails if a start is not at rest (the |gyro|/|f| checks switch it off), if g differs, or if the detector calls a moving start static.
2. VZ: world vertical velocity prior sd 0.3 m/s (was 0.5, per-frame whitened with tau 2 s) in the steady-state prior. Assumption: planner holds altitude (|vz| RMS 0.30, p99 1.0). Fails for climbing/stair flights.
3. LAT: body-lateral (y) velocity ~ N(0, 0.5^2), tau 2 s, after the startup prior. Assumption: quadrotor faces its travel direction (lateral RMS 0.52, p50 0.13 m/s). Fails for sideways/strafing flight or heavy-slip planners.
Fuel: three tiny updates per frame (3x1 rows), no measurable change expected; peak fuel not re-checked on the server.

## Findings worth keeping
- The initial hover window is not at rest for 0.4 s (truth |w| 0.12 -> 0.03 rad/s, |v| 0.06 -> 0.02): a hold pseudo-measurement from frame 1 is wrong; the first version (switch off at gyro norm 0.15) deactivated in 84/84 flights at the first frames.
- Camera-frame truth at the first frames: lateral velocity correlates with yaw rate (0.71) and roll rate (-0.56), forward velocity with pitch rate (0.45) but the forward component is not predictable out of sample; the regression-based mean did not help in the filter.
- Mid-start velocity angle off the camera axis is broad (quartiles about +-92 deg at frame 0 when measured correctly: forward is axis 2 of the camera-frame truth).
