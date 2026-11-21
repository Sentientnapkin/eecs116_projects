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

## More single-replicate arms (r0): A2 speed prior, fast-start sigma calibration, phases, starved pull
| arm | fresh (>3/>5/>10, mean) | dev(fresh f0-2) >3 | conf(f3-4) >3 | sel search mean (>3) | peak fuel |
| spd25 (3-s mean speed >2.5 -> pull to 1.6, sd 0.5) | 12/5/1, 0.523 | 8 | 4 | 0.858 (10) | 12.6 M | no effect on fresh, 1 flight on sel (chaos level)
| spdk05 (LC_SPD_K 0.5: net sigma x(1+0.5*pred speed)) | 11/2/0, 0.528 | 6 | 5 | 0.872 (8; one >10 m) | 12.4 M | tails 12->11, mean flat
| spdk10 (LC_SPD_K 1.0) | 17/5/0, 0.546 | 8 | 9 | 1.040 (13) | 12.3 M | WORSE (>3 up, mean up): sigma inflation hurts the net's benefit
| pv35 (thr 0.35, T0 2.0) | 9/5/0, 0.491 | 6 | 3 | 0.754 (8) | 15.3 M
| pv25 | 7/4/0, 0.476 | 5 | 2 | 0.636 (4) | 15.8 M
| pull (starved pull: live<25 for 40 frames & moving -> position toward origin, sd 2 m) | 10/4/1, 0.515 | 7 | 3 | 0.857 (11) | 12.6 M | on the 31 starved flights (stress_all live<25): mean 2.38 -> 2.24, >3: 12 -> 10
Phase gating of the re-anchor stages (TC_PH 0..3, sel only): sel search mean 0.705-0.713, >3: 5/7/6/6, peak 15.3-16.6 M: does NOT cut the peak (begin/capture gray conversions on a busy frame are ungated) -> TC_PHB (begin-phase) test queued.
## pv25 with 3 chaos replicates (base 3 reps same pipeline), per-replicate means
| | base | pv25 |
| fresh 711 mean | 0.530 | 0.482 |
| fresh dev(f0-2) >3 / >5 | 8.3 / 3.3 | 5.3 / 2.0 |
| fresh conf(f3-4) >3 / >5 | 5.0 / 1.3 | 3.0 / 1.7 |
| fresh >10 | 0.3 | 0 |
| sel search (119) mean, >3 | 0.854, 10.0 | 0.656, 4.3 |
| sel val (25) mean, >3 | 0.395, 0 | 0.396, 0 |
| peak fuel | 12.8 M | 15.8 M (limit ~14 M: NOT met) |
Persistence (855 flights, 3 reps): base fails (>3 m) in >=1 rep: 32 flights, in >=2 reps: 23; pv25: 17 / 11. Fixed (base >=2 reps, pv25 0 reps): 10 of the 23 persistent; newly failing (pv25 >=2 reps, base 0): 1 (fresh fastmid-ProcTHOR-Train-161-00, base 2.4/1.7/2.3 vs 1.7/3.1/3.0). Unfixed: the three flat/dark and starved scenes (fast-ProcTHOR-166-05, -100-02, 85-01, sel 106366104 flat), as expected.

## combo (pv25 + starved pull), 3 reps: fresh 0.481 (>3 8.7, >5 3.0), dev >3 5.3, conf >3 3.3, sel search 0.669 (5.3); starved(31): base 2.56 (12 >3) | pv25 2.20 (8.7) | combo 2.17 (10.3) => pull adds nothing beyond pv25; NOT adopted.
## Fuel of the re-anchor: begin-phase gating (TC_PHB 0-3: peak 15.1-16.3 M), stage-phase gating (TC_PH: 15.3-16.6), both (phx: 15.3-16.8): no phase combination brings peak under 14 M; the extra (gray128 ~2 M x2 + prep 5.3 + forward 4.7) lands on frames already at ~10-12 M. Needs per-frame fuel profiling (fuel agent) or a cheaper re-anchor (e.g. reuse the base pyramid for the gray128 instead of the raw RGB resample, or LC_SPREAD=2 style staging validated for re-anchors).
## DECISION: tail count falls on dev AND confirm with 3 replicates for pv25 (mechanism: net as velocity sensor while sqrt(trace Pv)>0.25 m/s), mean better (fresh 0.530->0.482, sel search 0.854->0.656), no >10 m flights, static unchanged by construction (moving gate); BUT peak fuel 15.8 M > 14 M => NOT ADOPTED as submit candidate pending fuel fix; no preflight run. Containment (A1), speed prior (A2), fast-start sigma inflation, starved pull: no gain/negative. Startup monitor (lock-out & runaway-ratio trigger) not tested separately (pv trigger dominated: AUC 0.89-0.97).
Source: tc_c.c (generated by mktc.py from tc_base.c = lc_b11.c); recommended defines: TC_MON=1 TC_STARTUP_MON=0 TC_PERIOD=0 TC_PV_THR=0.25 TC_T0=1.5. Tables tables/*.json; certify.py not run (needs per-flight tables with holdout; holdout not scored by rule).

## B15 = B11 + pv25 (default-on build tc_b15.c = 5 defines + tc_c.c; wasm tailcap/gp_msckf_startup_b15_pv25.wasm; sha256 in preflight_b15/SHA256SUMS)
FOUND AND FIXED in preflight: the first tailcap build did not reset its state on re-init (reset check failed on 4 of 8 fixtures); tc_reset() now called at init (mktc.py). Wasm sha after fix: 93b2bdaa25fc5499c4f45f0c58fcb584e7f749a5fb1171d843ddbbbe30f7d659.
Preflight (preflight_b15/): ABI check ok; zero imports; rebuild byte-identical; determinism: sel144 scored twice, ATE and estimate.tum bit-identical 144/144; default-on build bit-identical to the define-built pv25 r0 (144/144 sel, 711/711 fresh); completed 144+711, filled 0; reset 8/8 fixtures x 700 frames (re-init, after-partial, fresh-process all equal); fuel: sel peak 15.51 M (p99 14.6 M), worst-flight p95 8.61 M, fresh peak 15.83 M (B11 11.9 / 12.8 M). Poison/prefix: see below. Fixtures: 18 from final/preflight_c1_fbh/fixtures_list.txt (folds 0-3), prefixes 1,2,4,5,6,8-12,29,30,31,40,41,60,120,600,1199.
certify.py (certify_out/): fresh-rate P(12 clean), pm 0.5/0.75: B11 reps 0.75/0.73, 0.75/0.73, 0.68/0.65 -> B15 0.84/0.83, 0.78/0.77, 0.81/0.80 (fresh is mildly optimistic; no holdout used). fresh >3 m B11 12/12/16 vs B15 7/9/9 flights.
## Cheaper re-anchor: TC_POST=1 TC_ROWMAX=n (re-anchor net stages run AFTER vision in the step and are deferred while this frame's compressed MSCKF rows > n): sel peak 15.5 -> 13.0 M (rm30, rm80), sel search mean 0.657/0.655, >3 3/3 (single run); full 3-rep eval 'rmf' queued.
Poison/prefix/repeat: 342/342 cases bit-equal (18 fixtures x 19 prefixes incl. 29,30,31 straddling the 1.5 s trigger), 0 guest failures (preflight_b15/poison_g*.log). All preflight checks PASS for wasm sha 93b2bdaa...d659 (B15, pv25, TC_POST off, peak 15.8 M).

## Second triggers and cheaper re-anchor, 3 reps each (per-replicate means; fresh >3 all/dev/conf; fresh mean; sel search mean (>3); peak)
| arm | fresh >3 | dev | conf | fresh mean | sel search | peak | persistent fail>=2 reps (of 855) | fixed / new vs base |
| base B11 | 13.3 | 8.3 | 5.0 | 0.530 | 0.854 (10.0) | 12.8 | 23 | - |
| pv25 = B15 | 8.3 | 5.3 | 3.0 | 0.482 | 0.656 (4.3) | 15.8 | 11 | 10 / 1 |
| pv25 + live<20 for 20 fr trigger (pvlive) | 9.3 | 5.0 | 4.3 | 0.481 | 0.659 (4.0) | 15.8 | 14 | 10 / 1 | no gain
| pv25 + 20-frame-mean Pv>0.18 in 1.5-3 s (pvw) | 8.3 | 5.7 | 2.7 | 0.472 | 0.641 (4.0) | 15.8 (val 14.4) | 11 | 10 / 1 | mean -0.01 (noise level), tails equal
| pv25 cheap re-anchor (rmf: TC_POST=1 TC_ROWMAX=30) | 8.3 | 6.0 | 2.3 | 0.482 | 0.685 (4.7) | 13.0 | 11 | 7 / 0 | same tails, peak 15.8 -> 13.0 M
Conclusion: second triggers add nothing measurable over pv25 (pv already encodes the low-track signal). rmf (B15b; source tc_c.c with defines TC_MON=1 TC_STARTUP_MON=0 TC_PERIOD=0 TC_PV_THR=0.25 TC_T0=1.5 TC_POST=1 TC_ROWMAX=30) is the fuel-cheaper variant; outputs differ from B15 (not bit-identical), NOT preflighted.

## B16 = B13 + pv25 (port onto bulk/exact/b13x.c: mktc2.py tc_b13.c tc_d.c / tc_e.c; runset --cmake bulk/exact/CMakeLists.txt; q13*.sh)
B13 defines: ITER_UPD=2 ITER_BACK=1.0 ITER_TH=0.03 MAP_MODE=1 MAP_AGE=100 MAP_ANG=40 MAP_TRY=6 MAP_ZNCC=0.85 MAP_NEAR=1. pv25 defines: TC_MON=1 TC_STARTUP_MON=0 TC_PERIOD=0 TC_PV_THR=0.25 TC_T0=1.5. tc_reset() at init included. Switch OFF (tc_d.c, no TC defines) is bit-identical to B13 on the 144 visible flights (144/144).
3 reps, per-replicate means (fresh = 711 incl. dev f0-2 / confirm f3-4 net-honest 236; fresh f3 = the 107 unselected fold-3 flights):
| | fresh >3 / >5 | dev >3 | conf >3 / >5 | fresh mean | conf mean | sel search mean (>3) | sel val | peak (sel / fresh) |
| B13 | 10.7 / 4.7 | 6.3 | 4.3 / 2.0 | 0.405 | 0.430 | 0.685 (8.0) | 0.364 | 18.5 / 20.2 M |
| B16 (pv25) | 4.7 / 2.0 | 2.7 | 2.0 / 1.0 | 0.358 | 0.370 | 0.593 (5.3) | 0.363 | 20.3 / 25.2 M |
| B16m = B16 + MAP flush at re-anchor (TC_MAPFLUSH=1) | 5.0 / 1.3 | 3.3 | 1.7 / 0.3 | 0.363 | 0.367 | 0.602 (5.0) | 0.362 | 20.3 / 25.2 M | no gain over B16 -> not used
| B16r = B16 + cheap re-anchor (TC_POST=1 TC_ROWMAX=30) = FINAL B16 | 4.3 / 1.3 | 3.0 | 1.3 / 0.3 | 0.356 | 0.368 | 0.595 (5.3) | 0.370 | 18.5 / 20.2 M (= B13) | same tails, no fuel increase
Persistence (855 flights x 3 reps): B13 fails >=1 rep 25 / >=2 reps 18; B16 14 / 9 (fixed 5, new 0); B16r 13 / 9 (fixed 7, new 0); B16m 14 / 10.
certify.py fresh-rate P(12 clean) pm 0.5 / 0.75, reps r0,r1,r2: B13 0.78/0.75, 0.78/0.75, 0.76/0.75 -> B16r 0.89/0.75*, 0.88/..., 0.90/... (column 1 = pm 0.5; see certify_out/tc_b16r_r*.md; fresh optimistic, no holdout).
FINAL B16 source tc_b16.c (B13 defines + pv25 + TC_POST=1 TC_ROWMAX=30 prepended to tc_e.c); wasm tailcap/gp_msckf_startup_b16.wasm sha256 1108dcfb4bef566ca7852cd7b78226629ac15f6b3c4482fa294ce14298fe8f63 (rebuild byte-identical, bulk/exact/CMakeLists.txt -O3). Preflight dir preflight_b16/ (ABI ok, zero imports, reset 8/8 x 700 frames PASS; score/poison below).
## B16 PREFLIGHT (preflight_b16/) all PASS: ABI ok, zero imports, rebuild byte-identical, determinism sel144 x2 ATE + estimate.tum identical 144/144 (equals b16r r0 table 144/144 sel, 711/711 fresh), completed 144+711, filled 0, causality/poison/prefix/repeat 504/504 (18 fixtures folds 0-3 x 28 prefixes: 1,2,4,5,6,8-12,16,20,29-31,40,41,60,99-105,120,600,1199), reset 8/8 x 700 frames, fuel peak 18.25 M (sel) / 20.17 M (fresh), worst p95 11.8 M (= B13's peak). wasm tailcap/gp_msckf_startup_b16.wasm sha256 1108dcfb4bef566ca7852cd7b78226629ac15f6b3c4482fa294ce14298fe8f63.
