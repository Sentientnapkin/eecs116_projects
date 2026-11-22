# Plan: cut GSLV fuel with analytic line Jacobians, and stop gyro-bias corruption at its root

Date: 2026-11-22. Written for a fresh Claude Code session. Repo root: `/data/backups/rganapa/Sebastian/eecs116_projects` (all paths below are relative to it unless absolute). Read this file, then `research/single_model/LOOP_LOG.md` (last ~15 entries), `research/single_model/geomstarve/NOTES.md` and `research/single_model/learnvel/NOTES.md` before touching code.

## 0. Context in one paragraph

We build a plain-C wasm32 monocular+IMU VIO estimator scored on a private 12-episode course server by the log-log area of (peak per-frame wasm fuel, mean unaligned ATE). Approximate score change: `0.28*log2(peak_old/peak_new) - 2.24*ln(ATE_new/ATE_old)` (one halving of peak fuel ≈ +0.28; a 10% ATE cut ≈ +0.24). Current best build is **GSLV** = `research/single_model/learnvel/final/gslm_lvnet.c` → `gslm_lvnet.wasm` (sha256 `5e4d2a0d40333b3f5152d60de84a688abc5d0eec8c1c73fa402dc9907839d196`): MSCKF + 3-D line features with Manhattan (vertical/horizontal/heading) constraints + RSOFT soft feature weighting + periodic learned-velocity re-anchoring + gyro-bias clamp ±0.021 rad/s. Holdout 0.379, peak fuel ~6.0–7.4 M. Its ancestor HM40/RSOFT ran at ~4.0 M. The two tasks below each target one axis.

| build | holdout | st2dev / st2conf (server-like) | fresh f0-2 / f3 | peak |
|---|---|---|---|---|
| RSOFT | 0.491 | 0.595 / 0.451 | 0.321 / 0.379 | 4.0 M |
| GSLM (lines+Manhattan) | 0.382 | 0.455 / 0.351 | 0.266 / 0.305 | ~7.0 M |
| **GSLV (current best)** | **0.379** | **0.415 / 0.333** | **0.257 / 0.270** | **6.0–7.4 M** |

---

## Task 1 — Analytic line Jacobians (fuel axis): GSLV outputs at ≤ ~4.5 M peak

**Goal:** same accuracy as GSLV (no regression beyond noise) with peak fuel back to ~4–4.5 M. Worth about +0.2 score points (7 M → 4.3 M ≈ 0.7 halvings).

**Why fuel went up:** `research/single_model/geomstarve/line_mod.c` (599 lines; inlined into `gs.c` / `gslm_lvnet.c`) computes every line Jacobian by central differences:
- Gauss-Newton line fit on the 4 line DoF: `line_mod.c:386-399` (`lperturb`, 2 evaluations per parameter per iteration).
- Constrained (vertical / horizontal / heading-snapped) line models: `line_mod.c:440-443` and `:464-467` (`lmodel`, 3 DoF).
- Update Jacobians: line part `:484-492` (Hl, 4 or NP columns) and **clone-pose part `:495-508`** (6 DoF × 2 evaluations × every observation, each calling `camera_pose` + `lres`). This last block is the big one: 12 full residual evaluations per observation per line.
- geomstarve already tried cheaper patches that lost accuracy: reusing the 1st-pass line fit in the 2nd update iteration (`EDGE_LCACHE`), capping line features per update (`EDGE_LMAXF`), and charging the governor per line (`EDGE_LROWX`) — all dropped. Don't retry those; make the arithmetic exact and cheap instead.

**Steps:**
1. **Profile first** (copy `research/single_model/fuelpush/prof.sh` / `mkprof.py` or `audit/prof.sh`): on ~60 st2dev flights, attribute fuel at the peak frame and the p99 frames of GSLV to (a) line tracking, (b) line GN fit, (c) line update Jacobians, (d) the periodic velocity-net micro-steps, (e) the rest of the MSCKF update. Write the table to NOTES.md. If (d) or (e) dominates instead of lines, say so and re-target.
2. **Derive analytic Jacobians** for the residual `lres` (point-to-line distance of the two observed segment endpoints to the projected 3-D line, normalised by endpoint/half-length terms): w.r.t. the clone rotation (right-perturbation `rot_right`) and position, and w.r.t. the line parameters in each parametrisation (`lperturb` free 4-DoF, `lmodel` constrained 3-DoF types). Use the Plücker/orthonormal form if it simplifies the chain rule. Keep the exact same parametrisation and perturbation conventions so the filter math is unchanged.
3. **Verify numerically before using:** a debug switch that computes both and logs the max relative difference over many observations (target < 1e-6 relative, as the numeric ones have eps 1e-6). The existing true-pose checkers `geomstarve/lchk.py`, `lvchk.py`, `lhchk.py` show how features are logged.
4. **Switch it in** behind a new define (e.g. `EDGE_AJAC=1`, default 0 = byte-identical to GSLV — verify the wasm sha with the switch off). Expect ATE to match GSLV to rounding (not bit-identical); compare per-flight ATE on st2dev (should differ by chaos-level noise only).
5. Then optional exact savings: share `camera_pose` per clone across all lines, compute the GN normal equations without forming full J, SIMD the 2×6 blocks.
6. **Re-tune the governor** only if the peak still exceeds the target: the line work must be charged with *measured* per-line costs (the fuelpush `NS_COST` cost-table idea) so no frame exceeds the budget.

**Gate:** 3 reps on st2dev + st2conf + st3 + fresh f0-2 + fresh f3: mean ATE within +2% of GSLV on every set (pooled CI including 0 is fine), no new >5 m flights, peak ≤ 4.5 M (stretch: ≤ 4.0 M).

---

## Task 2 — Gyro-bias corruption at the root (ATE axis)

**Goal:** remove the catastrophic tilt-runaway flights instead of clamping them. Target: −10% or better on st2dev+st3 pooled vs GSLV, fewer >3 m flights, no regression on fresh/st1.

**What is known (learnvel/NOTES.md lines ~40-65, filtcons/NOTES.md):**
- Catastrophic starved flights (e.g. ProcTHOR scene 100, flight 100-009) show absolute filter tilt error growing ~1.5°/s to 6–8° (normally ~1°). Tilt leaks gravity into velocity (~1 m/s² at 6°), which re-diverges velocity within ~1 s of each net correction; the filter's velocity sd stays 0.2–0.3 (≈13σ overconfident).
- Cause: the gyro-bias estimate is pushed beyond the physically possible range (bg_y 0 → 0.038 rad/s; the simulator draws biases within ±0.02), attributed mostly to **starved VISION updates (+0.025)**, net updates −0.011 (`learnvel/bgattr.py`).
- No drag in the simulator → the accelerometer carries no tilt or velocity information; tilt comes from vision only (and now from vertical lines in GSLM).
- Things that HURT or did nothing: tilt process-noise boost when starved (+9 to +31%), velocity/tilt random-walk inflation, Huber, chi2 gating of net updates, a learned gravity-direction net (2.5° error, worse than the filter), covariance resets. Current mitigation: hard clamp `LV_BGC=1 LV_BGMAX=0.021` (~−5% alone on HM40).
- Filtcons also found 15–24% of accepted corner features on untextured flights are >2 px wrong but pass chi2 because P is large — a likely source of the bad bias updates. RSOFT soft-weights them (residual > 1 px → weight 1/r).

**Steps:**
1. **Confirm the simulator's bias model** from the generator/simulator source (search `research/native_campaign.py`, `research/gen.py`, the HyperDrone/l2f simulator config for gyro bias: constant per flight? uniform ±0.02? random walk?). This sets the correct prior: a uniform ±0.02 constant bias has sd ≈ 0.0115 and **no random walk**.
2. **Diagnose on GSLV** (not HM40): rerun `learnvel/bgattr.py`-style attribution with GSLV on st2dev + st3: per update type (corner rows, line rows, vertical/horizontal constraints, net re-anchor, priors), the cumulative change in bg and tilt. Identify which update types and which conditions (live tracks, features per update, parallax, P_bg) produce the wrong bias moves. Log to NOTES.md.
3. **Arms to try** (each behind a define, default off = byte-identical to GSLV):
   - **A. Correct bias prior/process model:** set the gyro-bias prior sd to the simulator's actual distribution and bias random walk to ~0 if biases are constant (check what the GP-bias model currently assumes; it may let bias wander). Replace the hard clamp with a proper bounded prior (e.g. a pseudo-measurement bg≈0 with sd 0.0115, or a truncated-Gaussian projection onto |bg| ≤ 0.02 that also corrects the cross-covariances).
   - **B. Schmidt/consider bias during starved updates:** when an update has few accepted features (use the correct accepted count = attempted − gated − triangulation failures; note `tc_used` is never incremented in `sa.c`, so the u20 counters are always 0 — don't gate on them), keep bg in the covariance but do not apply its state correction (consider-state). Bias then only learns from well-conditioned updates.
   - **C. Cap the per-update bias correction** (information-limited): limit |Δbg| per update to k·sd_bg_prior·(features/threshold).
   - **D. Bias freezing after convergence:** after the bias has converged in good conditions (P_bg small, ≥N seconds of well-tracked flight), fix it (or inflate its measurement weight) for the rest of the flight; static-start flights already estimate it well during the hold.
   - **E. Startup bias from the static hold / net:** better initial bias estimate on static starts; on mid starts, no update of bg from vision until enough parallax/features.
   - Combine the best with the existing clamp only if it still adds something.
4. **Evaluate**: tune on st2dev + st3 pooled; confirm on st2conf, fresh f3; no-regression on fresh f0-2, st1dev/st1conf. 3 reps for anything recommended.

**Gate:** pooled st2dev+st3 ≤ −8% vs GSLV with CI excluding 0, st2conf and fresh f3 not worse than +2%, no new >5 m, peak unchanged.

---

## Evaluation protocol and tooling (both tasks)

- **Sets:** st2dev (156) / st2conf (84) in `/data/backups/rganapa/Sebastian/tmp/st_pools/{st2dev,st2conf}`; st1dev/st1conf (easy fast flights) same dir; st3 (234 flights in st2-dev scenes) from `/data/backups/rganapa/Sebastian/gen/raw-learnvel-st3/` (see learnvel/NOTES.md for its pool dir); fresh pools `/data/backups/rganapa/Sebastian/tmp/lv_pools/{fdev,fconf}` (folds 0-2 / fold 3; **fold 4 excluded**). Pool runner: `research/single_model/learnvel/runpool.py`, `bp.sh`, `cmp.py`, `pooled.py`, `reps.sh`; geomstarve has `bp.sh`/`runpool.py`/`rep3.py`.
- **Replicates:** rep 1 / rep 2 add `PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0` / `PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0` (chaos nudges). Report mean over 3 reps, paired scene-bootstrap CI, tails >3/5/10 m summed over reps, peak and p99 fuel.
- **Build:** copy the source into a new work dir (Task 1: `research/single_model/linejac/`; Task 2: `research/single_model/gbias/`). New switches default 0; with all new switches off the wasm must be **byte-identical** to GSLV (`5e4d2a0d…`). Build via a copy of `learnvel/bp.sh` / `mkwasm.py` (CMake -O3).
- **Preflight for a recommended build:** copy `research/single_model/learnvel/final/preflight.sh` (based on `tier1m/preflight.sh`): sha, zero imports, ABI check, poison/prefix/repeat on 18 fixtures × 41 prefixes (add prefixes around any new event frames), reset 8/8, byte-identical rebuild, 0 filled frames.
- **Machine:** 192 cores; ≤ 64 eval workers per session if both tasks run at once (≤ 96 if alone). Always use `TMPDIR=/data/backups/rganapa/Sebastian/tmp` (root `/` is full). Run long jobs with `nohup`. Keep `NOTES.md` updated after every result — sessions get interrupted by usage limits; on resume, check `ps` for your own jobs before relaunching. Never `pkill -f`/`pgrep -f` with a pattern that also appears in your own command line (it kills your shell).

## Hard rules

- Never score on the clean 240-flight holdout (`research/single_model/holdout/`, `gen/raw-holdout/final`) — the coordinator session scores each final build exactly once with `holdout/score_build.sh`.
- Never read or evaluate fold 4 or sealed data; never train on holdout or st2conf scenes.
- Never download or probe the private server episodes. Never use Sim(3)-aligned ATE as the metric (mean unaligned ATE only).
- No `git commit`/`push`, no uploads, don't write into `final*/` or `submit/` outside your work dir.

## Deliverable from each session

A short final summary at the top of its NOTES.md: results table (sets above, 3 reps, tails, peak), the recommended `.c` + `.wasm` + sha256 in `<workdir>/final/` with preflight output, and what failed. Then tell the user so the coordinator can score it once on the holdout. If both succeed, the next step is to combine them (Task 2's switches on top of Task 1's build) and re-run the gates.

## Suggested prompt for the other window

> Read `reports/Plan line Jacobians and gyro bias.md` and implement Task 1 (or Task 2) exactly as described, in its own work dir, following the evaluation protocol and hard rules. Keep NOTES.md current. Report the final table and sha256 when done.
