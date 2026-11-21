# tier1m NOTES (~1 M peak fuel tier; own dir only; no git; holdout untouched; fold-4 sealed never read)

Base: fuel_b13/b16s.c copied as t1.c (B16 + exact rewrites + VIS4 arm; all switches default = B16 exact).
Tools: prof.sh SRC TAG "-DX=1" [N=60] [REF] (profile build with phase marks, N search-fold flights, phase table prof/an_TAG.txt,
optional pose bit-compare vs another tier1m profile), ev.sh NAME SRC "X=1 Y=2" [rep] (cmake -O3 build + fresh-711, 24 workers,
waits while load > 170; table tables/NAME.json), cmp.py NAME [NAMEr1 NAMEr2] (paired vs frozen B16 reps tailcap/tables/b16r_r*.json,
dev = fresh folds 0-2, confirm = folds 3-4).
Score arithmetic (vs B16 server 17.0 M, local fresh 0.354): break-even local fresh ATE at peak 4 M 0.46, 2 M 0.52, 1 M 0.59, 0.5 M 0.67
(points = 0.28*log2(17/peak) - 2.24*ln(ATE/0.354)).

## Log
- Baseline profile (t1.c, defaults = B16 exact, 60 search flights): peak 14.67 M, p99 10.6, median 6.07, mean 6.26.
- KLT_INT=1: integer SIMD KLT (8x8 window, Q7 bilinear samples, i16x8 rows, i32 dot products): klt 2.85 -> 0.36 M/frame avg;
  profile peak 11.26 M, median 3.42 M. Remaining per-frame floor: detect 1.1-2.2 M (empty cells rescored every frame), pyramid 0.50,
  propagate 0.15, update 0.6 (median frame), solve_dx 0.2, map 0.1-3.6 (spiky). Peaks: frame 0 (detect 2.95 + gray128 2.1),
  net frames 5/6 (prep 3.56 + gray128 2.1 / conv 4.26), window-slide frames 21-23, 61-63, 101-103 (QR 2.2, update 1.95, gate H0P 1.6, solve_dx 0.9).
- Fuel accounting insight: wasmtime fuel = 1 per wasm instruction incl. local.get/set/const, so real cost is ~2.5-3.5x a
  "vector-op" count; memcpy compiles to memory.copy (1 instruction regardless of size) -> stashing a 230 KB RGB frame is free.
- Switches added to t1.c (all default off = B16 exact):
  KLT_INT (int SIMD KLT) | DET_BUDGET/DET_BUDGET0/DET_T0/DET_COOL/DET_STRIDE/DET_SIMD (detection limits) | GRAY_G (level 0 = green)
  | COVPROP (covariance propagated once per frame, nominal per sample) | ROWCAP / LOST_KEEP (max (2n-3) rows of features taken per frame)
  | UPD_LR (low-rank sequential update: NOT cheaper, 55k/row vs 44k: dropped) | PRIOR_MERGE (thrust + velocity priors in one update)
  | F_MIRV (exact: P mirror by 2x2 transposes, -20k/update call) | NET_SLICE + NET_UNITS/NET_UNITS_IDLE/NS_BUSY (net as 97 row-chunk
  micro-steps from memcpy'd RGB of frame 0 and K, run after vision; more steps on frames without MSCKF rows) | NS_PRIOR_KEEP (heading
  prior until the net lands) | NS_GRAYI (integer gray128: verified 0/614400 px differ from the float path) | NS_PREPF (float prep, approx)
  | MAP_ZI (integer SIMD ZNCC: bit-identical poses 30/30, map 0.233 -> 0.077 M avg, spikes 4 M -> 0.7 M).
- Measured costs (profile): MSCKF row ~36k (update) + 23k (solve_dx, ITER_UPD=2) + 9k (gate) instructions; per-frame small priors
  0.225 M (3 update calls) -> 0.146 (PRIOR_MERGE) -> 0.126 (F_MIRV). Net under NET_SLICE: gray pair-steps ~0.12 M each (float), ~0.24 M/2 units.
## fresh-711 results (1 rep, vs B16 0.354; d = paired)
| name | config | fresh | d | dev / conf d | >3/5/10 | note |
|---|---|---|---|---|---|---|
| ki | KLT_INT | 0.330 | -0.023 [-0.047,-0.001] | -0.030 / -0.010 | 2/0/0 | int KLT is BETTER and 8x cheaper |
| kd | ki + DET_BUDGET=3 DET_COOL=8 | 0.449 | +0.095 | +0.102 / +0.081 | 3/0/0 | REJECT: detection budget hurts |
| kdT | kd but unlimited first 24 frames | 0.429 | +0.076 | +0.067 / +0.094 | 1/0/0 | REJECT: steady-state refill matters, not startup |
| kdC | ki + DET_COOL=8 | 0.344 | -0.009 | -0.006 / -0.016 | 1/0/0 | ok (cooldown fine; the per-frame BUDGET was the problem) |
| ka2 | ki + ALT2 (vision at 10 Hz on alternate frames) | 0.408 | +0.055 | +0.032 / +0.100 | 4/1/0 | 10 Hz costs ~+0.08 vs ki |
| lf1 | ki + GRAY_G COVPROP NET_SLICE(1/3 units) PRIOR_MERGE F_MIRV NS_GRAYI NS_PREPF MAP_ZI | 0.645 | | | | BAD: net lands ~frame 35-50 |
| a5 | ALT2 stack + ROWCAP=12 etc. | 2.72 | | | | BAD: ROWCAP head-of-line blocking bug (features > cap blocked the lost queue) + net delay |
| kS4 | ki + DET_STRIDE=4 | 0.346 | -0.007 | -0.016 / +0.010 | 1/0/0 | ok |
- BUGFIX: ROWCAP/GOV feature selection now splits a feature that does not fit (oldest m observations now, the rest later, sharing
  one observation: take_lost_cap/gov_take_track/gov_split) -> no head-of-line blocking.
- 48-flight quick subset (qe.sh, sub48 = every 15th fresh flight; tails dominate its mean -> look at medians): ki 0.377 / med 0.281.
  Bisection of the a5 stack: PRIOR_EVERY+PRIOR_MERGE 0.342 ok; COVPROP+GRAY_G 0.357 ok; NET_SLICE group 0.720 (BAD);
  detection group (PERIOD 2, STRIDE 4, COOL 4, BUDGET 12) 0.508 (bad; budget again).
- NET_SLICE root cause = DELAY of the net measurement, not arithmetic (LC_DEBUG: mu/sd identical to the unsliced net to 3 decimals;
  NS_GRAYI/NS_PREPF outputs identical). All units in frame K: 0.345 / med 0.246; post-K start delayed 3 frames: 0.455 / 0.258;
  8 frames: 0.516 / 0.338; 8 units/frame (lands ~frame 12-15) 0.52 / 0.366; + VKC (velocity-at-K clone, exact delayed fusion) 0.55 / 0.316;
  NS_PRIOR_KEEP=0 0.54. Hypothesis: early MSCKF updates linearized with the wrong start velocity. Test NS_HOLD (no MSCKF until the net lands).
- Net micro-step costs (post-K work 8.5 M): gray 16k/pair (0.77 M/image), prep 102k per 4 rows (3.07 M even in float!), conv0 1.21,
  conv1 1.88, conv2 0.84, conv3 0.35, head 0.40 M.
- memcpy is NOT free: memory.fill/copy cost ~1 fuel per byte in wasmtime (measured 230410 for 230400 bytes); RGB stash = 0.235 M.
- GOV (op-budget governor, t1.c GOV=1): per-frame budget GOV_B; vision (GOV_VIS=1 every frame, 2 = 10 Hz; VSPLIT=1 splits the 10 Hz
  vision A=pyramid+even tracks+clone / B=odd tracks+record+zupt+detect), then MSCKF features within the budget (feature splitting),
  detection cells, map try, net units. Calibrated constants GC_* (instructions): pyramid 211k, KLT call 5.2k, row ~80k, cell 20k.
- (rate-limit pause 06:41-09:24; resumed from disk)
| kP2C | ki + DET_PERIOD=2 DET_COOL=8 | (see tables) | | | | |
| kB12 | ki + DET_COOL=8 DET_BUDGET=12 | 0.358 | | | | ok: 12 cells/frame budget is fine (3 was not) |
- NS_PREPV (f32x4 projective derotation, exact to 3 decimals on mu after fixing a u8 load bug): prep 3.07 -> 2.01 M total.
- NS_CONVQ (12-bit i16 dot-product conv): outputs match (1e-3) but MORE fuel (first-use weight quantization 0.75 M, steps 150-200k): off.
- VKC (velocity-at-K clone, CORE 24 incl. 3 zero padding states so D stays a multiple of 6) + NS_HOLD (no MSCKF until the net lands):
  sub48 median recovers (0.271 vs instant-net 0.287) but tails remain (>1 m: 5 vs 1).
- GOV tiers, full fresh-711 (1 rep; common: KLT_INT GOV NET_SLICE NS_GRAYI NS_PREPV NS_HOLD VKC PRIOR_MERGE F_MIRV F_CLONEV GRAY_G COVPROP
  MAP_ZI MAP_SCAN=24 DET_STRIDE=4 DET_COOL=8 GATE2 ITER_TH=0.1; GC_ROW=105k GC_UNIT=160k):
| T4 | GOV_B=3.6e6 | 0.392 | +0.039 [+0.017,+0.063] | +0.034 / +0.047 | 4/0/0 | peak 3.98 M |
| T2 | GOV_B=1.8e6 | 0.666 | +0.313 | +0.361 / +0.215 | 16/4/0 | peak 2.07 M; BAD |
- T2 diagnosis (sub48): free net units 0.64/0.43, free detection 0.87/0.53, free MSCKF rows 0.49/0.32 (peak 19.9 M) -> the MSCKF row
  budget is the problem: demand 10.8 rows/frame (p90 27, p99 54) at ~105k instructions/row = 1.13 M/frame MEAN; supply at B=1.8 M 7.7.
  GOV_PRUNE (drop observations of marginalized clones from queued features before budgeting) added.
| T3 | GOV_B=2.7e6 PRUNE | 0.410 | +0.057 [+0.028,+0.086] | +0.039 / +0.093 | 4/1/0 | peak 2.96 M |
| T2b | GOV_B=2.0e6 PRUNE ITER_UPD=1 GC_ROW=65k | 0.492 | +0.139 | +0.126 / +0.165 | 11/2/0 | peak 2.41 M |
- Area vs B16 server point (0.28*log2(17/peak) - 2.24*ln(fresh/0.354)): ki +0.25 (13.5 M, 0.330), T4 +0.36, T3 +0.38, T2b +0.05.
- Queued: T2c (T2b + 40 tracks), T4u (T4 + PRUNE + GOV_UMAX=40: net lands faster), T6 (B=5.6e6 UMAX 60 ROWCAP 36: net lands frame 7,
  profile peak 5.71 M), T1v (B=0.9e6, 10 Hz VSPLIT, KLT_VEL, PRIOR_EVERY=2, ITER 1), T1n (T1v without the net, profile peak 1.08 M).
- preflight.sh <wasm> <outdir>: sha, imports, ABI check, poison/prefix/repeat on 18 fixtures x 33 prefixes (0-16, 20, 24, 29-31,
  40, 41, 60, 99-105, 120, 600, 1199), reset check on 8 fixtures.
| T2c | T2b + GRID 8x5 (40 tracks) | 0.501 | +0.147 | | 12/2/0 | peak 2.51 M |
| T4u | T4 + PRUNE + GOV_UMAX=40 (net lands ~frame 8) | 0.389 | +0.036 [+0.007,+0.063] | +0.024 / +0.059 | 3/0/0 | peak 4.00 M |
| T6 | B=5.6e6 PRUNE UMAX 60 ROWCAP 36 (net lands frame 7) | 0.387 | +0.033 [+0.010,+0.056] | +0.030 / +0.038 | 4/0/0 | peak 5.92 M |
- COORDINATOR targets (09:5x): <=7 M with ATE as close to B16 as possible (<=0.39 beats b16_mid_m7 0.890@7.27 M server), ~0.41 at
  <=3.5 M, 1 M tier. T4u and T6 both meet target 1; T4u dominates on area (4.0 M). Baked sources t1m_T4u.c / t1m_T6.c (defines
  prepended to t1_i.c); wasm byte-identical to the define builds: t1m_T4u.wasm sha256 aa99218d04b2b93fb6b5cf56f2461f07198dab9f033f7da3ddfa06f5cdf124db,
  t1m_T6.wasm 44ffff2eb5c2a6094435a26175a98dbe8ce24331cc15dc659b8abdd4c15a22b5. Preflight running (preflight_T6/, preflight_T4u/);
  T6 ABI ok, zero imports. Reps r1/r2 queued; component attribution at B=50e6 (X50*) queued.
- sel144 (visible folds 0-3) T4u: search 0.613 vs B16 0.595 (>3 m 6/6), val (n=25) 0.503 vs 0.374 (one flight 3.78 vs 1.42; chaotic tails both ways). Peak sel 3.98 M.
| T6 x3 reps | | 0.387 (0.387/0.389/0.386) vs B16 0.356 | +0.031 [+0.010,+0.052] | +0.030 / +0.032 | 3.0/0.0/0.0 (B16 4.3/1.3/0) | peak 5.97 M |
- PREFLIGHT T6 and T4u: PASS. ABI check ok, zero imports, poison/prefix/repeat 594/594 each (18 fixtures x 33 prefixes incl 0-16,
  20, 24, 29-31, 40, 41, 60, 99-105, 120, 600, 1199), reset 8/8 x 700 frames, 711/711 completed, 0 filled, 0 errors,
  determinism sel144 scored twice: ATE identical 144/144 (T4u). SHA256SUMS in tier1m/.
| T4u x3 reps | | 0.391 (0.389/0.395/0.390) vs B16 0.356 | +0.035 [+0.011,+0.060] | +0.028 / +0.049 | 2.7/0.0/0.0 | peak 4.10 M; area +0.37 vs B16 point |
| T1v | B=0.9e6 10 Hz VSPLIT KLT_VEL PRIOR_EVERY=2 ITER 1 RESERVE | 1.106 | +0.752 | +0.717 / +0.823 | 43/15/1 | peak 1.20 M; net lands frame ~45-80 |
| X50 | common at B=50e6 (no budget; net lands at K) | 0.360 | | | | peak 12.3 M: components cost ~+0.03 vs ki, budget/delay another ~+0.03 |
## B17 (coordinator 10:2x): B17 = B16 + LI_GATENET=0.2 + LI_PVS=1 (LI_PVS_T0=3.0); fresh 0.337 (lateinit/tables/gnp_r*.json)
- addb17.py ports both switches (same code as lateinit/li.c) into any B16-path source; t1.c now has them (default off).
- b17_exact.c = fuel_b13/final/b16_exact_and_g0_source.c + B17 switches ON: fresh-711 ATE bit-identical to B17 711/711, peak 16.09 M
  (B17 20.17 M); rebuild byte-identical; wasm b17_exact.wasm sha256 44dcb8615023e636c795e530a2793a2dad3c1c45b0f42a3fdc52f26bc420f74a.
  Preflight running (preflight_b17x/, prefixes now incl. 61-66, 70, 80 for the static re-anchor) + sel144 determinism.
- cmp.py: BASE env selects the reference tables (BASE=lateinit/tables/gnp_r%d.json for B17).
| T4uB | T4u + LI_GATENET=0.2 LI_PVS=1 | 0.384 vs B17 0.338 | +0.045 [+0.014,+0.082] | +0.040 / +0.056 | 3/1/1 | peak 4.00 M (T4u vs B17: +0.051) |
- E7 family (near-exact, no governor): NET_SLICE + NS_SCHED (gray0 4 steps/frame before K, gray5+prep at K, convs+head at K+1 = B16
  timing; re-anchor split over 2 frames and deferred while rows > NS_RA_ROWS) + KLT_INT MAP_ZI MAP_SCAN=24 MAP_SPREAD F_CLONEV F_MIRV
  ROWCAP=30 (split) DET_COOL=8 DET_STRIDE=4 GRAY_G COVPROP PRIOR_MERGE + B17 switches. Profile peak 5.68 M (initial net K+1 frame 5.5 M).
- PREFLIGHT b17_exact: PASS. ABI ok, zero imports, poison/prefix/repeat 738/738 (18 fixtures x 41 prefixes incl. 0-16, 20, 24, 29-31,
  40, 41, 60-66, 70, 80, 99-105, 120, 600, 1199), reset 8/8 x 700 frames, determinism sel144 identical to B17 144/144 (and fresh
  711/711 identical to B17), 0 filled. b17_exact.wasm = zero-risk submission (local peak 16.09 M fresh / 14.66 M sel).
| E7c | E7 family, NS_RA_ROWS=12 | 0.380 vs B17 0.338 | +0.042 [+0.014,+0.077] | +0.045 / +0.035 | 2/1/1 | fresh peak 7.51 M: dominated by T4uB (4.0 M) |
| X50n | X50 without NET_SLICE/HOLD/VKC (B16 net timing) | 0.383 | +0.029 | | | single-rep noise ~+-0.012..0.02: X50 0.360 vs X50n 0.383 is not a real ordering |
- DECISION for the <=7 M target: T4uB (4.0 M) beats every 5-7.5 M build on local ATE within noise -> submit candidate = T4uB.
  Baked source t1m_T4uB.c (byte-identical wasm to the define build), wasm t1m_T4uB.wasm; preflight_T4uB/ running; reps r1/r2 queued.
| T4uB x3 reps | | 0.381 (0.384/0.383/0.377) vs B17 0.337 / B16 0.356 | +0.045 [+0.022,+0.069] vs B17; +0.025 [+0.003,..] vs B16 | +0.040 / +0.054 | 2.0/0.3/0.3 (B17 2.3/0/0) | peak 4.10 M, 0 filled, 0 errors |
- PREFLIGHT T4uB: PASS (ABI ok, zero imports, poison/prefix/repeat 738/738 incl. 60-66/70/80 static re-anchor prefixes, reset 8/8,
  baked source byte-identical). t1m_T4uB.wasm sha256 e13ccbbf1502c9e6d115ee88e5e1a35ce672f6368da9af06ebfc4528201faaa2.
  Area vs B16 server point: +0.42 (server projection ~0.84 m at 4.1 M vs b16_mid_m7 0.890 @ 7.27 M).
- T4uB sel144 determinism 144/144 identical.
- T4uB sel144 vs B17: search 0.633 vs 0.556 (>3 m 6 vs 5), val 0.497 vs 0.367 (1 flight >3 m): the selected set shows a larger loss than fresh (+0.08/+0.13).
| T3u | B=2.9e6 PRUNE UMAX 40 (no B17 switches) | 0.400 | +0.046 [+0.025,+0.069] | +0.040 / +0.060 | 3/0/0 | peak 3.15 M; area +0.41 |
| T1n | T1v without the net | 0.994 | +0.640 | +0.591 / +0.739 | 50/16/1 | peak 1.18 M |
## PARETO (fresh-711; area = 0.28*log2(17/peak) - 2.24*ln(fresh/0.356) vs the B16 server point)
| build | peak M | fresh | reps | >3/5/10 | area |
| b17_exact (bit-identical B17) | 16.1 | 0.338 | = B17 | 2.3/0/0 | +0.12 |
| T6 (B=5.6 M) | 5.97 | 0.387 | 3 | 3/0/0 | +0.24 |
| T4uB (B=3.6 M + B17 sw.) PREFLIGHTED | 4.10 | 0.381 | 3 | 2/0.3/0.3 | +0.42 |
| T3u (B=2.9 M) | 3.15 | 0.400 | 1 | 3/0/0 | +0.41 |
| T2b (B=2.0 M, ITER 1) | 2.41 | 0.492 | 1 | 11/2/0 | +0.05 |
| T1v (0.9 M, 10 Hz) | 1.20 | 1.106 | 1 | 43/15/1 | -1.48 |
| T1n (0.9 M, no net) | 1.18 | 0.994 | 1 | 50/16/1 | -1.23 |
Why the curve breaks below ~3 M: MSCKF rows cost ~100k instructions each (demand ~11 rows/frame mean, p99 54) and the startup
net (7.5 M after frame K) must land within ~2-3 frames of K (delay of 3 frames +0.01 median, 8 frames +0.09; VKC+HOLD recovers the
median but not the tails). Next levers: cheaper rows (Givens null-space, f32 P, dynamic VK block), cheaper exact net prep (scalar
bilinear gather dominates the 2 M prep).
