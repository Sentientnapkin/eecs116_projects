# Task 1 final summary — analytic line Jacobians

**Outcome: implementation and evaluation complete; no build passes all Task 1 gates. No build is recommended for holdout scoring.**

Arithmetic-only (`ajc`) preserves accuracy within the plan's noise allowance, but exceeds the 4.5 M fuel target. Measured-cost/budget (`ajgb4`) reaches the fuel target, but regresses accuracy and creates a new >5 m flight. See the exact gate results in `tables/ajc_gates.json` and `tables/ajgb4_gates.json`.

All entries below are means over 3 reps. Tails >3/>5/>10 m are summed over reps; peak is the maximum across frames/reps and p99 pools all frames. CIs use 10,000 paired scene-bootstrap resamples with all three replicates kept together per flight. All 4,368 flights/build completed with zero filled frames.

## Compact comparison

| set | GSLV ATE m | arithmetic ATE m | budget ATE m | arithmetic peak/p99 M | budget peak/p99 M |
|---|---:|---:|---:|---:|---:|
| st2dev (156) | 0.4154 | 0.4086 | 0.4352 | 5.052/3.202 | 4.122/3.045 |
| st3 (234) | 0.4156 | 0.4214 | 0.4484 | 4.783/3.202 | 4.401/3.042 |
| st2conf (84) | 0.3334 | 0.3438 | 0.3490 | 4.703/3.219 | 4.204/3.064 |
| fdev (475) | 0.2567 | 0.2556 | 0.2577 | 5.113/3.189 | 4.305/3.021 |
| fconf (107) | 0.2701 | 0.2679 | 0.2937 | 5.040/3.183 | 4.382/3.014 |
| st1dev (244) | 0.1773 | 0.1765 | 0.1874 | 4.807/3.156 | 4.099/2.986 |
| st1conf (156) | 0.2459 | 0.2522 | 0.2538 | 4.691/3.197 | 4.190/3.031 |

## Full arithmetic table (candidate only; fuel gate failed)

| set (flights) | GSLV ATE | candidate ATE | delta [scene-bootstrap 95% CI] m | tails >3/5/10 baseline → candidate | peak M (base → candidate) | p99 M (base → candidate) |
|---|---:|---:|---|---|---:|---:|
| st2dev (156) | 0.4154 | 0.4086 | -0.0068 [-0.0220,+0.0051] | 5/0/0 → 4/0/0 | 6.844 → 5.052 | 3.577 → 3.202 |
| st3 (234) | 0.4156 | 0.4214 | +0.0058 [-0.0053,+0.0177] | 4/1/0 → 4/2/0 | 6.826 → 4.783 | 3.582 → 3.202 |
| st2conf (84) | 0.3334 | 0.3438 | +0.0105 [-0.0087,+0.0410] | 0/0/0 → 0/0/0 | 6.564 → 4.703 | 3.593 → 3.219 |
| fdev (475) | 0.2567 | 0.2556 | -0.0011 [-0.0051,+0.0025] | 1/0/0 → 1/0/0 | 6.958 → 5.113 | 3.540 → 3.189 |
| fconf (107) | 0.2701 | 0.2679 | -0.0023 [-0.0046,+0.0001] | 0/0/0 → 0/0/0 | 6.746 → 5.040 | 3.584 → 3.183 |
| st1dev (244) | 0.1773 | 0.1765 | -0.0008 [-0.0027,+0.0012] | 0/0/0 → 0/0/0 | 6.984 → 4.807 | 3.548 → 3.156 |
| st1conf (156) | 0.2459 | 0.2522 | +0.0063 [-0.0017,+0.0163] | 0/0/0 → 1/0/0 | 6.410 → 4.691 | 3.530 → 3.197 |

## Full budget table (rejected: accuracy/tails)

| set (flights) | GSLV ATE | candidate ATE | delta [scene-bootstrap 95% CI] m | tails >3/5/10 baseline → candidate | peak M (base → candidate) | p99 M (base → candidate) |
|---|---:|---:|---|---|---:|---:|
| st2dev (156) | 0.4154 | 0.4352 | +0.0198 [-0.0041,+0.0491] | 5/0/0 → 5/1/0 | 6.844 → 4.122 | 3.577 → 3.045 |
| st3 (234) | 0.4156 | 0.4484 | +0.0328 [+0.0018,+0.0656] | 4/1/0 → 9/0/0 | 6.826 → 4.401 | 3.582 → 3.042 |
| st2conf (84) | 0.3334 | 0.3490 | +0.0156 [-0.0000,+0.0340] | 0/0/0 → 0/0/0 | 6.564 → 4.204 | 3.593 → 3.064 |
| fdev (475) | 0.2567 | 0.2577 | +0.0010 [-0.0116,+0.0121] | 1/0/0 → 0/0/0 | 6.958 → 4.305 | 3.540 → 3.021 |
| fconf (107) | 0.2701 | 0.2937 | +0.0235 [-0.0006,+0.0529] | 0/0/0 → 0/0/0 | 6.746 → 4.382 | 3.584 → 3.014 |
| st1dev (244) | 0.1773 | 0.1874 | +0.0101 [+0.0043,+0.0164] | 0/0/0 → 0/0/0 | 6.984 → 4.099 | 3.548 → 2.986 |
| st1conf (156) | 0.2459 | 0.2538 | +0.0079 [+0.0002,+0.0152] | 0/0/0 → 0/0/0 | 6.410 → 4.190 | 3.530 → 3.031 |

## Artifacts and validation

- `gslv_linejac_arith`: `final/gslv_linejac_arith.c` and `final/gslv_linejac_arith.wasm`; wasm SHA256 `eb2799cbdc8dd9fa2711cdeda3062447364b6dfd4b05e72e543edd3ffa1a8e6d`.
- `gslv_linejac_budget`: `final/gslv_linejac_budget.c` and `final/gslv_linejac_budget.wasm`; wasm SHA256 `b0e379fce2fe4dcbc67c6a22e2c73bc5b11074f807504db6da209c7c637f761e`.

Both: CMake -O3; zero imports; ABI PASS; 738/738 poison/prefix/repeat PASS (18 fixtures ×41 prefixes); reset 8/8 PASS; byte-identical rebuild; zero filled frames. Full outputs are in `final/preflight_arith/` and `final/preflight/`. All new switches off reproduce GSLV SHA256 `5e4d2a0d40333b3f5152d60de84a688abc5d0eec8c1c73fa402dc9907839d196` (also verified for the fused experimental source).

Analytic implementation covers free, vertical, horizontal and heading-snapped models plus clone right rotation and translation with arbitrary camera extrinsics. Numeric checks: >210k real observation blocks; pose/constrained derivatives <3e-8 relative at eps=1e-6. Rare ill-conditioned free fits show central-difference truncation (max 4.85e-5 at eps=1e-6 → 4.85e-7 at eps=1e-7); a near-zero snapped block has small absolute but large relative finite-difference noise. Independent ~12k nondegenerate synthetic geometries pass <2.6e-8 for line and <5.3e-10 for pose at eps=1e-6. `analytic.h`, `tables/check*.txt`, `tables/synthetic_numeric.txt` contain derivation/check evidence. SIMD line kernels and Cholesky preserved trajectories on 156/156 flights each.

## What failed

- Analytic line Jacobians alone: st2dev r0 ATE 0.40416 vs GSLV 0.40421, peak 5.976M. Profiling showed substantial line null-space/gating and general EKF costs beyond finite differences.
- Exact SIMD line backend, forward-only EKF and SIMD Cholesky reduce fuel substantially, but the full protocol still exceeds 4.5M.
- Measured-cost governor alone: peak 4.830M on dev. With 3.2M budget: ATE +9.55%, new 5.406m flight (rejected). With 3.4M budget: full 3-rep results above; significant st3 regression and new 5.268m dev flight (rejected).
- Triangular normal-equation accumulation did not improve peak. Fusing line residual/Jacobian work preserves outputs on seven peak fixtures but saves only 22–44k; peak remains 5.006M, not adopted.
- No retry of EDGE_LCACHE, EDGE_LMAXF or blind EDGE_LROWX; measured admission costs were considered only after analytic/exact savings missed the target, as permitted by step 6. No governor variant was adopted.

Holdout/fold 4/sealed data remained untouched; no training, private-server access, commits, pushes or uploads. All source changes and staged final artifacts are inside this work directory; canonical build/eval outputs are under `research/results/single_model/lj_*`.

## Historical session log
# Task 1: analytic line Jacobians

Historical startup status: in progress; final outcome is above.
Base: GSLV, expected wasm SHA256 5e4d2a0d40333b3f5152d60de84a688abc5d0eec8c1c73fa402dc9907839d196.
Scope: own linejac directory; no holdout, fold 4, sealed data, training, commits, uploads or server access.
Evaluation: 3 chaos replicates, st2dev/st2conf/st3/fdev/fconf; paired scene bootstrap, tails >3/5/10, peak/p99 fuel. At most 64 eval workers (another Claude session is active). TMPDIR=/data/backups/rganapa/Sebastian/tmp. Long jobs use nohup.

## Session log
- Read plan, last loop-log entries, geomstarve and learnvel notes before editing. Selected Task 1. No ancestor AGENTS.md found. Preparing 60-flight st2dev profiling before edits.
- Baseline CMake -O3 build verified byte-identical to GSLV SHA256. First profiling launch failed before evaluation (inherited profiler assumed includes within 200 lines); corrected header scan and absolute paths.

## Initial GSLV profile
60 st2dev flights, 72000 frames; p99 3.532 M. Host-marker build (small instrumentation overhead).
| phase | peak frame M | mean of top 1% frames M |
|---|---:|---:|
| line tracking/detection | 0.102 | 0.248 |
| line GN fit | 0.557 | 0.275 |
| line update Jacobians | 0.383 | 0.165 |
| velocity net | 0.004 | 0.127 |
| rest MSCKF update | 4.178 | 2.387 |
| other | 0.741 | 0.756 |
| total | 5.965 | 3.957 |

- Profile: update() itself is dominant (3.35 M on peak frame), solve_dx 0.81 M. Analytic line GN/pose/line Jacobians implemented under EDGE_AJAC (default 0), with EDGE_AJCHECK retaining numeric results and logging comparisons. Derivation in analytic.h includes arbitrary camera extrinsics/lever arm and right-body perturbations. Will retarget the remaining update arithmetic after measuring analytic savings.

## Numeric verification (12 spread st2dev flights, numeric retained)
```
kind 0: n=63939, relative max=4.85e-05, p99=5e-10, absolute max=0.0476
kind 1: n=11576, relative max=8.31e-10, p99=5.46e-10, absolute max=2.93e-09
kind 2: n=56560, relative max=2.08e-08, p99=3.95e-10, absolute max=2.48e-06
kind 3: n=38067, relative max=2.23e-09, p99=4.93e-10, absolute max=1.05e-09
kind 4: n=3320, relative max=3.22e-09, p99=3.45e-10, absolute max=3.02e-07
kind 5: n=2894, relative max=8.43e-10, p99=5.3e-10, absolute max=2.7e-09
kind 6: n=1332, relative max=1.38e-09, p99=4.18e-10, absolute max=5.42e-10
kind 7: n=12689, relative max=1.03e-09, p99=4.88e-10, absolute max=9.79e-10
kind 8: n=20235, relative max=2.5e-09, p99=2.14e-10, absolute max=3.15e-09
```
Free-GN rare near-singular cases exceed 1e-6 (p99 ~5e-10); testing difference step 1e-7 to separate central-difference truncation from analytic mistakes. All clone and constrained derivatives pass at eps=1e-6. Switch-off lj.c wasm remains byte-identical 5e4d2a0d...

- eps=1e-7 check: free GN max relative 4.85e-7 (100x lower than eps=1e-6: central-difference O(eps^2) truncation). A snapped Q block with effectively zero derivatives has max relative 5.65e-4 but absolute error <=9.16e-9; p99 relative ~5e-9. Production keeps original parametrizations and no numerical-step change.
- AJ-only r0 st2dev: ATE 0.404162 vs GSLV 0.404214, peak 5.976 M, 0 filled. Fuel target not yet met. Added EDGE_ASIMD default 0 for line null-space and gating matrices (same scalar summation order), and LJ_FWD default 0 for forward-only square-root covariance update (algebraically identical EKF; rounding changes).
- ajs r0 st2dev: ATE 0.404162, peak 5.212 M, filled 0.
- ajsf r0 st2dev: ATE 0.402811, peak 4.946 M, filled 0.
- EDGE_ASIMD outputs verified byte-identical to AJ-only on all 156/156 st2dev trajectories. Forward-only EKF reduces peak further but target not yet reached. Testing forced specialization of analytic helper (same math, compile-time removal of unused outputs).
- Result ajsfi / st2dev: n=156, mean unaligned ATE=0.402811, peak=4.787 M, tails >3/5/10=2/0/0, filled=0, completed=156.
- Result ajc / st2dev: n=156, mean unaligned ATE=0.402811, peak=4.694 M, tails >3/5/10=2/0/0, filled=0, completed=156.
- Result ajc / st3: n=234, mean unaligned ATE=0.421829, peak=4.434 M, tails >3/5/10=2/1/0, filled=0, completed=234.
- Forced specialization reduces st2dev peak 4.946 -> 4.787 M; SIMD Cholesky (same per-element order, transpose stored in unused upper triangle) -> 4.694 M. SIMD Cholesky identical trajectories 156/156.
- Independent native check of ~12000 nondegenerate geometries with random extrinsic rotations/lever arms: all four line models max relative <2.6e-8, clone pose <5.3e-10 (eps=1e-6); tables/synthetic_numeric.txt.
- Step 6 invoked because arithmetic-only build remains above fuel gate. Profiled 23060 calls on 60 st2dev flights: worst per-line fuel by n=3/4/5/6/7 is 80010/119180/178204/253673/356872. LJ_LCOST (default 0) uses these measured fit costs plus measured ~50k/backend row, reserving constrained rows 2n-2, with 20% fit allowance. This differs from the rejected uniform EDGE_LROWX charge; most n>=5 admissions stay the same, short n3/n4 rows were undercounted. Evaluating before adopting.
- Result ajc / st2conf: n=84, mean unaligned ATE=0.353620, peak=4.605 M, tails >3/5/10=0/0/0, filled=0, completed=84.
- Result ajg / st2dev: n=156, mean unaligned ATE=0.402965, peak=4.830 M, tails >3/5/10=1/0/0, filled=0, completed=156.
- Latest lj.c with ALL new switches off rebuilt to exact GSLV SHA256 5e4d2a0d...; regeneration script also reproduces source byte-for-byte. Verified all 18 inherited preflight fixtures belong to folds 0-3. Measured-cost governor alone r0 st2dev ATE 0.4030, peak 4.830 M: still exceeds gate; testing budget 3.2 M with measured costs.

## Refined profile: base_detail
60 st2dev flights, 72000 frames; p99 3.532 M. Host-marker build (small instrumentation overhead).
| phase | peak frame M | mean of top 1% frames M |
|---|---:|---:|
| line tracking/detection | 0.102 | 0.248 |
| line GN fit | 0.557 | 0.275 |
| line update Jacobians | 0.383 | 0.165 |
| line null-space/gating/row output | 1.521 | 0.868 |
| velocity net | 0.004 | 0.127 |
| rest MSCKF update | 2.657 | 1.519 |
| other | 0.741 | 0.756 |
| total | 5.965 | 3.957 |

## Refined profile: fees
60 st2dev flights, 72000 frames; p99 3.211 M. Host-marker build (small instrumentation overhead).
| phase | peak frame M | mean of top 1% frames M |
|---|---:|---:|
| line tracking/detection | 0.256 | 0.228 |
| line GN fit | 0.593 | 0.043 |
| line update Jacobians | 0.138 | 0.012 |
| line null-space/gating/row output | 0.392 | 0.064 |
| velocity net | 0.004 | 1.698 |
| rest MSCKF update | 2.265 | 0.583 |
| other | 0.446 | 0.708 |
| total | 4.095 | 3.335 |
- Result ajc / fdev: n=475, mean unaligned ATE=0.254868, peak=4.828 M, tails >3/5/10=0/0/0, filled=0, completed=475.
- Result ajc / fconf: n=107, mean unaligned ATE=0.275465, peak=5.040 M, tails >3/5/10=0/0/0, filled=0, completed=107.
- Result ajgb / st2dev: n=156, mean unaligned ATE=0.442820, peak=3.975 M, tails >3/5/10=1/1/0, filled=0, completed=156.
- REJECT ajgb (measured-cost + GOV_B=3.2M): r0 st2dev 0.442820 (+9.55%), peak 3.975 M, new >5m flight 100-009 (5.406m). Trying 3.4M before choosing finalist; arithmetic-only remains fallback but exceeds strict fuel gate on fresh f3 (5.040M).

## Derivation / implementation
Let q=Rwcᵀ(Q−pwc), d=RwcᵀD, l=q×d, n=√(lx²+ly²), and v_s=(x−sg·hl·ey,y+sg·hl·ex,1). The original residual is h_s=l·v_s/n. Its row gradient is g_s=(v_s−h_s(lx,ly,0)/n)/n. Thus A_c=d×g_s and B_c=g_s×q give dh=A_c·dq+B_c·dd. Transforming A=Rwc A_c, B=Rwc B_c gives the free columns (A·e1,A·e2,B·e1,B·e2); the normalization of D in lperturb has zero first-order effect along the orthogonal basis. Vertical columns are (Ax,Ay); horizontal are (−Ax sin f+Ay cos f,Az,−Bx sin f+By cos f); snapped horizontal omits the yaw column and uses exactly the stored direction in its Q tangent.

For right body rotation, q_b=Rbc q+pbc, d_b=Rbc d. The rotation row is (Rbc A_c)×q_b+(Rbc B_c)×d_b, and the world-position row is −A. This includes the camera lever arm. Residual signs remain r=−h, H=dh/dx. No fit iterations, model selection thresholds, perturbation conventions, accepted-row weighting, or feature counts change in arithmetic-only arms. LJ_FWD uses W=L⁻¹HP and z=L⁻¹r, so dx=Wᵀz and P←P−WᵀW; gating still uses the original scalar gate calculation. EDGE_ASIMD and LJ_CHOL preserve scalar per-element summation order; their trajectory identity checks passed on 156/156 st2dev flights each.
- Result ajgb4 / st2dev: n=156, mean unaligned ATE=0.427314, peak=4.122 M, tails >3/5/10=0/0/0, filled=0, completed=156.
- ajgb4 (measured-cost governor + 3.4M budget): r0 st2dev 0.4273 (+5.7%), peak 4.122M. Launching full 3-rep protocol to distinguish chaos from regression; no recommendation yet. Also testing exact triangular normal-equation accumulation to reduce remaining arithmetic-only line GN cost.
- Result ajgb4 / st2dev: n=156, mean unaligned ATE=0.427314, peak=4.122 M, tails >3/5/10=0/0/0, filled=0, completed=156.
- Running full ajgb4 protocol (PID 1522670; logs/ajgb4_all.txt; setsid nohup). 48 workers, plus 16-worker exact-normal-equation trial ajn. Check these processes before relaunching after interruption. Cached GSLV references verified: r0 5e4d2a0d..., r1 36b44e71..., r2 fff09c80... (manifest in tables/reference_manifest.json). GSLV >5m tails: st3 only, one rep (5.271m); none on other sets.
- Result ajn / st2dev: n=156, mean unaligned ATE=0.402811, peak=4.734 M, tails >3/5/10=2/0/0, filled=0, completed=156.
- Result ajgb4 / st3: n=234, mean unaligned ATE=0.445272, peak=4.144 M, tails >3/5/10=2/0/0, filled=0, completed=234.
- Exact normal-equation arm ajn does not help peak (4.734M vs 4.694M; ATE identical): not adopted, LJ_NORMAL remains off. Full arithmetic-only ajc 3-rep protocol queued in logs/ajc_all.txt; ajgb4 and ajc use 32 workers each once current pool finishes (worker cap 64/session). No more arithmetic changes planned pending the complete comparisons.
- Result ajgb4 / st2conf: n=84, mean unaligned ATE=0.345278, peak=4.204 M, tails >3/5/10=0/0/0, filled=0, completed=84.
- Result ajgb4 / fdev: n=475, mean unaligned ATE=0.256942, peak=4.305 M, tails >3/5/10=0/0/0, filled=0, completed=475.
- Result ajgb4 / fconf: n=107, mean unaligned ATE=0.288956, peak=4.145 M, tails >3/5/10=0/0/0, filled=0, completed=107.
- Result ajgb4 / st1dev: n=244, mean unaligned ATE=0.185350, peak=4.017 M, tails >3/5/10=0/0/0, filled=0, completed=244.
- Result ajgb4 / st1conf: n=156, mean unaligned ATE=0.254475, peak=4.041 M, tails >3/5/10=0/0/0, filled=0, completed=156.
- Budget r0 COMPLETE on all seven sets, zero filled. Worker-control script edit raced with its running shell and stopped the queue at the r1 boundary (WORKERS unbound); corrected script is stable and queue restarted, reusing completed r0 evaluations with hash/count validation. No in-flight evaluations were lost. Final source with all switches off still rebuilds byte-identically to GSLV; staged arithmetic and budget source rebuilds match their evaluated wasm bytes.
- Result ajgb4_r1 / st2dev: n=156, mean unaligned ATE=0.426005, peak=4.109 M, tails >3/5/10=3/0/0, filled=0, completed=156.
- Result ajc / st1dev: n=244, mean unaligned ATE=0.178579, peak=4.807 M, tails >3/5/10=0/0/0, filled=0, completed=244.
- Result ajgb4_r1 / st3: n=234, mean unaligned ATE=0.439283, peak=4.401 M, tails >3/5/10=3/0/0, filled=0, completed=234.
- Result ajgb4_r1 / st2conf: n=84, mean unaligned ATE=0.344088, peak=3.916 M, tails >3/5/10=0/0/0, filled=0, completed=84.
- Result ajc / st1conf: n=156, mean unaligned ATE=0.248286, peak=4.382 M, tails >3/5/10=0/0/0, filled=0, completed=156.
- Budget preflight: 550/550 prefix groups passed so far; arithmetic preflight queued sequentially after budget preflight to stay under 64 workers. Rep 1 results so far: budget st2dev 0.4260, st3 0.4393, st2conf 0.3441; still no new >5m flights in these completed reps. Final decision awaits rep 2 and scene-bootstrap CIs; st3 mean may regress beyond 2% even if statistically unresolved.
- Result ajc_r1 / st2dev: n=156, mean unaligned ATE=0.423109, peak=4.898 M, tails >3/5/10=2/0/0, filled=0, completed=156.
- Result ajc_r1 / st3: n=234, mean unaligned ATE=0.417125, peak=4.783 M, tails >3/5/10=1/1/0, filled=0, completed=234.
- Result ajgb4_r1 / fdev: n=475, mean unaligned ATE=0.260735, peak=4.196 M, tails >3/5/10=0/0/0, filled=0, completed=475.
- Result ajc_r1 / st2conf: n=84, mean unaligned ATE=0.329523, peak=4.703 M, tails >3/5/10=0/0/0, filled=0, completed=84.
- Result ajgb4_r1 / fconf: n=107, mean unaligned ATE=0.298952, peak=4.157 M, tails >3/5/10=0/0/0, filled=0, completed=107.
- Result ajgb4_r1 / st1dev: n=244, mean unaligned ATE=0.189498, peak=4.099 M, tails >3/5/10=0/0/0, filled=0, completed=244.
- Result ajgb4_r1 / st1conf: n=156, mean unaligned ATE=0.253368, peak=4.039 M, tails >3/5/10=0/0/0, filled=0, completed=156.
- Result ajc_r1 / fdev: n=475, mean unaligned ATE=0.258483, peak=5.113 M, tails >3/5/10=1/0/0, filled=0, completed=475.
- Budget preflight COMPLETE: zero imports, ABI PASS, all 738/738 poison/prefix/repeat combinations PASS, reset 8/8 PASS, byte-identical source rebuild. Arithmetic preflight running next. Budget fresh f3 r0/r1 0.2890/0.2990 vs baseline 0.2801/0.2643 is concerning; not recommending based only on fuel. Testing fused residual+Jacobian line fits in separate lj_exact.c on the seven arithmetic-r0 peak flights with one worker (total eval workers <=64).
- Result ajgb4_r2 / st2dev: n=156, mean unaligned ATE=0.452404, peak=4.088 M, tails >3/5/10=2/1/0, filled=0, completed=156.
- Result ajc_r1 / fconf: n=107, mean unaligned ATE=0.262920, peak=4.425 M, tails >3/5/10=0/0/0, filled=0, completed=107.
- Result ajfuse / peaks: n=7, mean unaligned ATE=0.610621, peak=5.006 M, tails >3/5/10=0/0/0, filled=0, completed=7.
- Result ajgb4_r2 / st3: n=234, mean unaligned ATE=0.460602, peak=4.122 M, tails >3/5/10=4/0/0, filled=0, completed=234.
- Result ajc_r1 / st1dev: n=244, mean unaligned ATE=0.176247, peak=4.590 M, tails >3/5/10=0/0/0, filled=0, completed=244.
- Result ajgb4_r2 / st2conf: n=84, mean unaligned ATE=0.357511, peak=4.132 M, tails >3/5/10=0/0/0, filled=0, completed=84.
- Fused line-fit pilot preserves ATE exactly on all 7 peak fixtures but only saves ~22–44k peak fuel; max remains 5.006M. Not adopted into frozen finalist. Budget st2dev 3-rep mean is now ~0.4352 vs GSLV 0.4154 (+4.8%); full scene-bootstrap result in tables/ajgb4_final.md (partial until all sets finish).
- REJECT budget ajgb4 under Task 1 gates: st3 3-rep mean 0.4484 vs 0.4156 (+7.9%), delta +0.0328 [0.0020,0.0649] excludes 0; dev gets new >5m flight st2Km-ProcTHOR-Train-100-009 r2=5.2677m (baseline max on this flight across reps <5). No build recommended. Complete remaining confirmation/fresh/easy runs and arithmetic comparison to provide final audited table; holdout must remain untouched.
- Result ajc_r1 / st1conf: n=156, mean unaligned ATE=0.254226, peak=4.374 M, tails >3/5/10=0/0/0, filled=0, completed=156.
- Result ajc_r2 / st2dev: n=156, mean unaligned ATE=0.400015, peak=5.052 M, tails >3/5/10=0/0/0, filled=0, completed=156.
- Result ajgb4_r2 / fdev: n=475, mean unaligned ATE=0.255507, peak=4.206 M, tails >3/5/10=0/0/0, filled=0, completed=475.
- Result ajc_r2 / st3: n=234, mean unaligned ATE=0.425125, peak=4.457 M, tails >3/5/10=1/0/0, filled=0, completed=234.
- Result ajgb4_r2 / fconf: n=107, mean unaligned ATE=0.293102, peak=4.382 M, tails >3/5/10=0/0/0, filled=0, completed=107.
- Arithmetic dev completed 3 reps: st2dev 0.4028/0.4231/0.4000 (mean ~0.4086 vs baseline 0.4154), st3 0.4218/0.4171/0.4251 (mean ~0.4213 vs 0.4156). This is useful accuracy-preserving fuel reduction, but peak remains >5M. Once budget r2 finishes all sets, arithmetic workers rise from 28 to 60 (plus <=3 preflight workers), still within the session cap.
- Result ajc_r2 / st2conf: n=84, mean unaligned ATE=0.348399, peak=4.257 M, tails >3/5/10=0/0/0, filled=0, completed=84.
- Result ajgb4_r2 / st1dev: n=244, mean unaligned ATE=0.187320, peak=4.024 M, tails >3/5/10=0/0/0, filled=0, completed=244.
- BOTH candidate preflights COMPLETE and programmatically verified: ABI, zero imports, 738/738 poison/prefix/repeat each (18 fixtures ×41 prefixes), reset 8/8 each, byte-identical rebuilds. Final artifacts remain rejected/ineligible under Task 1 gates (budget accuracy/tail regression; arithmetic fuel >4.5M).
- Result ajgb4_r2 / st1conf: n=156, mean unaligned ATE=0.253576, peak=4.190 M, tails >3/5/10=0/0/0, filled=0, completed=156.
- Result ajc_r2 / fdev: n=475, mean unaligned ATE=0.253430, peak=5.020 M, tails >3/5/10=0/0/0, filled=0, completed=475.
- Result ajc_r2 / fconf: n=107, mean unaligned ATE=0.265270, peak=4.948 M, tails >3/5/10=0/0/0, filled=0, completed=107.
- Result ajc_r2 / st1dev: n=244, mean unaligned ATE=0.174674, peak=4.641 M, tails >3/5/10=0/0/0, filled=0, completed=244.
- Result ajc_r2 / st1conf: n=156, mean unaligned ATE=0.254164, peak=4.691 M, tails >3/5/10=1/0/0, filled=0, completed=156.
- Result ajp2 / st2conf: n=84, mean unaligned ATE=0.342232, peak=4.261 M, tails >3/5/10=0/0/0, filled=0, completed=84.
- Result ajp1 / st2conf: n=84, mean unaligned ATE=0.321788, peak=4.703 M, tails >3/5/10=0/0/0, filled=0, completed=84.
- Result ajp1 / fconf: n=107, mean unaligned ATE=0.264835, peak=4.425 M, tails >3/5/10=0/0/0, filled=0, completed=107.
- Result ajp2 / fconf: n=107, mean unaligned ATE=0.271638, peak=4.645 M, tails >3/5/10=0/0/0, filled=0, completed=107.
- Result ajp1 / st2dev: n=156, mean unaligned ATE=0.415931, peak=4.694 M, tails >3/5/10=2/0/0, filled=0, completed=156.
- Result ajp2 / st2dev: n=156, mean unaligned ATE=0.406426, peak=5.056 M, tails >3/5/10=1/0/0, filled=0, completed=156.
- Result gbdiag / pool: n=7, mean unaligned ATE=0.805267, peak=4.333 M, tails >3/5/10=1/0/0, filled=0, completed=7.
- Result gbdiag / pool: n=7, mean unaligned ATE=0.805267, peak=4.333 M, tails >3/5/10=1/0/0, filled=0, completed=7.
- Result gbdiag / pool: n=7, mean unaligned ATE=0.805267, peak=4.333 M, tails >3/5/10=1/0/0, filled=0, completed=7.
- Result gbdiag / pool: n=7, mean unaligned ATE=0.805267, peak=4.381 M, tails >3/5/10=1/0/0, filled=0, completed=7.
- Result gbdiag / pool: n=7, mean unaligned ATE=0.805267, peak=4.381 M, tails >3/5/10=1/0/0, filled=0, completed=7.
- Result gbschmidt / pool: n=7, mean unaligned ATE=0.945784, peak=4.571 M, tails >3/5/10=1/0/0, filled=0, completed=7.
- Result ljarithschcap / pool_highgyro: n=10, mean unaligned ATE=0.240506, peak=4.037 M, tails >3/5/10=0/0/0, filled=0, completed=10.
- Result ljarithbase / pool_highgyro: n=10, mean unaligned ATE=0.240506, peak=4.037 M, tails >3/5/10=0/0/0, filled=0, completed=10.
- Result ljmidpoint / pool_highgyro: n=10, mean unaligned ATE=0.235484, peak=3.911 M, tails >3/5/10=0/0/0, filled=0, completed=10.
- Result ljmidpoint / pool: n=7, mean unaligned ATE=1.398419, peak=4.415 M, tails >3/5/10=1/1/0, filled=0, completed=7.
- Result ljarithbase / pool: n=7, mean unaligned ATE=0.805267, peak=4.294 M, tails >3/5/10=1/0/0, filled=0, completed=7.
- Result ljmidrate / pool_highgyro: n=10, mean unaligned ATE=0.235243, peak=4.063 M, tails >3/5/10=0/0/0, filled=0, completed=10.
- Result ljmidrate_bad / pool: n=7, mean unaligned ATE=0.717503, peak=4.295 M, tails >3/5/10=0/0/0, filled=0, completed=7.
- Result ljbase_r1 / pool_highgyro: n=10, mean unaligned ATE=0.230270, peak=3.864 M, tails >3/5/10=0/0/0, filled=0, completed=10.
- Result ljbase_r2 / pool_highgyro: n=10, mean unaligned ATE=0.232251, peak=4.335 M, tails >3/5/10=0/0/0, filled=0, completed=10.
- Result ljmidrate_r1 / pool_highgyro: n=10, mean unaligned ATE=0.208026, peak=4.001 M, tails >3/5/10=0/0/0, filled=0, completed=10.
- Result ljmidrate_r2 / pool_highgyro: n=10, mean unaligned ATE=0.223636, peak=3.846 M, tails >3/5/10=0/0/0, filled=0, completed=10.
- Result ljcap_bad / pool: n=7, mean unaligned ATE=0.732364, peak=4.294 M, tails >3/5/10=0/0/0, filled=0, completed=7.
- Result base1 / pool_highgyro20: n=20, mean unaligned ATE=0.269143, peak=4.233 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result mid2 / pool_highgyro20: n=20, mean unaligned ATE=0.271437, peak=3.994 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result base0 / pool_highgyro20: n=20, mean unaligned ATE=0.281582, peak=4.053 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result mid0 / pool_highgyro20: n=20, mean unaligned ATE=0.283606, peak=4.414 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result base2 / pool_highgyro20: n=20, mean unaligned ATE=0.270884, peak=4.335 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result mid1 / pool_highgyro20: n=20, mean unaligned ATE=0.260804, peak=4.665 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result ljaccelend / pool_highgyro20: n=20, mean unaligned ATE=0.268456, peak=4.267 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result ljaccelend_bad / pool: n=7, mean unaligned ATE=0.894932, peak=3.934 M, tails >3/5/10=1/0/0, filled=0, completed=7.
- Result try_rsoft / pool_highgyro20: n=20, mean unaligned ATE=0.409546, peak=3.967 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result try_hm40 / pool_highgyro20: n=20, mean unaligned ATE=0.422158, peak=3.966 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result try_lines / pool_highgyro20: n=20, mean unaligned ATE=0.344102, peak=5.652 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result try_ljarith / pool_highgyro20: n=20, mean unaligned ATE=0.281582, peak=4.053 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result try_rsoft_ctl / pool: n=7, mean unaligned ATE=1.081208, peak=3.891 M, tails >3/5/10=0/0/0, filled=0, completed=7.
- Result try_hm40_ctl / pool: n=7, mean unaligned ATE=1.983307, peak=3.797 M, tails >3/5/10=2/1/0, filled=0, completed=7.
- Result try_ljarith_ctl / pool: n=7, mean unaligned ATE=0.805267, peak=4.294 M, tails >3/5/10=1/0/0, filled=0, completed=7.
- Result try_lines_ctl / pool: n=7, mean unaligned ATE=0.991832, peak=5.846 M, tails >3/5/10=1/0/0, filled=0, completed=7.
- Result ljarith_no_rsoft_controls / pool: n=7, mean unaligned ATE=1.249035, peak=4.186 M, tails >3/5/10=1/0/0, filled=0, completed=7.
- Result ljarith_lines_no_manhattan_controls / pool: n=7, mean unaligned ATE=0.810659, peak=3.582 M, tails >3/5/10=0/0/0, filled=0, completed=7.
- Result ljarith_no_lines_controls / pool: n=7, mean unaligned ATE=0.994243, peak=3.711 M, tails >3/5/10=1/0/0, filled=0, completed=7.
- Result ljarith_no_lines_highgyro20 / pool_highgyro20: n=20, mean unaligned ATE=0.354792, peak=3.731 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result ljarith_no_rsoft_highgyro20 / pool_highgyro20: n=20, mean unaligned ATE=0.295859, peak=4.017 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result ljarith_lines_no_manhattan_highgyro20 / pool_highgyro20: n=20, mean unaligned ATE=0.316185, peak=3.558 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result ljarith_yaw_only_controls / pool: n=7, mean unaligned ATE=0.810659, peak=3.582 M, tails >3/5/10=0/0/0, filled=0, completed=7.
- Result ljarith_rsoft15_controls / pool: n=7, mean unaligned ATE=0.834964, peak=3.952 M, tails >3/5/10=0/0/0, filled=0, completed=7.
- Result ljarith_rsoft05_controls / pool: n=7, mean unaligned ATE=1.088848, peak=3.695 M, tails >3/5/10=1/0/0, filled=0, completed=7.
- Result ljarith_vertical_only_controls / pool: n=7, mean unaligned ATE=0.770732, peak=3.809 M, tails >3/5/10=0/0/0, filled=0, completed=7.
- Result ljarith_yaw_only_highgyro20 / pool_highgyro20: n=20, mean unaligned ATE=0.316185, peak=3.558 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result ljarith_rsoft15_highgyro20 / pool_highgyro20: n=20, mean unaligned ATE=0.284108, peak=4.560 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result ljarith_vertical_only_highgyro20 / pool_highgyro20: n=20, mean unaligned ATE=0.314781, peak=3.741 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result ljarith_rsoft05_highgyro20 / pool_highgyro20: n=20, mean unaligned ATE=0.332120, peak=4.095 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result ljarith_horiz_yaw_only_controls / pool: n=7, mean unaligned ATE=0.822137, peak=4.397 M, tails >3/5/10=1/0/0, filled=0, completed=7.
- Result ljarith_horizontal_free_controls / pool: n=7, mean unaligned ATE=0.869286, peak=3.648 M, tails >3/5/10=1/0/0, filled=0, completed=7.
- Result ljarith_horizontal_free_highgyro20 / pool_highgyro20: n=20, mean unaligned ATE=0.325336, peak=3.740 M, tails >3/5/10=0/0/0, filled=0, completed=20.
- Result ljarith_horiz_yaw_only_highgyro20 / pool_highgyro20: n=20, mean unaligned ATE=0.311163, peak=3.837 M, tails >3/5/10=0/0/0, filled=0, completed=20.
