# Slideshow outline: how we optimised the GP + MSCKF drone estimator

A slide-by-slide plan for a ~20-slide talk. Each slide lists its title, what goes on it (visual + bullets), and speaker notes. Numbers come from our logs (`research/single_model/LOOP_LOG.md`) and the build write-up (`reports/GP MSCKF build history explained.md`).

---

## Slide 1 — Title

**Title:** From 3.2 m to under 1 m at a fifth of the fuel: optimising a monocular visual-inertial estimator

**On the slide:** team name, course (EECS 116), date. Background image: one simulated flight, true path vs estimated path.

**Speaker notes:** one sentence on the task. A drone with one camera and an IMU has to know where it is at every frame, using as little compute as possible.

---

## Slide 2 — The task and how it is scored

**Visual:** the server's log-log plot: x = peak fuel per frame, y = mean position error, with baselines and our points.

**Bullets:**
- Input every frame: one 320×240 camera image plus 10 IMU samples (200 Hz). Output: a 6-DoF pose.
- Runs as plain-C WebAssembly; "fuel" = number of executed wasm operations.
- Score = area gained on a log-log plot of **peak** per-frame fuel vs **mean unaligned ATE** over 12 hidden server flights.
- Both axes are logarithmic: halving fuel and cutting error by the same factor are worth the same.

**Speaker notes:** peak, not average, fuel counts, so a single expensive frame sets your score. Unaligned ATE means a constant offset at the start counts against you for the whole flight.

---

## Slide 3 — Why this is hard: no drag, so no free velocity

**Visual:** a diagram of the drone. The accelerometer measures thrust + gravity only; arrows show velocity coming only from the camera.

**Bullets:**
- The simulator has no rotor drag, so the accelerometer carries no information about velocity.
- Velocity must come from vision. When the camera sees little texture, or the drone starts mid-flight, velocity is unobserved and position drifts.
- A 1° tilt error makes the filter remove gravity slightly wrong: a false acceleration of ~0.17 m/s².

**Speaker notes:** almost every improvement in this talk attacks one of these three problems: unknown start velocity, starved vision, tilt drift.

---

## Slide 4 — The baseline estimator

**Visual:** a block diagram. IMU propagation → MSCKF update (sliding window of past poses) ← KLT feature tracks; GP bias model on the side.

**Bullets:**
- MSCKF: a Kalman filter that keeps ~10 past camera poses; tracked features correct them without being stored.
- Biases are modelled as a Gaussian process; features are corners tracked with Lucas–Kanade optical flow.
- First server result: **3.22 m @ 19.5 M fuel**. Static starts were fine (0.82 m locally); mid-flight starts averaged 3.58 m.

**Speaker notes:** error locked in during the first 2–5 s and stayed flat: an offset, not drift.

---

## Slide 5A — Building our own dataset: why we had to

**Visual:** side-by-side bars of the public set (18 m path per flight), our first pool (16 m) and the server (60 m, range 39–80 m).

**Bullets:**
- The server's 12 episodes are hidden. We only see per-episode scores, so we never downloaded or probed them.
- The public examples were too few and too slow: ~18 m of path per 60 s flight, against ~60 m on the server.
- Learned components need thousands of labelled flights, with true pose, velocity and gravity at every frame.
- So we generated our own flights with the same simulator the course uses.

**Speaker notes:** the first local pool predicted the server badly. Our first learned model scored 2.3× worse on the server than locally, which pushed us to make our data match the server.

---

## Slide 5B — How a flight is generated

**Visual:** a pipeline diagram: scene catalog (HSSD houses, ProcTHOR rooms) → trajectory planner (speed, acceleration, jerk, yaw-rate limits) → simulator renders 320×240 RGB at 20 Hz + IMU at 200 Hz + ground truth → zip → cached frames for training.

**Bullets:**
- **Generator:** `research/native_campaign.py generate`, driven by a JSON roster (scene, seed, planner settings, start type) and run in parallel on CPU/GPU workers.
- **Two start types:** static (hover, then fly) and mid-flight (already moving at frame 0).
- **Planner overrides** (`task_overrides`): the default planner (cruise 0.45–0.8 m/s) cannot exceed ~48 m in 60 s, so we raised speed, acceleration, jerk and yaw-rate limits to reach server-like 40–80 m paths.
- **Each flight:** 1200 frames, with ground truth used only for labels and scoring, never as an input to the estimator.

**Speaker notes:** the same flight is reproducible from its roster entry and seed, which made every set auditable.

---

## Slide 5C — One dataset, three jobs

**Visual:** one big box labelled "Our simulated flight dataset (~3,000 flights, 60 s each, same simulator as the server)", split by scene into three coloured parts:

| Part | Share | What it's for | Rule |
|---|---|---|---|
| **Training** | most scenes | teaching the learned velocity net | never used to judge a build |
| **Tuning** | a separate set of scenes | comparing ideas and picking settings | always 3 runs per idea; a dev half to choose, a confirm half to check |
| **Holdout** | 240 flights kept separate from tuning (some rooms overlap) | the final exam for a finished build | scored exactly once per build |

Down one side, a strip: "Includes a deliberately hard slice: fast flights in untextured rooms, matched to the server's worst episodes."

**Bullets:**
- **One dataset,** split mostly by scene. Some holdout rooms also appear in earlier training and tuning flights, so a small benefit from familiar rooms can't be ruled out.
- **Training → tuning → holdout** is the same discipline as train/validation/test in machine learning.
- **The hard slice** was added later, when the server showed us which flights we were missing (slide 5D).

**Speaker notes:** keep this to one dataset. If someone asks why the logs mention names like "fresh-711", "st1" or "st2", those are just batches of the same dataset, generated at different times with different speed settings. They are listed in the backup slide B5.

---

### Backup slide B5 — Batch names behind the one dataset (only if asked)

| Batch name in our logs | Flights | Belongs to | Notes |
|---|---|---|---|
| fresh (711) | 711 | tuning (folds 0–3); fold 4 sealed | first fast batch, folds by scene |
| holdout | 240 | holdout | new seeds; scenes kept out of tuning |
| st1 | 400 | tuning | long, fast flights in normal rooms ("fast but easy") |
| st2 / st3 | 240 / 234 | tuning (hard slice) | fast flights in the hardest untextured rooms |
| raw-fast/raw-speed folds 0–2, roster_a, roster b | ~1,300+ | training | texture-weighted, fast planners |
| selected pool | 171 | early tuning | first local pool, before the dataset was server-matched |

---

## Slide 5D — Calibrating the dataset against the server

**Visual:** a scatter of path length and spatial extent for the holdout vs the server. Two matching numbers are highlighted (59.4 vs 59.6 m path; 4.696 vs 4.694 m extent).

**Bullets:**
- **Anchors from the server's own published numbers:**
  - the "identity pose" baseline scores 4.694 m, which equals the flights' RMS extent
  - the per-episode distances travelled average 59.6 m
- **The holdout was tuned to match both:** 59.4 m path, 4.696 m extent.
- **It still missed the hard case:** the server ran 1.4–1.85× worse than the holdout. Per-episode server scores showed fast flights in untextured rooms.
- **So we built st2 to match that failure signature:** 2–8 m error, over-extension, 0.5–1.3 m/s velocity error. It became the main tuning set for the latest builds.

**Speaker notes:** a test set is only as good as its resemblance to the real one. Matching averages wasn't enough; we had to match the failure mode.

---

## Slide 5 — Our evaluation discipline

**Visual:** a funnel: generated flights → dev folds → confirm fold → one-shot holdout → server.

**Bullets:**
- **Generated our own flights** in the same simulator: 711 "fresh", 240 clean holdout, later server-like sets.
- **Dev / confirm split** by scene. Holdout scored exactly once per final build, by the coordinator only.
- **Three replicates per candidate,** because the filter is chaotic: tiny input changes give ~0.012 m differences.
- **Every submission passes a preflight:**
  - zero imports
  - deterministic
  - never uses future frames (738 prefix/poison checks)
  - resets cleanly
  - byte-identical rebuild
- **Never touched** the server's private episodes, never optimised Sim(3) error.

**Speaker notes:** this is what kept us honest. Several ideas that looked good on one set died on the next.

---

## Slide 6 — Fix 1: guessing the start (G and C1)

**Visual:** before/after error over time for mid-flight starts.

**Bullets:**
- **Startup gate:** detect from the IMU whether the drone is already moving.
- **Heading prior:** if moving, assume it flies forward at a typical speed.
- **C1 priors:** a 1-s hover-hold estimates biases and gravity on static starts; weak "little vertical / little sideways velocity" priors.
- Holdout 1.72 → 0.97 m. Server 3.22 → **1.24 m**.

**Speaker notes:** the lesson came from one server episode that went from 0.92 to 7.70 m. The forward guess was wrong for a slow start and locked the scale 1.75× too large. Hand-written guesses are fragile.

---

## Slide 7 — Fix 2: better tracks (B7)

**Visual:** an image with tracks; rejected tracks in red (forward-backward mismatch).

**Bullets:**
- **Forward-backward KLT check:** track each feature back to the previous frame and drop it if it misses by > 0.5 px.
- About 10% of tracks dropped, mostly drifting ones on edges.
- Fresh flights 0.73 → 0.62 m.
- **Same build, exact fuel rewrite:** identical outputs, peak 23 → 12 M.

**Speaker notes:** first example of the two axes together. A quality fix for error, and a zero-risk code rewrite for fuel.

---

## Slide 8 — Fix 3: let a neural net tell us the start velocity (B10)

**Visual:** the net architecture (64×48 frame pair → small CNN → velocity + uncertainty), and a scatter of predicted vs true start velocity.

**Bullets:**
- ~105 k parameters, ~1.7 M multiply-adds, written in plain C.
- Runs once at frame 5–6 and is injected as a velocity measurement with its own uncertainty; replaces the hand-written heading prior.
- Trained only on our own generated flights (folds 0–2).
- Holdout 0.88 → **0.74 m**.

**Speaker notes:** the net learns the direction from image motion, including starts that aren't forward. That was exactly where the hand prior failed.

---

## Slide 9 — Fix 4: use the net again when vision fails (B15, B13, B16)

**Visual:** a timeline of one flight. Velocity uncertainty rises; a "re-anchor" marker; error drops.

**Bullets:**
- **pv25:** when the velocity uncertainty exceeds 0.25 m/s, re-run the net and re-anchor velocity.
- **Iterated update:** re-linearise and update again when the state moved a lot.
- **Map:** re-match old 3-D points when the drone revisits an area.
- **B16 = all three:** holdout 0.56 m; server **0.782 m @ 17 M**.

**Speaker notes:** four server episodes still carried 79% of the error, all with rigid offsets. That pointed us at what happens after the start.

---

## Slide 10 — Diagnose before you build

**Visual:** a bar chart: error explained by "remove rigid offset", "remove heading error", "perfect first 5 s".

**Bullets:**
- Removing each flight's best rigid shift: 0.40 → 0.26 m. Fixing heading: almost nothing. A perfect first 5 s: only 0.03–0.06 m.
- So the error is a translation offset built up after 5 s, in stretches with little to track.
- Found two bugs: the movement gate forced a "still" update on moving starts, and the re-anchor never fired on static starts → **B17**, holdout 0.52 m.

**Speaker notes:** the analysis killed several attractive ideas (closed-form re-initialisation, heading fixes) before we spent time on them.

---

## Slide 11 — Going left: where the fuel goes

**Visual:** a stacked bar of fuel per frame by module (KLT, detection, pyramid, filter update, second iteration, map, net), with the peak frame highlighted.

**Bullets:**
- Peak = max over frames → periodic bursts (window slide, net, map matching) set the score.
- Profiling showed tracking dominates the median frame; filter updates and the net dominate the peak frame.
- Rule: exact rewrites first (bit-identical outputs), approximations only if accuracy holds on honest sets.

**Speaker notes:** we never accepted a fuel cut on faith. Every approximate change had to tie on dev and confirm with 3 replicates.

---

## Slide 12 — The fuel toolkit (T4uB)

**Visual:** before/after fuel-per-frame traces. A spiky B17 line vs a flat T4uB line capped at ~4 M.

**Bullets:**
- **Integer SIMD tracker:** 8× cheaper, slightly more accurate.
- **SIMD patch matching** for the map: 3× cheaper, identical outputs.
- **Per-frame budget governor:** each optional job has a cost, and work that doesn't fit is deferred to the next frame.
- **Startup net split into micro-steps** across frames.
- Result: **B16-level accuracy at 4.1 M** (from 20 M).

**Speaker notes:** the governor is the key idea. Because the score uses the peak, spreading work evenly is worth as much as removing it.

---

## Slide 13 — Audit: what is necessary, and no holes

**Visual:** a table of modules with verdicts (keep / remove / simplify), and a stress-test matrix (green/red).

**Bullets:**
- **Ablation:**
  - the startup net, map, re-anchor, second iteration and FB check are all needed (each costs 0.03–0.13 m when removed)
  - the movement gate is now harmful → removed
- **Stress tests:** NaN / Inf IMU data, IMU spikes, dropped frames, black frames, 3000-frame flights, odd attitudes.
- **Hardening:**
  - an IMU sanitiser
  - a divergence watchdog
  - an output guard

  All identical on normal data.
- **HFG** = T4uB + hardening + exact work reuse + gate removed → server **0.948 m @ 4.0 M (best score, area 4.54%)**.

**Speaker notes:** the server number got slightly worse than B16 on error but much better on fuel, so the score rose.

---

## Slide 14 — The server is harder than our tests

**Visual:** per-episode bars for HFG on the server; three tall bars (3.46, 2.69, 2.28 m).

**Bullets:**
- Three episodes carry 74% of the error; the other nine average 0.34 m.
- The server/holdout ratio grew to 1.85×: our tests were missing something.
- Built a server-like test set: fast flights in the hardest untextured rooms. It reproduced the failure (2–8 m, over-extension, 0.5–1.3 m/s velocity error).

**Speaker notes:** fast flights in textured rooms were easy. The hard case is fast + textureless.

---

## Slide 15 — Starved scenes: use the net more, distrust bad tracks

**Visual:** an untextured room frame; a histogram of feature errors (good vs bad tracks).

**Bullets:**
- **HM40:** remove the 12-re-anchor cap and stop down-weighting the net → −8% on hard flights.
- **RSOFT:** 15–24% of accepted features in untextured rooms were > 2 px wrong. Down-weight features that don't fit the recent poses (1/error) → −10 to −12%.
- **What failed:** every form of "add uncertainty", hard rejection, a bigger fuel budget (8–16 M bought only 6–9%).

**Speaker notes:** rejection starves the filter. Soft weighting keeps the information but limits the damage.

---

## Slide 16 — Breakthrough: walls are straight (GSLM)

**Visual:** a frame with detected 3-D lines. Vertical lines in one colour, horizontal lines snapped to two axes in another.

**Bullets:**
- The diagnosis: tilt drifted 2–10° on starved flights, leaking gravity into velocity.
- Untextured rooms still have long straight edges, so track them as 3-D lines (0.1 px accurate against the true poses).
- **Manhattan constraints:**
  - vertical lines → exact vertical → direct tilt information
  - horizontal lines → snapped to the room's axes → direct heading information
- Holdout 0.49 → **0.38 m** (−0.11, CI −0.17 to −0.05); hard flights −31%. Fuel ~7 M.

**Speaker notes:** the biggest single gain since the learned net, and it came from looking at what the images actually contain.

---

## Slide 17 — Periodic learned velocity (GSLV)

**Visual:** a line chart of net error vs filter error, binned by filter error. The net is 2× better where the filter fails.

**Bullets:**
- The net is worse than the filter on average, but much better where the filter has failed, and its errors decorrelate within ~1 s.
- So re-anchor every 0.5 s with a wide uncertainty; clamp the gyro bias to the physical range; retrain the net on 700 fast flights.
- −5 to −12% on hard flights, holdout tie (0.379), worst flight 6.7 → 4.9 m.

**Speaker notes:** many weak, independent corrections beat a few strong ones.

---

## Slide 18 — The whole journey on one chart

**Visual:** a log-log scatter of every build (peak fuel vs holdout error), connected in order, with server points overlaid. Or the two bar charts from our build chart.

**Bullets:** a ladder of holdout error:

| Stage | Holdout error |
|---|---|
| base | 1.72 |
| G | 1.07 |
| B7 | 0.88 |
| B10 | 0.74 |
| B16 | 0.56 |
| B17 | 0.52 |
| T4uB (at 4 M) | 0.54 |
| HFG | 0.51 |
| RSOFT | 0.49 |
| GSLM | 0.38 |
| GSLV | 0.38 |

- Peak fuel: 22 M → 4 M → 6–7 M.
- Server: 3.22 → 1.24 → 0.78 → 0.95 at 4 M (best score).

**Speaker notes:** the path went down (error) first, then left (fuel), then down again once the remaining failure class was understood.

---

## Slide 19 — What didn't work (and why that mattered)

**Visual:** a grid of crossed-out ideas, each with a one-line reason.

**Bullets:**
- **Reduced rates and resets:** vision at 10/5 Hz; closed-form late re-initialisation; window restarts.
- **Textbook and hand-written fixes:** standard consistency fixes (FEJ/OC), hand-written motion priors, speed limits.
- **Adding uncertainty in any form:** process noise, random walks, Huber, Schmidt.
- **Learned ideas that didn't pay:** a learned gravity net; relocalisation to early keyframes (ceiling only 0.01–0.02 m); a 419 M-fuel displacement net (server 0.99 m).
- **More fuel budget:** a big cost for a small gain.

**Speaker notes:** most ideas failed. The process (diagnose, honest sets, 3 replicates, one-shot holdout) is what let us tell real gains from noise.

---

## Slide 20 — Next steps and takeaways

**Bullets — next:**
- Exact (analytic) line Jacobians to bring GSLV back to ~4 M (≈ +0.2 score points).
- Fix gyro-bias corruption at its root instead of clamping it.
- A long teacher → student training run for a better periodic velocity net.
- Target: server mean below 0.5 m.

**Bullets — takeaways:**
1. **Diagnose first:** find which flights carry the error and why.
2. **Peak fuel is a max:** spread the work, don't just shrink it.
3. **Prefer soft over hard:** down-weight bad data instead of rejecting it.
4. **Use the structure of the world:** straight, vertical walls.
5. **Measure honestly:** your test set may not look like the real one.

**Speaker notes:** close on the server-vs-holdout gap. The biggest wins came after we built a test set that looked like the server's hard cases.

---

### Optional backup slides

- **B1: Preflight checklist** (ABI, imports, causality prefixes, reset, rebuild).
- **B2: Per-episode server table** for each submission.
- **B3: The fuel-only Pareto** (T6 / T4uB / T3u / G24) with area estimates.
- **B4: Glossary** (MSCKF, KLT, ATE, Sim(3), ZNCC, fuel, governor).
