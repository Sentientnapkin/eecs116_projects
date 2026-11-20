# Single-model implementation plan: Track A (one filter) and Track B (one learned net)

Date: 2026-11-20. Metric: mean unaligned ATE (m). Goal: one wasm, no guard or selector. All expected gains below are estimates, not results.

Inputs: `reports/Drone VIO ATE approaches.md`, `reports/Drone VIO implementation plan.md`, `reports/Out of the box odometry paradigms.md`, the new `Final Project/classical_vio/gp_msckf/` (README, JOURNAL, `solution.c`, pulled from origin `1f5a89a`), and the repo state as of 03:41 today (`research/campaign`, `research/guard_fusion`, `research/server_training`).

---

## 1. What reading the gp_msckf journal changes

1. **gp_msckf is a different kind of estimator than what we had tried.** It is plain C (libc/libm only, no OpenCV, static memory) with a 2-level KLT front end, an MSCKF back end and 19.5 M peak fuel per frame. It already links into one wasm with no dependency conflict.
2. **Its local and server numbers disagree, and the journal tells us why we should care.**
   - On the first 30 hover-start flights of our own pool (`SentientNapkin/viobench-server-calibrated`) it scores 0.76 m mean and 0.50 m median. The server gives 3.22 m mean and 1.25 m median.
   - The journal never tested the 85 mid-flight starts, and it measures in-flight starts at about 0.7–1.3 m of offset built up in the first 5 s (public in-flight mean 1.49 m against 0.75 m for hover starts).
   - So the likeliest explanations for the gap are (a) the server has in-flight starts and (b) textureless fast flights. Neither is confirmed. This is the first thing to measure (A0).
3. **Its tail looks like a prior problem, which is a hypothesis.**
   - The only velocity information it has when tracks are lost is a zero-mean speed prior (σ 0.5 m/s per axis, τ 2 s; `solution.c:69-76` and `:436-441`). The journal says weaker priors make tails much worse and stronger ones bias the in-flight start.
   - Three server episodes have Sim(3) scale 0.49, 0.63 and 0.73, which looks like a pull toward "not moving". N2 shows the same shrinkage on the pool (0.35 m/s estimated against 0.91 m/s true).
   - A zero-mean prior can only be right on average. N2 velocity is a nonzero-mean replacement for exactly that prior, which is why Track A is natural.
4. **The journal's lessons transfer directly.**
   - Applying a correlated measurement independently at 20 Hz makes the filter overconfident; scale the variance by τ/Δt (m7).
   - Accept a change only if a paired bootstrap interval excludes zero and the effect holds on both episode halves (`robust_eval.py` protocol). Tuning on the 10 public episodes overfits.
   - NEES (target about 3) is the consistency check. Velocity NEES is about 8 and position about 80–125, so the filter is still overconfident.
5. **Scoring trade-off (from the journal's own score code, approximate).** At its operating point halving ATE is worth about 2.36 points and halving fuel about 0.28. Adding a 1.1–1.7 B-fuel N2 to a 19.5 M-fuel filter is about 6 doublings of fuel, so it must cut ATE by roughly half to pay for itself. This is why Track A should prefer a small distilled student (stage A5) over the full N2. You said to ignore fuel for now, so this only fixes the order of work.

---

## 2. Shared prerequisites (do first, mostly CPU, under a day)

| ID | Task | Files / commands | Output |
|---|---|---|---|
| S1 | Score `gp_msckf.wasm` on all 171 pool flights (hover and mid-start) with the pinned evaluator | `research/guard_fusion/composite/score.py` pattern (`--wasm /abs/path --episodes gen/raw-fast/selected --workers 64`); wasm SHA `c7413a81…357d` | `perflight.jsonl` rows via `research/campaign/perflight.py`; second calibration anchor (B-D0 server 4.55 vs local 4.20 is the only anchor today) |
| S2 | Per-flight diagnostics for every guest: Sim(3) scale, speed slope (estimated/true speed), error at 5 s, extent, tail flag | new `research/campaign/diagnose.py` reading `estimate.tum` + truth from `gen/raw-fast/selected/<ep>.zip` | table showing whether tails are scale collapse or startup offset, per guest |
| S3 | Decide the headline mean (weighted vs unweighted selection) and the scene-grouped fold assignment | reuse `guard_fusion/evaluate.py` fold rule (SHA256(catalog:scene) mod 5) | one agreed definition before any arm is scored |
| S4 | Register arms in the ledger | `research/campaign/specs/*.json`, `ledger.py`, `leaderboard.py` | rows stay unranked until preflight and three-seed rules are met |

Gate on S1/S2 before spending GPU time:
- If gp_msckf scores about 0.8 m or better on the pool (including mid-starts), the server's 3.22 m is mostly a scene or start-condition difference and the pool undercounts server difficulty for geometric filters. Then calibration, not modelling, is the next problem.
- If it scores around 3 m with a similar tail, the pool matches the server and the tail is a genuine estimator failure we can iterate on locally.

---

## 3. Track A: one filter, with learned velocity as a sensor

**Idea:** keep gp_msckf as the only estimator. Replace its zero-mean velocity prior by a velocity measurement from a learned network, so it survives in-flight starts and track loss without a hover. It ships as one wasm and one state.

### A0. Diagnose the tails (0.5 day, CPU)
- Add a host-only debug counter build (the journal's `DEBUG_COV=1` and stderr counters) logging per frame: live tracks, features used per update, prior-dominated fraction (frames where the prior update is the only velocity information), speed estimate.
- Test hypothesis H-A1 (tails are prior-driven shrinkage): in the three worst server-like pool flights, speed-estimate error should rise during long track-lost spans. Kill H-A1 if scale error is uncorrelated with lost-track time; then Track A's value is only the startup fix.

### A1. Offline N2-velocity pseudo-measurement (2–3 days, CPU only)
No N2 in wasm yet; use saved per-frame N2 velocities, which exist for all 171 flights at `baselines/bench-fast/selected/n2_kfinputs_s217-*/<ep>/report/logs/*/twist.txt` (camera-frame twist).
- **Harness:** a host C driver (`research/single_model/host_driver.c`) that links `solution.c` unchanged except a compile flag `N2_VEL_FILE` and feeds frames, IMU and the twist stream. This avoids new N2 builds while we learn how the filter wants the measurement.
- **Integration point:** `solution.c:436-441`, where the speed prior is a 3-D zero-mean update. Add a second update `z = v_n2(k)` with H = d(R_bc^T R^T v)/d(dθ, dv). The output convention is already camera-axes twist, so rotating into the filter's world frame is a fixed transform (`write_state`).
- **Covariance:** start with a constant per-axis σ calibrated on the training pool, then the speed-dependent σ(|v|). Apply the journal's correction: N2 errors are autocorrelated (SSM state), so use variance σ²·τ_n2/Δt with τ_n2 from the residual autocorrelation, never raw 20 Hz independence.
- **Bias handling:** N2 under-reports speed on server-speed flights, so fit a gain g and bias on a training-scene residual, or restrict use to direction plus a bounded speed. Test both.
- **Arms** (all vs the current prior as control, same 171 flights, scene-grouped):
  - A1a: N2 only at startup (first 5 s).
  - A1b: N2 only when live tracks fall below a threshold.
  - A1c: N2 always, τ-scaled.
  - A1d: N2 direction only, speed from vision or the prior.
- **Gate (declared before scoring):** raw mean improves at least 10% over the same filter with the prior, scene-grouped CV, paired bootstrap over scenes excludes 0, no worse on mid-start vs hover halves, velocity NEES not worse. Kill if all arms are under 5%.
- **Estimate (guess):** this attacks the one dominant failure we can identify. A plausible range is 3.2 → 1.8–2.5 m on the server-like set if H-A1 holds, much less if not.

### A2. Make the covariance honest (2 days, CPU)
- NEES for velocity and position on all arms; inflate process or measurement noise where NEES exceeds about 3.
- Add a Mahalanobis gate on the N2 measurement so a bad N2 chunk is down-weighted against a vision-locked filter, never overriding it.
- Compare against the journal's existing finding that the tail gets worse when the prior is weakened.

### A3. Learned covariance for N2 (3–4 days, 1–2 GPUs)
- Retrain a small NLL head that outputs a per-frame velocity variance (the repo lists this as untried item 1 in `research/APPROACHES.md` section 5). Train on server-style flights from the `server_training` pool.
- Gate: calibration (NLL, coverage) on held-out scenes, then A1c with learned σ against A1c with constant σ.

### A4. Startup (in-flight) handling (2 days)
- The journal's remaining in-flight cost is the first 5 s (0.7–1.3 m). Use the N2 velocity plus the filter's tilt/gyro-bias estimates as the initial state instead of the zero-mean prior with σ 1 m/s (`INIT_VELOCITY_STD`, `solution.c:63`, `:376`).
- Reference: its parked visual-inertial initialization worked in Python (in-flight 1.875 vs 2.205 m) but failed in C because C tracks are too short (~30 vs ~65 tracks of length ≥ 8). N2 initialization sidesteps that.

### A5. Put the network in the wasm (1–2 weeks)
- **Dependency.** N2's kf_grid attitude needs OpenCV 5.1; the guard composite already built a separate N2 backend on OpenCV 4.12 (`research/guard_fusion/composite/`). gp_msckf uses no OpenCV, so combining them needs the same toolchain resolution.
- **Cleaner option (N2f):** train N2 with attitude from the filter's own orientation (it already estimates gyro bias and tilt) instead of kf_grid. That removes the OpenCV dependency and the visual-attitude parity problems. Cost: training data must be generated by running the filter (host build) on the training flights, and a feedback loop (net uses filter attitude, filter uses net velocity) must be trained and tested for stability.
- **Size:** distil to the compact student (about 20 k parameters, 175–250 M MACs in `research/native_odometry/README.md`) before porting if fuel matters.
- **Gate:** preflight 12-step list from `reports/Drone VIO implementation plan.md` (ABI, causality/future-poison, reset, mid-start, no filled frames, fuel, parity).

### Track A decision points
- After A0/A1: if no arm beats the prior by 5%, stop Track A's N2 idea. Keep the diagnostics.
- After A2/A3: if the filter beats 1.5 m on the pool with honest NEES, move to A5. If it reaches under 1 m, it is a candidate for a server submission (three per day, two remaining today).

---

## 4. Track B: one learned network without the amplitude collapse

**Idea:** fix the specific measured failure of N2 on server-style flights and keep the single-network architecture.

### B0. Confirm the diagnosis (CPU, under a day)
- Speed-slope check over all 171 flights for N2 and B-D0: regress estimated speed on true speed per flight. The 40-flight result (0.35 vs 0.91 m/s) must hold on all 171.
- Read the running pilot (`research/server_training/`): a three-seed N2 warm-start with 50/50 server-regime data against an equal-update control. Gate in the README: at least 10% raw-mean improvement, every seed better, original-dev regression ≤ 5%. This is the cheapest evidence for or against H1 (speed distribution shift). I have not seen its results.

### B1. Server-regime data at scale (GPU, 1–2 days wall)
- Current facts: training flights have p90 speed 0.51 m/s against 1.58 m/s on the pool, and mean path 13.7 m against 46–56 m.
- Tiers: 200 (pilot, running), then 1,000, 3,000, and 6,000 only if the scaling curve holds. The pool of 882 took about 80 minutes with 48 workers. Use all of GPUs 1–7 for generation, GPU 0 only for evaluation (a foreign service uses 2 GB).
- Splits: keep the benchmark's clean and dev scenes and the reserved test scenes out of training. Hold out about 15 ProcTHOR and 12 HSSD-train scenes as a validation set (`ftrain-val`).

### B2. Training changes aimed at amplitude (3–5 days)
| Change | Rationale | File |
|---|---|---|
| Long stateful windows at equal optimizer updates | training windows are about 4.8 s; inference carries state for 60 s | `research/odometry_train.py` (already modified locally) |
| Position-integral loss over 10–30 s plus log-speed or relative-error term | plain L2 on velocity pulls toward the mean | same |
| Binned or mixture velocity head | avoids mean collapse; also gives an uncertainty for Track A | `research/seq_heads.py` |
| Held-out 60 s checkpoint selection | the original-dev replays are 14 short flights | `research/campaign/specs` |

Dropped from the earlier list: yaw-drift-aware loss (the earlier learned bias head regressed), test-time adaptation, rotor features (thrust is not in the ABI), seed ensembling (seeds correlate 0.97).

### B3. Gates and seeds
- Screen at 12 epochs with seeds 217/218, promote the best one or two arms to three seeds. Training is about 3 minutes plus 75 s compile on one H100, so independent runs, not DDP.
- Accept at least 5% raw-mean gain with all three seeds better, on pool-171, plus guard sets (original dev, campaign) with no more than 5% regression. Differences under 0.4 m are noise (the selection's effective size is about 90 flights).

### B4. What the ceiling looks like
- Learned-only estimate: about 2.1–2.6 m on the pool if H1 holds, 2.8–3.2 m if not. Nothing found supports 0.5 m for a pure network.
- If B reaches about 2 m or better, it becomes the velocity sensor for Track A (A1/A3), which is why Track A does not wait for Track B.

---

## 5. How the tracks combine

- **Track A uses today's N2** (saved velocity streams) for A0–A2 and Track B's improved network for A3 onward. Whichever track passes its gate first sets the final single model: filter plus network (A5) or network alone.
- **Compute:** A0–A2 and S1–S4 are CPU-only. Track B and A3 use GPUs 1–6, as in the running pilot. Keep GPU 7 and the CPU cores for evaluation. The machine has 192 cores and eight H100s, and GPU 7 was busy at 97% when I last looked.
- **Order:** S1–S4 → A0 and B0 in parallel → A1 → (B2 pilot result) → A2/A3 → decide → A4/A5.
- **Rough effort (my estimates):** Track A about 10–14 engineering days to a wasm candidate; Track B about 7–10 days plus 40–80 GPU-hours.

---

## 6. Risks and open items

- **gp_msckf's local and server numbers disagree** (0.76 vs 3.22 m). Until S1 is done we do not know whether the pool predicts the server for this estimator.
- **H-A1 is unverified.** The prior-shrinkage story fits the scale factors (0.49–0.73) and the journal's prior sweeps, but nothing has isolated it.
- **N2 under-reports speed on server-speed flights**, so using it as a measurement before Track B's fix needs the bias handling in A1 or it may add a different shrinkage.
- **Feedback stability in N2f.** A network that takes filter attitude and a filter that takes its velocity can couple errors. Test with future-poison and reset checks.
- **Fuel.** The full N2 is about 90 times the filter's fuel; see section 1, point 5.
- **Git:** the gp_msckf directory is copied into the working tree but the merge with origin is not committed (no git identity). You said to pick an identity later; committing waits for that.
- **Unverified references:** several 2026 arXiv IDs in the earlier reports are snippet-only; none of this plan depends on them.
