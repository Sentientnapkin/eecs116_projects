# Accuracy floor: can monocular+IMU reach ~0.1 m mean unaligned ATE on ~60 s / ~60 m indoor flights?

Context used throughout: our best is ~0.34 m locally, 0.52 m on a clean holdout and 0.78 m on the 12-episode server set at ~17 M ops/frame. 8 of 12 server episodes are 0.13-0.5 m. On the same server set, full VINS-Mono scores 0.475 m (at 3.4 B fuel/frame) and OpenVINS 0.553 m (3.96 B). The server's cpp_minimal identity-pose baseline scores 4.69 m, which is the RMS distance of the truth from its start. Server flights are ~60 m of path (from project memory files, not a web source).

Research-process caveat: several primary PDFs (DM-VIO, Delmerico & Scaramuzza 2018, the Jetson benchmark) could not be read as text in this session. The UZH-FPV leaderboard renders through JavaScript and returned no rows. Numbers from those sources are either taken from secondary summaries (flagged as such) or listed under Gaps.

## 1. Best published monocular-VIO accuracy vs trajectory length; aligned vs unaligned; who reaches 0.1-0.2 % drift

### Takeaway
On EuRoC (drone, ~40-130 m, high-grade IMU, 752x480), the best monocular-inertial systems reach 0.04-0.11 m RMS ATE. That is roughly 0.05-0.15 % of path length, but **only after an SE(3)/posyaw alignment over the whole trajectory**. The best result (ORB-SLAM3, 0.043 m) also uses map reuse/merging. No published number is unaligned in our sense. On longer TUM-VI indoor runs (300-900 m), the best monocular-inertial systems sit at ~0.05-0.5 % of length, with the very low values only where loop closure fires.

### Cited Findings
- ORB-SLAM3 paper, Table II, EuRoC monocular-inertial RMS ATE (m), averages: MSCKF 0.414, OKVIS 0.231, ROVIO 0.224, VINS-Mono 0.110, VI-DSO 0.089, ORB-SLAM3 **0.043**. ORB-SLAM3 per sequence: MH01 0.062, MH02 0.037, MH03 0.046, MH04 0.075, MH05 0.057, V101 0.049, V102 0.015, V103 0.037, V201 0.042, V202 0.021, V203 0.027 — [ORB-SLAM3, Campos et al. 2021](https://arxiv.org/html/2007.11898v2)
- ORB-SLAM3 mono-inertial average scale error on EuRoC is 0.9 % (per sequence 0.3-2.2 %). VI-DSO's average is 0.7 % — [ORB-SLAM3](https://arxiv.org/html/2007.11898v2)
- ORB-SLAM3 aligns pure monocular with Sim(3) and all other configurations, including mono-inertial, with **SE(3)**. So the EuRoC numbers are aligned, not unaligned — [ORB-SLAM3](https://arxiv.org/html/2007.11898v2)
- ORB-SLAM3 multi-session (map reuse) mono-inertial: MH01-05 0.065 m (VINS-Mono 0.210 m), V101-103 0.040 m, V201-203 0.048 m — [ORB-SLAM3](https://arxiv.org/html/2007.11898v2)
- ORB-SLAM3 TUM-VI mono-inertial RMS ATE: room1-6 0.01-0.04 m (lengths 67-146 m, loop closure possible on all). corridor1/2/5 0.02-0.04 m (~270-322 m, LC). corridor4 0.17 m (114 m, no LC). magistrale4 0.13 m (688 m, LC). magistrale3 4.89 m (566 m, no LC). VINS-Mono on the same sequences: rooms 0.04-0.20 m, corridors 0.25-1.56 m — [ORB-SLAM3 Table III](https://arxiv.org/html/2007.11898v2)
- TUM-VI benchmark paper: ATE is RMSE after an optimal **SE(3)** alignment using all poses with ground truth. On long sequences that means only the start and end segments in the mocap room. Median start-segment ATE is <0.1 m and median end-segment ATE <0.5 m across methods. Room-sequence ATE (m): OKVIS 0.03-0.11, ROVIO 0.05-0.33, VINS 0.04-0.20. 1 s RPE is ~0.012-0.031 m and ~0.4-0.67° — [TUM-VI, Schubert et al. 2018](https://ar5iv.labs.arxiv.org/html/1804.06120)
- DM-VIO (mono-inertial, no loop closure) averages 0.069 m on EuRoC, versus BASALT (stereo-inertial) 0.072, VI-DSO 0.089, VINS-Mono 0.184 and OKVIS 0.231. Its average scale error is 0.6 %. Mean TUM-VI drift: DM-VIO 0.472 %, BASALT 0.939 %, VINS-Mono 1.700 % (**secondary summary, not verified against the paper PDF**) — [visual-slam-roadmap DM-VIO summary](https://raw.githubusercontent.com/changh95/visual-slam-roadmap/main/level-06-vio-vins/dm-vio.md); paper: [DM-VIO, von Stumberg & Cremers 2022](https://arxiv.org/abs/2201.04114)
- The DM-VIO paper notes that some comparison results were taken from another source and are Sim(3)-aligned — [DM-VIO search snippet](https://arxiv.org/pdf/2201.04114)
- Monocular OpenVINS (SLAM features on) averages ~1.445° / 0.079 m ATE on the EuRoC Vicon rooms (V2_03 excluded), the best of the monocular systems compared (**secondary summary**) — [visual-slam-roadmap OpenVINS summary](https://raw.githubusercontent.com/changh95/visual-slam-roadmap/main/level-06-vio-vins/openvins.md)
- UZH-FPV ranks by KITTI-style average relative translation error (%) over sub-trajectories of 40-120 m. Prize thresholds were <5 % and <2 %, which says aggressive drone-racing VIO lives in the percent range, not 0.1 % — [UZH-FPV leaderboard description](https://fpv.ifi.uzh.ch/uzh/2019-2020-uzh-fpv-benchmark/)
- EuRoC-grade IMU vs ours: TUM-VI's BMI160 white noise is gyro 8.0e-5 rad/s/√Hz and accel 1.4e-3 m/s²/√Hz — [TUM-VI](https://ar5iv.labs.arxiv.org/html/1804.06120)

### Inferences
- **0.1 m on a 60 m path is 0.17 % of length, unaligned.** Without map reuse, only the best mono-inertial VIO (DM-VIO, VI-DSO, OpenVINS-mono, ~0.07-0.09 m on EuRoC) gets into that range. They get there with SE(3)/posyaw alignment, which absorbs the initial yaw/position offset and the best-fit rotation. They also use a much better IMU and twice the image resolution.
- Unaligned ATE is usually much larger than aligned ATE for the same run. Alignment removes the constant startup offset and any tilt/yaw gauge error. Our own Sim3 vs unaligned gap on the server (0.233 vs 0.782 mean for B16) shows the same thing.
- Our IMU: if the stated 0.07 rad/s and 0.28 m/s² are per-sample sigmas at 200 Hz, the densities are ~4.9e-3 rad/s/√Hz and ~2.0e-2 m/s²/√Hz. That is ~60x worse gyro and ~14x worse accel than TUM-VI's BMI160 (the EuRoC ADIS16448 is in the same class). If they are densities, it is far worse still. So inertial bridging through textureless or dark stretches will be much weaker than in the published benchmarks.
- "0.1-0.2 % drift" in the literature mostly comes from (a) SE(3)-aligned ATE on short EuRoC runs, or (b) TUM-VI runs where loop closure fired. Pure-VIO TUM-VI long-run drift is ~0.5-1.7 % (DM-VIO, BASALT, VINS-Mono figures above).

### Gaps
- Could not extract the Delmerico & Scaramuzza 2018 tables (PDF not text-readable here). Their per-method EuRoC errors, posyaw alignment details and Up Board/ODROID timings are unverified. Qualitatively, a slide deck says SVO+MSF is the most efficient but least accurate, OKVIS is consistent but low-accuracy, and ROVIO could not run on the Up Board ([Scaramuzza slides](https://udel.edu/~ghuang/iros19-vins-workshop/davide-scaramuzza.pdf), via search snippet).
- No UZH-FPV or Blackbird leaderboard numbers retrieved; the page is dynamically rendered.
- I found no published benchmark that reports **unaligned** ATE in the first-camera frame. All major tables are SE(3), posyaw or Sim(3) aligned.
- I did not confirm EuRoC per-sequence path lengths (commonly ~37-131 m) from a primary source in this session.

## 2. How much do loop closure, map reuse and global BA reduce ATE on indoor ~60 m trajectories? Cheapest forms and cost

### Takeaway
In small indoor spaces that are revisited, loop closure and map reuse cut ATE by roughly 2-10x. Examples: TUM-VI rooms go from 0.04-0.20 m for VINS-Mono to 0.01-0.04 m for ORB-SLAM3; corridors go from 0.25-1.56 m to 0.02-0.31 m. For our unaligned metric, relocalizing against the **first keyframe(s)** is the most valuable form. Position, and the startup offset, is otherwise unobservable forever, and a relocalization against the frame-0 map pins the error back to relocalization accuracy.

### Cited Findings
- VINS-Mono with loop closure has the smallest translation error in its own EuRoC plots. Without loop closure, VINS-Mono and OKVIS are "hard to distinguish" — [VINS-Mono, Qin et al. 2018](https://arxiv.org/pdf/1708.03852) (via search snippet)
- Third-party example: loop closure reduces VINS-Mono error from 0.375 to 0.220 m on EuRoC MH-04, and the gain held on all five sequences tested — [PL-VINS](https://arxiv.org/pdf/2009.07462) (via search snippet)
- ORB-SLAM3 TUM-VI mono-inertial, sequences with loop closure vs without: corridor1/2/5 0.02-0.04 m (LC) vs corridor4 0.17 m (no LC, shorter). magistrale4 0.13 m (LC) vs magistrale3 4.89 m (no LC) — [ORB-SLAM3](https://arxiv.org/html/2007.11898v2)
- ORB-SLAM3 map reuse (multi-session): VINS-Mono 0.210 m vs ORB-SLAM3 0.065 m on MH01-05 (3.2x) — [ORB-SLAM3](https://arxiv.org/html/2007.11898v2)
- Cost (ORB-SLAM3 mono-inertial, EuRoC V202, desktop CPU): tracking 23.2 ± 15.0 ms/frame (IMU integration 0.18 ms). Local mapping 191.5 ± 80.5 ms per keyframe, of which local BA is 121 ms. Map of 332 keyframes / 10,306 points. Place recognition 3.45 ± 2.81 ms, map merge 287 ms. Runs at 30-40 fps with 3-6 keyframes/s — [ORB-SLAM3 Table VI/VII](https://arxiv.org/html/2007.11898v2)
- DM-VIO runtime (2013 MacBook i7, real-time mode): tracking 10.3 ms, keyframe processing 53.7 ms, delayed marginalization 0.44 ms (**secondary summary**) — [roadmap summary](https://raw.githubusercontent.com/changh95/visual-slam-roadmap/main/level-06-vio-vins/dm-vio.md)

### Inferences
- A desktop at ~23 ms/frame is on the order of 10^8-10^9 ops/frame, which fits the server's 3.4-4 B fuel figure for VINS-Mono and OpenVINS. That is 2-3 orders of magnitude above our 17 M budget.
- The cheapest useful form for our metric is "anchor relocalization". Store a few keyframes from the first ~1-3 s, each with ~100-300 binary descriptors (ORB/BRIEF-like, 32 B each) plus triangulated 3D points. When a later frame matches enough of them, do one PnP/RANSAC (or a single EKF update with those landmarks as fixed map points) to fix position and yaw relative to the origin.
- Rough cost of matching 300x300 descriptors by brute force: ~90 k Hamming distances ≈ 0.2-0.5 M ops. P3P+RANSAC with ~50 iterations adds ~0.1 M. Doing it every N frames fits easily in a 1-17 M budget. This estimate is my own, not from a source.
- The gain applies only if flights re-observe the start area. A 60 s, 60 m indoor flight with ~4.7 m RMS extent almost certainly revisits the same room. A pose-graph correction smooths the error from that point on, but **per-frame causal output cannot fix frames already emitted**, so the benefit is bounded by how early the first revisit occurs.
- Global BA buys little over a good sliding window on 60 s flights. The main driver is re-observing old landmarks (map reuse), not re-optimising.

### Gaps
- No source quantifies loop closure's ATE reduction specifically on ~60 m, ~60 s drone flights with unaligned evaluation.
- No documented compute figure for a minimal keyframe-relocalization module on embedded hardware was found.

## 3. Error-budget arithmetic for the unaligned metric (initial attitude, velocity, unobservable yaw)

### Takeaway
In the camera-0 frame, yaw and position at t=0 are **zero by definition**, so there is no initial yaw error. The things that count fully are:
- **gravity direction (roll/pitch) in camera-0**: about 0.08 m per degree of error, at ~4.7 m RMS extent
- **velocity error during the startup transient**: integrates into a permanent position offset
- **yaw drift**: gauge-free in VIO, about 0.04-0.08 m per degree accumulated
- **scale error**: about 0.05 m per 1 %

Reaching 0.1 m needs every one of these held to roughly 0.03-0.05 m. That is plausible on static starts and very hard on mid-motion starts without an anchor relocalization.

### Cited Findings
- VIO has four unobservable directions (global position and yaw about gravity). Relative pose is observable only through vision. Divergence is declared at >2 m end-segment ATE on TUM-VI, where median end-segment ATE was <0.5 m after hundreds of metres — [TUM-VI](https://ar5iv.labs.arxiv.org/html/1804.06120)
- Typical good VIO rotation drift: 1 s RPE of 0.4-0.67° on TUM-VI (mostly per-frame noise, not cumulative yaw) — [TUM-VI Table III](https://ar5iv.labs.arxiv.org/html/1804.06120)
- Our server extent anchor: identity-pose RMS distance of the truth from its start is 4.69 m (project memory, server_baseline_anchors).

### Inferences (my own arithmetic; noise assumed per-sample at 200 Hz)
- **Gyro angle random walk** (IMU only): σ_g = 0.07/√200 ≈ 4.95e-3 rad/√s, giving 0.038 rad ≈ 2.2° after 60 s and ~0.7° after 6 s. While landmarks are tracked, vision bounds relative rotation, so yaw drift accrues only across feature-handover gaps such as textureless or dark stretches.
- **Yaw drift → position**: a yaw error δψ acquired at time t rotates every later displacement about the vertical. In a ~5 m-extent room flight, position error is ≈ δψ × (distance from the rotation point), at most ~δψ × 2 × extent. Linear growth to 1° by 60 s therefore gives ~0.04 m RMS and ~0.09 m worst case. To stay <0.03 m RMS, cumulative yaw drift must be ≲0.5-0.7° over 60 s. That is roughly what the IMU alone gives in 6-10 s, so yaw must come almost entirely from vision, or be re-anchored by relocalization to frame-0 landmarks.
- **Roll/pitch (gravity direction) in camera-0**: if the output is rotated by δθ relative to truth, error ≈ δθ × r. With r_RMS ≈ 4.7 m, 1° gives 0.08 m and 0.5° gives 0.04 m.
  - Static start: averaging 1 s of accelerometer data gives σ = 0.28/√200 / 9.81 ≈ 0.002 rad ≈ 0.12° of tilt (bias aside), contributing ≈ 0.01 m.
  - Mid-motion start: the specific force contains unknown acceleration (planner MAX_ACC 0.7 m/s² → up to ~4° tilt ambiguity), which must be resolved by visual-inertial initialization. A 2° residual costs ~0.16 m by itself.
- **Initial velocity**: position is unobservable, so a velocity error δv0 that decays with time constant τ leaves a permanent offset ≈ δv0·τ. With τ ≈ 2 s (typical VI-init convergence), 0.05 m/s gives 0.1 m. So 0.1 m total needs |δv0| ≲ 0.02 m/s, or τ ≲ 1 s at 0.05 m/s.
  - Static start: δv0 = 0 exactly (zero-velocity prior), so this term vanishes.
  - Mid-motion start: this is the dominant term, consistent with our pool, where static starts score 0.82 vs mid-flight 3.58 for the older gp_msckf build.
- **Accelerometer white noise** (if uncorrected by vision): velocity random walk 0.28/√200 ≈ 0.0198 m/s/√s gives position error ≈ 0.0198·t^1.5/√3, about 0.035 m at 3 s and 0.36 m at 10 s. So textureless stretches longer than ~3 s cost ≥3-4 cm each, unless bounded by priors (controller model, see §4).
- **Scale**: the best mono-inertial scale error is 0.6-0.9 % on EuRoC (DM-VIO, ORB-SLAM3), which gives ≈0.03-0.04 m at r_RMS 4.7 m. With our ~14x worse accelerometer and 320x240 images, expect 1-3 % unless flights excite enough acceleration. At 2 %, scale alone costs ~0.09 m.
- **Combined budget, root-sum-square, static start, good texture**: tilt 0.01 + velocity 0 + yaw drift 0.03-0.04 + scale 0.04-0.09 + local VO noise/handover 0.02-0.05 gives ≈ **0.06-0.12 m**. So 0.1 m is at the edge of feasibility for clean static-start episodes.
- **Mid-motion starts**: add tilt 0.05-0.15 and velocity offset 0.05-0.2, giving ≈ **0.15-0.3 m** unless the startup error is later removed by relocalizing to frame-0 landmarks.
- **Textureless/dark segments**: dead reckoning with this IMU adds ~0.03-0.4 m depending on gap length (3-10 s).
- **Is 0.1 m achievable without an absolute heading reference?** In this metric yaw is relative to camera 0, so the frame-0 view **is** the heading reference. Re-observing the frame-0 scene gives absolute yaw and position for free. Without such revisits, yaw drift alone probably sets a ~0.03-0.08 m floor over 60 s with this gyro.

### Gaps
- Whether the IMU noise figures are per-sample or density values is not confirmed; all arithmetic assumes per-sample at 200 Hz.
- No literature source gives unaligned-ATE error budgets for VIO initialization. The figures above are first-order derivations, not measured.

## 4. Is the remaining error scale/depth or attitude? Which simulator facts lower the floor?

### Takeaway
For aligned benchmarks the residual is mostly scale (~0.5-1 %) plus local drift. For **unaligned** ATE on our flights, the startup terms (tilt and velocity offset, locked in) and yaw drift dominate. Our own data supports this: the server shows Sim3 0.233 vs unaligned 0.782, meaning most of the error is a rigid or similarity transform, i.e. gauge and startup error, not trajectory shape. The simulator facts to exploit are those that sharpen startup and bound drift.

### Cited Findings
- On EuRoC, mono-inertial scale error averages 0.9 % (ORB-SLAM3) and 0.7 % (VI-DSO); ATE remains 0.04-0.09 m — [ORB-SLAM3](https://arxiv.org/html/2007.11898v2)
- Our B16 server result: 0.782 m unaligned mean vs 0.233 m Sim3 mean; 4 episodes carry 79 % of the total (project memory, server_baseline_anchors).
- The default planner draws cruise speed 0.45-0.8 m/s, MAX_ACC 0.7 and MAX_JERK 2.0. Server flights are ~1 m/s (project memory, server_flight_distribution).

### Inferences
- Unaligned minus Sim3 (≈0.55 m of our 0.78 m server mean) is error removable by one global similarity: startup offset, tilt, yaw, scale. **This is the biggest lever and is fixed by startup accuracy plus frame-0 relocalization, not by better local VO.**
- Simulator-exploitable facts:
  1. **Exact IMU noise and (probably) zero or known bias**: tighter filter tuning, and bias states can be dropped or strongly constrained, which reduces scale/tilt ambiguity.
  2. **Exact gravity magnitude** (9.81, known): removes one VI-init unknown and makes scale observable sooner.
  3. **Exact intrinsics and extrinsics, no distortion and no time offset**: no online calibration, so subpixel feature noise is the only vision error.
  4. **Controller/planner model** (bounded jerk 2 m/s³, accel 0.7 m/s²): a smooth-motion prior on velocity/acceleration (jerk-limited process model) can replace much of the IMU noise between frames and bound dead reckoning in textureless gaps.
  5. **Static vs mid-motion start detection**: zero-velocity prior and accelerometer tilt averaging on static starts give ~0.01 m error terms.
  6. **Flat-floor / known-altitude structure, if present in the sim scenes**: constrains depth and scale. Unverified for this simulator.
  7. **Deterministic renderer**: photometric (direct) alignment works better than on real cameras, with no exposure changes or rolling shutter, except in dark areas.
- Attitude (roll/pitch) is well observed after init via gravity. The residual attitude contribution is mainly the frame-0 tilt estimate on mid-motion starts.

### Gaps
- No published study isolates the gain from these simulator-only priors. The size of each gain is my estimate.

## 5. Cheapest documented system at ≤0.2 % drift

### Takeaway
No documented monocular-inertial system reaching ~0.1-0.2 % drift (aligned) runs anywhere near 17 M ops/frame. The documented ones (DM-VIO, VI-DSO, ORB-SLAM3, OpenVINS, VINS-Mono) need ~10-25 ms of desktop CPU per frame plus a 50-200 ms keyframe/BA thread. That is roughly 10^8-10^9 ops/frame, consistent with the server's 3.4-4.0 B fuel for VINS-Mono/OpenVINS. Even those full systems score only 0.475-0.553 m unaligned on the server set.

### Cited Findings
- ORB-SLAM3 mono-inertial: 23 ms tracking and 191 ms per keyframe for local mapping on a desktop — [ORB-SLAM3](https://arxiv.org/html/2007.11898v2)
- DM-VIO: 10.3 ms tracking and 53.7 ms per keyframe (2013 MacBook, **secondary**) — [roadmap summary](https://raw.githubusercontent.com/changh95/visual-slam-roadmap/main/level-06-vio-vins/dm-vio.md)
- Delmerico & Scaramuzza: SVO+MSF was the most efficient but least accurate. ROVIO had tight resource bounds and competitive accuracy but could not run on the Up Board (slides via snippet) — [Scaramuzza slides](https://udel.edu/~ghuang/iros19-vins-workshop/davide-scaramuzza.pdf)
- Server: VINS-Mono 0.475 m at 3.40 B fuel/frame; OpenVINS 0.553 m at 3.96 B (project memory, server_baseline_anchors).

### Inferences
- **Feasibility verdict**: 0.1 m mean unaligned ATE over 12 server-like episodes is not supported by any published evidence at any compute budget. Classic VINS-Mono/OpenVINS land at ~0.5 m on this exact server set, and the best literature numbers are aligned, use a ~15-60x better IMU and 2x the resolution.
- **Realistic floor**: clean static-start, textured episodes can plausibly reach ~0.06-0.12 m; our best server episodes are already 0.13 m. Mid-motion starts and textureless gaps put the realistic **mean** floor at ~0.2-0.3 m. The precondition is getting the tail episodes (currently 0.9-2.4 m) down to ~0.3 m.
- **Mechanisms needed to approach 0.1 m, in order of expected payoff for the unaligned metric**:
  1. Tail control: detect and recover from failures; the tails carry 79 % of the current error.
  2. Frame-0 anchor relocalization (cheap descriptor matching + PnP against stored startup keyframes) to cancel startup offset and yaw drift.
  3. Better mid-motion initialization: tilt and velocity in <1 s, using known gravity and exact noise.
  4. A jerk-limited motion prior to bound dead reckoning in dark or textureless stretches.
  5. Scale accuracy under 1 %, from longer feature tracks and more IMU excitation.
  6. Only then, a better local VO front end.
- Per-frame compute for items 1-4 is small, estimated <5 M ops/frame. That is compatible with a ~1-17 M budget; the estimate is my own.

### Gaps
- No source documents a sub-10 M-ops/frame monocular VIO with published ATE. Cheap-system benchmarks (Delmerico 2018, the Jetson benchmark [arXiv 2103.01655](https://arxiv.org/abs/2103.01655)) were not readable in this session.
