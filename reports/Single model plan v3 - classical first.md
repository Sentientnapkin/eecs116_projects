# Single-model plan v3: classical improvements first, then the small-CNN / learned startup work

Date: 2026-11-20. Metric: mean unaligned ATE (m). One estimator, one wasm, no guard. Builds on `Single model plan v2.md` (read its section 2 for the startup-offset finding). Everything labelled "guess" is a prior expectation, not a result.

## 0. What is verified today (the facts this plan stands on)

| Fact | Evidence |
|---|---|
| gp_msckf on the 171-flight pool: mean 2.21 / median 0.80; static starts 0.82; mid-flight starts 3.58 | pinned evaluator, `research/results/loop/gp-msckf-pool/` |
| Its mid-start error is a startup offset: 1.71 m at 2 s, 2.88 at 5 s, then flat (3.63 final). 49 of 86 mid starts average 0.97 m, the other 37 average 7.03 m | `estimate.tum` vs truth, all 86 |
| Mid-flight starts begin at 1.01 m/s on average (p10 0.33, p50 0.95, p90 1.85, max 2.26); static starts at 0.04 m/s | truth over the first 0.5 s, all 171 |
| **A rebuild from source on this machine reproduces the pool score exactly** (2.21 / 0.799 / 22 flights over 5 m). The rebuilt wasm is 71,507 bytes against 71,502 submitted, so the build is not bit-identical (Linux vs the Windows build), but the accuracy is | wasi-sdk 34 at `/data/backups/rganapa/Sebastian/tmp/viobench-toolchain`, `research/results/loop/gp-msckf-variants/rebuild_linux/` |
| The fast loop works: edit C → build (about 10 s) → score 171 flights (about 95 s with 48 workers) | same |
| The evaluator keeps each flight's `stderr.txt` | `report/logs/*/stderr.txt`, so debug counters printed from the wasm come back per flight |

Reading of `solution.c` that drives the classical list:
- `initialize()` (`solution.c:362-381`) sets roll/pitch from the mean specific force and gives tilt σ 0.05 rad (`INIT_TILT_STD`, line 59-ish) and velocity σ 1.0 m/s (`INIT_VELOCITY_STD`, `:63`). For a quadrotor in flight the specific force points along thrust, not gravity, so initial roll/pitch is wrong by the vehicle's tilt. The journal says exactly this ("in flight the accelerometer gives no tilt"). Measured mean tilt is about 6° with maxima of 16–35° (24-flight sample from the structural-priors notes). A 0.1 rad tilt error is about 1 m/s² of spurious horizontal acceleration, so velocity drifts about 1 m/s each second until vision corrects it. The filter claims 0.05 rad, i.e. it is overconfident on exactly the flights that fail.
- The velocity prior (`imu_measurements`, `:436-441`) is zero-mean, isotropic, in the world frame, σ 0.5 m/s per axis with τ 2 s, and its update has no gate (`INFINITY`). Mid starts begin at 1.0 m/s on average and up to 2.26 m/s, so many starts sit 2–4.5σ from the prior mean.
- The stacked MSCKF update is also ungated (`:713`, `INFINITY`); only per-feature χ² gating protects it. There is no health monitor or recovery path.
- First vision update cannot happen before about 0.6–1.2 s (clone every 4 frames, 3 observations needed, spread updates), so the first second is IMU plus prior only.
- Detection uses a fixed Shi-Tomasi threshold (`DETECT_MIN_SCORE 1000`) and plain gray KLT with no brightness compensation; the bad mid starts lean dark/flat (correlations +0.31 and +0.22 with ATE).

## 1. Experiment protocol (shared by every phase)

1. **Three disjoint slices by scene** (hash of scene id, same rule as `guard_fusion/evaluate.py`): *search* (about 60%), *val* (about 20%), *final* (about 20%, touched only at phase gates). The raw pool has 882 flights (441 static, 441 mid); the 171 selected are the server-calibrated view and stay a reporting set, with 21 clean scenes as the least-seen subset.
2. **Score gp_msckf and every variant on all 882 flights**, not only the 171. At about 95 s per 171 flights this is about 8 minutes per variant, and it takes the effective sample from about 90 to several hundred flights. Disk: roughly 40 GB per variant with video, so delete `trajectory.mp4` after scoring or point at a no-video option if the evaluator has one (unchecked).
3. **Adoption rule** (the journal's own, which already caught an overtuned change): paired bootstrap resampling scenes, 95% interval excludes zero, effect holds on both val halves, no static-start regression above 0.05 m, no new tail flights above 10 m. Differences under about 0.4 m on the 171 set are noise.
4. **Report columns** for every arm: raw mean, median, p90, flights above 5 and 10 m, static/mid split, error at 2/5/30 s, clean-scene mean, peak fuel. Raw unaligned ATE only; no Sim(3) in rankings.
5. **Ledger:** register each arm as a spec in `research/campaign/specs/` (the harness already enforces raw metric and immutable declarations). The existing `leaderboard` format is reused.
6. **Variant mechanics:** every parameter change is a `-D` flag on `solution.c` built into `build/<variant>.wasm`; no repo edits to the submitted source until an arm is adopted. Runner: `scratchpad/run_variant.py <wasm> <name>`, to be promoted to `research/single_model/run_variant.py`.
7. **Debug builds:** add counters to stderr (live tracks, features used, NIS of each update, speed, tilt estimate, prior-dominated flag). Truth-based NEES is computed offline from the saved `estimate.tum` and covariances logged to stderr.

## 2. Phase 1: classical improvements (no learned model)

Order is by expected gain per hour. Each work package lists the code locus, the arms, the hypothesis it tests and the kill rule. All gain figures are guesses.

### C1. Honest initial tilt and velocity uncertainty (0.5 day)
- **Change:** `INIT_TILT_STD` 0.05 → {0.10, 0.15, 0.20, 0.30} rad; `INIT_VELOCITY_STD` 1.0 → {1.5, 2.0}. Keep the 1 s hover case unchanged by making the widening conditional on a motion detector (gyro or specific-force variance in the first window) so static starts keep their tight initialization.
- **Hypothesis:** the tilt error from thrust-aligned specific force plus an overconfident initial covariance is a main cause of the in-flight offset.
- **Kill:** no arm improves mid-start mean by 10% on search and val.
- **Guess:** 10–30% of the mid-start gap.

### C2. Better velocity priors at startup (1–2 days)
- **Arms:**
  - (a) widen the startup prior σ to cover 2 m/s;
  - (b) anisotropy: vertical σ 0.3 m/s, horizontal σ 1.0 m/s (measured mean |vz| 0.24 vs 0.92 m/s horizontal);
  - (c) heading-aware, non-zero-mean prior for the first 2 s: body-forward mean about 0.9 m/s with σ 0.6, lateral σ 0.4 (60% of moving samples have heading within 20° of velocity, median body slip 6°, p75 15°, p90 33°; from the 24-flight sample, to be re-measured on the search slice);
  - (d) schedule: strong while tracks are few, weak once vision is locked on (the journal found weakening the prior globally hurts tails, so this must be conditioned on track count);
  - (e) gate the prior update instead of `INFINITY`.
- **Kill:** as C1. Fit prior parameters on search only.
- **Guess:** 10–25% of the gap, partly overlapping C1.

### C3. Earlier vision lock-on (1 day)
- **Change:** during the first 40 frames use `CLONE_EVERY` 2, `MIN_OBS` 2, and a relaxed `TRI_MIN_EIG`, then return to the current values. Fuel stays flat because the spread-update logic already bounds per-frame work.
- **Hypothesis:** the first second without vision constraints lets the C1/C2 errors grow; shortening it cuts the offset.
- **Guess:** 5–15%.

### C4. Startup batch re-initialization with replay (1–1.5 weeks, only if C1–C3 leave a large gap)
- **Idea:** when enough tracks exist (about 1–2 s), solve a small visual-inertial problem over the retained first window for initial velocity, roll/pitch and accelerometer bias, then **replay the stored IMU samples from frame 0 with the corrected initial state** and replace the current state and covariance. This removes the position offset built during the first seconds, which a forward-only velocity correction cannot.
- **Reference:** the journal's closed-form plus variable-projection initializer worked in Python (in-flight 1.875 vs 2.205 m) and failed in C because C tracks were too short (about 30 tracks ≥ 8 frames vs about 65 with OpenCV). It was removed from the submitted `solution.c`; the frozen copy lives in the journal's workspace, which is not in the repo (`JOURNAL.md` m6). Plan to rewrite, not recover.
- **Storage:** first window only: about 50 frames of poses/IMU, a few hundred KB.
- **Kill:** if C1–C3 already bring the mid-start mean within 0.3 m of the static mean, skip C4.
- **Guess:** this is the strongest classical fix if the oracle test (L0 below) shows large remaining upside.

### C5. Health checks and recovery (2–3 days)
- **Checks:** (a) NIS gate or monitor on the stacked MSCKF update (`:713`); (b) plausibility limits from measured flight envelopes (speed above 3.5 m/s, vertical speed above 1.5 m/s, tilt above 40°, position jump) as pseudo-measurements; (c) a *soft reset* when a limit trips: inflate the velocity/position covariance rows and re-apply the startup prior, rather than a full reinitialization; (d) track-starvation mode: fewer than N live tracks for more than 1 s switches to stronger priors and freezes visual-only states.
- **Logging:** every trip increments a stderr counter so we can see which checks fire on which flights.
- **Kill:** if the checks fire on under 5% of flights and do not change the mean, keep only the logging.
- **Guess:** mostly tail protection (2 static flights above 5 m and the bad mid starts), 5–15%.

### C6. Steady-state priors from the flight envelope (1–2 days)
- **Arms:** vertical position prior relative to start (height std about 0.52 m per flight; σ 0.8 m), vertical velocity prior σ 0.3 m/s, soft non-holonomic constraint (body lateral velocity small relative to forward), speed upper bound.
- **Caveat:** these statistics come from 24 flights; recompute on the 882-flight search slice and freeze before val. A prior fitted to simulator planner statistics may not transfer if the server's flights differ.
- **Guess:** 3–10%; the vertical prior mostly trims z error.

### C7. Consistency fixes (4–6 days)
- **Context:** the journal measures velocity NEES about 8 (ideal about 3) and position NEES 80–125 (an overconfident filter that mis-gates).
- **Arms:** first-estimate-Jacobian (FEJ) linearization for clone and velocity/orientation terms in the feature Jacobians; process-noise multipliers fitted to NEES on the search slice; pixel noise by track length or depth.
- **Guess:** 5–10% on the mean but more robust gating for C5.

### C8. Smoothing (2–5 days, mostly inside C4)
- The output must stay causal (the repo's future-poison test enforces it), so smoothing means in-filter: (a) the C4 replay is a fixed-window smoother over the startup window; (b) test the window size again (the journal found 10 clones worse, 5 clones near equal at less fuel, 6 chosen); (c) bias model: Wiener vs OU kernel (`BIAS_KERNEL` was tested in IMU-only m1 and made no difference, so low priority).
- No post-hoc trajectory smoothing: it cannot reduce a persistent offset and breaks causality if it uses future data.

### C9. Textureless and dark frames (2–3 days)
- Adaptive detection threshold (a fixed 1000 passes few corners in flat or dark frames), brightness-normalized or affine-gain KLT residuals, a darker-frame exposure floor. Test on the dark/flat-flagged flights in search.
- **Guess:** helps the 2 static tails and the dark mid starts; 3–8%.

### C10. Parameter search under cross-validation (2 days, last)
- After structural changes, random search over about 12 parameters (priors, noise terms, thresholds), 60–100 evaluations on search, top 3 on val, one on final. At about 8 minutes per full-pool evaluation and 3–4 concurrent runs on the 192 cores this is about a day.
- The journal's lesson applies: its own noise sweep showed halves of the public set disagreeing, so only accept settings that hold on both val halves.

### Phase 1 expected outcome
- **Guess:** pool mean 2.21 → 1.3–1.7 if C1–C3 work, 1.0–1.3 with C4. If C1–C3 move the mid-start mean by under 10%, the startup offset is not a tilt/prior problem, and Phase 2 becomes the main lever.

## 3. Phase 2: oracle test, then the small-CNN / learned startup work

### L0. Oracle ceiling (1 day, after C1–C3)
- Native build of the chosen `solution.c` driven by raw episode inputs (`viobench episodes feed` exports them; `runtime/native/viobench_debug_main.c` is the native debug entry), with a compile flag that injects the **true** initial velocity (and, separately, true roll/pitch) at frame 0 with σ in {0.1, 0.3, 0.6, 1.0}.
- **Reading:** if true initial velocity brings the mid-start mean near the static mean, a learned initial velocity is worth building and σ sets its required accuracy. If not, the remaining error is lock-on or tracking and no velocity network will fix it.

### L1. Startup-velocity network (3–5 days, 1–2 GPUs)
- **Job:** predict the initial 3-D velocity (and optionally tilt) with a variance from the first 1–2 s, then switch off. It never runs in steady flight, so a small CNN is enough and the per-frame max fuel stays near the filter's.
- **Input:** two or three gyro-derotated frames at 64×48 (rotation from the filter or from IMU preintegration) plus body-frame preintegrated acceleration; output velocity mean and log-variance, Gaussian NLL loss.
- **Data:** time-crops of server-speed flights. A crop at any offset of a 60 s flight is a valid in-flight start with exact truth, so one flight yields many start points. Use only scenes outside the final slice and outside the 171 selected; the 200-flight server-regime training set in `research/server_training/` is the first source.
- **Use:** the network's velocity enters `initialize()` and the first-seconds prior as a measurement with its predicted variance (not as a hard reset), gated against vision once tracks lock.

### L2. CNN size grid for L1 (1–2 GPU-days)
| Axis | Values |
|---|---|
| Input size | 128×96, 64×48, 32×24 |
| Width | full, 1/2, 1/4 |
| Frames | 2, 3 |
| Variant | no CNN: the filter's own 10×6 KLT track grid (displacement and validity per cell) plus IMU into a small MLP/GRU |
- Choose the smallest net within 5% of the best raw mean on val. Reference sizes: N2's CNN is about 354 M MACs per frame; the repo's archived 32×24 encoder is about 175 K MACs. At 40 frames only, even a mid-size net adds under 1/30 of its per-frame cost on average.
- **Risk:** the track-grid variant depends on KLT tracks that are short in the C front end; the CNN variant avoids that dependence.

### L3. Calibration and integration (2–3 days)
- Check the network's predicted σ against residuals on val (coverage, NLL); inflate if overconfident (the journal's lesson on independent 20 Hz measurements applies only if the net is used repeatedly; at a single startup measurement it is applied once).
- NEES and the C5 gates stay on; the net measurement is rejected if the filter's vision-locked velocity disagrees strongly.

### L4. Continuous learned velocity (only if residual error justifies it)
- Triggered if after L1–L3 the mid-start gap still exceeds about 0.3 m, or tails remain on textureless flights. This is the old Track B (server-speed data, long stateful windows, binned velocity head), now as a small distilled student rather than the full N2. The server-regime pilot in `research/server_training/` supplies free evidence here.

### L5. Port, preflight, submit (1–2 weeks)
- Plain-C kernels for the small net inside the filter's wasm (no OpenCV), the 12-step preflight from `reports/Drone VIO implementation plan.md` (ABI, determinism, causality/future-poison, reset, mid-start, no filled frames, fuel, parity), then a server submission within the 3-per-day cap.

## 4. Timeline and gates

| Days | Work | Gate |
|---|---|---|
| 1 | Phase 0 setup: splits, 882-flight baseline score, variant runner, debug counters | baseline reproduced on search/val/final |
| 2–5 | C1, C2, C3 (parallel arms), C5 logging | adopt arms meeting the rule; stop if mid-start mean moves under 10% |
| 5–8 | C5 checks, C6 priors, C9 textureless | same rule |
| 8–10 | L0 oracle on the adopted build | decides whether L1 is built |
| 10–15 | L1/L2 (GPUs) in parallel with C7 consistency and C4 if needed | L1 gate: mid-start mean within 0.3 m of static, no static regression |
| 15–20 | C10 search, L3 integration, final-slice check | pool mean and median, tails, NEES |
| 20+ | L5 port and submission | preflight passes |

Parallelism: the classical loop is CPU-bound (192 cores), so L1/L2 training on GPUs 1–6 can start as soon as L0 says it is worth it without blocking C-work. GPU 0 hosts another service and GPU 7 was busy at last check.

## 5. Risks

- **The startup offset may not be tilt or prior driven.** C1–C3 are cheap tests of that; L0 is the decisive one. Otherwise lock-on in dark or flat frames is the cause and C9 and a visual lock-on detector matter more.
- **Overfitting to the simulator's planner.** Priors from flight statistics (C6, the heading-aware prior in C2) rely on the simulator's trajectory generator. The server's flights share a source with ours but this is unverified. Keep the final slice untouched and report static/mid and clean-scene numbers separately.
- **Server mix unknown.** The pool's gp_msckf tail rate on mid starts (23%) fits the server's 3 of 12, while VINS-Mono's clean server score fits static starts better; the 12-episode draw cannot separate them.
- **Replay complexity (C4).** State replacement mid-flight can introduce discontinuities; the existing prefix and reset tests must pass.
- **Fuel.** Phase 1 changes are cheap. L1 adds a small net for about 40 frames, so the per-frame maximum is about the filter's cost plus the net's per-frame cost; measure before submission.

## 6. Decisions I need from you

1. Approve spending about a day on the 882-flight baseline score (about 40 GB of logs unless the evaluator can skip the video).
2. Pick the git identity so the gp_msckf merge and any new work can be committed (you said SentientNapkin later).
3. Confirm whether the final slice should instead be a freshly generated set of flights, which the earlier notes estimate at about 0.4 hours of wall time for 200 flights with the existing generator (extrapolated from the pool's 80 minutes for 882 flights on 48 workers, not re-timed) but avoids reusing the 882-flight pool for both tuning and the final check.
