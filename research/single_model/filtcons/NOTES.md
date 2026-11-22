# filtcons NOTES (FILTER-CONSISTENCY agent; own dir only; no git; holdout/fold-4/sealed never touched; no server probing)

Base HM40 = fc.c (copy of servertail/sa.c) + hm40.defs (HARDEN=1 F_REUSE=1 GATE_MODE=0 TC_MAXANCH=40 TC_RE_SCALE=1.0).
VERIFIED: fc.c + hm40.defs builds sha 4920835f...0c98 (= servertail/final/hfg_m40s1.wasm) -> results/single_model/fc_chk.
Tools: bp.sh NAME SRC "DEFS" POOLS.. (build fc_NAME, _r1/_r2 suffix adds rep perturbation PIXEL_STD/DETECT_MIN_SCORE),
rp.sh NAME WASM POOL [W], runpool.py, mets.py, cmpr.py POOL BASE ARM [dev|conf] (3-rep paired, from servertail).
Baseline tables copied from servertail/tables (hfg*, hm40*, b17x, C30m*, GB6).
Pools: tmp/st_pools/st2dev (156) st2conf (84) st1dev (244) st1conf (156); fresh = tmp/fresh_pool (dev f0-2 / conf f3 via cmpr.py).

## Session log
- S1: queue qladder.sh (nohup, W=40, logs/qladder.txt): L6/L8/L12/L16 (HM40 at GOV_B 5.4/7.2/11/14.5 M) x3 reps on st2,
  then B17+m40s1 (ap_m40s1 reps, named Bm40s1*), b17x reps r1/r2 (li_gnp_r1/r2), hm40 on st1 (baseline for no-regression).
- FC_LOG=1 (fc.c, default 0, switch-off sha verified 4920835f): per-frame 'N' line (camera-centre pos/vel + their covariances
  in the OUTPUT world frame M = Rci R0^T, yaw var, tilt var, bg var, gravity dir) and per-re-anchor 'L' line (net mu/sd,
  filter VK velocity + cov at frame K). nees.py EVALDIR POOL OUT (truth-only analysis), nsum.py, ts.py (per-frame series).
  Logging does not change outputs (nlog st2dev 0.6308 = hm40 r0 0.631).
- NEES on st2dev (HM40, tables/nees2_hm40_st2dev.json), median over flights:
  | group | n | vel NEES med (exp 3) | |e_v|^2/tr Pv | pos NEES med | vrmse | sqrt tr Pv | starved frac | re-anchors |
  | ATE>1 | 21 | 6.3 | 4.4 | 20 | 0.44 | 0.20 | 0.70 | 18 |
  | 0.5-1 | 34 | 3.4 | 2.0 | 8.7 | 0.23 | 0.13 | 0.28 | 7 |
  | <0.5 | 101 | 2.5 | 1.2 | 4.0 | 0.14 | 0.11 | 0.14 | 1 |
  => good flights are consistent; bad flights 2x overconfident in velocity sd on average, but the BAD part is bursts:
  e.g. 100-009 t 3.6-9 s: u20=0 (no accepted features at all), filter velocity error grows 0.3 -> 3.8 m/s (filter
  accelerates ~1-1.5 m/s^2 wrong) while sqrt tr Pv grows only 0.18 -> 0.43; rotation error 0.12-0.14 rad there
  (= g*tilt ~1.3 m/s^2: TILT error drives the velocity runaway, dead reckoning with a wrong gravity direction).
- NET RE-ANCHOR consistency (L lines, 940 applies): sd sits at the floor 0.15 (TC_RE_FLOOR) for re-anchors; z rms
  body-x 1.65 overall, 2.08 on ATE>1 flights with mean z -0.97: the net UNDER-predicts speed at high speed (net/true
  speed median 0.76 on bad flights; e.g. true 2.5 -> net 1.0, z -4..-6). Re-anchor error median 0.32 m/s vs filter 0.41
  on bad flights. Startup apply (sd ~0.05-0.06) is consistent (z rms ~1.1, err 0.10). Filter-vs-truth NIS at K median 6.6
  on bad flights (filter overconfident).
- Filter speed/true speed over flights ~0.94-0.99 (no systematic over-extension in speed on st2dev for HM40).
- Tilt consistency (nees3): tilt sd ~0.012 rad everywhere; tilt NEES (exp 2) median 1.5 on good flights, 3.5 on ATE>1, up to
  10-27 (100-009 tilt max 0.15 rad during the u20=0 stretch). True gyro bias from truth (gyro - R_bc w_true): 100-009
  (-0.019, 0.003, -0.021) rad/s ~ the +-0.02 uniform range edge; mid start => never estimated => tilt drifts ~0.02 rad/s.
- Small diagnostic pools (symlinks): tmp/fc_pools/st2bad (30 worst st2dev by hm40 3-rep mean, 1.81) / st2good (30 random, 0.378).
- FC_QV_ON (starved velocity random walk, tc_monitor) qv03 (0.3 m/s/sqrt s when u20<10): st2dev 0.631 -> 1.716 (!!). 143/156
  flights worse, sim3 scale 1.0 -> 1.1-1.7 (UNDER-extension): with Pv inflated, the zero-mean velocity prior (AB_VPRIOR,
  SPEED_STD 0.5, TAU 2 s) and lateral prior (INV_LAT 0.5) pull velocity to 0. Only the over-extended tails improve
  (166-010 3.10 -> 0.62, 100-009 6.21 -> 3.26). => the hand priors are an essential (hidden) part of the velocity model;
  inflation must not be done naively. Queued: qv01, qv03+vp0, vp0, lat0, qt01/02 (tilt RW), hub3.
- bias.py (nlog4 on st2bad): gyro-bias error vs filter sd at 3-5 s is often 1.5-3.2 sigma on mid starts (100-009 5 s:
  0.036 vs sd 0.011; 64-005 0.027/0.014; 160-005 0.023/0.013) => bias sd shrinks without real information (no accepted
  features). Candidate culprit: hand priors with attitude Jacobians (INV_LAT lateral prior has TH columns; zero-mean velocity
  prior via V-TH cross-cov) inform tilt/bias falsely. => FC_SCHMIDT=1: velocity priors (startup prior, AB_VPRIOR, INV_LAT)
  applied as Schmidt/consider updates (no correction of TH, BG, BA, TH0; full Joseph-like covariance), thrust rows normal.
  Switch-off sha verified. 
- vp0 (AB_VPRIOR=0, no zero-mean velocity prior): st2dev 0.636 (hm40 r0 0.631): neutral.
- Fuel ladder partial (st2dev / st2conf): L6 0.647/0.561, 0.593/0.559, 0.651; L8 0.586/0.535, 0.602/0.532; L12 0.589/0.529,
  0.572; L16 0.591/0.522, 0.571/0.511. Peak caps ~9 M even at GOV_B 14.5 M (other limits bind).
- qt01 (FC_QT=0.01 rad/sqrt s tilt RW when u20<10): st2dev 0.747 (worse; rest 0.388 -> 0.501). Inflating tilt lets the
  (false) prior information move tilt even more.
- sch (FC_SCHMIDT=1, always): st2dev 0.653 (r0 hm40 0.631, 3-rep 0.660); top30 (worst by hm40) 1.806 -> 1.565 (-13%), rest
  0.388 -> 0.436 (+12%); peak 4.44 M (+0.4 M, naive O(D^2 k) code). TRADE-OFF => gate it on starvation: FC_SCH_U (u20 < thr).
- pf.py ARM BASE [POOL]: per-flight vs base 3-rep mean, top30/rest split.
- qv01 (FC_QV 0.1 when u20<10): st2dev 0.812 (worse). Velocity-RW inflation is bad at every level tried (likely: Pv > 0.25
  => pv trigger fires at every gap; with larger Pv the net, which under-predicts high speeds, dominates => under-extension).
- Net re-anchor error vs speed (784 re-anchors, nees2): by NET speed 0-0.5/0.5-1/1-1.5/1.5-2: |e_net| median 0.19/0.29/0.40/0.50
  while the filter at K has 0.28/0.30/0.26/0.31 => above ~0.8 m/s the filter is BETTER than the net, yet the net sd is the
  0.15 floor. By TRUE speed 2-5 m/s: net 1.58 (median) vs filter 2.00, |e_net| 0.97 vs |e_filt| 0.40.
  Consistent per-axis sd ~ 0.10 + 0.13 * net speed. => FC_RE_SPDON/FC_RE_SPD: re-anchor floor += FC_RE_SPD * net speed.
- !!! BUG FOUND (pre-existing, harmless for HM40): tc_used is NEVER incremented in sa.c/fc.c, so u20 (TC_LOG 'u20', tc_uring,
  TC_STARTUP_MON's lock-out test) is always 0. => my qv03/qv01/schu10 'starved-only' gates were ALWAYS ON (qv03 = always-on
  0.3 m/s/sqrt s velocity RW; schu10 == sch exactly). Fixed for filtcons switches: fc_uring = att - gate - tri per frame
  (only compiled with FC_QV_ON or FC_SCHMIDT; HM40 sha unchanged). Re-queued schu10b, qv03u, qv01u (gated properly).
- resp12 (re-anchor floor + 0.12*net speed): st2dev 0.692 (top30 1.806 -> 1.952, rest 0.392): WORSE. Weaker net pulls hurt the tails even though more 'consistent' at re-anchor time (agrees with s1: RE_SCALE 1.5 -> 1.0 helped). resp06 dropped.
- schu10b (Schmidt only while starved, fixed counter): st2dev 0.749 (top30 2.055, rest 0.438): worse than always-on sch.
  Next: schs0 = sch but the startup (heading) prior stays a normal update (FC_SCH_ST=0); schu3 dropped.
- Ladder: L12 == L16 (identical r2 dev 0.6430) => HM40 logic saturates at ~8-9 M actual peak; budget above ~8 M is unused.
- Bm40s1 (B17 16 M + m40s1, ap_m40s1) st2dev r0 0.622, peak 15.3 M.
- qv03u (velocity RW 0.3 only while starved, correct counter): st2dev 0.840 (top30 1.946, rest 0.577; vel rmse up on both
  groups). => Inflating Pv (any form) or Pth HURTS. Robust conclusion; drop the adaptive-Q family.
- schs0 (Schmidt except startup prior): 0.708 (top30 1.961). NOISE: hm40 3 reps on st2dev are 0.631/0.650/0.700 (sd ~0.035),
  so single-rep screens only resolve >~0.07 effects. Clear losers: qv*, qt01. Inconclusive: sch 0.653, schu10b 0.749,
  schs0 0.708, resp12 0.692, vp0 0.636. => run sch 3 reps on st2dev+conf (sch_r1, sch_r2, schc).
- CHI2_Z made overridable (#ifndef; sha unchanged). Queued chi90 / chi99.
- hub3 (INV_HUBER=3: chi2 in (gate, 3 gate) down-weighted instead of rejected): st2dev 0.708 (inconclusive/worse; atepush saw
  the same on B17 pool_bad).
- Bm40s1 (B17 16 M + m40s1) st2dev 3 reps 0.622/0.598/0.574 (mean 0.598, -9.4% vs hm40) ~ same as HM40 at 8 M (L8/L12/L16).
- AREA ARITHMETIC: area = 0.28 log2(17/peak) - 2.24 ln(ATE/0.356). 4 -> 8 M costs 0.28; it pays only if ATE drops > 11.8%;
  4 -> 16 M needs > 22%. st2dev gains at 8-16 M are ~9% (dev) and ~0% (conf) => budget alone does NOT pay; stay at ~4 M.
- sch_r1 st2dev 0.664 (hm40_r1 0.650); with r0 0.653 vs 0.631: Schmidt priors NEUTRAL/slightly worse -> dropped (no r2).
- sch_r1 st2conf 0.548 (hm40_r1 0.496): Schmidt rejected.
- Re-read of the 100-009 runaway with the counter fix in mind: 2-4 features/frame ARE accepted (att 2, gate 0, NIS 0.04-0.3)
  while the velocity error grows 2 -> 3.4 m/s => accepted features carry little/no velocity information there (degenerate
  geometry or far points); queued md12 (MAX_DEPTH 12 m) and chi90/chi99 (gate strictness).
- FC_RUN_ON (runaway trigger, default off, sha unchanged): fire a net re-anchor when filter speed > FC_RUN_R x last net speed
  (and > FC_RUN_MIN). Motivation: re-anchors with filt/net > 2 have true/net 1.82, true/filt 0.70 => the fused value beats
  either. Queued run2 (R 2, min 1.0), run15 (R 1.5, min 0.8).
- lat0 (INV_LAT=0): st2dev 0.635 neutral (like vp0 0.636).
## FUEL LADDER (st2, 3 reps; all240 = (156 dev + 84 conf) per rep; area vs HM40 = 0.28 log2(peak_HM40/peak) - 2.24 ln(ATE/ATE_HM40))
| build | st2dev r0/r1/r2 (mean) | st2conf r0/r1/r2 (mean) | all240 | >3 m dev/rep | peak p99-max M | area vs HM40 |
| HFG (4 M) | 0.713/0.646/0.796 (0.718) | 0.545/0.501/0.494 (0.514) | 0.647 | 6,4,8 | 4.0 | -0.14 |
| HM40 (GOV_B 3.6) | 0.631/0.650/0.700 (0.660) | 0.544/0.496/0.497 (0.512) | 0.609 | 4,3,2 | 4.0 | 0 |
| L6 (GOV_B 5.4) | 0.647/0.593/0.651 (0.630) | 0.561/0.559/0.541 (0.554) | 0.603 | 5,2,7 | 6.4-7.4 | -0.22 |
| L8 (7.2, UMAX 50) | 0.586/0.602/0.630 (0.606) | 0.534/0.532/0.526 (0.531) | 0.580 | 2,2,3 | 6.5-6.9 | -0.11 |
| L12 (11, UMAX 60) | 0.589/0.572/0.643 (0.601) | 0.529/0.516/0.531 (0.525) | 0.575 | 2,0,4 | 7.7-8.7 | -0.18 |
| L16 (14.5, UMAX 80) | 0.591/0.571/0.643 (0.602) | 0.522/0.511/0.535 (0.523) | 0.574 | 2,0,4 | 8.8-9.2 | -0.20 |
| b17x (B17, 16 M) | 0.631/0.631/0.614 (0.625) | 0.472/0.475/0.461 (0.469) | 0.571 | 5,4,5 | 17.2-18.7 | -0.48 |
| B17+m40s1 | 0.622/0.598/0.574 (0.598) | 0.482/0.488/0.472 (0.481) | 0.557 | 4,4,4 | 14.9-16.4 | -0.37 |
=> Budget buys at most ~6-9 % on st2 (dev -9 %, conf +2..+4 % for the HM40 ladder; B17 16 M -9 % / -6 %), saturating at ~8 M;
   NO ladder point pays in area. The st2 gap (b17x 0.63 vs HFG 0.72 dev) is mostly m40s1 (HFG->HM40), not budget.
   Recommendation: stay at ~4 M.
- run2 (runaway trigger R 2, min 1.0) st2dev 0.658, run15 (R 1.5, min 0.8) 0.675: neutral. Dropped.
- hm40 (1 rep) st1dev 0.263 (244), st1conf 0.334 (156) = no-regression baseline for st1.
- *** FEATURE TRUTH CHECK (fchk.py; FO/C lines; nlog5 st2bad): triangulate each MSCKF feature's observations with TRUTH camera
  poses. Accepted features with truth rms > 2 px (full-res, fx 150): 2-5 % on textured flights, 15-24 % on the worst
  untextured ProcTHOR flights (100-009 18 %, 142-003 19 %, 166-007 24 % (>5 px 14 %), 100-010 17 %, 166-010 18 %,
  64-004 17 %, 100-001 19 %); those flights also have only 0.15-0.3 features/frame. Gated features median 6-16 px.
  => in starved scenes the few accepted features include many BAD TRACKS that pass chi2 (P large -> loose gate) and
  drive the velocity runaway. Output-pose residual cannot separate them (fchk2: inlier median 1.6 vs outlier 4.0 px).
  Next: FC_RMAX_ON/FC_RMAX = reject if rms residual under the CLONE poses after triangulation > FC_RMAX px (solution
  res; fc_trirms), P-independent; FO lines now log that residual (nlog6) to pick the threshold offline.
- fchk3 (nlog6, logged CLONE-pose residual after triangulation, solution px): truth outliers (>2 full-res px) are 7.7 % of
  accepted on st2bad, 4.5 % on st2good; clone-residual median inliers 0.34 px vs outliers 1.31 px. Threshold 0.75 px:
  catches 88 % / 87 % of outliers, loses 12 % / 8 % inliers (bad / good); 1.0 px: 74 % / 73 % caught, 6 % / 3 % lost.
  Outlier rate by track length (bad): 3 obs 12.6 %, 4 10.8 %, 5 7.6 %, 6 5.0 %. Queued rmx10, rmx075 (front of q2).
- chi90 (CHI2_Z 1.2816, stricter) st2dev 0.635, chi99 (2.326, looser) 0.651: neutral both ways.
- qt01u (tilt RW 0.01 only while starved, fixed counter): st2dev 0.690 (worse-ish).
- qt03u (tilt RW 0.03 when u20<5): 0.761 worse. Tilt/velocity/bias inflation family closed.
- rmx10 (RMAX 1.0 px from t=0): st2dev 0.767: top30 1.806 -> 1.758, rest 0.388 -> 0.531 (51 flights worse by >0.2, many
  static starts): absolute residual test under poor startup clone poses rejects good features -> feedback loop.
  Added FC_RMAX_T0 (check only after T0 s). Queued rmx10t5, rmx15t5.
- rmx075 (RMAX 0.75 from t=0): 0.965 (much worse). qb3u (gyro-bias RW 0.003 rad/s/sqrt s when starved): 0.633 neutral.
- FC_RMAX_ON=2 (relative): reject if residual > max(FC_RMAX, FC_RMAX_K x median of the last 32 features' residuals);
  adapts when the state is off. (static ring: needs reset-at-init if adopted.) Queued rrel3, rrel4t3.
- md12 (MAX_DEPTH 12 m): 0.654 neutral.
- rmx10t5 (RMAX 1.0 after 5 s): 0.727 (top30 1.825, rest 0.466): rejecting features hurts even after startup.
  => the filter needs every feature; outlier REJECTION by residual is harmful. Trying soft down-weighting FC_RMAX_ON=3
  (row weight FC_RMAX/residual when residual > FC_RMAX, after T0): rsoft1, rsoft05.
- rrel3 (relative RMAX K 3, min 0.5): 0.727 worse. Rejection family closed. Net calibration: E[true speed | net speed] ~ net speed for net > 1 m/s (by net-speed bins net/true 0.98/0.96), so the net is conditionally unbiased; only its sd is too small at speed -> re-test resp06 (floor + 0.06 v ~ consistent per-axis 0.24 at 1.5 m/s).
- rmx15t5 0.676, rrel4t3 0.662: neutral. Mild knobs single-rep (mean / top30 / rest; base 0.660/1.806/0.388, a neutral arm
  regresses to ~1.70 on top30): vp0 0.636/1.746/0.372, lat0 0.635/1.668/0.389, chi90 0.635/1.705/0.380, qb3u 0.633/1.676/0.385,
  sch 0.653/1.565/0.436. Nothing outside the rep noise. 3-rep st2 runs queued for lat0 and vl0 (INV_LAT=0 + AB_VPRIOR=0 =
  drop both hand velocity priors; simplification, priors are false for fast flights).
- *** rsoft1 (FC_RMAX_ON=3: rows of features whose clone-pose residual > 1.0 px down-weighted by 1.0/residual, after 3 s): st2dev 0.596 (top30 1.602, rest 0.356 - both better), peak 4.03 M. Best single rep at 4 M. 3 reps + st2conf queued first.
- resp06 (re-anchor floor + 0.06 v): 0.665 neutral (top30/rest above). Net sd consistency changes don't help.
- rsoft05 (0.5 px): 0.704 (too aggressive).
- rsoft1 reps: st2dev r0/r1/r2 0.596/0.653/0.637 (hm40 0.631/0.650/0.700), st2conf r1/r2 0.466/0.492 (hm40 0.496/0.497); r0 conf + fresh03 + st1 running.
- (interruption: usage limit; stale qx loops had the old fresh_pool mapping -> fresh03 runs failed with 0 episodes; queues
  restarted as q1c/q2c with fixed qx.sh.)
- rsoft1 r0 st2conf 0.477 (hm40 0.544). st1 (1 rep): rsoft1 st1dev 0.235 / st1conf 0.328 vs hm40 0.263 / 0.334 (no regression).
- Queued: rsoft1 fresh03 x3 (folds 0-3 only; fold 4 excluded from the pool), rsoft15, rsoft1t0, lat0_r1.
- *** rsoft1 3 reps (cmpr.py vs hm40): st2dev 0.660 -> 0.629 (-4.8%; d r0/r1/r2 -0.035/+0.003/-0.063), st2conf 0.512 -> 0.478
  (-6.6%; -0.067/-0.030/-0.005); 5/6 rep-pairs negative; but st2dev >3 m per rep 4,3,2 -> 5,6,5 (more mid-size tails, fewer >5).
  Peak 3.96-4.05 M (unchanged). Candidate; fresh03 pending.
- rsoft1 fresh03 (folds 0-3): dev r0/r1 0.351->0.322 (-0.028 [-0.047,-0.013]), 0.361->0.342 (-0.018 [-0.038,+0.001]);
  conf r0/r1 0.357->0.359 (+0.002), 0.398->0.370 (-0.028 [-0.044,-0.010]). r2 pending.
- FINAL candidate: final/hm40_rsoft1.c (8 #defines + fc.c) builds byte-identical to fc_rsoft1 (sha 7998d1b8...);
  final/hm40_rsoft1.wasm; preflight running (final/preflight, logs/preflight.txt).
- rsoft15 (1.5 px) 1 rep: st2dev 0.646 / st2conf 0.511 (weaker than 1.0). Keep 1.0.
- *** rsoft1 fresh03 3 reps: dev 0.3567 -> 0.3315 (-7.1%; d -0.028/-0.018/-0.029, CI excl 0 in r0,r2), conf 0.3740 -> 0.3563
  (-4.7%; +0.002/-0.028/-0.027). Fresh tails unchanged (>3 m 1/1). Peak 3.98-4.05 M. => RECOMMENDED (HM40 + FC_RMAX_ON=3).
- lat0 r1: st2dev 0.653 / conf 0.502 (hm40_r1 0.650/0.496): neutral -> lat0/vl0 dropped.
- rsoft1t0 (soft weighting from t=0): st2dev 0.587, st2conf 0.443 (r0; best single rep). Queued t0 reps r1/r2 + fresh03 x3.
- PREFLIGHT final/hm40_rsoft1.wasm (sha 7998d1b8094262844f908a35822f96216ac1d6f5ef11f0efe7036b484744273d; source
  final/hm40_rsoft1.c = 8 #defines + fc.c; rebuild byte-identical to the define build): ABI check ok (5 steps), zero imports,
  poison/prefix/repeat all PASS (18 fixtures x 41 prefixes, 0 failures), reset 8/8 PASS. final/SHA256SUMS.
- rsoft1t0 st2 3 reps: dev 0.587/0.598/0.599 (0.595, -9.9% vs hm40 0.660), conf 0.443/0.460/0.449 (0.451, -12.0% vs 0.512).
  fresh03 r2 0.3331 (rsoft1 r2 0.3317). Built final/hm40_rsoft1t0.c/.wasm (sha 7ef3a329..., byte-identical to fc_rsoft1t0);
  preflight running (final/preflight_t0).
- *** rsoft1t0 3 reps vs hm40: st2dev 0.660 -> 0.595 (-10.0%; d -0.044/-0.052/-0.101), st2conf 0.512 -> 0.451 (-12.0%;
  -0.101/-0.036/-0.048, all CI excl 0), fresh dev 0.357 -> 0.321 (-10.1%; all 3 CI excl 0), fresh conf 0.374 -> 0.379 (+1.2%,
  +0.020/-0.025/+0.019, CIs straddle 0). Tails: st2dev >3 m 4,3,2 -> 2,3,2; fresh >3 m ~1/rep. Peak 3.96-4.05 M.
  vs rsoft1 (T0=3): st2dev -5.4%, st2conf -5.8%, fresh dev -3.3%, fresh conf +6.3%.
- rsoft1t0 st1 (1 rep): st1dev 0.237 / st1conf 0.317 (hm40 0.263 / 0.334): no regression.
- PREFLIGHT final/hm40_rsoft1t0.wasm (sha 7ef3a3294f55a2e29518...; final/SHA256SUMS): ABI ok, zero imports, poison/prefix/repeat
  738/738 PASS, reset PASS, rebuild from final/hm40_rsoft1t0.c byte-identical to the define build.

## FINAL SUMMARY
RECOMMENDED: final/hm40_rsoft1t0.wasm = HM40 + FC_RMAX_ON=3 FC_RMAX=1.0 FC_RMAX_T0=0 (soft residual down-weighting: after
triangulation, a feature whose rms reprojection residual under the CURRENT CLONE POSES exceeds 1.0 px (solution res) has its
rows scaled by 1.0/residual, i.e. noise sd x residual; no state, no extra fuel). Switch-off (no FC_* defines) = HM40 sha 4920835f.
| build | st2dev | st2conf | fresh dev (f0-2) | fresh conf (f3) | st1dev/conf (1 rep) | peak |
| HM40 | 0.660 | 0.512 | 0.357 | 0.374 | 0.263/0.334 | 3.97-4.04 |
| hm40_rsoft1t0 (REC) | 0.595 (-10.0%) | 0.451 (-12.0%) | 0.321 (-10.1%) | 0.379 (+1.2%, ns) | 0.237/0.317 | 3.96-4.05 |
| hm40_rsoft1 (T0=3, alt) | 0.629 (-4.8%) | 0.478 (-6.6%) | 0.332 (-7.1%) | 0.356 (-4.7%) | 0.235/0.328 | 3.96-4.05 |
Negative results: Pv/Pth/bias inflation (adaptive Q), Schmidt priors, Huber, chi2 strictness, hard residual rejection
(absolute/relative), consistent (speed-scaled / per-axis) net re-anchor sd, runaway trigger, MAX_DEPTH, dropping hand priors.
