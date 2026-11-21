# lateinit: diagnose B16 >1 m flights; late init / startup fixes (work log, newest at bottom)

Base: tailcap/tc_b16.c (B16, wasm sha 1108dcfb...). Working copy li.c = tc_b16.c + define-switched arms (all default off).
Tools: diag.py (per-flight error decomposition from estimate.tum vs truth), ts.py (time series of one flight),
grav.py (filter gravity-direction error from LI_LOG lines), licmp.py (closed-form solution vs filter vs truth),
chk.py (closed-form model check with truth), runpool.py (build + run on small pools), runset.py / summ.py (copies of
tailcap's, tables in lateinit/tables, results research/results/single_model/li_<name>_r<k>).
Pools: pool_bad = the 27 dev flights (fresh f0-2 + selected search) with B16 r0 ATE > 1 m; pool_good = 40 random dev flights < 0.5 m.

## 1. Diagnosis (B16 r0, dev = fresh f0-2 + sel search, n=594, mean 0.399; 27 flights > 1 m carry 28% of the total)
Counterfactual means on dev (diag_tc_b16r_r0_all.json): remove best rigid translation 0.261; yaw+translation (4-DoF) 0.241;
yaw-only about the origin 0.375; zero the error of the first 3 s (offset frozen afterwards removed) 0.380 (min with actual 0.350);
first 5 s 0.373 (0.338). => a rigid offset is the largest component (0.40 -> 0.26), but only ~1/4 of it is acquired in the first
3-5 s; perfect start-up handling is worth ~0.03-0.06 m on dev mean (8-15%). Yaw-only alignment helps little.
Bad flights (27): 19 mid starts, 8 static. Two groups:
* start-up group (~8: 106878858-01, 103997478-00, 176-01, 176-05, 74-02, 151-03, 6-00, 107734158-02): velocity error 1.4-2.5 m/s
  at t=1 s, error 2-3 m by 3 s, then a rigid offset; ate_pre3 (start-up error alone) 1.7-2.8 m.
* later-drift group (static 100-02, 85-01, 57-00, 154-x, starved 106366104-x, mid 143-01, 176-06): offset acquired after 5 s
  (vision failure / starved scenes); not a start-up problem.
Gravity (tilt) error of the filter frame (LI_LOG, grav.py): bad mid flights 3-14 deg at 1.5 s, 2-8 deg at 2-3 s, some never
converge (106878858-01 5 deg at 59 s; 103997478 2 deg; 0-01 2 deg); good mid flights converge to ~1 deg by 1.5 s (median 0.5).
Mechanisms seen in the logs (TC_LOG + LC_DEBUG + LI_LOG on pool_bad):
* the net update at frame 6 (0.3 s) moves the tilt by 3-23 deg (V-TH cross-covariance), in good and bad flights alike; it
  makes tilt worse in ~12/19 bad and ~9/18 good mid flights (tilt err 0.05 s vs 0.5 s);
* FALSE GATE ZUPT: the movement gate (GATE_MODE 1) releases + forces a ZUPT at 0.4 s when the first two clone pairs have < 2 px
  disparity (distant scene) although the drone moves (0.4-0.5 m/s; the net said 0.45 m/s): velocity -> 0 with sd 0.02 and a
  14-22 deg tilt jump (176-01, 103997478-00); then IMU-only drift at ~2 m/s^2 for 1.5 s (no MSCKF updates accepted before the
  first window slide at 1.2 s: nis 0, Pv grows 0.03 -> 0.8) until the pv25 re-anchor at 1.85 s;
* pv25 re-anchor (1.85 s) fixes velocity but not tilt; the velocity drifts again (0.6 m/s^2 in 176-01).
Rotation error is mostly yaw drift: flights with rotation RMSE > 0.1 rad (48 of 594, mean ATE 1.13, 23% of total) have
median |yaw(40 s)| 0.15 rad vs 0.034 overall; relative tilt at 10 s is 0.01-0.014. log ATE correlates with log velocity RMSE
(r 0.84) more than with log rotation RMSE (0.63). Server bad episodes (rotation 0.11-0.18 rad, velocity 0.5-0.6 m/s) look like
this yaw-drift + velocity-offset group.

## 2. Closed-form late init (li_module.c, LI_MODE=1 observe / 2 apply)
Kaiser/Martinelli bearing-cross-product LS for v0 and g0 over frames 0..30 (1.5 s), depths eliminated per feature (Schur),
|g| refinement, depth re-weighting, outlier drop, optional net velocity prior (LI_NET). Model check against truth (chk.py):
preintegration matches truth positions to ~2-9 cm at 1.4 s (accel bias z and gyro bias not modelled: rotation error 1.3 deg at
1.4 s). Accuracy at 1.5 s (licmp.py, 19 bad + 18 good mid flights): CF tilt error 0.4-10 deg (good flights median ~2.5 deg vs
filter ~1 deg); CF velocity error typically 2-5x the filter's; CF is better than the filter only where the filter was corrupted
(176-01: 1.8 vs 13.8 deg; 176-05: 3.3 vs 13.2; 157-03: 2.6 vs 10.3) but a CF-vs-filter disagreement gate cannot tell those from
cases where CF is wrong (106366410-02 10.4 vs 1.4; 143-01 7.9 vs 2.8; 74-02 8.3 vs 2.9). Free LS (no |g| constraint) on 155-01:
tilt 0.2 deg but v0 error 0.32 m/s; truth (v0, g0) has 8x the LS cost -> unmodelled gyro/accel bias and 1.5 s of weak
excitation dominate; 1-sigma estimates (0.01-0.04 m/s) are far too optimistic. Not usable as a re-anchor in this form.

## 3. Oracle / counterfactual headroom (dev, B16 r0)
* Perfect INITIAL tilt (oracle truth gravity at init, oracle/oracle_table.h, sel144 only, li_oracle.c; analysis only):
  sel search 0.595 -> 0.567 (tilt sd 0.15) / 0.563 (sd 0.03); mid 0.753 -> 0.70; val 0.374 -> 0.34. => ~5 % headroom.
* Remove the yaw error along the path (rotate every position increment by -yaw(t), yawcf.py): dev 0.399 -> 0.394;
  remove the whole rotation error: 0.403. => heading/rotation is NOT the cause of the position error (velocity is estimated in
  world axes; rotation error is a correlate of bad vision, not a driver). Heading fix (candidate c) not pursued.
* Remove first-3/5-s error: 0.380/0.373 (see 1). Start-up error total headroom ~0.03-0.06.

## 4. Arms on li.c (all OFF = B16: li_off_r0 sel144 ATE and estimate.tum bit-identical 144/144). 1 rep, B16r r0 paired; dev = fresh f0-2 + sel search (594), conf = fresh f3-4 + sel val (261)
| arm | dev mean (d, 95% CI) | dev >1/>3/>5 | conf mean (d, CI) | conf >1/>3 | better/worse >0.3 (dev; conf) | peak |
| B16 | 0.399 | 27/9/2 | 0.362 | 11/1 | | 20.2 M |
| gn3 = LI_GATENET=0.3 (no gate-forced ZUPT once the net predicted > 0.3 m/s) | 0.390 (-0.009 [-0.021,-0.001]) | 25/8/2 | 0.360 (-0.002 [-0.006,0.000]) | 11/1 | 4/0; 1/0 | 20.2 M | 7 flights change
| vd1 = net updates act on velocity only (V cross-cov cleared) | 0.504 (+0.104) | 48/15/9 | 0.554 (+0.193) | 23/9 | 18/56; 5/23 | REJECT: the net's tilt coupling is valuable
| w1 = restart MSCKF window at net re-anchor | 0.416 (+0.017) | 36/8/1 | 0.378 (+0.016) | 11/2 | 6/15; 3/5 | REJECT
| w2 = shift clone positions by dv x age at re-anchor (pools only) | bad27 2.50 -> 2.90, good40 0.262 -> 0.295 | | | | | REJECT
| vd2 = ZUPTs act on velocity only | 0.392 (-0.007 [-0.024,+0.009]) | 29/8/1 | 0.362 (0.000) | 9/1 | 12/12; 5/3 | 20.2 M | neutral, no
| cf6 = closed-form late init applied at 1.5 s when tilt differs > 6 deg (LI_MODE=2 LI_DTH=6) | 0.535 (+0.136) | 69/14/3 | 0.520 (+0.158) | 27/5 | 4/79; 3/35 | 36.6 M | REJECT

## 5. Finding: the pv25 re-anchor never fires on STATIC starts
tc_monitor's pv trigger requires `moving` (the start-type flag), so a hover start that later flies into a starved/flat scene is
never re-anchored even with sqrt(tr Pv) > 0.25 for 57-95 % of its frames (bad static dev flights: 100-02, 85-01, 106366104-00,
57-00, 154-04: 0 fires each; mid flights in the same scenes fire up to 12 times). Arm LI_PVS=1 LI_PVS_T0=3.0 (trigger also for
static starts after 3 s). Pools (1 rep): bad27 2.499 -> 2.203; static bad: 100-02 5.76 -> 1.57, 85-01 4.19 -> 2.63, 57-00 2.25 ->
0.48, 154-04 1.48 -> 0.43, 155-00 1.09 -> 0.42, 154-09 1.61 -> 1.81, 106366104-00 3.51 -> 4.53 (starved, live tracks ~1);
good40 0.262 -> 0.260. Full dev/confirm runs queued (pvs3, pvs1).
