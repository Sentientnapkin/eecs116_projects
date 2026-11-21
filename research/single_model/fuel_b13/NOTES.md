# fuel_b13 NOTES (fuel agent on B13 code path; own dir only; no git; holdout untouched)

Base: bulk/exact/b13x.c (B13 exact, defs in defs.txt, -O3 CMakeLists copy here). Working source: b13y.c (default = exact rewrites, approximate arms are #ifndef-defined, default off).
Tools: mkprof.py (inserts PH/PM phase marks -> PROF build), pcmp.sh SRC TAG [-Dflags] (profile build, 60 search flights, pose bit-compare vs frozen profile run, peak/median),
an.py (phase tables), ev.sh NAME SRC "DEFINES" REP (cmake build + fresh-711, matched replicate nudges as bulk), cmp.py PREFIX (paired vs frozen xC reps), mkwasm.py, run_fresh_fb.py.
Frozen fresh-711 reference (bulk/tables bk_xC, xCr1, xCr2): mean 0.405/0.418/0.394, >3/5/10 = 10-11/3-6/0, peak 20.17 M.

## 1. Profile of B13 (60 search flights, 72 000 frames; prof_b13.txt). peak 18.26 M, p99 12.8, median 6.50, mean 6.82
Fixed floor every frame (M): klt 3.2 (60 tracks, FB on half) + detect 1.0 + pyramid 0.50 + propagate 0.15 + map_relocalize 0.23 avg (4.9 at one frame/300) = ~5.3 M.
Peak frames (21-23, 61-63, 101-103: the window slide cohort; nbatch only ~8 features but ~62 rows -> QR to 36-42 rows; D = 60 with the transient 7th clone), top 0.5% frames (14.0 M mean):
QR compression 2.0 (4.7 at peak), solve_dx 2.6 (iteration-0 dx; unoptimised scalar code), update() 1.95, gate H0P 0.9 (2.0 at peak, both passes), gate S 0.46, nullspace 0.35, chol 0.14, triangulate 0.15; klt 3.4, detect 1.0.
Startup: frame 0 5.2 (detect 2.95 + gray128 2.1), net prep frame 5 = 9.4 (net prep 3.6 + gray128 2.1 + klt), net conv frame 6 = 8.4-10.5 (conv 4.2); first slide frames 21-23 up to 15-18 M.
Iterated update = two passes of build_rows (feature_rows + QR) + solve_dx + final update.

## 2. Exact rewrites (bit-identical poses on the 60 profiled flights; fresh-711 ATE compare in section 4)
* E1 QR compression (build_rows): column-chunked (6/2/1 columns) register accumulators, same per-element order: QR 4.7 -> 2.8 M at peak.
* E2 solve_dx: same register-blocked HP/S kernels as update() plus SIMD dx: 2.6 -> 0.9 M.
  Peak (60 flights) 18.26 -> 14.67 M, median 6.50 -> 6.06, mean 6.82 -> 6.26.
* Tried and discarded: skipping zero-v rows in the Householder loops (no zero rows: no gain, peak 15.07).

## 3. Fresh-711 single-arm screens (1 replicate; B13 frozen xC r0 0.405 [reps 0.405/0.418/0.394], peak 20.17 M; chaos sd ~0.012/rep)
Exact y1 (b13y.c = QR+solve_dx rewrites): ATE bit-identical 711/711 vs bk_xC; fresh peak 20.17 -> 16.07 M.
| arm (on b13y exact) | fresh mean | d | >3/5/10 | fresh peak M |
| MAX_CLONES=5 (cl5) | 0.411 | +0.007 | 7/2/0 | 12.54 |
| GATE2=1 (iteration passes reuse pass-1 chi2 decision) | 0.391 | -0.013 | 9/3/0 | 14.70 |
| FB_PERIOD=4 | 0.449 | +0.044 | 11/3/1 | 16.14 | REJECT (FB check matters)
| KLT_ITERS=3 | 0.423 | +0.018 | 10/6/0 | 15.69 | marginal
| DET_PERIOD=2 (empty cells rescored every 2nd frame) | 0.401 | -0.003 | 7/2/0 | 14.64 |
| ITER_TH=0.1 | 0.390 | -0.015 | 11/4/0 | 16.09 | (skips 2nd pass when |dx|<0.1)
| KLT_R=3 (7x7 window) | 0.382 | -0.022 | - | 14.68 | median frame -20%
| GRID 8x6 | 0.400 | -0.005 | - | 15.46 |
| MAP_TRY=4 alone | 0.410 | +0.006 | - | 16.07 |
(profile screens: all-arm combo MAX_CLONES=5 GATE2 MAP_SPREAD KLT_ITERS=3 FB4 DET2 ITH peak 9.6 M median 4.7 M; net frames 5/6 become the peak -> LC_SPREAD=4 table row added (gray128 at K, prep K+1, conv0+1 K+2, rest K+3): peak 9.3 -> net <=7 M.)
NOTE queue2 (c1*) accidentally ran single arms (shell var bug): c1=exact, c1kr3=KLT_R=3, c1g86, c1kit3, c1mt4 are the single-arm numbers above.

## 4. B16 port (coordinator: frozen ATE build is now B16 = tailcap/tc_b16.c, same fuel path)
b16x.c = tc_b16.c + b13y exact rewrites + arms (patch b13x_to_w.patch; top defines made #ifndef). Pose bit-identical to B16 on 60 profiled flights.
Frozen B16 fresh reference tables: tailcap/tables/b16r_r{0,1,2}.json (fresh mean 0.388/0.394/0.389 on 855 set; fresh-711 via cmp.py).
## 5. VIS4 = time-sliced vision (b16s.c, -DVIS4=1)
Pyramid + add_clone only on phase 0 (every 4th frame); the 60 tracks tracked 1/4 per frame (i%4==phase) from the stored previous-cycle image pair (5 Hz tracking, gyro-predicted over 4 frames), observation recorded for the cycle's clone;
oldest-clone takes per phase use the same slice; remove_oldest + vision_zupt at phase 3; detect one cell quarter per phase; map at phase 0 only. Delayed MSCKF rows stay consistent (rows only involve clones).
Profile (30 search flights, VIS4 + MAP_TRY=2 MAX_CLONES=5 GATE2 ITER_TH=0.1 LC_SPREAD=4 KLT_R=3): median frame 1.82 M, mean 2.09 M, p99 5.4, peak 7.9 (startup frame 0 5.3; window-slide frames 20-23/60-63 6-7 M: update fixed cost). ATE not yet measured (queue4).

## 6. B16-based results (fresh-711, 1 replicate, vs B16r r0 fresh 0.354 [reps 0.354/..], >3/5/10 4/1/0)
| build | fresh mean | d | >3/5/10 | fresh peak M |
| b16exact (QR+solve_dx exact rewrites) | 0.354 | 0.000 (bit-identical 711/711) | 4/1/0 | 16.07 (B16 20.17) |
| s1 = C1(cl5 gate2 det2 ith0.1 ms ls4)+KLT_R=3 | 0.440 | +0.087 | 8/3/0 | 9.44 | arms do NOT compose on B16 (singles on B13 were neutral): REJECT
| s1b = s1 + MAP_TRY=4 KLT_ITERS=4 | 0.415 | +0.061 | 4/1/0 | 8.91 |
| v4a VIS4 (+MAP_TRY=2 cl5 gate2 ith ls4 KLT_R=3) | 0.788 | +0.435 | 18/5/0 | 8.57 |
| v4b VIS4 (same minus KLT_R=3) | 0.830 | +0.477 | 19/5/0 | 8.67 |
| v4c VIS4 + MAP_TRY=2 only | 0.808 | +0.454 | 20/2/0 | 15.2 (frame-0/net unsliced) |
Score arithmetic: halving peak = +0.28 pt, 20% ATE cut = +0.5 pt => a halving pays only if ATE rises < ~11%. So deep cuts need near-lossless accuracy.
VIS4 bug found: forward-backward parity (frame_no+i)%2 is constant within a slice => FB check was never applied (diagnosis: nis 1.2 vs 0.27, more gate rejects). Fixed (vis_cycle + i/4); v4d/v4e rerun queued (queue7), plus single arms on b16q (k_*).
VIS4 diagnosis/fixes (fresh-711, 1 rep, vs B16 0.354): FB parity bug fixed -> v4d (FB every pass) 0.503 (+0.150); v4e (FB every 2nd cycle) 0.577; + velocity-extrapolated KLT guess (VIS4_VEL=1) v4f 0.457 (+0.103); + LEVELS=3 (capture range) v4g 0.392 (+0.039 [+0.003,+0.087], >3/5/10 4/1/0 = same tails as B16); KLT_ITERS=8 v4h 0.437 (no help).
Single arm on B16: MAX_CLONES=5 0.377 (+0.024 [+0.006,+0.043]).
SIMD pyramid for LEVELS>=2 (exact, bit-identical to scalar): 3-level pyramid 1.29 -> 0.32 M.
LC_PSPLIT=1 (prep stage over 3 frames; exact when LC_PSPLIT=0 verified 60/60). Profile-peak for planned finalists (60 search flights): w1 (V4 L3, cl6) 14.1 M median 2.9 | w2 (+cl5 gate2 ith0.1) 8.65 M median 2.7 | w3 (+cl4 ITER_UPD=1 CAP_OLD=4 CAP_LOST=5) 6.67 M median 2.4. ATE evals queue9 (w1-w4).
Single arms on B16 (fresh-711, 1 rep, B16 0.354): KLT_R=3 0.348 (-0.005) | GATE2+ITER_TH=0.1 0.354 (0.000) | DET_PERIOD=2 0.359 (+0.006) | MAX_CLONES=5 0.377 (+0.024) | MAP_SPREAD+LC_SPREAD=4 0.388 (+0.034 REJECT).
=> gated-safe set g1 = KLT_R=3 GATE2=1 ITER_TH=0.1 DET_PERIOD=2 (profile peak 10.8 M, median 4.2 vs exact 14.7/6.1): 3-rep eval queued (queue10).
w1 (V4 L3 + LS4 + PSPLIT) 0.395 (+0.041) fresh peak 16.7 (unsliced startup/other frame); w2 (+cl5 gate2 ith) 0.432 (+0.078), peak 9.84 M.
Score check: w2 = 1.04 halvings of peak vs B16 20.17 (+0.29 pt) but ATE +22% (about -0.44 pt) => NOT favourable. Fuel cuts only pay where ATE is neutral.

## 7. FINAL PARETO (fresh-711; ATE = mean of reps; peak = max fresh frame; mean/median fuel from 60-flight search profile)
| build | peak M | mean / median M | fresh mean (reps) | d vs B16 [CI] | >3/5/10 | est. points vs B16* |
| B16 frozen | 20.17 | 6.8 / 6.5 | 0.356 (3) | 0 | 4.3/1.3/0 | 0 |
| b16_exact (QR + solve_dx rewrites, bit-identical 711/711) | 16.07 | 6.3 / 6.1 | 0.356 | 0 (identical) | same | +0.09 |
| b16_g0 = exact + KLT_R=3 GATE2=1 ITER_TH=0.1 | 15.01 | 5.1 / 4.9 | 0.359 (3) | +0.003 [-0.014,+0.019] | 7.3/2.0/0 | +0.10 |
| g1 = g0 + DET_PERIOD=2 (3 reps) | 13.29 | 4.4 / 4.2 | 0.385 | +0.028 [+0.008,+0.055] FAILS gate | 7.7/2.3/0.3 | ~0 |
| w1 = VIS4 L3 (5 Hz sliced vision, 3 levels, FB every pass, velocity guess) | 16.7 | 3.2 / 2.9 | 0.395 (1) | +0.041 | 4/1/0 | -0.15 |
| w4 = w1 + cl5 + gate2 + ith0.1 + KLT_R=3 | 8.60 | ~2.7 / ~2.6 | 0.413 (1) | +0.060 [+0.028,+0.097] | 3/2/0 | ~0 |
| w2 = w1 + cl5 gate2 ith0.1 | 9.84 | 2.9 / 2.7 | 0.432 (1) | +0.078 | 8/2/0 | -0.14 |
| w3 = V4 cl4 ITER_UPD=1 caps | 7.54 | 2.5 / 2.4 | 0.533 (1) | +0.180 | 12/2/0 | strongly negative |
*points: +0.28 per halving of peak vs 20.17 M, -0.5 per +20% ATE (log scale), reps=1 rows noisy (chaos sd ~0.012/rep).
Rejected singles on B16: LC_SPREAD=4 +0.038, LC_SPREAD=4+LC_PSPLIT +0.325 (net delay hurts; PSPLIT likely also has a bug), MAP_SPREAD +0.011, cl5 +0.024, FB_PERIOD=4 (B13) +0.044, KLT_ITERS=3 +0.018.
Peak floor of g0: map_relocalize (3.6-5 M on clone frames with 6 tries), net frames 5/6 (9-10 M) and re-anchor net stages (conv 4.3, prep 3.3), KLT 2.2-3.4.
Deliverables: final/b16_exact.wasm (preflight/exact: ABI ok, zero imports, poison/prefix/repeat 486/486, reset 8/8, 711/711 ATE identical to B16), final/b16_g0.wasm (preflight/g0 pending/see below), final/SHA256SUMS, source final/b16_exact_and_g0_source.c (= b16q.c; g0 = -DKLT_R=3 -DGATE2=1 -DITER_TH=0.1 with the cmake recipe, -O3).
Conclusion: exact rewrites give -20% peak free; ATE-neutral arms give a further -7%; deeper cuts (1/2 peak) cost 15-20% ATE which is about break-even to negative under the stated score slopes. Ideas not done: exact SIMD of map ZNCC (lane per dx, 3.6 M), Givens null-space, f32 covariance blocks, op-budget governor.
Transfer: all changes are in b16x/b16q (B16 source); B13 differs only by the tc_* blocks, B15 (B11 base) lacks iterated update/map so only QR/solve_dx-free paths: KLT_R=3, DET_PERIOD, cl5, VIS4 transfer; GATE2/ITER_TH/solve_dx do not apply.
