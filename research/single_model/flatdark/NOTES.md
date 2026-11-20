# flatdark: flat / dark / starved-coasting failure class (base B7 = fuel/adopted_c1_fbh_exact.c)  -- WORK LOG

Files: mkstress.py (stress table from sidecar audit + B6-diag stderr live-track counters; B6 diag == B7 behaviour), stress_all.json (855 flights = 711 fresh + 144 visible selected; fold-4 selected excluded by the scene-hash fold),
imgstats.py (pixel stats + per-cell Shi-Tomasi counts), mkfd.py -> fd.c (B7 + switchable FD_* arms, all off = B7), fdrun.py (build + run on pool_stress), pool_stress/ (167 symlinks).

## 1. Stress set (starved = median live tracks over the flight < 25, outcome independent; live counted per frame from the B6-diag stderr)
| subset | n | B7 mean | G mean | B0 mean | B7 >3 / >5 m |
|--|--|--|--|--|--|
| all (855) | 855 | 0.66 | 0.83 | 1.40 | 33 / 12 |
| STARVED live<25 | 31 | 2.93 | 3.06 | 4.62 | 14 / 7 |
| live<15 | 11 | 4.02 | 5.03 | 5.47 | 9 / 2 |
| live>=25 | 824 | 0.57 | 0.75 | 1.27 | 19 / 5 |
| audit flat or dark >0.05 | 86 | 1.63 | 1.64 | 2.53 | 17 / 7 |
| audit flat or dark >0.2 | 18 | 2.71 | 3.37 | 4.41 | 8 / 4 |
| flat/dark>0.05 but live>=25 | 59 | 0.89 | 0.84 | 1.36 | 3 / 0 |
| starved without flat/dark flag | 4 | 0.93 | | | 0 |
Starved flights are 3.6 % of the pool but 14 of 33 B7 tails (42 %) and 7 of 12 >5 m. Audit flat/dark fraction is a partial proxy only (starved flights: scenes 66104 (4 flights), ProcTHOR 85, 57, 64, 100, 154, 166, 176, 106, 0, 167). Primary stress set = the 31; extended pool (pool_stress, 167 flights) = live<40 or flat/dark>0.05, for no-harm checks. Fold split by scene hash: dev (folds 0-2) 115 pool / 23 starved, confirm (3-4) 52 / 8.

## 2. Diagnosis (pixel statistics, imgstats_1.txt, 12 flights, 12 frames each, 320x240)
* The starved scenes are physically featureless, not mis-tuned detection: ProcTHOR 85/64/166/100 frames are 45-67 % pure black (void outside the mesh / missing geometry, noise 0, uniform) next to uniform untextured gray/beige walls; 57/154 are bare beige walls (std 14-16, brightness 170-190, smooth shading gradient only) with an occasional door or floor tile; 66104 is a uniform gray wall/ceiling with a weakly textured floor patch (std 3, noise 0.4).
* Cells of the 10x6 grid with a Shi-Tomasi score above threshold (mean per frame, of 60): 66104: 2.1 @1000, 6.6 @500, 12.4 @250, 16.8 @100 (threshold DOES matter: 8x more cells at 250); ProcTHOR 85/64/166/100/57/154: 5-11 @1000 and 5-12 @100 (threshold does NOT matter: strong corners at wall/void/door edges or nothing); a normal flight has 24-40 cells.
* Mean gray: the "dark" flight (100-02) is dark only because it is half black void (mean 20, std 18); exposure is not the issue (A2/detbright result consistent).
* Failure is not only coasting: err/live time series of the 15 starved failures show 6 with error > 3 m already at t<10 s (startup divergence compounding), others drift slowly; B7 vs the stay-at-origin ATE (audit zero_motion_ate_m): equal on average (2.93 vs 2.98) and on 12 of 31 B7 is worse than not moving at all (e.g. 166-05 static: 6.3 vs 1.6; 85-01 4.1 vs 1.8).
* The velocity prior (SPEED_STD 0.5 m/s/axis, tau 2 s) is already always on, so a coasting speed shrinkage already exists; more shrinkage = health/ hard-clamp family (hurt).

## 3. Fix arms (fd.c = B7 + FD_* switches; control build with all off is bit-identical to B7 on all 167 pool flights)
Pool = pool_stress (167: 31 starved + near-starved/flat/dark), runs `research/results/single_model/fd_*`, tables table_fd_*.json, cmp.py. Chaos floor from two 1%-nudged B7 controls (ctl_r1/r2): starved31 mean 3.05 / 2.84 (B7 2.93), >3 m 15 / 14 (B7 14), >5 m 4 / 5 (B7 7), one >10 m in r1; so differences < ~0.3 m mean / +-2 tails are noise. Stress-set arms are single runs.
| arm (rationale) | starved31 mean, >3, >5 | dev23 mean, >3 | conf8 mean, >3 | ext pool nonstarved136 (>3) |
|--|--|--|--|--|
| B7 | 2.93, 14, 7 | 2.71, 11 | 3.57, 3 | 0.80 (5) |
| thr300 (FD_THR=300 while live<25: 8x more candidate cells on 66104-type floor texture) | 3.18, 16, 8 | 3.15, 11 | 3.27, 5 | 0.75 (2) |
| cell2 (second feature per cell while starved) | 3.08, 14, 7 | 3.02, 10 | 3.27, 4 | 0.75 (2) |
| fast1 (min_obs 2 + relaxed triangulation while starved, from frame 40) | 3.21, 12, 7 (+1 >10 m) | 3.27, 10 | 3.04, 2 | 0.82 (6) |
| fast2 (fast1 + clone every 2) | 3.04, 14, 7 (+1 >10 m) | 2.72, 8 | 3.95, 6 | 0.87 (6) |
| vs50 (horizontal speed-prior sd x0.5 after 5 s starved) | 2.94, 14, 5 | 2.78, 11 | 3.39, 3 | 0.80 (4) |
| vs30 (x0.3 after 3 s) | 3.19, 15, 6 | 2.98, 9 | 3.78, 6 | 0.98 (11) harmful |
Debug counters (thr300 on 66104): live tracks rise from 1 to ~10 but ATE does not improve (weak floor-texture tracks die within a few frames; most never reach 3 observations), consistent with the physical diagnosis: these scenes carry almost no observable structure.
## DECISION: nothing adopted. No arm lowers the tail count on both dev and confirm beyond the chaos floor; not taken to fresh-711 (stress-set gate failed first), no 3-replicate finalists, nothing ported to lc_b11.c, no preflight.
Open (not done, would need a real new front end rather than a tweak): edge/line features with 1-D (normal-flow) measurements; coarse-scale/phase-correlation global flow as a weak direction measurement; shading-gradient photometric tracking. Load on the machine was 165-180 throughout; runs used 12 workers x 2 concurrent.
