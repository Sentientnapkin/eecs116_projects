# Preflight of f0 (written by the coordinator from the preflight agent's findings)

Candidate: research/single_model/final/f0.c -> research/results/single_model/final_f0/solution.wasm
(SHA-256 begins 0d9d923c, ends ...2464). Scripts and per-check results: research/single_model/final/preflight/ and research/results/single_model/preflight_*.

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Official ABI check (`viobench check`) | PASS | "check: ok (5 steps)", exit 0 with a private TMPDIR (candidate and baseline); with a shared tmp it prints a harmless tempfile-cleanup traceback |
| 2 | C only, no dependencies | PASS | zero wasm imports, same exports as baseline; includes only viobench_abi.h, math.h, stdlib.h, string.h |
| 3 | Determinism | PASS | estimate.tum SHA-identical on 171/171 flights across two independent evaluator runs |
| 4 | Causality (future-sensor poisoning, prefix equality) | PASS | 10 fixtures (4 static, 6 mid, none from fold 4, including worst tails) x prefixes 1, 2, 40, 41, 120, 600, 1199: all 70 repeat/prefix/poison cases pass |
| 5 | Reset / re-init | PASS | real init re-called on 4 flights; replay bit-equal to the first run, including after an interrupted partial replay |
| 6 | No filled frames, all completed | PASS | filled_full 0 and completed true on all 171 flights |
| 7 | Fuel | PASS | peak 22.54 M per frame (0.11% of the 2e10 limit), worst p95 15.9 M |
| 8 | Motion detector | FINDING (not a blocker) | see below |
| 9 | Independent re-score | PASS | rebuilt wasm byte-identical; ate_full bit-identical on 171/171 flights; sealed aggregate not opened by the preflight agent |

## Finding on check 8: the "motion detector" is a constant
The detector flags motion if |mean gyro| > 0.2 rad/s OR |mean specific force| > 8.8 m/s^2. A quadrotor's specific force is about 9.8 m/s^2
(thrust ~ gravity) at rest AND in flight, so the force test is always true: all 85 static and all 86 mid flights are classified "moving"
(confusion table 0 static / 171 moving). At 2x preset IMU noise and bias nothing flips (mid->static 0.05%, static->moving 99.8%).
Consequences:
* The heading-aware prior and the 0.15 rad tilt sigma are applied to EVERY start, including the hover (1 s hold) starts.
* The startup NOTES statement that hover starts are "untouched by construction" is wrong. 0 of 68 search/val static flights match the baseline score exactly.
* The reported scores are still valid: they were all measured with this code. Static start mean is 0.808 vs baseline 0.825 (all 171 flights), so applying the prior to hover starts did not hurt; the filter corrects the wrong prior within about a second.
* A working detector is NOT obviously better: a gyro-only test would classify mid starts with low yaw rate as static and withdraw the prior where it matters most. The uniform application is the robust behaviour on these data.
* Not testable here: starts that are at rest for long periods before the flight; the pool's static flights have a 1 s hover.

## CORRECTION (from the gate agent, verified inside the guest with a debug build; supersedes "Finding on check 8" above)
The preflight measured the detector inputs on `imu_window(1)`, but the harness gives frame 0 its own IMU window and f0's initialize() sees THAT window
(10 samples, t=0..0.045 s), where the motors have not spun up yet. On the search slice (n=119), as seen by the guest:
* static (56): |mean f| 8.13 / 8.37 / 8.69 (min/med/max), |mean gyro| 0.00 / 0.06 / 0.11 -> NOT moving, 56/56
* mid (63): |mean f| 8.81 / 9.90 / 11.35, |mean gyro| 0.04 / 0.62 / 1.33 -> moving, 63/63
So the detector works on this pool and hover starts ARE untouched in f0 (static 0.678 on search = the baseline rebuild's number). The margins are THIN:
static max 8.69 vs threshold 8.8 (0.11 m/s^2); 8 of 63 mid starts are detected by force alone; the closest mid is 8.81.
When the detector is forced to 'always moving' (gate_s3_f0const) static search goes 0.678 -> 0.872 and search overall 1.033 -> 1.124, i.e. applying the
prior to hover starts is NOT free (about +0.2 on static). The vision gate (research/single_model/gate/) restores it (gate_s4_gconst: static 0.659, search 1.019).
Check 8 therefore stays a robustness caveat (thin margin), not a constant-detector bug. All other checks are unaffected.
