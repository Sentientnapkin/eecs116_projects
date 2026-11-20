# Fuel optimisation of gp_msckf (plain C -> wasm): notes, measurements, adopted patch

Base build: gate build G = `research/single_model/final/submit/gate.c` (copy: `fuel/gate_base.c`; wasm sha256 ac825145...,
rebuilt here bit-identically through the repo's cmake recipe). Per the coordinator's later instruction this replaces fgt.c as base
(the tails patch does not generalize on the 711 fresh flights). Peak fuel of G: 22.54 M (search+val), 22.76 M (fresh pool).

RESULT IN ONE LINE: a bit-exact rewrite of the hot loops (SIMD128 + loop restructuring, same arithmetic order) plus `-O3` cuts
the peak frame from 22.54 M to 11.97 M (-47 %), median 8.47 -> 5.13 M, p95 14.2 -> 7.6 M, with **zero** change in the output
(all 144 search+val flights byte-identical estimate.tum; all 711 fresh flights identical ATE; 8 sensor fixtures bit-identical).
Approximate arms (f32 KLT, detect throttling, 5 clones, fast-math, fewer features) can go to 8.8-10.6 M but their ATE effect is
inside the replicate chaos noise and they fail the strict fresh criterion; they are reported, not adopted.

Files (all in `research/single_model/fuel/`): `adopted_exact.c` (adopted source), `adopted_exact.patch` (diff vs gate.c),
`v.c` (same + switchable approximate arms), `mkv.py` + `arms.py` + `klt_f32.inc` (generator of v.c / adopted_exact.c from gate_base.c),
`mkprof.py`/`prof_run.py`/`analyze_prof.py` (per-component profiler), `micro/` (wasm microbenchmarks), `pareto.py`, `cmprep_fuel.py`,
`cmp_fresh.py`, `run_fresh_fuel.py`, `score_calc.py`/`score2.py` (area-score arithmetic). Runs: `research/results/single_model/fuel_*`.

## 1. How the evaluator counts fuel (verified)

Source: `viobench/tools/runner/engine.py`, `sandbox.py`, `run.py`, `docs/TASK.md`, `viobench/tools/config.json`.
- Engine: wasmtime 50.0.1 with `consume_fuel=True`, `cranelift_opt_level="speed"`, `wasm_simd=True` (SIMD128 IS allowed), bulk memory, wasm EH.
  No custom operator cost is configured, so wasmtime's default per-operator cost applies.
- Metering window: `Sandbox._arm` sets fuel = `step_fuel` (2e10) right before `exports["step"]` and `fuel = step_fuel - store.get_fuel()` right after.
  Only the guest `step()` call is metered: host-side PNG decode, frame/IMU memcpy into guest memory, state read-back are free.
  `init()` has its own budget (2e11; our init is ~39 k). A failing/trapping step still counts. Score uses the MAX over all attempted frames of all
  episodes (`summarize`: pooled `fuel_per_frame_max`); median/p95/mean are reported but not scored.
- What one unit is (microbenchmarks `micro/mb.c`, `micro/run.py`, results `micro/mb_results.txt`; disassembly with llvm-objdump):
  **one wasm operator = 1 fuel, including `local.get`, `local.set`, `*.const`, loads, stores; `loop`/`end`/`block` = 0.** Everything is unweighted:

  | kernel (N-iteration dependent chain) | fuel/iter | wasm operators per iter (from disassembly) |
  |---|---|---|
  | f64 add chain (10x unrolled) | 2.70 | const+add per add, + loop overhead 7/10 |
  | f64 mul chain | 2.70 | same as add |
  | f64 div chain | 3.40 | div counted as ONE op, same as add (no latency weighting) |
  | f64 sqrt(a+b) chain | 3.875 | sqrt = 1 op |
  | f32 add chain | 2.70 | same as f64 |
  | f64x2 add chain (SIMD) | 2.70 | **one SIMD op = 1 fuel for 2 lanes** (twice the work for the same fuel) |
  | i32x4 mul+add chain | 1.375 | 4 lanes per op |
  | f64 load + add, indexed | 10.4 | index math (`local.get`,`const`,`add`,`and`,`shl`) is metered too |
  | store + load round trip | 18.0 | |
  | `sin()` (libm compiled to wasm) | 157.9 per call | libm is ordinary wasm code, metered op by op |
  | empty step | 121 | |

  Consequences: (a) fuel is an instruction count, not cycles: division/sqrt are as cheap as add, memory is as cheap as arithmetic, so only
  executed-operator count matters; (b) SIMD128 divides the op count by the lane count only for pure lane-parallel work; widening
  (`extend`), `splat`, shuffles, lane extracts each cost 1; (c) unrolling/pointer-increment loops pay off because every `local.get`/
  index op is metered; (d) libm calls (sin ~158, acos/atan2 several hundred) are expensive but our hot paths use almost none (sqrt is an op);
  (e) `-O3`, `-funroll-loops` change op counts directly; `-Os/-Oz` are strictly worse (+29/+43 % peak).
- The Python runtime numbers in docs/RUNTIME.md (empty 0.09 M, KLT baseline 50-130 M) are consistent with this model.
- Unverified: the exact default `OperatorCost` table of wasmtime 50 (docs list per-operator fields but give no defaults in the portion fetched);
  the measurements above are the evidence.

## 2. Where the fuel goes (per-frame component profile)

Method: host-import `env.mark(id)` calls compiled into a profiling copy (`prof.c`, never submitted) read the store fuel at component
boundaries (`prof_run.py`); fuel between marks is attributed to the earlier mark. The marks cost a few ops each; totals match the evaluator
(peak 22.55 M vs 22.54 M). 119 search flights, 142 800 frames (`research/results/single_model/fuel_prof/gate_profile.txt`, `v4_profile.txt`).
Millions of fuel per frame:

| component | G mean | G median frame | G peak frames (top 0.1 %) | adopted mean | adopted median | adopted peak frames |
|---|---|---|---|---|---|---|
| IMU propagate (10 rows) | 0.21 | 0.21 | 0.21 | 0.15 | 0.15 | 0.15 |
| gray + pyramid | 1.27 | 1.27 | 1.27 | 0.50 | 0.50 | 0.50 |
| KLT (60 tracks, 2 levels) | 2.83 | 2.87 | 3.09 | 2.40 | 2.43 | 2.77 |
| detect (re-scores every empty cell each frame) | 2.01 | 2.32 | 2.69 | 1.27 | 1.35 | 1.93 |
| per-feature: triangulate + Jacobians | 0.04 | 0.02 | 0.20 | 0.04 | 0.02 | 0.19 |
| per-feature: null-space Householder | 0.12 | 0.08 | 0.73 | 0.04 | 0.03 | 0.23 |
| per-feature: chi2 gate (H0 P H0^T, chol) | 0.52 | 0.32 | 3.25 | 0.21 | 0.16 | 1.18 |
| QR compression of stacked rows (74-82 rows -> 36) | 0.08 | 0.00 | 2.06 | 0.05 | 0.00 | 1.29 |
| EKF update: HP | 0.60 | 0.38 | 1.75 | 0.16 | 0.12 | 0.45 |
| EKF update: S | 0.13 | 0.05 | 0.56 | 0.07 | 0.04 | 0.27 |
| EKF update: Kt solves | 0.45 | 0.24 | 1.56 | 0.13 | 0.08 | 0.51 |
| EKF update: P update + dx | 0.63 | 0.52 | 1.24 | 0.32 | 0.30 | 0.60 |
| rest (chol, inject, remove clone, ...) | 0.07 | 0.06 | 0.2 | 0.07 | 0.06 | 0.2 |
| **TOTAL** | **8.99** | **8.36** | **18.9** | **5.44** | **5.27** | **10.3** |

KLT detail in the adopted build (mean M): template extract 0.34, template gradient/Hessian loop 0.35, per-iteration extract 0.86,
per-iteration residual/reduction loop 0.81, glue 0.04.

Which frames set the max (G, 119 flights): clone frames (index%4==0) are the CHEAPEST (mean 7.2 M, p99 11.3 M); the three in-between frames
carry the spread MSCKF updates (mean 9.4-9.7 M, p99 16.4-16.8 M). 40 % / 33 % / 26 % of the top 1 % frames are phases 1/2/3, 0.7 % clone
frames. Fuel correlates with the number of features in the update batch (r = 0.81): nbatch 0 -> 6.9 M, 4-8 -> 11.9 M, 12-20 -> 15.8 M,
>20 -> 17.5 M. The top frames have ~11 features / ~81 rows before QR compression (all frames: 2.2 / 13). 160 of the top 200 frames are dominated by
the EKF update segment, 40 by the per-feature rows. 17 of 119 flights peak inside the first 40 frames (startup: all 60 grid cells empty ->
detect + first updates). The movement gate, startup prior and flow code are NOT visible in the profile (negligible fuel).
Peak per flight: median 18.3 M, max 22.5 M, min 8.4 M. Whole-flight median frame 8.4 M.

## 3. Candidates and what they do

Exact (no change of any output bit), all implemented in `adopted_exact.c`; each behind `#if F_xxx` in `v.c` for ablation:

| switch | change | where fuel drops |
|---|---|---|
| F_PYR | gray + 2x2 pyramid with SIMD (shuffle de-interleave, u16 mul-add, narrow; `extadd_pairwise`) | 1.27 -> 0.50 |
| F_DET | per cell: integer gradient products via `i32x4.extmul`, 3x3 box sums in ints, skip `sqrt` when `0.5(sxx+syy) <= best` (score cannot exceed it) | 2.0 -> 1.27 |
| F_UPD | EKF update in row-vector form: HP (2 rows x 6 columns of accumulators in f64x2 registers), S via compact H^T, Kt = S^-1 HP as row substitution on all columns at once, P update in column chunks | update 1.8 -> 0.7 |
| F_GATE | per-feature gate: H0P per observing-clone block in registers, S from compact H0^T | 0.52 -> 0.21 |
| F_QR | QR compression and null-space projection with row-major vector loops, null-space only over the observing clones' columns | 0.20 -> 0.09 |
| F_EXT | KLT bilinear patch in f64x2 (u8 -> u32 -> f64 convert, same expression order) | 0.2 of KLT |
| `-O3` | compiler flag (cmake `target_compile_options(... -O3)` after `viobench_solution`) | -3 to -6 % of the rest |

The rewrites keep the per-element summation order and use no FMA, so results are bit-identical (verified, section 5). `-ffast-math`
is NOT used by the adopted build. Flag-only results (fuel only, 119 search flights; rows 2-7 were measured on the fgt.c source, 22.98 M at -O2, row 1 and the rewrite rows on G; -O3/-flto/-funroll give the same output bits, fast-math does not):

| flags | peak | p95 | median | note |
|---|---|---|---|---|
| -O2 (cmake default) | 22.54 (fgt.c: 22.98) | 14.27 | 8.38 | submitted G (fgt.c: p95 14.70, median 8.85) |
| -O3 | 22.30 | 14.05 | 8.28 | bit-identical |
| -O3 -flto | 21.88 | 13.81 | 8.25 | single TU, little gain (fgt.c measurement) |
| -O3 -funroll-loops | = -O3 | | | no effect |
| -O3 -ffast-math | 21.16 | 13.38 | 7.91 | NOT bit-identical (fgt.c measurement) |
| -mno-simd128 | 25.57 | 17.26 | 11.41 | compiler auto-vectorisation already gives 12-26 % |
| -Os / -Oz | 28.97 / 32.27 | 19.9 / 22.0 | 13.6 / 15.2 | worse |
| source rewrites, -O2 | 13.87 | 9.52 | 5.88 | |
| source rewrites, -O3 | 12.04 | 7.77 | 5.26 | |
| + SIMD detect gradients (adopted) | **11.97** | 7.64 | 5.11 | |

Approximate / structural arms (in `v.c`, default off; `-D` through `run_variant --defines`):

| arm | what | peak (s+v) |
|---|---|---|
| A_KLTF32 | whole KLT (template, iterations, sums) in f32x4 | 10.62 |
| DET_PERIOD=2 | an empty detection cell is re-scored every 2nd frame | 10.34 |
| fast-math (`FUEL_FASTMATH`) | clang -ffast-math | 11.6-11.8 |
| GRID 8x6 (48 tracks) | fewer features | 10.17 |
| KLT_ITERS=3 | | 11.83 |
| MAX_CLONES=5 | window 1.0 s instead of 1.2 s; D 48 instead of 60 | 9.5-9.9 |
| f32 + DET_PERIOD=2 | | 8.8-9.0 |
| MAX_CLONES=5 + f32 + DET_PERIOD=2 | | 6.5-6.8 |
| MAX_UPDATE_FEATURES 6/10 | cap on ended tracks per frame | 11.97 (no effect on the peak) |
| quarters instead of thirds (A_SPREAD4) | spread leaving tracks over 4 frames | 13.7 (worse; fuel only, not evaluated) |

Ideas considered and NOT built (reasoning): integer fixed-point KLT (the f32x4 arm already captures most of the op-count win and its ATE effect is
the unresolved question; int16 would add a quantisation error on top); skipping KLT iterations on converged tracks (the loop already breaks at
0.03/0.1 px); avoiding libm (none in hot paths: sqrt is an op, the only libm in the frame loop are acos/cos in the 3x3 eigen test per feature,
~0.02 M); tracking every second frame (changes the estimator, no budget to evaluate, would need new gating); lazy QR (needs a different
update schedule); sparsity of P (P is dense after the first updates; the nz-column logic of the original already exploits H sparsity).
Zeroing the sub-diagonal rounding residue of the QR-compressed H and skipping it in HP/S would halve HP+S but is not bit-exact (not built).

## 4. ATE cost: replicate noise dominates

The system is chaotic: nudging PIXEL_STD by 1 % and DETECT_MIN_SCORE by 1 % (`reps.sh`, as in tails/rep.sh) on the BIT-IDENTICAL exact build
gives search-slice means 1.028 / 1.223 / 1.293 (new >10 m flights 0 / 2 / 1) instead of the single-run 1.028, so the submitted G run is at the favourable end:
the replicate mean is 1.181. Single-run comparisons of fuel arms (1.08-1.32) are therefore NOT interpretable; all arms were replicated x3.
Reference = exact build replicates (`fuel_xb_r0..2`). Per-flight means over the 3 replicates, paired scene bootstrap (4000 resamples), `cmprep_fuel.py`:

| arm (replicate means) | search d vs ref [95 % CI] | search per-rep means | search >10 m per rep | val d [95 % CI] | peak (s+v) |
|---|---|---|---|---|---|
| ref (exact, nudged) | 1.181 | 1.028 / 1.223 / 1.293 | 0 / 2 / 1 | 0.545 | 11.97 |
| A_KLTF32 | +0.070 [-0.004,+0.158] | 1.151 / 1.211 / 1.392 | 0 / 1 / 2 | -0.037 [-0.055,-0.018] | 10.62 |
| DET_PERIOD=2 | -0.070 [-0.222,+0.061] | 1.103 / 1.069 / 1.164 | 0 / 0 / 0 | +0.175 [-0.061,+0.543] | 10.34 |
| fast-math | +0.039 [-0.005,+0.115] | 1.078 / 1.231 / 1.351 | 0 / 2 / 2 | +0.006 [-0.020,+0.026] | 11.79 |
| MAX_CLONES=5 | -0.043 [-0.186,+0.095] | 1.098 / 1.182 / 1.134 | 0 / 1 / 0 | +0.028 [-0.041,+0.078] | 9.88 |
| f32 + DET_PERIOD=2 | -0.028 [-0.180,+0.104] | 1.092 / 1.208 / 1.160 | 0 / 1 / 0 | +0.076 [-0.040,+0.195] | 8.98 |
| 5 clones + f32 + DET_PERIOD=2 | **+0.186 [-0.020,+0.394]** | 1.372 / 1.350 / 1.380 | 3 / 2 / 3 | +0.128 [+0.012,+0.251] | 6.76 |

Single runs (no replicates): GRID 8x6 1.258 (+0.23, one >10 m), KLT_ITERS=3 1.319 (+0.29, one >10 m): both lose accuracy (more features / iterations matter) and were dropped.

Fresh pool (711 flights not in the 171; `run_fresh_fuel.py`, copy of fresh/run_fresh.py writing only here; reference table `fresh/table_gate.json`, mean 0.8130):

| build | fresh mean | d vs G [95 % CI] | >5 m / >10 m | max ATE | static / mid | peak fuel |
|---|---|---|---|---|---|---|
| G (submitted) | 0.8130 | | 17 / 1 | 12.5 | 0.573 / 1.054 | 22.76 |
| exact (adopted) | 0.8130 | 0.0000 (all 711 identical) | 17 / 1 | 12.5 | 0.573 / 1.054 | **12.12** |
| exact, chaos nudge (PIXEL_STD 1.515, DETECT 1010) | 0.8319 | +0.019 [-0.051,+0.091] | 16 / 2 | 12.7 | 0.643 / 1.021 | 12.16 |
| f32 + DET_PERIOD=2 | 0.8387 | +0.026 [-0.092,+0.171] | 11 / 1 | **35.2** | 0.550 / 1.128 | 9.60 |
| MAX_CLONES=5 | 0.8540 | +0.041 [-0.051,+0.138] | 19 / 2 | 16.3 | 0.692 / 1.016 | 9.97 |

The 711-flight mean itself moves by +0.019 under a 1 % chaos nudge of an otherwise bit-identical build, so the coordinator's "mean within
0.02 m on the fresh set" test is at the replicate-noise floor for any non-bit-exact change: the f32+det2 effect (+0.026) is indistinguishable from
noise, but one flight went to 35 m, so it does not pass the "no new large tail" part. Second nudge replicate (PIXEL_STD 1.485, DETECT 990): fresh mean 0.8564, d +0.0435 [-0.036,+0.124], 3 flights >10 m, max 13.7 m. Chaos alone therefore moves the fresh mean by +0.019 and +0.044 (always upward from the lucky G realisation), the same size as f32+det2 (+0.026) and 5 clones (+0.041): neither can be distinguished from noise on the fresh set, only the exact build can be certified.

Adoption rule applied (search paired CI includes 0 and |mean| < 0.05, no new >10 m, peak falls, fresh within 0.02, no new tail):
- EXACT rewrite + -O3: adopted (change is identically zero).
- f32+det2 and 5 clones pass the search-slice rule (-0.028 / -0.043) but fail the fresh rule (+0.026 with a 35 m flight; +0.041 with static ATE
  0.573 -> 0.692). Not adopted; documented as optional follow-ups that need many more replicates or a fix of the cause (a 35 m flight).

## 5. Preflight of the adopted build (`research/results/single_model/fuel_exact/solution.wasm`)

sha256 419f8c6e398450493a891fa400fd80e416f304d21d7f6f9e52e21fcedf5ac2d5 (built from `adopted_exact.c` with `FUEL_O3`; byte-identical to
the build of `v.c` since the arms are compiled out).
- ABI: no imports; exports memory, _initialize, abi_version, alloc, frame_width, init, step (`final/preflight/wasm_imports.py`). Static memory only, plain C + libm.
- Bit-identity vs G: 119 search flights (pose+twist of every frame, `cmp_pose.py`) identical; full 171-flight run `fuel_exactfull` vs `fuel_base`:
  144/144 search+val estimate.tum byte-identical (fold-4 flights deliberately not compared); 8/8 sensor-only fixtures 1200 frames bit-identical
  (`fixture_bitcmp.py`); 711/711 fresh ATE identical.
- Determinism, prefix and future-poison causality (`research/check_future_poison.py`, fixtures from `final/preflight_gate/make_sensor_fixture_f0win.py`,
  8 search flights = 4 static + 4 mid, prefixes 300 and 900, fresh process per replay): 16/16 pass (`fuel_preflight/poison_exact.log`).
- The SIMD code reads up to 7 bytes past a row (never used) and writes up to 3 doubles past a patch buffer (buffers padded +4); no data-dependent branches changed.

## 6. Area-score arithmetic (`score_calc.py`, `score2.py`; server `evaluations.dominated_area/area_gains` copied)

Score = dominated area / (ln(1.2*step_fuel/1) * ln(ref_err/0.001)) with ref_err = 1.2 * ATE of the lowest-fuel baseline (reference box fuel 1..24 G, ATE
0.001..~6.1 m). Marginals do not depend on our fuel except through ln(frontier fuel / our fuel): for a point below the baseline frontier,
d score/d ln(fuel) = -ln(ref_err/ATE) / D and d score/d ln(ATE) = -ln(F_b/fuel) / D, D = 208.5 nats^2, F_b = fuel of the first baseline whose ATE is lower than ours.
Two frontier scenarios (the actual baseline set is not available; baselines quoted in the task: identity 4.69 m @113, VINS-Mono 0.475 m @3.4 G, OpenVINS 0.553 m @4.0 G,
tiny_cnn 5.8 @14.7 M and dead_reckoning 9.07 @5.15 M are dominated by identity and do not matter; the identity reference ATE 5.09 m is back-computed from the 6.11 m box):
A = identity (113, 5.09) + VINS (3.4 G, 0.475); B = a hypothetical baseline at 1.15 G chosen so that the server's claimed 2.71 % at (20.9 M, 1.244 m) is reproduced (B gives 2.66 % for the 22.54 M point).

| point | A | B |
|---|---|---|
| G as submitted (22.54 M, 1.244 m) | 3.39 % | 2.66 % |
| exact rewrite (11.97 M, 1.244 m) | **3.82 %** | **3.09 %** |
| 8.7 M at 1.244 m (hypothetical, if f32+det2 were free) | 4.04 % | 3.30 % |
| 8.7 M at 1.49 m (+20 % ATE) | 3.52 % | 2.88 % |
| 30 % fuel cut only | 3.63 % | 2.90 % |
| 10 % ATE cut only | 3.65 % | 2.86 % |

- Worth of a 30 % fuel cut: +0.24 points in both scenarios; worth of a 10 % ATE cut: +0.25 (A) / +0.20 (B) at the old point, +0.29 / +0.23 at 12 M.
  So a 30 % fuel cut == a 8.5-12 % ATE cut (journal's old-point figure: halving fuel +0.28 / halving ATE +2.36 at 2.07 m, similar order).
- Rule of thumb: +0.676 points per ln-unit of fuel (cutting fuel by factor e = 2.72), i.e. exact rewrite (22.54 -> 11.97 M) = +0.43 points for free;
  every further 10 % of fuel = +0.07 points and must not cost more than ~3 % ATE (0.04 m at 1.2 m).
- Therefore f32+det2 (-25 % peak, +0.16 points) pays only if its true ATE effect is below ~+9 % (0.11 m); the evidence is +0.03 +-0.15 (search) and +0.026 on the
  fresh pool with one 35 m outlier, i.e. not resolvable with our replicate budget. MAX_CLONES=5 (-18 %, +0.11 points) has a measured +0.04 (fresh) with a worse static ATE.

## 7. Adopted patch

`adopted_exact.patch` (diff -u `gate_base.c` `adopted_exact.c`, ~340 changed lines): adds `#include <wasm_simd128.h>`, the F_* switches (all 1), SIMD `build_pyramid`,
integer/SIMD detect cell scan, row-vector `update()` (HP, S, Kt, P), SIMD per-feature gate and null space over the observing-clone columns, row-major QR compression,
f64x2 `extract()`, +4 doubles of padding on the KLT patch buffers. CMake: after `viobench_solution(solution solution.c)` add
`target_compile_options(solution PRIVATE -O3)` (the file `fuel/CMakeLists.txt` does that behind a `FUEL_O3` marker in CMAKE_C_FLAGS; for the submission simply set -O3 unconditionally).
Porting to fgt.c (gate+tails) was NOT done or tested: the tails patch changes `detect()` (score threshold) and `klt()` (min-eigenvalue test) which the rewrite also edits, so the string anchors in mkv.py would need adapting; re-run the bit-identity check after any port.

Regenerate: `cd fuel && python3 mkv.py` (v.c with arms) or `NOARMS=1 OUT=adopted_exact.c python3 mkv.py`.
Evaluate: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .../venv-teacher/bin/python -B -m research.single_model.run_variant --name fuel_X --src research/single_model/fuel/v.c --defines "FUEL_O3 A_KLTF32=1" --workers 24`.

## 8. Remaining exact headroom (not done)
Profile of the adopted build at its peak frames (10.3 M): KLT 2.8, detect 1.9, per-feature gate 1.2, QR 1.3, update 1.9, pyramid 0.5, propagate 0.15, null-space 0.23, rest 0.3.
Further bit-exact ideas: SIMD the 3x3 box-sum loop of detect (~0.6 M), restructure the QR compression per 6-column block with register accumulators (~0.5 M),
unroll the KLT residual loop with pointer increments (~0.3 M; bit-exact only if the summation order is kept), cheaper gray conversion constants (~0.1 M).

---------------------------------------------------------------------------------------------------------------------------------
# PART 2: port onto G + C1 (`research/single_model/inventive/adopted.c`) and further exact work

## 2.1 Port result (files: `adopted_base.c` = copy of inventive/adopted.c, `adopted_c1_exact.c`, `adopted_c1_exact.patch`, `c1/CMakeLists.txt`+`CMakeLists_c1.txt` with -O3 unconditional)
Generated by `IN=adopted_base.c NOARMS=1 OUT=adopted_c1_exact.c python3 mkv.py` (all anchors applied unchanged: adopted.c only adds parameters and the
hold/prior blocks that call `update()` with 1-3 row Jacobians; those calls go through the rewritten, row-count-agnostic `update()`).
Built exactly like the loop does (`run_variant`, repo cmake recipe, plus -O3): wasm sha256 6f5990d167067910b1f291600525bf6a93e0980f6100e1ef6f363fabfc5d944f
(`results/single_model/fuel_c1x/solution.wasm`); the wasm of record (inv_adopted) is 28ab1367...
- Bit identity: 144/144 visible (search+val) flights estimate.tum byte-identical to `inv_adopted` (fold 4 not compared); 711/711 fresh ATE identical (mean 0.732668 both);
  8/8 sensor fixtures x 1200 frames bit-identical; 119 search flights pose+twist bit-identical in the profiling harness.
- Fuel (search+val, 144 flights): peak 21.32 -> **11.80 M**, median of per-flight peaks 18.30 -> 9.88, mean p95 14.32 -> 7.66, mean median 8.60 -> 5.21.
  Fresh pool (711): peak 23.40 -> **12.70 M**, median per-flight peak 18.67 -> 10.03, mean p95 14.57 -> 7.79, mean median 8.70 -> 5.26.
  (The coordinator's 21.71 M includes the sealed flights; only visible flights are read here.)
- Registry compatibility (`regtest.py`, uses autoloop/params.py read-only): all 44 parameters have exactly one `#define NAME token` in the exact source;
  `params.render(default_vec, 1.0, src)` reproduces the exact source byte for byte; 9 vectors (all-hi, all-lo, structural extremes MAX_CLONES 8 / CLONE_EVERY 3 /
  MAX_UPDATE_FEATURES 40 / MIN_OBS 2 / KLT_ITERS 10, 6 random log-uniform vectors; ill-posed ones skipped) rendered into BOTH adopted.c and the exact source, built, run on 24
  search flights each: 216/216 flights bit-identical (peaks e.g. all-hi 34.1 -> 16.8 M, struct-hi 46.4 -> 23.3 M, all-lo 13.1 -> 7.6 M).
  Static buffers are sized with MAXD/MAX_OBS, so MAX_CLONES up to 8 and CLONE_EVERY/KLT_ITERS/MAX_UPDATE_FEATURES ranges of the registry are covered; the loop's `evalvec.py`
  builds with `RV.CMAKE_DEFAULT` (-O2): that gives the same bits (-O3 is bit-identical), only ~3 % more fuel than -O3 (round-1 measurement on G: 13.87 vs 12.04 M); to get -O3 in the loop point CMAKE at c1/CMakeLists.txt (not done: the loop is not touched).
  Apply a tuned vector by `params.render(vec, nudge, Path('research/single_model/fuel/adopted_c1_exact.c'))`.
- Preflight (`fuel_preflight/`): reset check on 5 fixtures (re-init in one instance, partial replay + re-init): second_equals_first, after_partial_equals_first, first pose identity all true, and
  the first replay equals inv_adopted's bit for bit (5/5). Causality/determinism: see 2.2.

## 2.2 Causality / determinism of the G+C1 exact build (`fuel_preflight/poison_c1x.log`)
`research/check_future_poison.py` on 8 sensor-only fixtures (4 static incl. the hold-window start, 4 mid-flight incl. gate release at frame 8), prefixes 8, 9, 14, 21, 300:
the cut at 8/9 straddles the gate decision frame 8, 14 lies inside the hold window (HOLD_T0 0.4 s = frame 8, HOLD_T 1.0 s = frame 20), 21 just after it.
Each case = fresh process x {full, repeat, prefix-only, future-poisoned (frames random, IMU N(0,100) after the prefix)}: 40/40 cases pass (prefix rows bit-identical in all modes, repeat bit-identical).

## 2.3 Round 2 of exact rewrites on G+C1 (final: `adopted_c1_exact.c`, wasm `results/single_model/fuel_c1y/solution.wasm`, sha256 dd5fb1c859cf58c865dc7a5ecb5aea3fb8725d3cbbbcc63dfd49599a99a328f0)
`opt2.py` (exec'd by mkv.py; switches F_EXT2, F_GATE2, F_UPD2, default 1) adds, all bit-exact:
1. KLT patch extraction: each of the n+1 source rows is converted u8 -> f64 once into a scratch row buffer and the four bilinear taps read it with unaligned f64x2 loads
   (324 u8->f64 conversions per 9x9 patch become 100; same expression order). -0.45 M at the peak frames, -0.24 M median.
2. Per-feature gate H0P: three rows of H0 per pass over P (P loads shared): gate 1.28 -> 1.00 M at peak frames.
3. P update: four rows of P per pass over Kt: 0.66 -> 0.51 M.
Tried and dropped: skipping zero rows in the QR compression (rows are dense: tracks span the whole window, peak +0.07 M, kept the median -0.2 M only through the detect part; reverted);
trace-first prune in detect (kept: skips the xy product for cells that cannot beat the best: median -0.23 M); clang flags `-fno-math-errno`, `-fno-trapping-math`, `-unroll-threshold` (-0.7 %, not adopted);
vector-product + sequential-sum rewrite of the KLT residual/Hessian reductions (counted: 1400 vs 1620 ops per patch, <3 % of KLT, not built).

Pareto of exact steps (G+C1, 119 search flights, harness fuel, M; every row bit-identical to inv_adopted on all 119 flights):

| build | peak | median of flight peaks | p99 | p95 | median frame | mean |
|---|---|---|---|---|---|---|
| inv_adopted (-O2) | 21.06 | 18.30 | 16.49 | 14.40 | 8.51 | 9.11 |
| round 1 rewrite + -O3 (c1x) | 11.16 | 9.88 | 8.85 | 7.72 | 5.18 | 5.36 |
| + detect trace prune | 11.23 | 9.59 | 8.56 | 7.56 | 4.95 | 5.13 |
| + patch rows converted once | 10.78 | 9.31 | 8.28 | 7.29 | 4.71 | 4.91 |
| + gate 3-row + P-update 4-row (c1y, final) | **10.24** | 8.98 | 7.99 | 7.02 | 4.62 | 4.80 |
| (+ -fno-math-errno -fno-trapping-math -unroll-threshold=600, not adopted) | 10.17 | 8.91 | 7.94 | 6.97 | 4.58 | 4.75 |

Official evaluator numbers for the final build (`fuel_c1y`, `fuel_fresh_c1y`): search+val 144 flights peak 21.32 -> **10.81 M**, median of flight peaks 18.30 -> 8.98, mean p95 14.32 -> 6.96, mean median 8.60 -> 4.63;
fresh 711 flights peak 23.40 -> **11.50 M**, median flight peak 18.67 -> 9.08, mean p95 14.57 -> 7.06, mean median 8.70 -> 4.67 (-51 % peak, -46 % median).
Verification of c1y (same suite as 2.1): estimate.tum byte-identical on 144/144 visible flights; ATE identical on 711/711 fresh flights (mean 0.732668); 8/8 fixtures bit-identical over 1200 frames;
registry test 216/216 flights bit-identical on 9 vectors; reset check 5/5 (+ first replay equal to inv_adopted); future-poison/prefix/determinism 40/40 (`fuel_preflight/poison_c1y.log`, prefixes 8,9,14,21,300 x 8 flights).

## 2.4 What sets the peak now and what cannot be moved exactly
Peak frames (top 0.1 %, 9.2 M in the marked build): KLT 2.5 (iteration extract 0.79, residual loop 0.95, template 0.34+0.40), detect 1.2, QR compression 1.35, per-feature gate 1.0,
EKF update 1.9 (HP 0.45, S 0.27, chol 0.19, Kt 0.52, P 0.51), null-space 0.24, triangulation+Jacobians 0.19, pyramid 0.50, propagate 0.15.
The single worst frames of a flight are often frames 22-23 (the first full-window batch, all 60 tracks born at frame 0 leave together: dense batches of 20 features).
- Moving exact work between frames: only forward-deferral of `detect()` (independent of the update) and backward precomputation of the next KLT templates into the cheap clone frame
  (phase 0, 4.6 vs 7-8 M) are bit-exact. Both would lighten phases 3 and 1 only; phase 2 sits between two heavy frames and sets the same max, so the max does not move (analysis only, not built).
  Re-batching MSCKF features (e.g. quarters instead of thirds, tested on G: 13.7 vs 12.0 M, worse because the clone frame already carries part of the batch) changes which state each feature is linearised at: not exact.
- Incremental Householder / skipping zero rows: the stacked Jacobian is dense over the window (tracks live as long as the window), so no sparsity to exploit; the sub-diagonal residue of the compressed H is non-zero in floating point and enters HP/S, so dropping it is not bit-exact.
- Fusing consecutive Householder passes breaks the summation order (the next pivot's v depends on the complete updated column norm); not exact.
Remaining exact ideas with small yield (each <= 0.2 M at peak): separable box sums in detect, register-chunked QR, 2-chunk Kt substitution. Approximate arms from Part 1 (f32 KLT, detect every 2nd frame, 5 clones) were NOT re-run on G+C1; they would need 10+ replicates and a paired fresh test as requested.

## 2.5 Area-score arithmetic for G+C1 (`score2.py` logic; ATE at the point does not change)
At fixed ATE, cutting peak 21.7 -> 10.8 M is worth 0.676 * ln(21.7/10.8) = +0.47 points (scenarios A/B above: 0.43-0.47 depending on the frontier). Exchange rate unchanged: a further 10 % fuel = +0.07 points; 30 % fuel = 8.5-12 % ATE.

# PART 3: forward-backward KLT check (frontend/adopted_fbh.c) on the exact source
`adopted_fbh_base.c` = copy of frontend/adopted_fbh.c; `IN=adopted_fbh_base.c NOARMS=1 OUT=adopted_c1_fbh_exact.c python3 mkv.py` gives `adopted_c1_fbh_exact.c` (+ `.patch`, `c1fbh/`).
The FB patch only edits `track_all`; the backward `klt(cur, prev, ...)` call goes through the same rewritten kernels (extract etc.). Wasm builds: `fuel_fbx` (exact, -O3),
`fuel_fbbase` (non-exact adopted_fbh.c, -O2, cmake default). In progress: results below are filled in as checks finish.

## 3.1 Results (exact FB build `fuel_fbx`, wasm sha256 31137e4fb26f73249d6ededffd71669df307886a3f929ffe2bc5d28204ff0137; non-exact `fuel_fbbase` = adopted_fbh.c at -O2)
- Bit identity vs adopted_fbh.c: estimate.tum byte-identical 144/144 visible flights; ATE identical 711/711 fresh (mean 0.618372 both); 8/8 fixtures x 1200 frames; reset check 5/5 (+ first replay equal);
  future-poison/prefix/determinism 40/40 (8 flights x prefixes 8, 9, 14, 21, 301: gate decision frame 8, hold window 8-20, FB alternation parity both ways; `fuel_preflight/poison_fbx.log`); 119 harness flights bit-identical.
- Fuel: search+val peak 21.78 -> **11.03 M**, median of flight peaks 19.37 -> 9.80, mean p95 15.40 -> 7.74, mean median 9.81 -> 5.47. Fresh: peak 24.50 -> **12.31 M**, p95 15.61 -> 7.83, median 9.83 -> 5.45.
  (FB check costs +0.85 M median / +0.2 M peak over the c1y exact build: 4.62 -> 5.47 M.)
- FB-specific exact savings: implemented (`opt3.py`, `USE_FBT=1`) a per-track template cache: the backward template (current image at the new position) is bit-for-bit the next frame's forward template; 46 % of forward
  level-templates hit the cache; measured saving only 0.06 M mean (1 %): templates cost ~3 k ops each, the FB overhead is dominated by the backward iterations (patch extraction 1.2 k + residual loop 1.6 k per iteration).
  Not adopted (bit-identical, 1 %, extra state). Not exact: reusing forward patches for the first backward iteration (positions differ by rounding); skipping back-tracks for new tracks (changes decisions).
- Registry: all 44 names have exactly one `#define` in the FB exact source, default render identical; 9 vectors rendered into adopted_fbh.c and the exact source: 216/216 flights bit-identical. The FB patch adds NO #define: the 0.5 px threshold is the literal `0.25` (squared)
  and the alternation is `(frame_no + i) & 1`. To register: `#define FB_MAX_PX 0.5` (range 0.25-1.0, log) used as FB_MAX_PX*FB_MAX_PX (value-identical at 0.5); not done, to keep the source identical to the evaluated one.
- Publishing: staged in `fuel/publish/` (wasm + source pairs, SHA256SUMS_new). Copying into final/submit was blocked by the permission classifier (see final message).
