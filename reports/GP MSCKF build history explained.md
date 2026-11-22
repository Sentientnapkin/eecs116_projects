# GP + MSCKF build history, explained

Date: 2026-11-22. Covers every GP + MSCKF build we scored on the clean 240-flight holdout, in the order they were made, plus the fuel-only rewrites and the main things that failed. Holdout = 240 simulated flights in scenes and seeds no tuning ever saw, each build scored once. Server = the course's 12 private episodes (we have only the scores, never the data). "Peak fuel" = the most expensive single frame, which is what the score uses. ATE = mean unaligned position error in metres.

Rule of thumb for the score: halving peak fuel is worth about +0.28 points; cutting ATE by 10% is worth about +0.24. The server has scored 1.4–1.85× worse than our holdout, because it has more fast flights in untextured rooms.

---

## How the estimator works (background for everything below)

The drone has one forward camera (20 frames/s) and an IMU (gyroscope + accelerometer, 200 samples/s). Every frame the estimator must output its pose.

- **IMU propagation.** Between frames the filter integrates the gyro (rotation) and accelerometer (acceleration, minus gravity) to predict where the drone moved. This drifts fast, because small sensor biases integrate into big errors.
- **MSCKF (Multi-State Constraint Kalman Filter).** The filter keeps a short window of past camera poses ("clones"). A feature tracked across several frames is triangulated, and how well its predicted image positions match the observed ones corrects the poses, velocity and biases. Features themselves are not kept in the state, which keeps it cheap.
- **GP bias model.** The gyro and accelerometer biases are modelled as a smoothly varying Gaussian process rather than a pure random walk.
- **KLT front end.** Corners are detected in a grid of image cells and tracked frame to frame with Lucas–Kanade optical flow.
- **The core weakness.** The simulator has no rotor drag, so the accelerometer tells you nothing about velocity (it only sees thrust and gravity). Velocity therefore comes only from vision. When the camera sees little texture, or the drone starts mid-flight with an unknown velocity, the filter has nothing to anchor velocity and position drifts. Almost every improvement below attacks this from a different angle.

---

## 1. base gp_msckf — holdout 1.724 m, ~22.5 M fuel, server 3.22 m @ 19.5 M

The starting point: the MSCKF + GP-bias filter with KLT corner tracking, started from zero velocity with a large uncertainty (1 m/s).

**Problem found:** on flights that start already moving (mid-flight starts) it locked in a large position offset within the first 2–5 s and never recovered. On the local pool, static starts averaged 0.82 m but mid starts 3.58 m, and 20 of the 22 flights above 5 m were mid starts. On the server, three episodes at 7.97–11.3 m carried ~72% of the total error. Those tails were over-extension (estimated trajectory too large, Sim(3) scale < 1) after a wrong startup velocity.

## 2. G — startup gate + heading prior — holdout 1.069 m, 20.9 M, server 1.244 m

**What it added:** a **startup gate** that decides from the first IMU samples whether the drone is moving (force and gyro magnitude), and a **heading prior**: if moving, assume it flies forward (along the camera axis) at a typical speed rather than at zero.

**Why it helped:** most mid-flight starts really are flying forward, so the filter starts close to the right velocity instead of zero. Holdout fell from 1.72 to 1.07 m.

**What went wrong:** on the server, episode e7aa5aee got worse (0.92 → 7.70 m). The forward-speed prior overstated a slow or ambiguous start and the scale locked 1.75× too high. The prior is a guess, and when the guess is wrong it does damage.

## 3. G+C1 — hover-hold, vertical and lateral priors — holdout 0.972 m, ~21 M

**What it added (C1 = three "inventive" priors):**
- **INV_HOLD:** on static (hover) starts, use the first ~1 s while the drone is known to be still to estimate the gyro and accelerometer biases and the gravity direction. This gives a much better starting attitude and bias.
- **INV_VZ = 0.3:** a weak prior that vertical velocity is small (drones mostly fly level).
- **INV_LAT = 0.5:** a weak prior that sideways velocity in the body frame is small (quadrotors mostly fly where they point).

**Why it helped:** these are cheap pseudo-measurements that constrain velocity directions the camera observes poorly. Fresh flights went from 0.813 to 0.733 m, and flights over 5 m from 17 to 8.

## 4. B7 — forward-backward tracking check + exact fuel rewrite — holdout 0.882 m, ~12 M

**What it added:**
- **Forward-backward KLT check:** each track is also tracked backwards from the new frame to the old one; if it doesn't land within 0.5 px of where it started, the track is dropped. Run on alternate frames to save fuel. It drops about 10% of tracks, mostly drifting ones on edges or repetitive texture. Fresh 0.733 → 0.618.
- **Exact fuel rewrite:** the same arithmetic reorganised (fewer copies, cheaper loops) so outputs are bit-identical but peak fuel fell from ~21–24 M to 11–12 M. This was our first big fuel cut with zero accuracy cost.

## 5. B10 / B11 — learned startup-velocity net — holdout 0.738 m, 12.6 M

**What it added:** a small convolutional neural net (64×48 grey images, ~105 k parameters, ~1.7 M multiply-adds) written in plain C. At frame 5 it looks at the change between frame 0 and frame 5 (rotation removed using the gyro) and predicts the drone's 3-D velocity plus an uncertainty. The prediction is injected into the filter at frame 6 as a velocity measurement, replacing the hand-written heading prior.

**Why it helped:** it learned the actual start direction and speed from image motion, including starts that aren't forward. Mid starts improved most (0.98 vs 1.26). It was trained on our own simulated flights, folds 0–2 only. B10 = on the B6 code; B11 = the same net on the exact (cheaper) B7 code, with identical outputs.

## 6. B15 — pv25 net re-anchor — holdout 0.652 m, 15.8 M

**What it added:** the "pv25" monitor. After 1.5 s, if the filter's velocity uncertainty (square root of the velocity covariance trace) grows above 0.25 m/s, which happens when vision is weak, it re-runs the learned net on recent frames and applies its velocity again (a "re-anchor").

**Why it helped:** it stops velocity runaways when tracks die later in the flight. Mostly a tail fix: holdout flights over 3 m fell from 8 to 5. It cost about 23% more fuel for the extra net runs.

## 7. B13 — iterated update + loop-closure-lite map — holdout 0.619 m, 20.2 M

**What it added:**
- **Iterated update (ITER):** after the normal Kalman update, re-linearise the measurement equations at the new estimate and update once more, if the first update moved the state a lot. This reduces linearisation error when the state was far off.
- **Map ("loop-closure-lite"):** keep a small store of well-triangulated 3-D points with image patches. When the drone looks at an old area again, match those patches (ZNCC correlation) and use the old points as measurements. This pulls the trajectory back towards where it was before.

**Why it helped:** better ordinary accuracy (the median flight), complementary to B15's tail fix. Fuel went up because of the second iteration and the map matching.

## 8. B16 — B13 + pv25 — holdout 0.564 m, 20.2 M, server 0.782 m @ 17.0 M

**What it was:** B13's accuracy plus B15's tail control. Best on every set at that point, with only 3 holdout flights over 3 m.

**Server:** 0.782 m, and e7aa5aee was fixed (7.70 → 0.50). But four episodes (2.22, 2.44, 1.83, 0.93 m) carried 79% of the total, all with rigid offsets and velocity errors of 0.5–0.6 m/s.

## 9. B17 — late-init fixes — holdout 0.521 m (b17_exact: same outputs at 16.1 M)

**Diagnosis first:** removing the best rigid shift from each flight's error dropped mean error from 0.40 to 0.26 m. So the remaining error was an offset accumulated mostly **after 5 s**, in stretches with little to track. Startup itself was worth only 0.03–0.06 m.

**Two bugs fixed:**
- **LI_GATENET = 0.2:** the movement gate sometimes declared a moving start "still" at 0.4 s and forced a zero-velocity update, even when the net said ~0.45 m/s (in distant scenes there is little image motion). This tilted the attitude by 14–22°. Now the net's speed can veto the zero-velocity decision.
- **LI_PVS = 1:** pv25 only fired on starts classified as moving, so static starts that later lost vision never got re-anchored, even though their velocity uncertainty was above the threshold 57–95% of the time. Now it can fire on static starts after 3 s.

**b17_exact:** the fuel-rewritten version (vectorised QR decomposition and solves) with bit-identical outputs at 16.1 M instead of 20 M.

## 10. T4uB — the low-fuel build — holdout 0.540 m, 4.1 M

The "go left on the graph" build: B17's logic at a quarter of the fuel.

**What made it cheap:**
- **Integer SIMD KLT:** the tracker rewritten with 16-byte integer vector instructions (wasm SIMD128), about 8× cheaper and slightly more accurate.
- **Exact integer SIMD ZNCC:** the map's patch matching vectorised, 3× cheaper with identical poses.
- **Per-frame budget governor:** every optional job (filter rows, net steps, map matching, the second iteration) reports its cost, and the governor fits them under a 3.6 M budget per frame, deferring the rest to later frames. Peak fuel is the maximum over frames, so flattening spikes is what matters.
- **Chunked startup net:** the net's forward pass split into micro-steps spread over several frames (matches the unsplit net to 3 decimals).
- **Smaller tweaks:** track pruning, plus a higher per-frame cap on net steps so the net lands by about frame 8.

**Result:** about B16's accuracy at a fifth of the fuel.

## 11. HFG — hardening, exact reuse, gate removed — holdout 0.512 m, 4.0 M, **server 0.948 m @ 4.0 M (current best score, area 4.54%)**

Named after its three switches:
- **H = HARDEN:** an IMU sanitiser (drops non-finite, time-reversed, physically impossible or spiky samples), a watchdog that restores the last good state if the filter produces NaN or absurd values, and an output guard that never emits an invalid pose. It is identical on normal data. Before it, a single NaN in the IMU stream failed the whole episode; IMU spikes caused 10 m errors.
- **F = F_REUSE:** on the 93% of updates where the second iteration doesn't run, the update reuses the matrix products and Cholesky factor already computed. Identical outputs, lower mean fuel.
- **G = GATE_MODE = 0:** the startup movement gate removed entirely. With the net and the B17 fixes, the gate was now doing more harm than good: fresh 0.381 → 0.364 over 3 reps, with fewer tails.

**Server:** best score yet, but three episodes (3.46, 2.69, 2.28 m) carried 74% of the error. Two of them were worse than with B16. The server/holdout ratio rose to 1.85.

## 12. HM40 — more net re-anchors — holdout 0.494 m, 4.0 M

**Diagnosis:** we built a server-like test set, "st2": 240 fast flights in the 20 hardest untextured ProcTHOR scenes. It reproduced the server's bad-episode signature (2–8 m errors, velocity error 0.5–1.3 m/s, over-extension). Long fast flights in textured scenes were easy. Mechanism: corners die, velocity is unobserved, and the net re-anchor, the only other velocity source, stopped after its cap of 12 uses.

**What it changed (m40s1):** TC_MAXANCH = 40 (effectively unlimited, since re-anchors are already 30+ frames apart) and TC_RE_SCALE = 1.0 (apply the net's velocity at its own uncertainty instead of an inflated one).

**Result:** st2 dev −8%, flights over 3 m roughly halved, holdout flights over 3 m from 4 to 1. The 16 M B17 build fails on the same st2 flights, so this was not a fuel problem.

## 13. RSOFT — soft down-weighting of bad features — holdout 0.491 m, 4.0 M

**Diagnosis:** re-triangulating features with the true poses showed 15–24% of the features the filter accepted on untextured flights were more than 2 px wrong (2–5% on textured flights). They passed the outlier (chi-square) test because the filter was so uncertain that almost anything looked plausible.

**What it changed:** after triangulation, compute each feature's reprojection error against the current clone poses. If it is above 1 px, scale the feature's influence down by 1/error. Nothing is rejected outright: hard rejection starved the filter and made everything worse.

**Result:** st2 −10% / −12%, fresh dev −10%; a tie on the holdout, which has few such flights.

**What failed in the same round:** process-noise inflation, velocity or tilt random walks, Huber weighting, Schmidt (consider) states. Every form of adding uncertainty hurt. A bigger fuel budget (8–16 M) bought only 6–9%, which isn't worth the fuel.

## 14. GSLM — 3-D lines + Manhattan constraints — holdout 0.382 m, ~7.4 M

The biggest single gain since the startup net.

**Diagnosis:** on starved flights the estimated **tilt** drifted, 2–10°. A tilt error makes the filter subtract gravity in slightly the wrong direction, which looks like a horizontal acceleration of about g × tilt and drives velocity off. Starved ProcTHOR frames contain only 6–10 corner cells, but plenty of long straight wall edges.

**What it added:**
- **3-D line features:** straight image edges are tracked and triangulated as 3-D lines, used in the MSCKF like points. Checked against the true poses, they are very accurate: 0.1 px median, none above 2 px. An earlier "edgelet" attempt (short edge pieces) slid along edges and gave 1–3 px errors.
- **Manhattan constraints:** in these indoor scenes walls are vertical and aligned to two horizontal axes (checked with true poses: vertical lines fit exactly vertical at about 0.1 px, horizontal ones cluster within about 1° of the scene axes). So near-vertical lines are forced exactly vertical, which gives the filter **direct tilt information**. Near-horizontal lines are forced horizontal and snapped to a heading learned from the first 15, which gives **direct heading information** (rotation error 0.068 → 0.046 rad).
- **KLT_VEL:** each track starts its search at the IMU-predicted position plus its own last motion. Free in fuel, and a big help on fast flights.
- **Built on RSOFT, with pixel noise tightened to 0.3.**

**Result:** st2 −31% / −32%, fresh −25% / −19%, holdout 0.491 → 0.382 (−0.109, interval −0.166 to −0.051). Fuel rose to about 7 M because the line Jacobians are computed numerically (12 extra residual evaluations per observation).

## 15. GSLV — periodic learned velocity + bias clamp — holdout 0.379 m, ~6–7.4 M (recommended, not yet submitted)

**Diagnosis:**
- **Net vs filter:** the net's velocity is worse than the filter's on average (0.255 vs 0.147 m/s), but about twice as good exactly where the filter has failed (0.42 vs 0.82 m/s when the filter is off by more than 0.5). Its errors become independent within about 1 s.
- **Bias corruption:** on the worst flights the gyro-bias estimate was pushed to 0.038 rad/s, beyond the simulator's ±0.02 range, mostly by vision updates built from very few features. That created the tilt runaway.

**What it added:**
- **Periodic re-anchor:** every 10 frames (0.5 s) apply the net's velocity with 3× its stated uncertainty. Its errors are independent, so frequent weak updates average out.
- **Gyro-bias clamp:** keep the bias estimate within ±0.021 rad/s.
- **New net (v700b):** retrained on 700 more fast flights with a loss that calibrates its uncertainty (beta-NLL). It underestimates speed less at speed: the speed scale went from 0.74 to 0.81, and error above 2 m/s from 0.69 to 0.55 m/s.

**Result:** better than GSLM on every server-like set (−5 to −12%), tied on the holdout (0.379 vs 0.382), worst holdout flight 4.9 m instead of 6.7 m. Estimated server: roughly 0.55–0.65 m.

---

## Fuel-only work (accuracy held)

| build | what | fresh ATE | peak |
|---|---|---|---|
| B5 / B7 exact | arithmetic reorganised, bit-identical | same | 23 → 11–12 M |
| b16_exact / b17_exact | vectorised QR + solves, bit-identical | same | 20.2 → 16.1 M |
| T6 / T4uB / T3u | governor budgets 5.6 / 3.6 / 2.9 M | 0.387 / 0.381 / 0.400 | 6.0 / 4.1 / 3.2 M |
| T2b / T1v | too aggressive | 0.492 / 1.11 | 2.4 / 1.2 M |
| G24 (not preflighted) | float32 SIMD products, cheaper outlier test, measured net step costs, budget-gated 2nd iteration | 0.390 | 2.7 M |
| G27m (not preflighted) | the same on HM40 | ≈ HM40 | 3.0–3.5 M |

Below about 3 M, two things block us: each filter measurement row costs about 100 k instructions, and the startup net must finish within 2–3 frames of frame 5.

## Tried and rejected (main ones)

- **Vision at 10 Hz or 5 Hz:** large ATE loss.
- **Closed-form late initialisation:** +0.14 m and 37 M peak.
- **Window restart and retroactive clone shift.**
- **FEJ / observability-constrained filtering:** the standard consistency fixes, neutral or destructive here.
- **Rotor-drag measurements:** the simulator has no drag.
- **Hand-written dynamics priors and limits:** coordinated turns, speed limits, containment radius. All neutral or worse.
- **Adding uncertainty in any form:** process noise, random walks, Huber, Schmidt, tilt-noise boost.
- **Hard rejection of bad features or net updates:** starves the filter.
- **Relocalisation against early keyframes:** its best case was worth only 0.01–0.02 m.
- **A learned gravity-direction net:** 2.5° error, worse than the filter's normal 1°.
- **Edgelets alone:** they slide along edges. Full 3-D lines worked instead.
- **Bigger fuel budgets (8–16 M):** 6–9% gain, not worth the fuel.
- **Teammate's displacement student:** server 0.992 m at 419 M.
- **Teammate's startup students:** better net on its own, a tie inside the filter.

## What is next

1. **Analytic line Jacobians:** bring GSLV back to about 4 M (worth about +0.2 points).
2. **Fix the gyro-bias corruption at its root** instead of clamping it.
3. **A better periodic velocity net:** long teacher → student training on thousands of fast, untextured flights.

The plan for 1 and 2 is in `reports/Plan line Jacobians and gyro bias.md`.
