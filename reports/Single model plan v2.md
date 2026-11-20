# Single-model plan v2 (after scoring gp_msckf on the pool)

Date: 2026-11-20. Supersedes the stage ordering in `Single model implementation plan.md`; its Track A/B structure stays. Metric: mean unaligned ATE (m). Expected gains are my estimates unless marked measured.

## 1. What was measured

`gp_msckf.wasm` (SHA `c7413a81…357d`, the server-submitted file) was run through the pinned evaluator on all 171 selected pool flights, 48 workers, about 93 s. Results are in `research/results/loop/gp-msckf-pool/` (summary and per-flight `scores.json`, `estimate.tum` per flight). All 171 completed with 0 filled frames, peak fuel 22.5 M.

| Slice (n) | gp_msckf mean / median | N2 s217 mean / median | VINS-Mono mean / median | OpenVINS mean / median |
|---|---|---|---|---|
| All (171) | **2.21** / 0.80 | 3.51 / 3.24 | 5.51 / 0.62 | 28.5 / 0.58 |
| Static start (85) | **0.82** / 0.52 | 3.30 / 3.02 | 4.99 / 0.48 | 31.3 / 0.45 |
| Mid-flight start (86) | **3.58** / 1.54 | 3.71 / 3.38 | 6.02 / 0.85 | 25.8 / 0.76 |

- The server's 3.22 m sits inside the pool's 12-flight 5–95% range for gp_msckf (0.80–4.18). The pool is therefore a consistent proxy for it, with a thin calibration (one 12-episode draw).
- gp_msckf is already the best single model we have on the pool (2.21 vs N2 3.51) at about 1/50 of N2's fuel.
- Oracle best-per-flight combinations (hindsight, not guests): VINS + OpenVINS + N2 = 0.759; plus gp_msckf = 0.670; gp_msckf + VINS = 0.980; gp_msckf + N2 = 1.341.

## 2. The finding that reorders the plan: gp_msckf's error is a startup offset on in-flight starts

Position error over time (mean over flights):

| | at 2 s | at 5 s | at 10 s | at 30 s | final | ATE |
|---|---|---|---|---|---|---|
| Static starts | 0.14 | 0.40 | 0.57 | 0.81 | 1.03 | 0.82 |
| Mid-flight starts | 1.71 | 2.88 | 3.47 | 3.62 | 3.63 | 3.58 |

- On mid-flight starts the error is already 1.7 m at 2 s and then stays flat. That is an offset built in the first seconds, not drift. It matches the journal's own description (about 0.7–1.3 m of startup offset on public in-flight starts), but on the longer, faster pool flights it is much larger.
- The mid starts split cleanly. 49 of 86 have under 1.5 m error at 5 s and average **0.97 m** ATE. The other 37 average **7.03 m**. Of the 22 flights above 5 m, 20 are mid starts.
- If every mid start behaved like the good half, the pool mean would be about 0.9 m (0.82 static, 0.97 mid). This is an upper-bound calculation under that assumption, not a prediction.
- What marks the bad starts: weakly dark and flat (textureless) frames (correlations +0.31 and +0.22 with ATE on mid flights, mean flat fraction 0.13 vs 0.01). Start speed does not predict it (correlation 0.06), so it is not "fast starts fail".

## 3. Corrections to earlier statements

1. **Scale direction.** I and the earlier report described the server tails (Sim(3) scale 0.49, 0.63, 0.73) as scale *shrinkage*. The evaluator's convention is `target ≈ s·R·source + t` (`viobench/tools/runner/metrics.py:34`), so s < 1 means the estimate is too *large*. The pool agrees: on gp_msckf's 22 flights above 5 m the median estimated/true path-length ratio is 1.48, and 17 are above 1.1. The "prior pulls toward zero speed" hypothesis (H-A1) is **not supported**. The tails are over-extension after a wrong startup velocity.
2. **N2's own amplitude collapse stands** (N2 speed 0.39 vs true 0.98 m/s over 0.5–1.5 s on mid starts, measured on all 86), but it is a separate problem from gp_msckf's tails.
3. The earlier "8 of 12 server episodes at 0.27–0.92 m" was wrong; it is 6 (already corrected in the previous reply).

## 4. The CNN question: N2's CNN is not buying accuracy where it matters

Evidence:
- 99.5% of N2's counted MACs (354 M of 356 M per frame) are in its three shared-weight CNN passes at 128×96, which is the fuel bottleneck (about 1.07 G fuel per frame, 0.86 G with the SIMD port).
- On the course server a 1.1 G-fuel B-D0 scored 4.55 m and the 25.5 M-fuel Exponential Moving Average guest scored 4.63 m. That is roughly a 40× fuel difference for a 0.1 m gap on one 12-episode draw (noise is about 0.4 m), so the large CNN is not obviously buying accuracy.
- On the pool N2 is barely better than outputting no motion (0.87× the identity-pose error).
- The repo's archived 32×24 compact encoder is 20,175 parameters and 175,328 MACs per frame (about 2,000× fewer than N2). The repo's own never-run falsifier (`research/APPROACHES.md` section 4.6): train a 1/4-width, 64×48 N2 for 3 seeds and compare.

Ranked options, cheapest first (gains are guesses until tested):

| # | Option | Cost reduction | Why it might hold | Test |
|---|---|---|---|---|
| 1 | **Run the CNN only for the startup window** (first ~2 s, about 40 frames), then switch it off | per-frame max stays at the CNN's cost, mean drops ~30× | static starts reach 0.82 m without any network; only the first seconds of in-flight starts need velocity | Section 5, experiment E3 |
| 2 | Input resolution 128×96 → 64×48 → 32×24 | 4× / 16× | motion cues are low-frequency (parallax about 0.5 px per frame at 320×240) | train the grid in E4 |
| 3 | Width 1/4 (and 1/2) | ~16× / ~4× in the convolutions | repo already lists it as low risk | same grid |
| 4 | Both: 64×48 + 1/4 width | ~64× | about 17 M fuel before overhead, about the filter's own cost | same grid, the repo's falsifier |
| 5 | **No CNN: feed the filter's own KLT track grid to a small MLP/GRU** | CNN cost → ~0 (tracks already computed) | gp_msckf already tracks one feature per cell of a 10×6 grid; N2's CNN is essentially learning flow | E5 |
| 6 | Depthwise-separable layers, int8 | 3–4× | standard | after the grid; needs int8 fuel check (unmeasured) |
| 7 | Run the CNN every 2nd–4th frame and let the SSM carry state | 2–4× | clone frames already come every 4th | cheap ablation |
| 8 | Distill the large N2 into the small student | none directly | helps only if labels are noisy; true velocity labels already exist | low priority |

Risk: option 5's KLT tracks in the C front end are short (journal: about 30 tracks last ≥ 8 frames, vs about 65 with OpenCV), and parallax is tiny, so the net may see too little.

## 5. Revised plan

**Principle:** keep gp_msckf as the single estimator. Its static-start accuracy (0.82 m) is already good. Replace "N2 velocity as a continuous sensor" with the narrower, cheaper job of getting a good initial velocity (and, if needed, a lock-on check) for in-flight starts. This also answers the CNN-size question, because a startup-only network can be small and runs for about 40 frames.

| Step | What | Cost | Gate |
|---|---|---|---|
| **E1** | Diagnose the 37 bad mid starts vs the 49 good: tracks alive and features used per second in the first 5 s, time to vision lock-on, filter velocity vs truth in a consistent frame (compare in the world frame; my quick comparison mixed frames and is not trusted for vectors) | 0.5 day, CPU, host build with the journal's debug counters | explains *why* lock-on fails (textureless vs wrong prior vs bad linearization) |
| **E2** | **Ceiling test**: a host build of `solution.c` with the true initial velocity injected at frame 0 (σ 0.2, then σ 0.5 and 1.0 m/s) on the 86 mid flights | 1 day, CPU; needs a host driver (ctypes + `read_episode`) since the wasm cannot see truth | if mid mean falls from 3.58 toward 1.0 at σ ≤ 0.5, the startup-velocity fix is validated and σ gives the accuracy the startup net must reach. If it stays above 2, the cause is elsewhere (lock-on or tracks) and the startup net is the wrong fix |
| **E3** | Startup-velocity net: input first ~1–2 s (derotated frame pairs or KLT grid + IMU), output initial 3-D velocity with a variance; train on server-style mid-start flights; use as the initial-state measurement in `solution.c` around `:63` and `:376` (replacing the σ 1 m/s zero-mean init and the early zero-mean prior); the net then switches off | 3–5 days, 1–2 GPUs | raw pool mean ≤ 1.5 m with mid-start median < 1.0 m, scene-grouped CV, paired bootstrap over scenes excludes zero, no static-start regression above 0.1 m |
| **E4** | Small-CNN grid for E3 (and, if kept, any continuous net): resolution {128×96, 64×48, 32×24} × width {1, 1/2, 1/4}, 12-epoch screens, seeds 217/218 | about 1–2 GPU-days total | pick the smallest net within 5% of the best |
| **E5** | CNN-free variant: KLT track grid + IMU → small GRU/MLP | 3 days | compare with E4 at equal data |
| **E6** | Honest covariance: NEES on all arms (target ~3; the journal's filter is at 8 / 80–125), χ²-gate the network measurement against vision once locked on | 2 days | NEES not worse; no tail regression |
| **E7** | Port to the single wasm: network weights embedded in the C filter (no OpenCV; the small-CNN path can reuse the repo's plain-C kernels, check `research/native_odometry/odometry.hpp`) | 1–2 weeks | 12-step preflight from `reports/Drone VIO implementation plan.md`, server submission (3/day cap; 2 left on 2026-11-19, resets at midnight Pacific) |

Parallel and optional:
- **Track B (continuous learned net) is demoted to a supporting role.** The server-regime pilot (`research/server_training/`) still gives free evidence on whether server-speed data fixes amplitude collapse, which matters for E3's training data design. Do not invest more in it until E2 says whether velocity is the missing piece.
- **Guard track** (being implemented by the other session): keep it as the fallback. The measured held-out mean there is 0.99 m for the three-source guard; adding gp_msckf to the hindsight oracle only improves it from 0.759 to 0.670. A single filter at about 0.9–1.2 m would match the guard's accuracy without three models, which is the point.
- **Remaining tails after startup** (2 static flights above 5 m, textureless/dark flights): gp_msckf coasts on the IMU when tracks are lost (journal "Known limitations"). Track them after E3.

## 6. Expected outcomes (estimates)

| Stage | Pool mean (guess) | Basis |
|---|---|---|
| Today, gp_msckf | 2.21 (measured) | |
| After E3 if E2 confirms the ceiling | 1.0–1.5 | upper bound 0.9 if all bad starts become good |
| After E6 consistency fixes | 0.9–1.3 | small additional gain |
| 0.5 m | under 10% likely | needs static starts below 0.5 too |

Honest uncertainty: E2 could show that the startup offset is mostly a lock-on problem in textureless frames. Then the lever is different (better tracking, or a startup-time vision check), and a velocity net would not fix it.

## 7. Open items

- The frame convention of the truth velocity vs the estimate twist is not verified; vector velocity comparisons are deferred to E1.
- The server's start-type mix is unknown. The pool's gp_msckf tail rate on mid starts (23%) fits the server's 3 of 12 tails (25%), while VINS-Mono's clean server score fits static starts better. The 12-episode draw cannot separate these.
- Git: the gp_msckf files are copied into the working tree, not merged or committed; the identity choice is pending. My scoring run wrote `research/results/loop/gp-msckf-pool/` and a driver in the scratchpad (`run_gp.py`) because `guard_fusion/composite/score.py` launches the evaluator with the wrong interpreter (`sys.executable` is the teacher venv, which lacks `conta`) when called directly.
