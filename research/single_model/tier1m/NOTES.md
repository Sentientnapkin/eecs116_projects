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
