# bulk/ NOTES (bulk-error agent; base B6 = frontend/adopted_fbh.c; own copy bulk/b6bulk.c)
Scripts: decomp.py (STEP 1 decomposition, writes decomp_<run>.json), agg.py, agg2.py, vel_decomp.py, chk.py; ev.sh (171 sanity + fresh711 per arm), run_fresh_bk.py (tables in bulk/tables/<name>.json; results in results/single_model/bk_*).
## STEP 1 DECOMPOSITION (B6, fresh 711, saved estimate.tum of fresh_fe2_fbh; ATE reproduces 0.6184)
Frames: truth/estimate both camera-0 frame (verified, ATE identical). Gravity from IMU+truth R. Oracles are POST-HOC open-loop (replace increments, not closed-loop).
Typical = ATE in pooled p25-p75 (0.235-0.572), n=355 (188 static, 167 mid), mean 0.368, median 0.351.
| oracle replacement (typical flights) | mean ATE after | note |
|---|---|---|
| none | 0.368 | |
| yaw error removed (rotate increments by -yaw(t)) | 0.352 | -4% ; yaw rms 3.9 deg, end 5.6 deg |
| roll/pitch error removed | 0.373 | 0 ; tilt rms 0.76 deg |
| full rotation error removed | 0.357 | -3% |
| scale (Sim3 scale ~0.992; path ratio 1.10 is jitter) | 0.390-0.444 | no scale bias (along-track bias -0.009 m/s) |
| first 5 s replaced by truth + 5 s offset removed | 0.356 | -3% (static 0.370, mid 0.340) |
| first 10 s likewise | 0.312 | -15% |
| constant per-flight mean offset removed | 0.255 | 48% of MSE is a constant offset (built up 3-10 s) |
| vertical error removed | 0.348 | vertical = 10% of MSE |
| horizontal increment error removed (along+lat) | 0.102 | |
Error vs time (median |e|, typical): 1 s 0.04, 2 s 0.06, 3 s 0.09, 5 s 0.17, 10 s 0.17, 20 s 0.25, 30 s 0.31, 40 s 0.36, 59 s 0.43. MSE share by time bin 0-5/5-10/10-20/20-40/40-60 s: 6/4/9/32/50 %.
High-frequency (<2 s) error rms 0.06; low-frequency 0.35; 1 s RPE 0.145. Rigid alignment: SE3 0.353 -> 0.216, rotation-only (3.8 deg) 0.310 -> error is NOT a rigid transform; it is a slow horizontal position wander (~0.5 %% of path, ~sqrt(t)).
Path ~45 m in ~4.7 m extent, 60 s for all flights, so per-metre and per-second drift are not separable across flights (duration constant).
=> DOMINANT: slow horizontal position drift accumulated over the whole flight (no loop closure/position anchor), not yaw, tilt or scale. Yaw/tilt/scale oracles are worth 0-4 %. Startup contributes ~15% (3-10 s) for the median.
Correlations across flights: ate vs tilt_rms 0.56, vs yaw_rms 0.49, vs |log path ratio| 0.61 (these are co-symptoms, not causes in oracle tests).
IMU noise in the simulator matches the config exactly (per-sample white: gyro 0.070, accel 0.280 measured by differencing); filter already uses these.
Decomposition refinements: random-walk-like horizontal wander, sigma ~0.054 m/sqrt(s) after 5 s (e^2 = 0.17^2 + 0.0029 t); equals ~0.04 m/s velocity error with 1 s correlation (~5% of 0.75 m/s speed). Increment-error removed along-track only or lateral only does not help (error direction is not tied to motion direction); removing both horizontal components leaves 0.10.
Ranking of levers by the oracle tests: (1) horizontal drift accumulation over 20-60 s (82% of MSE) -> needs better per-window relative motion (longer baselines / more constraints), persistent landmarks, or loop closure; (2) startup 3-10 s offset (~15% for the median); (3) yaw 4%, scale ~0, roll/pitch ~0.

## STEP 2/3 ARMS (fresh 711; dev = folds 0-2 n=475, confirm = folds 3-4 n=236; ref B6 0.618/0.351 (dev 0.608, confirm 0.640)); build b6bulk.c, control bk_ctrl bit-identical to B6 (711/711 same ATE 0.618372)
| arm | defines | fresh mean/median | dev d | confirm d | >3/5/10 | peak fuel (non-exact) |
|---|---|---|---|---|---|---|
| bk_ctrl | - | 0.618 / 0.351 | 0 | 0 | 21/8/0 | 24.5 M |
| bk_w10 | MAX_CLONES=10 MAX_OBS=10 | 0.722 / 0.324 | +0.113 [+0.03,+0.22] | +0.086 | 35/13/2 | 81.7 M |
  w10: median and p25 improve (0.351->0.324, 0.235->0.216), static confirm -0.039 (sig.), but 56 flights >0.5 m worse vs 29 better; mean is carried by +105 m total on ~14 mid flights (ProcTHOR), the other 697 flights improve by -0.04 on average (static -0.033, mid -0.060). => bulk gain, tail loss; try window growth only after the startup (WIN_BIG/WIN_T0).
| bk_wd10 | WIN_BIG=10 WIN_T0=10 (window 6 clones for 10 s, then 10) | 0.625 / 0.327 | +0.015 | -0.011 | 23/10/1 | 60.9 M | tie on mean, median -0.024, p25 0.222 |
| bk_anch1 | ANCH_MODE=1 (KLT re-registration to last clone image, 1.5 px) | 0.656 / 0.354 | +0.026 | +0.062 | 24/6/1 | 27.1 M | REJECTED |
| bk_anchd | ANCH_MODE=1 ANCH_DROP=1 | 0.621 / 0.352 | -0.025 | +0.059 | 23/7/0 | 27.1 M | no effect, REJECTED |
| bk_iter2 | ITER_UPD=2 (re-linearized Gauss-Newton stacked MSCKF update, 2 iterations) | 0.545 / 0.319 | -0.077 [-0.140,-0.012] | -0.067 [-0.164,+0.027] | 15/8/1 | 40.4 M | paired all -0.074 [-0.127,-0.020]; mid dev -0.148; static dev -0.009; 57 flights better >0.5 m vs 23 worse; new >10 m flight = fast-ProcTHOR-Train-100-02 (static, B6 4.28 -> 10.65, a known chaotic flight; w10 also blew it up) ; 171 search 0.875 (B6 0.950), val 0.556 (B6 0.442, n=25) |
Method note: ITER_UPD=k relinearizes feature_rows (re-triangulation, Jacobians) at x0 (+) dx_i, uses r_eff = r_i + H_i dx_i with the prior P (standard IEKF), final iteration applies the normal update with the true prior; gate uses innovation w.r.t. prior. all-off bit-identical (bk_ctrl).
Revisit statistics (truth poses, typical flights, frames after 10 s with a >=5 s older view within distance/angle): (0.5 m,25 deg) 17%, (1 m,35 deg) 37%, (1.5 m,50 deg) 57%. MAP_MODE (loop-closure-lite: map points of long tracks, ZNCC re-observation at half resolution, known-landmark updates) implemented; ~25-30 accepted map updates per flight at default thresholds.
| bk_iter3 | ITER_UPD=3 | 0.552 / 0.339 | -0.074 [-0.129,-0.024] | -0.052 [-0.134,+0.029] | 20/3/0 | 56.3 M | like iter2, fewer >5 m (3), more fuel |
| bk_gyro056 | GYRO_NOISE=0.056 (autoloop's best single sensitivity) | 0.641 / 0.343 | +0.027 | +0.016 | 27/9/0 | 24.7 M | REJECTED (does not generalize, as before) |
| bk_map1 | MAP_MODE=1 (defaults: age 200 fr, ang 30, try 6, zncc 0.90) | 0.565 / 0.281 | -0.052 [-0.067,-0.037] | -0.057 [-0.073,-0.044] | 22/9/0 | 24.8 M | paired all -0.054 [-0.065,-0.042]; static dev -0.073 conf -0.081; mid -0.03; median 0.351 -> 0.281, p25 0.193 p75 0.495; no tails change; 171: search 0.895 val 0.375 |
| bk_map2 | MAP_MODE=1 MAP_AGE=100 MAP_ANG=40 MAP_TRY=12 MAP_ZNCC=0.85 | 0.556 / 0.277 | -0.058 [-0.080,-0.030] | -0.071 [-0.105,-0.044] | 21/8/0 | 30.4 M | paired all -0.062 [-0.081,-0.042]; static conf -0.092; median 0.277, p25 0.180; 171: search 0.874 val 0.392 |
=> MAP (loop-closure-lite) is the first lever aimed at the dominant component (slow drift): bulk (median) -21 %, tight CIs (low variance, unlike window/iterated arms), no new tails. ITER_UPD=2 gives -0.07 on the mean mostly on mid (startup/tails). They act on different parts => combine.
| bk_wd10i | WIN_BIG=10 WIN_T0=10 ITER_UPD=2 | 0.537 / 0.316 | -0.084 | -0.075 | 17/8/0 | 101.5 M | ~ iter2 alone; window adds nothing, REJECTED (fuel) |
| bk_m4 | map2 + AGE 60, COOL 30, TRY 20, S 10 | 0.556 / 0.277 | -0.059 | -0.069 | 23/8/0 | 45.1 M | same as map2 (yield saturated), more fuel |
| bk_m5 | map2 + SIG0 0.2 SIGD 0.1 (looser map-point std) | 0.555 / 0.275 | - | - | - | - | same as map2 (insensitive to sigma) |
| bk_i2map | ITER_UPD=2 + map2 | 0.486 / 0.259 | -0.132 [-0.201,-0.050] | -0.133 [-0.234,-0.038] | 16/7/2 | 40.4 M | p25 0.173, p75 0.413; effects add; two >10 m flights (chaotic, see below); 171: search 0.854 val 0.478 |
Decomposition of i2map fresh estimates (decomp_bk_fresh_i2map.json): typical median |err| 5 s 0.17, 10 s 0.17, 20 s 0.22, 40 s 0.24, 59 s 0.26 (B6: 0.43 at 59 s) -> the late-time drift is largely removed by the map; what remains is the 3-5 s takeoff offset (static flights: pos err 0.03 at 2 s -> 0.2 at 5 s, vel err 0.1-0.17 m/s while accelerating 0 -> 1 m/s in 1 s) and a floor of ~0.1 m/s velocity error (10% of speed) => o_start10 oracle now -14%.
Catastrophic flights in iterated arms: fastmid-104348361_171513414-01 (B6 1.14, iter2 6.4 [jump to 7 m between 12 and 20 s during 1.8 m/s motion], i2map 11.7, iter3 0.92, map2 0.94) and fast-ProcTHOR-Train-100-02 (B6 4.28, iter2 10.65, iter3 2.85): path-dependent divergences; ITER_BACK (fall back to the plain update when the relinearized residual grows) added as a safeguard.
| bk_m3 | map2 + SIG0 0.05 SIGD 0.03 | 0.562 / 0.281 | -0.055 | -0.059 | 23/6/0 | 30.2 M | same |
| bk_m6 | map2 + MAP_N=512 MAP_SUB=1 MAP_PIX=1.5 | 0.550 / 0.273 | -0.073 | -0.057 | 21/7/0 | 30.0 M | tiny gain |
| bk_m7 | map2 + MAP_NEAR=1 (a live track near the prediction identifies the feature; match only +-3 half-res px around it) | 0.547 / 0.273 | -0.073 [-0.089,-0.058] | -0.070 [-0.091,-0.051] | 22/7/0 | 27.6 M | best map-only; paired all -0.072 [-0.085,-0.060] |
| bk_i2b | ITER_UPD=2 ITER_BACK=1.0 (fall back to the plain update when the relinearized stacked residual grows) | 0.513 / 0.323 | -0.117 [-0.177,-0.067] | -0.080 [-0.190,+0.021] | 11/4/0 | 40.4 M | safeguard halves >3 m (21->11) and >5 m (8->4), no >10 m: the iter2 divergences were Gauss-Newton overshoots |
Velocity-state bias (i2map typical flights): est speed / true speed = 0.93 during takeoff (3-6 s), 0.97 steady (rms speed err 0.08 m/s, direction err 3.1 deg). Prior shrinkage suspected (SPEED_STD 0.5) -> bk_spd075 / bk_spd15 queued.
## NEAR-MISS BAND (B6 fresh flights with ATE 1.5-3 m: n=33, 28 mid / 5 static; mean 2.10)
Error is a STARTUP OFFSET, not drift: median |err| 1.49 m at 2 s, 1.86 at 5 s, 1.84 at 10 s, 1.94 at 59 s (flat plateau); offset at 5 s 1.8 m. Oracles (typical-band mean ATE 2.10): yaw removed 2.08, roll/pitch 2.10, full rotation 2.08 (3/33 flights cross below 1.5), scale (Sim3) worse (Sim3 scale 0.85: est too large on some), first-5 s truth+offset removal 1.47 (16/33 cross below 1.5), first-10 s 1.29 (22/33 below 1.5), constant offset removed 0.92 (28/33). => yaw/tilt/scale do NOT push flights over 3 m; the 3-5 s startup state (velocity/scale lock-in) does. Slow drift contributes little to the band.
## PERSISTENCE vs B6 (fresh 711; >3 m count arm/B6; flights <=3 -> >3 (new fails); fixed (>3 -> <=3); previously <1.5 m now >3 m)
iter2 15/21: 6 new, 12 fixed, 4 clean->fail | iter3 20/21: 11, 12, 5 | i2b (iter2+BACK) 11/21: 4, 14, 4 | map2 21/21: 1, 1, 0 | m7 22/21: 1, 0, 0 | m6 21/21: 2,2,0 | i2map 16/21: 7,12,4 | wd10 23/21: 4,2,0 | wd10i 17/21: 7, 11, 3 | anchd 23/21: 10, 8, 7.
Map arms are persistent/safe (<=2 flights change, band 33->27) but do not move the startup-driven band; iterated update re-rolls tails (fixes ~12-14, newly fails 4-7: chaos re-roll plus real fixes; ITER_BACK reduces new fails and total >3 m to 11).
| bk_spd075 | SPEED_STD=0.75 | 0.679 / 0.347 | worse (+0.06) | | | | REJECTED (the velocity prior is not the cause of the speed shrink; weaker prior hurts) |
| bk_i2mb | ITER_UPD=2 ITER_BACK=1.0 + map2 + MAP_NEAR=1 (FINALIST) | 0.451 / 0.259 | -0.188 [-0.249,-0.137] | -0.126 [-0.220,-0.035] | 14/4/0 | 40.4 M | paired all -0.167 [-0.216,-0.121]; p25 0.172 p75 0.431; static dev -0.121 conf -0.083; mid dev -0.256 conf -0.166; vs B6: 6 newly >3 m, 13 fixed, 3 clean(<1.5)->fail; band 1.5-3: 22 (B6 33); 171: search 0.773 (B6 0.950) val 0.413 (0.442) |
