# tailcap: tail-capping mechanisms on B11 (work log; written early, updated as I go)
Base = learned_c/lc_b11.c (copy tc_base.c; build with fuel/CMakeLists_c1.txt reproduces staged wasm sha 38f9aab0...bd37f, verified).
Tools: sets.py (honest sets), runset.py (build+score sel144 / fresh711 with replicates; tables/<name>_r<k>.json), truth_extent.py (truth envelope).

## Honest sets (sets.py, fresh_sets.json)
Fresh 711 by scene fold: f0 161, f1 225, f2 89 (ALL these scenes are in the net's training rosters, in_train=True), f3 107, f4 129 (not in rosters: honest). So there is NO honest fresh dev set in folds 0-2.
Split used: DEV = folds 0-2 (fresh f0-2 = 475 flights, net-seen scenes but different flights; + selected search 119) -- used to learn/tune triggers;
CONFIRM = folds 3-4 (fresh f3 107 + f4 129 = 236 honest flights; selected val fold 3 = 25 honest). Fresh f3 (107) is the learned_c "unselected fold-3" set.

## A. Truth envelope (truth_extent.py -> truth_extent.json; analysis only, no outcomes tuned)
Max distance from start (m), p50/p90/p99/max: fresh711 4.79/7.97/12.76/16.89 ; holdout240 7.38/12.29/17.55/21.81 (RMS distance mean 4.70 = the server identity-pose ATE 4.694, consistent).
Vertical max |z|: fresh p90 2.18 p99 3.20; holdout p90 2.50 p99 6.80 max 9.66. Peak speed: fresh p99 3.64, holdout p99 3.67 (max 3.73); max 1-s path rate p99 3.28/3.34; max 2-s 2.61/2.69; max 3-s 2.00/2.24 (max 2.51); max 5-s 1.64/2.02 (max 2.17). Mean speed 0.74 fresh / 0.99 holdout.
=> The 'flights stay inside a house' is true only for RMS (4.7 m); the maximum excursion reaches 17-22 m for 1% of flights. A containment radius that never clips a real flight must be >= ~22 m, far beyond the 3-5 m ATE failures. A 1-s speed cap at 2.5-3 m/s WOULD clip real motion (holdout p50 of peak 1-s rate is 2.74); only 3-5 s average speed caps (>=2.5 / 2.2 m/s) are safe, and those are 2.5x the typical mean speed.

## Baseline B11 tables (tc_base r0; same flights bit-identical with TC_LOG=1 and with all tailcap blocks off)
fresh711: >3 m 12, >5 m 5, >10 m 1 (mean 0.523); sel144 (search/val): >3 11 / 0, >5 3 / 0. Dev (fresh f0-2 475 + sel search 119): 19 tails >3 m; confirm (fresh f3-4 236 + sel val 25): 4 tails. 3 replicates of the base: see below.
## A diagnostic (tailan.py on B11 tails, n=23): estimated max distance of tail flights 4.8-19.4 m (only 2 > 13 m; none > 22 m), est 3-s mean rate max 1.0-5.0 m/s (4 of 23 above 2.5), est/true path ratio mostly 1.2-1.6 (2.27 worst). Flights are NOT outside any envelope that is safe for real flights.
## B diagnostic (monan.py, TC_LOG run, 855 flights, 23 tails; AUC tail vs non-tail of window means): live tracks at 1-2 s 0.20 (tails 19 vs 50 live), accepted features/frame 2-3 s 0.08-0.03 (i.e. low u strongly flags), sqrt(trace Pv) at 2-3 s 0.89, at 5-10 s 0.97 (tails 0.32-0.40 vs 0.08-0.10 m/s); est-speed/net-speed ratio AUC ~0.6 (weak). Candidate triggers: live_2<25: dev 9/19 tails flagged, 42/575 false; pv_3>0.25: dev 15/19, 24/575 false; confirm 2/4, 10/257.
=> response arm: when sqrt(trace Pv)>thr (velocity not observable), re-anchor the net (lc_begin at that frame; innovation applied 6 frames later) every >=20 frames, sd x TC_RE_SCALE, floor TC_RE_FLOOR. Source tc_c.c (mktc.py).

## First arm results (single replicate r0; counts = flights >3 m; fresh dev = f0-2 475, conf = f3-4 236; sel search 119 / val 25)
| arm | fresh all mean (>3/>5/>10) | fresh dev >3/>5 | fresh conf >3/>5 | sel search mean (>3/>5) | sel val | peak fuel |
| base B11 | 0.523 (12/5/1) | 8/4 | 4/1 | 0.868 (11/3) | 0.400 (0/0) | 12.6 M |
| A1 rad12 (soft radius R_out 12 m, sd 3, vertical 6 m) | 0.524 (12/5/1) | 8/4 | 4/1 | 0.870 (11/3) | 0.403 | 12.6 M | -> no effect (never binds enough)
| B pv25 (re-anchor net when sqrt(trace Pv)>0.25 m/s after 1.5 s, every >=20 frames, sd x1.5, floor 0.15) | 0.476 (7/4/0) | 5/2 | 2/2 | 0.636 (4/1) | 0.397 | 15.8 M (too high; phase gating TC_PH tried next) |
