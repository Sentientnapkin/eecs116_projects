# Reducing the per-frame wasm fuel of gp_msckf (gate build G) without hurting accuracy

All measurements below were made on this machine with the repo toolchain (wasi-sdk 34 / clang 23, wasmtime 50.0.1 through the VIOBench evaluator). Full engineering notes, tables, scripts and the patch: `research/single_model/fuel/NOTES.md`. "Source" links are local files unless a URL is given. Base = `research/single_model/final/submit/gate.c` (G), as instructed after the fresh-set result; fgt.c was only used for the first flag measurements.

## (1) How does the VIOBench evaluator count fuel?

### Takeaway
Fuel is wasmtime's per-operator fuel with the default cost: one unit per executed wasm operator (including `local.get`, constants, loads, stores; `loop`/`end` are free), no weighting for division, sqrt, memory or SIMD; a SIMD128 operator is 1 unit for all its lanes. Only the guest `step()` call is metered, and the score is the maximum over all frames of all episodes.

### Cited Findings
- The engine is wasmtime 50.0.1 with `consume_fuel=True`, `wasm_simd=True` (SIMD128 allowed), `cranelift_opt_level="speed"`, no custom operator costs — [engine.py](/dev/shm/sebastian-vio/viobench/viobench/tools/runner/engine.py)
- Fuel is armed to `step_fuel` (2e10) just before the guest `step` export and read back just after, so host PNG decoding and the memcpy of frame/IMU into guest memory are not charged; a failing step still reports its consumed fuel — [sandbox.py](/dev/shm/sebastian-vio/viobench/viobench/tools/runner/sandbox.py)
- The score point is the maximum single-step fuel across all attempted frames of all selected episodes (mean/median/p95 are reported only); init fuel is separate with a 2e11 budget — [TASK.md](/dev/shm/sebastian-vio/viobench/docs/TASK.md), [config.json](/dev/shm/sebastian-vio/viobench/viobench/tools/config.json), [run.py](/dev/shm/sebastian-vio/viobench/viobench/tools/runner/run.py)
- The repo's cmake recipe already compiles with `-O2 -msimd128` — [viobench_reactor.cmake](/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native/viobench_reactor.cmake)
- Wasmtime documents per-operator fuel cost fields (`OperatorCost`, e.g. `LocalGet`, `I32Add`) — [wasmtime OperatorCost docs](https://docs.wasmtime.dev/api/wasmtime/struct.OperatorCost.html) (opened; the default values are not shown in the part of the page that could be read)
- Microbenchmarks compiled with the repo toolchain and run through the evaluator's `Sandbox` (fuel per loop iteration): f64 add chain 2.70, f64 mul 2.70, f64 div 3.40, f64 sqrt 3.875, f32 add 2.70, f64x2 SIMD add 2.70 (same count, 2 lanes), i32x4 mul+add 1.375, indexed f64 load+add 10.4, store+load 18.0, libm `sin` 157.9 per call, empty step 121; disassembly (llvm-objdump) confirms 27 operators per 10 unrolled adds, i.e. every operator including `local.get`/`const` costs 1 and div/sqrt cost the same as add — [mb.c](research/single_model/fuel/micro/mb.c), [mb_results.txt](research/single_model/fuel/micro/mb_results.txt)

### Inferences
- Fuel is an instruction count, not a cycle model: division, sqrt and memory ops are as cheap as an add, so only the number of executed operators matters. Savings come from lane-parallel SIMD, fewer index/`local.get` operators (unrolling, pointer-increment loops), fewer redundant loads, and avoiding libm calls (sin ~158 each).
- SIMD helps only for lane-parallel work; `splat`, `extend`, shuffles and lane extracts each cost one operator.
- `-Os`/`-Oz` are worse (+29 %/+43 % peak); `-O3` helps 3-6 %.

### Gaps
- The default wasmtime `OperatorCost` table was not found in the docs; the rule "1 per operator" is empirical (microbenchmarks).

## (2) Where does the fuel go per frame (max frame vs median frame)?

### Takeaway
G averages 8.99 M per frame: KLT 2.8 M, detect 2.0 M, gray+pyramid 1.3 M, MSCKF per-feature work and EKF update ~2.3 M, IMU 0.2 M. The peak frames (up to 22.5 M) are the three in-between frames of each 4-frame cycle that process the spread MSCKF batch (~11 features, ~81 rows): the extra ~10 M over the median is the batch's gate, QR compression and covariance update; clone frames are the cheapest.

### Cited Findings
- Profile method: a profiling copy of the source calls a host import `env.mark(id)` at component boundaries and the harness reads the store fuel (never submitted); totals match the evaluator (peak 22.55 M vs 22.54 M) — [prof_run.py](research/single_model/fuel/prof_run.py), [mkprof.py](research/single_model/fuel/mkprof.py)
- Per component, M fuel (G, mean / median frame / peak frames): propagate 0.21/0.21/0.21; pyramid 1.27/1.27/1.27; KLT 2.83/2.87/3.09; detect 2.01/2.32/2.69; per-feature gate 0.52/0.32/3.25; null-space 0.12/0.08/0.73; QR compression 0.08/0.00/2.06; update HP 0.60/0.38/1.75, S 0.13/0.05/0.56, Kt 0.45/0.24/1.56, P update 0.63/0.52/1.24; total 8.99/8.36/18.9 — [gate_profile.txt](research/results/single_model/fuel_prof/gate_profile.txt)
- Frame phase: clone frames (index%4==0) mean 7.2 M (p99 11.3 M); the other three phases 9.4-9.7 M (p99 16.4-16.8 M); 40/33/26 % of the top 1 % frames are phases 1/2/3 and 0.7 % clone frames; fuel correlates with update-batch size (r=0.81: 0 features 6.9 M, 4-8 11.9 M, >20 17.5 M); 17 of 119 flights peak in the first 40 frames (startup: all cells empty) — analysis of `fuel_prof/gate/*.npz` over 119 search flights (143k frames)
- The startup prior, movement gate and flow code do not appear in the profile (negligible fuel); the tails patch was not part of the base.

### Inferences
- The max is set by the per-frame MSCKF batch size, not by clone frames; reducing the cost of the batch kernels (gate, QR, EKF update) lowers the max much more than reducing the always-on front end, while the front end (KLT+detect+pyramid ~6 M in G) sets the median.

### Gaps
- Per-component profile covers the 119 search flights only (fold 4 deliberately not analysed).

## (3) Candidate savings and their ATE cost

### Takeaway
A bit-exact rewrite of the hot loops with SIMD128 plus `-O3` cuts the peak 22.54 -> 11.97 M (-47 %), median 8.47 -> 5.13 M, p95 14.2 -> 7.6 M with identical output on every checked flight (144 search+val byte-identical, 711 fresh identical, 8 fixtures bit-identical). Approximate options (f32 KLT, detect throttling, 5 clones, fast-math, fewer features) save another 3-45 % of peak but their ATE effect is within the chaotic replicate noise and they fail the strict fresh criterion, so they are not adopted.

### Cited Findings
- Exact rewrites (each behind a switch, per-element summation order unchanged, no FMA): SIMD gray+pyramid 1.27 -> 0.50 M; integer SIMD detect with sqrt prune 2.0 -> 1.27 M; EKF update in row-vector form 1.8 -> 0.7 M; SIMD per-feature gate 0.52 -> 0.21 M; QR/null-space vector form 0.20 -> 0.09 M; f64x2 KLT patch extraction; `-O3` — [adopted_exact.patch](research/single_model/fuel/adopted_exact.patch), [adopted_exact.c](research/single_model/fuel/adopted_exact.c)
- Peak fuel (search+val) by step: G 22.54 M; source rewrites at -O2 13.87 M; at -O3 12.04 M; plus SIMD detect gradients 11.97 M — [pareto_single_runs.txt](research/results/single_model/fuel_prof/pareto_single_runs.txt) and `fuel_prof/fl_*`
- Flag-only (fgt.c source, 22.98 M at -O2): -O3 22.30, -O3 -flto 21.88, -O3 -ffast-math 21.16, -mno-simd128 25.57 (compiler auto-vectorisation already worth 12 %), -Os 28.97, -Oz 32.27 — [fuel_prof/fl_*](research/results/single_model/fuel_prof)
- Replicate noise: three chaos replicates (PIXEL_STD and DETECT_MIN_SCORE nudged 1 %) of the bit-identical exact build give search means 1.028 / 1.223 / 1.293 (>10 m flights 0/2/1); the submitted single run is the favourable end (replicate mean 1.181) — [cmprep_fuel.py](research/single_model/fuel/cmprep_fuel.py), `research/results/single_model/fuel_xb_r*`
- Approximate arms vs replicate reference (search paired d [95 % CI], peak s+v): f32 KLT +0.070 [-0.004,+0.158], 10.6 M; detect every 2nd frame -0.070 [-0.222,+0.061], 10.3 M; fast-math +0.039 [-0.005,+0.115], 11.8 M; 5 clones -0.043 [-0.186,+0.095], 9.9 M; f32+det/2 -0.028 [-0.180,+0.104], 9.0 M; 5 clones+f32+det/2 +0.186 [-0.020,+0.394] with 2-3 flights >10 m per replicate, 6.8 M; single runs: 48 tracks +0.23, KLT 3 iterations +0.29 (rejected) — `research/results/single_model/fuel_*_r*`, [NOTES.md](research/single_model/fuel/NOTES.md)
- Fresh pool (711 flights, vs G mean 0.8130): exact 0.8130 (all identical, peak 22.76 -> 12.12 M); chaos nudges of the exact build +0.019 (2 flights >10 m) and +0.044 (3 flights >10 m); f32+det/2 +0.026 with one flight at 35.2 m; 5 clones +0.041, static 0.573 -> 0.692 — [fresh_table_*.json](research/single_model/fuel), [fresh/table_gate.json](research/single_model/fresh/table_gate.json)
- Preflight of the adopted wasm (sha256 419f8c6e...): no imports, 16/16 determinism+prefix+future-poison checks on 8 search flights (prefixes 300/900) — [poison_exact.log](research/results/single_model/fuel_preflight/poison_exact.log)

### Inferences
- Rank by (peak fuel saved)/(ATE cost): exact rewrite + -O3 (-10.6 M, zero cost) >> f32 KLT/detect throttle (-1.4 to -1.7 M each, cost unresolved at about +-0.07 m) > 5 clones (-2.1 M, probably some static-start cost) > fast-math (-0.4 M, not exact) > fewer features/KLT iterations (-1.8 M/-0.1 M, clearly costly).
- A 1 % chaos nudge moves the 711-flight mean by +0.019 / +0.044 m (two nudges), so a fresh-set criterion of 0.02 m cannot separate any non-bit-exact change from noise; only bit-exact changes can be certified.
- MAX_UPDATE_FEATURES (cap on ended tracks per frame) has no effect on the peak because the leaving-track thirds, not ended tracks, dominate the batch.

### Gaps
- Approximate arms were not replicated more than three times; effects of +-0.05 m are not resolvable with that budget.
- The 35 m outlier flight of the f32+det/2 fresh run was not diagnosed.
- Porting the patch to fgt.c (gate+tails) was not tested.
- Integer fixed-point KLT, tracking every second frame and sub-diagonal zeroing of the compressed Jacobian were reasoned about but not built.

## (4) Experiments, Pareto set and the area-score arithmetic

### Takeaway
Pareto set (peak fuel s+v vs search mean ATE, replicate means; val in brackets): G 22.54 M / 1.18 (0.545) dominated by exact 11.97 M / 1.18 (0.545) [identical output]; optional non-exact points f32+det/2 8.98 M / 1.15 (0.62), 5 clones 9.88 M / 1.14 (0.57); all within replicate noise of exact. With the server's area code, the exact rewrite is worth about +0.43 score points (3.39 -> 3.82 % in scenario A, 2.66 -> 3.09 % in scenario B); a 30 % fuel cut is worth about +0.24 points, equal to an 8.5-12 % ATE cut.

### Cited Findings
- Area score: dominated area in log-log coordinates over fuel 1..1.2*step_fuel (24 G) x ATE 0.001..1.2*ATE of the lowest-fuel baseline, as a percentage of the rectangle; floors fuel 1, ATE 0.001 — [evaluations.py](/dev/shm/sebastian-vio/viobench/viobench/tools/server/evaluations.py), [STUDENT_GUIDE.md](/dev/shm/sebastian-vio/viobench/docs/STUDENT_GUIDE.md)
- Computed with that code (scenario A: identity 113 fuel/5.09 m + VINS-Mono 3.4 G/0.475 m; scenario B: an extra baseline at 1.15 G calibrated so the server's claimed 2.71 % at 20.9 M/1.244 m is reproduced): G (22.54 M, 1.244 m) 3.39 % / 2.66 %; exact (11.97 M, 1.244 m) 3.82 % / 3.09 %; 8.7 M at 1.244 m 4.04 % / 3.30 %; 8.7 M at 1.49 m (+20 % ATE) 3.52 % / 2.88 %; 30 % fuel cut alone 3.63 % / 2.90 %; 10 % ATE cut alone 3.65 % / 2.86 % — [score2.py](research/single_model/fuel/score2.py)
- Marginals at (22.5 M, 1.244 m): +0.676 points per natural-log unit of fuel; 30 % fuel cut = +0.241 points; 10 % ATE cut = +0.254 (A) / +0.199 (B); so 30 % fuel == 9.5 % (A) / 12 % (B) ATE — [score2.py](research/single_model/fuel/score2.py)
- Baseline numbers (VINS-Mono 0.475 m @ 3.4 G, OpenVINS 0.553 m @ 4.0 G, identity 4.69 m @ 113, tiny_cnn 5.8 m @ 14.7 M, dead_reckoning 9.07 m @ 5.15 M) are the ones quoted in the assignment/memory; the server's claimed area for G (2.71 %) — [SERVER_RESULT.md](research/single_model/final/SERVER_RESULT.md)
- Journal's older exchange rate (halving ATE +2.36 points, halving fuel +0.28 at 2.07 m / 20 M) — [JOURNAL.md](Final Project/classical_vio/gp_msckf/JOURNAL.md)

### Inferences
- Each further 10 % of fuel is worth about +0.07 points, so a non-exact change must not cost more than about 3 % ATE (0.04 m at 1.2 m); f32+det/2 (-25 % peak, +0.16 points) breaks even at roughly +9 % ATE, which is within what the replicate noise cannot rule out in either direction.
- Recommendation: submit the exact + -O3 build now (same estimates, ~0.43 points more by the area code); treat the approximate arms as optional and require more replicates before using them.

### Gaps
- The real baseline set/frontier on the server is not known; scenarios A and B bracket it.
- Fold-4 (sealed) flights were not analysed, so the peak-fuel numbers are search+val maxima (the exact whole-set max may differ slightly).


## (5) Follow-up: port onto G + C1 and second round of exact rewrites

### Takeaway
The bit-exact rewrite ports unchanged onto the new accuracy base (G + C1, `inventive/adopted.c`) and, with a second round of exact rewrites, lowers the peak frame from 21.3 M to 10.8 M on search+val (23.4 -> 11.5 M on the 711 fresh flights) with byte-identical outputs and the whole autoloop parameter registry still applicable by value replacement.

### Cited Findings
- Final build `adopted_c1_exact.c` (wasm sha256 dd5fb1c8...): search+val peak 21.32 -> 10.81 M, median of flight peaks 18.30 -> 8.98, mean p95 14.32 -> 6.96, mean median 8.60 -> 4.63; fresh peak 23.40 -> 11.50 M, mean p95 14.57 -> 7.06, mean median 8.70 -> 4.67 — [NOTES.md section 2.3](research/single_model/fuel/NOTES.md), [verify_c1.py](research/single_model/fuel/verify_c1.py)
- Bit identity vs the G+C1 wasm of record: estimate.tum byte-identical on 144/144 visible flights; ATE identical on 711/711 fresh flights; 8/8 sensor fixtures x 1200 frames; reset check 5/5; determinism + prefix + future-poison 40/40 cases (prefixes 8, 9, 14, 21, 300 straddling gate decision frame 8 and hold window frames 8-20) — [poison_c1y.log](research/results/single_model/fuel_preflight/poison_c1y.log)
- Registry compatibility: all 44 autoloop parameters have exactly one `#define NAME token` in the exact source; `params.render` of the default vector reproduces it byte for byte; 9 vectors (all-high, all-low, structural extremes incl. MAX_CLONES 8, CLONE_EVERY 3, KLT_ITERS 10, and 6 random) rendered into both sources give 216/216 bit-identical flights — [regtest.py](research/single_model/fuel/regtest.py), [params.py](research/single_model/autoloop/params.py) (read only)
- Round-2 steps (G+C1, 119 search flights, peak M): inv_adopted 21.06; round 1 11.16; + detect trace prune 11.23 (median -0.23); + KLT patch rows converted once 10.78; + gate 3-row and P-update 4-row 10.24 — [NOTES.md 2.3](research/single_model/fuel/NOTES.md)

### Inferences
- The peak is now the sum of an irreducible-by-exact-means front end (KLT 2.5, detect 1.2, pyramid 0.5 M) and the dense MSCKF batch (QR 1.35, gate 1.0, update 1.9 M); exact frame-shifting can only lighten some of the three heavy phases, so the max does not move; further exact steps are worth <= 0.2 M each.
- With the loop tuning parameters, the exact source should be rendered via `params.render(vec, nudge, src=adopted_c1_exact.c)`; the loop's own build uses -O2 (same bits, ~3 % more fuel than -O3).

### Gaps
- Approximate arms (f32 KLT, detect throttling, 5 clones) were not re-run on G+C1; they would need 10+ replicates and a paired fresh test.
- The loop's build step was not changed to -O3 (the loop was not touched).


## (6) Forward-backward KLT check on the exact source

### Takeaway
The alternate-frame forward-backward KLT check ports onto the exact source with identical outputs; the exact FB build needs 11.0 M peak (search+val) and 12.3 M (fresh) versus 21.8 / 24.5 M for the non-exact FB build.

### Cited Findings
- Bit identity of `fuel_fbx` vs adopted_fbh.c: 144/144 visible estimate.tum byte-identical, 711/711 fresh ATE identical, 8/8 fixtures, reset 5/5, 40/40 causality cases — [NOTES.md Part 3](research/single_model/fuel/NOTES.md)
- Fuel (search+val): peak 21.78 -> 11.03 M, p95 15.40 -> 7.74, median 9.81 -> 5.47; fresh peak 24.50 -> 12.31 M.
- A per-track template cache (backward template == next forward template) is exact but saves only 1 % (0.06 M); the FB overhead is the backward iterations.
- The FB patch adds no `#define`; the registry renders identically (216/216 flights bit-identical on 9 vectors); proposed parameter FB_MAX_PX 0.5 (0.25-1.0).

### Inferences
- Remaining exact savings are small; the FB check costs about 0.85 M median and 0.2 M peak.

### Gaps
- Publishing into final/submit and the full preflight of the non-exact FB build are outside this work.
