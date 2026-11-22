# geomstarve NOTES (starved-vision agent; own dir only; no git; holdout/fold-4/sealed never touched; no server probing)

Goal: usable visual constraints in vision-starved untextured ProcTHOR scenes (st2 = server-like set) on top of HM40
(servertail/final/hfg_m40s1.c, sha 4920835f..., ~4.0 M). Fuel up to ~16 M acceptable if it buys ATE.
Pools: tmp/st_pools/st2dev (156, tune) / st2conf (84, confirm) / st1dev / st1conf; fresh: folds 0-2 dev / fold 3 conf (cmpr.py).
Baseline hm40 3 reps (servertail/tables/hm40{,_r1,_r2}__*.json): st2dev 0.631/0.650/0.700 (0.660), st2conf 0.512.
Reps = PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0 (r1) / 1.485, 990.0 (r2) (atepush ev.sh convention) -- verify vs servertail.

## Session log
- S1: read servertail/atepush/lateinit notes. Plan: gs.c = sa.c + atepush edge patches (mk_gs.py), EDGE=0 must build
  byte-identical to HM40; AUD_STATS-style per-frame diagnostics on st2dev first.
- Tools: mk_gs.py (sa.c + edge_mod.c/edge_rows.c local copies + GS_DIAG + edge_on() gate EDGE_ON_LIVE) -> gs.c;
  bp.sh NAME "DEFS" POOLS (HM40 defines prepended; REP=1|2 env for rep nudges; results results/single_model/gs_NAME; tables/NAME__POOL.json);
  q.sh JOBFILE PAR (xargs queue, logs/q_JOB.txt). edge_reset also added to HARDEN hz_recover.
- CHECK: gs.c + HM40 defines (EDGE=0) wasm sha 4920835f... == HM40 BYTE-IDENTICAL.
- jobs1 (2x W32): dA (GS_DIAG+TC_LOG diag, st2dev), eB (atepush best edgelets, always on), eBb8 (eB + GOV_B 8e6), b8 (GOV_B 8e6 control).
- Image look (st2Km-100-009, hm40 6.2 m): ~40 % frames fully black; others = one flat gray polygon (gray ~50) on black, a handful of
  sharp vertices + long straight silhouette edges; interior folds contrast ~5. flatdark/ earlier: lower thresholds (thr300, cell2) no gain.
- (q.sh bug: first launch split DEFS; killed, results wiped, relaunched with setsid. Use `setsid nohup ./q.sh jobsN.txt 2 &`.)
- DIAG dA (st2dev, = hm40 r0 0.6308 exactly; tables/ga_dA.json via ga.py, ts.py per-flight time series):
  flights with median live < 15 (22/156, scenes 100/166/85/0/167) mean 1.73 m = 39 % of the ATE sum; live 15-25 (39) 0.56;
  25-40 (55) 0.35; >40 (40, textured 107734146/108294897/130) 0.48 (107734146 0.81: textured but long fast -> not my class).
  Frames: 'black' pixel fraction typically 0.6-0.98 (small gray polygon on black); fully black frames only 3.8 %.
  live<10 in 16 % of frames. Bad starved flights still get ~5-10 accepted features/s, but error jumps by 2-5 m within 3-4 s
  (100-009: 0 -> 9.9 m by 6 s, horizontal v err 2 m/s; 166-x: VERTICAL error dominant, ez -4..-7 m, vez err +-0.5-1 m/s,
  oscillating -> corrections then re-divergence). Rigid-translation-removed mean 0.41 vs 0.63.
- eB (atepush edgelets, always on, 64 edgelets, GOV path) 1 rep vs hm40 r0/r1/r2: st2dev 0.6315 (d +0.001/-0.019/-0.069, CI +-0.07);
  st2conf 0.4409 (d -0.103/-0.055/-0.056, CIs exclude 0). Peak 5.4 M. Per-flight swings +-3 m both ways (chaotic).
  eBb8 (eB + GOV_B 8e6) st2dev 0.5897, peak 11.6 M.
- jobs2: eB_r1, eB_r2 (st2), eBd (eB + GS_DIAG/TC_LOG, st2dev: edgelet counts).
- Offline detector check (det.py in scratch; 320x240 replica of F_DET Shi-Tomasi): starved frames have only 6-10 of 60 cells with a corner
  at any stride/threshold (stride 4 -> 1: 5.6 -> 7.0 cells; thr 1000 -> 300: +1-2 cells). Corner supply is physically saturated;
  remaining content = polygon edges. (flat shading -> no interior gradients -> direct/DSO points only at edges = edgelets.)
- b8 (HM40 + GOV_B 8e6, 1 rep) st2dev 0.606 / conf 0.526, peak 6.9 M.
- *** eB 3 reps (r0/r1/r2): st2dev 0.6315/0.6204/0.5979 = 0.6166 vs hm40 0.6604 (-6.6 %; per-rep d +0.001/-0.030/-0.102);
  st2conf 0.4409/0.4926/0.4565 = 0.4633 vs 0.5122 (-9.5 %; d -0.103/-0.003/-0.040). >3 m dev 5/1/3 vs 4/3/2. Peak 5.4 M.
  eBb8 (1 rep): dev 0.590 conf 0.460, peak 11.6 M.
- jobs3: eL20 (starved-only spawning LIVE20 + edge_on gate 25), eN96 (96 edgelets 12x8), eP1 (PIX 1.0), vp0 (AB_VPRIOR=0).
  jobs4: c2m8 (CLONE_EVERY 2, MAX_CLONES 8, GOV_B 8e6), c2m12 (CE2, 12 clones, MAX_OBS 12, GOV_B 12e6). (mk_gs: CLONE_EVERY/MAX_OBS #ifndef; zero-check still 4920835f.)
- Diag pool tmp/gs_pools/st2starve (22 st2dev flights with median live<15; diagnostics only). eB on it: 1.665 (hm40 r0 1.73).
  Counters (GS_DIAG; K lines; counters compiled only with GS_DIAG, eB outputs identical with/without): mean 8.9 edgelets alive (of 64),
  life ~17 frames; kills: border 45 %, coherence 25 %, no peak 15 %, contrast 5 %, ambiguous 5 %. Spawn: 4.5 candidate cells per clone frame,
  39 % fail coherence. Edge features: 59 % accepted, 24 % tri-fail, 17 % RMAX; edge rows only ~0.7 / frame => cheap, room for many more.
- 166-007 (P1s, 4.3 m) start: t=2.2-3.5 s no updates (att 0, net not ready) yet filter vz goes -0.7 while truth +1.8 m/s
  (-2.5 m/s^2 vertical accel error in pure propagation) -> filter issue beyond vision (noted for filtcons/learnvel).
- jobs6: eG20 (grid 20x15, N 128), eG20s8 (+ EDGE_S 8 px search).
- fresh pool without fold 4: tmp/gs_pools/fresh03 (582 = f0-3). cmp2.py (SUB=dev|conf for fresh), rep3.py ARM [BASE] [pools].
- jobs3 (1 rep): eL20 (spawn only live<20, edge_on 25) st2dev 0.683 conf 0.494 peak 5.4 (worse, no fuel saving: peak is at clone-frame
  detection); eN96 0.637/0.449 (= eB); eP1 (PIX 1.0) 0.627/0.487; vp0 (AB_VPRIOR=0) 0.636/0.489, peak 3.95.
- jobs4: c2m8 (clone every 2, 8 clones, B 8e6) 0.942/0.649 peak 13.3; c2m12 0.832/0.621 peak 32.6 => clone-rate increase HARMFUL. Drop.
- Peak-fuel frames of eB are clone frames (edgelet spawn pass not budgeted realistically: EDGE_GCDET 400k). Added EDGE_DSTR (scan stride),
  EDGE_DMAX (cells per call, round robin), EDGE_DEVERY (spawn pass every frame) -> eBds4 / eBdm (st2starve, in jobs5).
- NEW line_mod.c (EDGE_LINE=1): 3-sample straight-edge LINE features (3-D line, 4 DoF, 2 endpoint-distance residuals per clone obs,
  2m-4 rows; numeric Jacobians; plane-LS init + GN; samples re-spawned along the line; sliding harmless). Smoke (3 flights) runs;
  ~1 line spawn / 5 frames, 55-70 % accepted. ln32 / ln32p1 queued in jobs6.
- NOTE for caller: stale atepush waiter (pid 1268672, 'sleep 60; while pgrep -f "q.sh jobs[345].txt"...; ./q.sh jobs6.txt' in atepush/)
  would launch atepush fresh-711 runs (incl. fold 4) when no q.sh jobs3/4/5 runs anywhere; my kill was denied by the permission system.
- eBb8 3 reps: st2dev 0.603 (-8.7 %), conf 0.477 (-6.8 %), peak 11.6 M -> no better than eB; filtcons L8 (GOV_B 7.2 M) 3 reps: dev -8.2 %, conf +3.6 %.
- aud (AUD_STATS on st2starve): live 11/frame, new corners 1.44/frame, FB rejects 0.92/frame, KLT fails 0.51/frame -> corner life ~0.4 s
  (< 3 clone obs). Added GS_FBS (FB threshold GS_FBTHR px^2 while live < GS_FBLIVE). Not yet run.
- st2starve 1 rep: eBds4 (spawn stride 4) 2.00, eBdm (spread spawn) 1.81 vs eB 1.665 (chaos +-0.3 on 22 flights; peak unchanged 5.1-5.2).
- FUEL of eB: profile on smoke3 (per frame): clone frames +0.9 M mean (spawn pass, not 400 k as budgeted) and edge rows all on the clone
  frame. FIX 'g' = EDGE_GSPREAD=1 (edge rows spread over in-between frames, as the corner tracks; new edge_take_phb) + EDGE_DEVERY=1
  EDGE_DMAX=16 EDGE_GCDET=250000 (spawn spread over frames) + GC_EDGE=20000: smoke peak 3.45 M (= HM40 3.52) vs eB 4.9.
- eB FRESH (fresh03, 1 rep) vs hm40 r0/r1/r2: dev 0.3350 (d -0.016/-0.026/-0.024), conf 0.3597 (d +0.002/-0.038/-0.007) -> no regression, -5 %.
- jobs6: eG20 (20x15 grid, 128) st2dev 0.657; eG20s8 (+search 8 px) st2dev 0.604 (1 rep). jobs7: eBg x3 reps, eGs8g.
- LINES 1 rep: ln32 (PIX 0.5 RMAX 1) st2dev 0.6145 conf 0.4406; ln32p1 (PIX 1.0 RMAX 1.5) st2dev 0.5703 conf 0.4493 (st2 all 0.528 vs hm40
  3-rep 0.608 = -13 %), peak 5.7-5.8 M. Line fuel fix (line_take_phb + GSPREAD/DEVERY): smoke peak 4.3-5.1 (p99 3.2), mean 1.2-1.4.
- jobs9 (before jobs8): lng (= ln32p1 + fuel fix) x3 reps, lngP15 (PIX 1.5 RMAX 2).
- eBg (eB + fuel fix) 3 reps: st2dev 0.6347 (-3.9 %; d -0.031/+0.050/-0.097), st2conf 0.4713 (-8.0 %), peak 4.43/4.55 M.
  eGs8g (20x15, 128, search 8, fuel fix) 1 rep: 0.613 / 0.458, peak 4.8.
- LINE TRUTH CHECK (lchk.py, GS_DIAG=2 'LO' lines, refit each logged 3-D line with TRUE camera poses, offset 0 confirmed):
  endpoint residual median 0.09-0.10 px, p90 0.13-0.16 px, 0 % > 2 px (filter-pose rms 0.16-0.25) -> line measurements are
  very accurate (edgelets were 0.2-0.6 median, p90 1-3 px). Lines are few (3-10 alive; 1-6 accepted / s): edge supply-limited.
- EDGE_LTRY (top-K gradient maxima tried per cell at spawn): LTRY 4 + N 48 -> spawns +25-45 % (smoke).
- lng (lines PIX1 RMAX1.5 N32 + fuel fix) r0/r1: st2dev 0.5876/0.5860, st2conf 0.4814/0.4903; peak 5.1-5.4 M (line feature cost not charged).
- EDGE_LROWX (extra row-equivalents charged per line feature for its numeric-Jacobian/GN cost): LROWX 3 + LTRY 4 + N 48 -> smoke peak
  3.37-3.56 M (= HM40). jobs10: lnB (that config) x3 reps st2 + fresh03 r0; then jobs8 (FB/KLT_VEL arms).
- lng 3 reps: st2dev 0.5986 (-9.4 %, all reps negative: -0.043/-0.064/-0.078), st2conf 0.4854 (-5.2 %), peak 5.2-5.4 M.
- lnB (lines + LROWX 3 charge + LTRY 4 + N48, fuel-capped peak ~4.3) 3 reps: worse than lng on dev (see rep3) -> line gain needs the fuel.
- ATTITUDE is the driver in starved flights: 100-009 (lines run) tilt error 2-5 deg in first 20 s, mean 10 deg over the flight
  (rot RMSE 0.21 rad); velocity error grows exactly as g*tilt (filter vx stays ~0 while truth accelerates 0.35 -> 1.2 m/s);
  net re-anchor then sets wrong velocity with Pv 0.04. => vision must observe TILT/YAW.
- MANHATTAN check (lchk.py / lvchk.py, truth poses): of 515 logged lines 160 are within 8 deg of vertical and ~300 within 10 deg of
  horizontal; EVERY line with free-fit angle < 20 deg fits an EXACTLY vertical line with truth poses at 0.10-0.14 px rms
  (free-fit direction is just poorly determined). => vertical lines are true verticals.
- NEW EDGE_VERT / EDGE_HORIZ (line_mod.c lmodel): near-vertical (EDGE_VTH 15 deg) lines refit as exactly vertical (2 DoF, 2m-2 rows),
  near-horizontal (EDGE_HTH 10 deg) as exactly horizontal (3 DoF, 2m-3 rows), if the constrained refit rms <= EDGE_VRMAX 3 px
  (chi2 gate decides). Direct tilt information. jobs11: lgV, lgVH (+r1 each).
- MANHATTAN YAW check (lhchk.py, truth): horizontal lines' yaw mod 90 cluster at the scene axes, |dev| median 0.8-3 deg.
  NEW EDGE_MYAW: phi0 learnt from the first EDGE_MYN=15 accepted horizontal lines (resultant of exp(4i phi) >= 0.85, then frozen);
  horizontal lines within EDGE_MYTH=6 deg of phi0 + k 90 are refit with that exact direction (2 DoF, 2m-2 rows) -> heading info.
  Smoke: 100-009 rot RMSE 0.047 (lvh 0.139, lines 0.21), ATE 1.95; 166-007 1.05; 85-005 (few horizontal lines, phi0 not fixed) 1.11.
- jobs11 rewritten (before start): lgVHY x3, lgVH x2, lgV.
- *** lgVHY (lines + vertical + horizontal + Manhattan yaw) r0: st2dev 0.5581 (d -0.073 [-0.150,-0.001] vs hm40 r0), st2conf 0.4104
  (d -0.134 [-0.205,-0.064]); rot RMSE mean 0.068 -> 0.046 (dev), 0.076 -> 0.044 (conf); peak 6.1-6.5 M.
  lgVH r0: 0.5841 / 0.4464 (rot 0.067/0.062). jobs12: lgVHY fresh03 r0/r1, st1 (hm40b baseline = HM40 bytes on st1).
- *** lgVHY 3 reps: st2dev 0.5581/0.5876/0.6150 = 0.5869 (-11.1 %; d -0.073/-0.062/-0.085), st2conf 0.4104/0.4187/0.4267 = 0.4186
  (-18.3 %; d -0.134/-0.077/-0.070); >3 m dev 1/2/5 vs 4/3/2, conf 0 vs 1; peak 6.3-6.5 M. BEST SO FAR (all 6 rep deltas < 0).
  (lng: -9.4/-5.2 %, eB: -6.6/-9.5 %.) Line cost: numeric Jacobians + GN redone in the 2nd update iteration -> peak; could be cut.
## S2 (resumed after usage limit; nothing was running; all queues through jobs13 + jobs8 DONE)
- lgVHY FRESH (fresh03 = f0-3, fold 4 never run): r0 dev 0.3108 vs hm40 r0/r1/r2 0.351/0.361/0.359 (d -0.040..-0.050, CIs exclude 0);
  conf 0.3061 vs 0.357/0.398/0.367 (d -0.051..-0.092); r1 dev 0.3316 (d -0.029 vs hm40_r1; >5 m 1), conf 0.3112. peak 6.3-7.2 M.
  st1 (hm40b = HM40 bytes, 1 rep): st1dev 0.2629 -> 0.2181 (-17 %), st1conf 0.3339 -> 0.2831 (-15 %). => NO REGRESSION anywhere; gains everywhere.
- lgVH_r1 0.639/0.476, lgV 0.616/0.473 (1 rep) -> Manhattan YAW is the main contributor.
- jobs13 (1 rep, st2dev/conf): lYp5 (PIX 0.5 RMAX 1.0) 0.5383/0.4092 BEST; lY2 (LTRY4 N48) 0.566/0.440; lYt10 (MYTH 10) 0.580/0.415;
  lYn8 (MYN 8) 0.580/0.433; lYb6 (GOV_B 6e6) 0.590/0.440 peak 9.4 (budget does not help).
- jobs8 (1 rep): kv1 (KLT_VEL=1.0 alone, HM40 fuel) 0.5768/0.4624 (!); fbs (FB relax) 0.684/0.498 worse; eBgF 0.665/0.504; eBgK 0.593/0.453.
- Fuel work on lines: EDGE_LCACHE=1 (2nd update iteration reuses 1st-pass line fit) and EDGE_LMAXF (max line features per update call).
  smoke3 peaks: lYp5 4.0/4.9/6.7; +LCACHE 4.0/4.9/5.7; +LCACHE+LMAXF4 4.0/3.9/5.0 (p99 ~3.3-3.5 all). jobs14 running: lYp5 r1/r2, lYpK (lYp5+KLT_VEL 1) x3, kv1 r1/r2.
- *** lYp5 (lgVHY with EDGE_PIX 0.5 EDGE_RMAX 1.0) 3 reps: st2dev 0.5383/0.5579/0.5207 = 0.5390 (-18.4 %; d -0.093/-0.092/-0.180),
  st2conf 0.4092/0.4179/0.3941 = 0.4071 (-20.5 %); >3 m dev 3/3/1 (base 4/3/2), >5 m 0/2/1 (base 1/1/1); peak 6.7-7.0 M. NEW BEST.
- jobs15: lYc (lYp5 + LCACHE + LMAXF 6) x3, lYp3 (PIX 0.3 RMAX 0.8), lYp5 fresh03 x3 + st1.
- *** lYpK (lYp5 + KLT_VEL=1.0: KLT start = gyro prediction + last translation flow) 3 reps: st2dev 0.4968/0.5256/0.4766 = 0.4997
  (-24.3 %; d -0.134/-0.124/-0.224), st2conf 0.3957/0.4496/0.4040 = 0.4164 (-18.7 %); st2 all-240 ~0.471 vs hm40 0.608 (-22.6 %).
  vs lYp5 per rep: dev better all 3 (-0.04), conf mixed. peak 6.6-7.5 M. kv1 alone (r0/r1): 0.577/0.589 dev, 0.462/0.459 conf at 4.0 M.
  jobs16: lYpK fresh03 x3 + st1, kv1 fresh.
  st2dev   kv1      reps 3 base 0.6604 arm 0.5688 (-13.9%) per-rep d -0.054 -0.061 -0.160 | >3 arm [1, 1, 1] base [4, 3, 2] | >5 arm [1, 1, 0] | peak 4.00 M
  st2conf  kv1      reps 3 base 0.5122 arm 0.4591 (-10.4%) per-rep d -0.082 -0.036 -0.041 | >3 arm [0, 0, 0] base [1, 0, 0] | >5 arm [0, 0, 0] | peak 4.02 M
- lYc (lYp5 + LCACHE + LMAXF 6): st2dev 0.4964/0.6135/0.5578, conf 0.4029/0.4347/(r2 pending) peak 5.6-6.5 -> no clear fuel win, noisier. Drop.
- lYp3 (PIX 0.3 RMAX 0.8) r0: st2dev 0.4902, conf 0.4056 (lYp5 r0 0.538/0.409). jobs17: lY3K (PIX 0.3 + KLT_VEL) x3, lY2K (PIX 0.2).
- lYp5 fresh03 r0/r1/r2: 0.2975/0.3055/0.2845 (all f0-3; hm40 ~0.351-0.361 dev, see cmp2 SUB=dev/conf); st1dev 0.2027 (hm40b 0.2629),
  st1conf 0.2723 (0.3339). Confirms gains generalize (fresh -15..-20 %, st1 -18..-23 %).
- lYpK fresh03 0.2939/0.2911/0.2907, st1dev 0.1976, st1conf 0.2815 (lYp5: 0.2975/0.3055/0.2845, 0.2027, 0.2723) ~ equal on fresh/st1.
- kv1 fresh03 0.3579 (hm40 r0 f0-3 ~0.352): neutral on fresh; its gain is st2-only.
