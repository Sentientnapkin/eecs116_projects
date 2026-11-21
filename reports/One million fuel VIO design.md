# One million fuel fits; 0.1 m does not

A ~1 M peak-fuel build is reachable from our current code, but only if two problems are solved first: the startup net must land by about frame 8 instead of frame 45-80, and each MSCKF row must cost about 3x less than its current ~105 k instructions. ATE near 0.1 m is not reachable at any fuel level. No published monocular-inertial system reports anything close under an unaligned metric. Full VINS-Mono and OpenVINS score 0.475 m and 0.553 m on this exact server set at 3.4-4 B fuel. Our own diagnosis says the remaining error is translation drift built up while vision is starved, which more compute does not fix. The realistic target is a server mean of roughly 0.4-0.5 m at 1-4 M fuel. Scoring makes the trade concrete. Cutting peak fuel from 17 M to 1 M at constant ATE is worth about the same as cutting ATE by 40% at constant fuel. A 1 M build therefore beats B16 only if local fresh ATE stays below about 0.59 m, and beats our measured 4 M build (T4uB) only below about 0.49 m. The next steps, in order: lock in T4uB as the low-fuel submission; fix startup-net latency; make MSCKF rows cheaper; then spend the freed budget on cheap gradient and flow measurements for starved stretches. Only after that, test a tiny learned motion prior, and only once it passes an offline falsification test.

## A 1 M build is worth about a 40% ATE cut, and no more

The score is a log-log area. Our working conversion, calibrated against the B16 server point, gives **+0.28 points per halving of peak fuel and −0.5 points per 20% ATE increase**, written as points = 0.28·log2(17/peak) − 2.24·ln(ATE/0.354) ([tier1m NOTES](../research/single_model/tier1m/NOTES.md)). Going from 17 M to 1 M is about four halvings, or **+1.14 points**. That equals a 40% ATE cut at fixed fuel. Halving ATE would be worth +1.55 points, more than the whole fuel descent. Accuracy is therefore still the steeper lever per unit of improvement. Fuel became the focus only because ATE gains got hard to find ([LOOP_LOG](../research/single_model/LOOP_LOG.md)). The fuel agent's result follows from this: **a fuel halving pays only if ATE rises by less than about 11%** ([fuel_b13 NOTES](../research/single_model/fuel_b13/NOTES.md)).

The measured Pareto points show where we stand. Local fresh-711 ATE converts to server ATE at roughly 2.2x for B16 (0.354 fresh → 0.782 server). The clean holdout sits in between (B17: 0.337 fresh, 0.521 holdout). Server peak fuel runs about 15% below local fresh peak (B16: 20.17 M locally, 17.0 M on the server) ([LOOP_LOG](../research/single_model/LOOP_LOG.md)).

| Build | Local fresh peak | Fresh-711 mean ATE | Est. points vs B16 | Status |
|---|---|---|---|---|
| B16 (server 0.782 m @ 17.0 M) | 20.17 M | 0.354 | 0 | submitted |
| b17_exact (bit-identical to B17) | 16.09 M | 0.337 | +0.13 | preflight pass |
| T6 (governor 5.6 M) | 5.97 M | 0.387 (3 reps) | +0.22 | preflight pass |
| **T4uB (governor 3.6 M + B17 switches)** | **4.00 M** | **0.383 (2 reps)** | **+0.41** | preflight running |
| T3 (governor 2.7 M) | 2.96 M | 0.410 | +0.38 | 1 rep |
| T2b (governor 2.0 M, 1 iteration) | 2.41 M | 0.492 | +0.05 | 1 rep |
| T1v (governor 0.9 M, 10 Hz vision) | 1.20 M | 1.106 | −1.48 | rejected |

Sources: [tier1m NOTES](../research/single_model/tier1m/NOTES.md) and [tier1m runner log](../research/single_model/tier1m/logs/runner.txt); points are computed with the formula above.

Two conclusions follow. First, **T4uB is already the best area point we have**: about 0.38 fresh at 4.0 M, which projects to a server ATE around 0.85 m at ~3.4 M. That should beat the teammate's 0.89 m at 7.3 M. Second, the area curve is nearly flat from 4 M down to 3 M and then falls off a cliff. That shape means the governor is starving something essential below ~3 M, not that small builds are inherently inaccurate. Using the same formula, **a 1 M build needs fresh ATE ≤ 0.49 to beat T4uB and ≤ 0.59 to beat B16**. A 2 M build needs ≤ 0.43 to beat T4uB.

## Below 3 M the build fails on net latency and MSCKF row cost, not front-end cost

The front end is no longer the main cost. The integer SIMD KLT cut tracking from 2.85 M to 0.36 M per frame, and it also improved ATE (fresh 0.330 vs 0.354). An integer ZNCC dropped map-relocalization spikes from 4 M to 0.7 M with bit-identical poses. A SIMD pyramid took the 3-level pyramid from 1.29 M to 0.32 M ([tier1m NOTES](../research/single_model/tier1m/NOTES.md), [fuel_b13 NOTES](../research/single_model/fuel_b13/NOTES.md)). After those changes, the median frame of the "ki" build costs 3.4 M. The largest remaining items are detection at 1.1 M (empty cells rescored every frame), the EKF update at 0.72 M, the pyramid at 0.50 M, the KLT at 0.36 M and map relocalization at 0.26 M. Peaks occur at frame 0, at the net frames 5/6 and at the window slides ([tier1m profile](../research/single_model/tier1m/prof/an_ki.txt)). Detection is already cheap when stride and cool-down are used: DET_STRIDE=4 and DET_COOL=8 were neutral. The only detection change that hurt was a hard budget of 3 cells per frame, at +0.095 ([tier1m NOTES](../research/single_model/tier1m/NOTES.md)).

**The first blocker is startup-net latency.** Under a 0.9 M governor, the net's post-K work only lands around frame 45-80. Its cost is about 8.5 M in total: preprocessing 3.07 M (2.01 M after the f32x4 derotation), then convolutions of 1.21, 1.88, 0.84 and 0.35 M, and a 0.40 M head. The arithmetic is not the problem: the sliced net produces the same mean and standard deviation to three decimals. The damage comes from the delay. Landing 3 frames late costs +0.11 on the sub48 subset, and landing 8 frames late costs +0.17. Exact delayed fusion (the velocity-at-K clone) plus holding MSCKF updates until the net lands recovers the median but not the tails ([tier1m NOTES](../research/single_model/tier1m/NOTES.md)). This loss matters because the net is our largest single accuracy gain: it improved holdout ATE from 0.882 to 0.738 ([LOOP_LOG](../research/single_model/LOOP_LOG.md)).

**The second blocker is MSCKF row cost.** Demand averages 10.8 rows per frame (p90 27, p99 54). At about 105 k instructions per row (update 36 k, iterated solve_dx 23 k, gating 9 k, plus overheads), that is **1.13 M per frame on average for the update alone**. A 1.8 M governor can therefore supply only 7.7 rows per frame, so it falls behind, and ATE jumps to 0.666 ([tier1m NOTES](../research/single_model/tier1m/NOTES.md)). Two further losses are measured and should not be repeated. Running vision at 10 Hz instead of 20 Hz costs +0.055 to +0.08. Time-sliced 5 Hz tracking (VIS4) costs +0.04 to +0.06 even after fixing its forward-backward parity bug ([fuel_b13 NOTES](../research/single_model/fuel_b13/NOTES.md)). Fuel accounting is also stricter than expected. Wasmtime charges about one fuel per instruction, including local.get and const, so real cost is about 2.5-3.5x a vector-op count. memory.copy costs about one fuel per byte, so stashing an RGB frame costs 0.235 M ([tier1m NOTES](../research/single_model/tier1m/NOTES.md)).

### A 1 M budget that closes on paper

The literature backs the general shape of a 1 M design but not its accuracy. An FMSCKF study found image processing to be about 90% of MSCKF cost at a 20-pose window ([FMSCKF](https://arxiv.org/html/2210.08117v2)). A downward-facing flow-plus-EKF pipeline on GAP9 runs at about 0.15 M cycles for tracking plus 0.16 M for the EKF per 160x120 frame, with indoor RMSE of 0.28-1.63 m ([Kuhne et al.](https://arxiv.org/html/2509.10021)). No source reports a forward-looking monocular MSCKF near 1 M ops. Taking our measured per-item costs as the anchor, the following allocation is the planning budget. The numbers are our estimates, not measurements of a finished build.

| Item | Measured today | 1 M target | How |
|---|---|---|---|
| IMU propagation | 0.15 M (0.025 with COVPROP) | 0.03 M | covariance propagated once per frame (COVPROP, already built) |
| Pyramid | 0.50 M | 0.08 M | green-channel level 0, SIMD, only searched levels |
| KLT (int SIMD) | 0.36 M for 60 tracks | 0.15-0.18 M | 25-30 tracks, 20 Hz, velocity-extrapolated start |
| Detection | 1.1 M → ~0.07 with stride/cool | 0.05 M | DET_STRIDE=4, DET_COOL=8, no per-frame budget below 12 cells |
| MSCKF rows | ~105 k instr/row × 10.8 rows | 0.25-0.35 M | ~35-45 k/row × ~6-8 rows (see plan item 3) |
| Small priors | 0.126 M | 0.10 M | merged and mirrored (PRIOR_MERGE, F_MIRV, built) |
| Map relocalization | 0.26 M average, 0.7 M spikes | 0.06 M | MAP_ZI with tries spread across frames |
| Net / re-anchor units | 8.5 M post-K | slack only | needs a ~4x cheaper net (plan item 2) |
| **Total steady-state** | 3.4 M median | **~0.75-0.9 M** | governor cap 1.0 M |

The table hides one constraint. The governor treats everything as deferrable, but deferral is what hurt T1v. The design has to keep vision and the MSCKF update at 20 Hz and defer only the net, map tries and detection refills.

## 0.1 m sits below every published floor; ~0.3-0.4 m on the server is the realistic target

No published monocular-inertial result supports 0.1 m mean unaligned ATE on ~60 m flights. The best EuRoC mono-inertial numbers are ORB-SLAM3 at 0.043 m (with map reuse), DM-VIO at 0.069 m, VI-DSO at 0.089 m and VINS-Mono at 0.110 m. All are **SE(3)-aligned**, and they use a much better IMU at 752x480 ([ORB-SLAM3](https://arxiv.org/html/2007.11898v2), [DM-VIO](https://arxiv.org/abs/2201.04114)). TUM-VI likewise reports ATE after optimal SE(3) alignment ([TUM-VI](https://ar5iv.labs.arxiv.org/html/1804.06120)). ORB-SLAM3's own table shows how much loop closure carries: magistrale4 reaches 0.13 m with loop closure, while magistrale3, at a similar 566 m length, reaches 4.89 m without it ([ORB-SLAM3](https://arxiv.org/html/2007.11898v2)). Our IMU is far worse than these benchmark sensors. Its noise is exactly 0.07 rad/s and 0.28 m/s² per sample ([LOOP_LOG](../research/single_model/LOOP_LOG.md)), about 60x the gyro noise and 14x the accelerometer noise of TUM-VI's BMI160 (8.0e-5 rad/s/√Hz, 1.4e-3 m/s²/√Hz), assuming a 200 Hz sample rate ([TUM-VI](https://ar5iv.labs.arxiv.org/html/1804.06120)).

Our own server evidence points the same way. Eight of B16's twelve episodes already score 0.135-0.289 m. Four episodes carry 79% of the total, with velocity RMSE of 0.51-0.60 m/s, drift of 0.02-0.03 per metre and Sim3 ATE of 0.45-0.59 ([LOOP_LOG](../research/single_model/LOOP_LOG.md)). A first-order error budget suggests 0.06-0.12 m for clean static, textured episodes. That budget uses about 0.08 m per degree of frame-0 tilt, permanent offset ≈ δv0·τ for startup velocity error, and about 0.05 m per 1% of scale error. Mid-motion starts and textureless gaps lift it to 0.15-0.3 m ([accuracy-floor notes](../research_notes/One%20million%20fuel%20VIO%20design/accuracy_floor.md), derived arithmetic rather than a published result). **A realistic best case is a server mean of about 0.3-0.4 m**, and it requires the four tail episodes to come down to ~0.5 m.

The lateinit diagnosis decides where effort should go, and it rules out startup as the main lever. On 594 dev flights with B16, removing the best rigid translation drops the mean from 0.40 to 0.26. Removing heading barely matters (0.394-0.403). A perfect first 3-5 s is worth only 0.03-0.06. The offset builds up mainly **after 5 s, during vision-starved stretches** ([lateinit NOTES](../research/single_model/lateinit/NOTES.md)). Fully featureless scenes (dark frames 45-67% pure black, bare walls with intensity std ~15) set a ~3 m floor for any vision-free estimator. Coasting from the oracle start velocity scores 2.93-5.11 m against 2.98 m for staying at the origin ([LOOP_LOG](../research/single_model/LOOP_LOG.md)). Several fixes have already been tried and failed here: the closed-form late initializer (+0.136 at 36.6 M peak), FEJ and OC variants, hand-written dynamics priors, and every flat/dark corner-tuning arm. None should be retried in the same form.

### Cheap gradient and flow measurements are the untested accuracy lever

The flat/dark study listed edge features with 1-D residuals, coarse global flow and photometric tracking as **never tried** ([LOOP_LOG](../research/single_model/LOOP_LOG.md)). These are the methods the literature recommends for low texture. DSO tracks 8-pixel gradient points rather than corners and reports tracking through very-low-texture scenes where indirect methods fail. In DSO's ablation, plain brightness constancy is the worst photometric model and an affine gain/offset per frame recovers most of the benefit ([DSO](https://ar5iv.labs.arxiv.org/html/1607.02565)). Coarse correlation flow reaches about 0.07 m/s horizontal-velocity RMSE against 0.15 m/s for PX4Flow-style SAD, but only for downward cameras with known height ([Correlation Flow](https://arxiv.org/pdf/1802.07078)). Line pipelines are too expensive for our budget: modified LSD alone takes 20 ms per frame and buys about 16% ATE on EuRoC ([PL-VINS](https://ar5iv.labs.arxiv.org/html/2009.07462)). Researcher op-count estimates put all of the cheap alternatives inside a ~0.2-0.3 M slice:

- gyro-derotated block SAD on 80x60, giving a focus-of-expansion velocity direction, at 40-60 k ops;
- 100-300 DSO-style gradient points or 1-D edgelets aligned against the previous frame, at 50-150 k ops;
- per-patch affine/ZNCC normalization, nearly free.

These figures are estimates, not measurements ([starved-vision notes](../research_notes/One%20million%20fuel%20VIO%20design/starved_vision_cheap_tracking.md)). A forward camera sees varying depth, so the flow measurement should be a direction (focus of expansion) or a v/d term with depth taken from live features, not a single global shift.

Learned inertial odometry is weak in this simulator. Every successful drone method relies on physics our simulator removes. IMO feeds thrust and learns drag, and a physics-only thrust model scores 10.1 m against 0.56 m with learning ([IMO](https://ar5iv.labs.arxiv.org/html/2210.15287)). DIDO uses rotor speeds and a drag model ([DIDO](https://ar5iv.labs.arxiv.org/html/2203.03149)). AirIO's simulated data includes linear drag ([AirIO](https://arxiv.org/html/2501.15659v2)). Our simulator has **no rotor drag**: body specific force is exactly (0, 0, T/m) ([LOOP_LOG](../research/single_model/LOOP_LOG.md)). A net can therefore learn only planner and controller regularities.

Published IO networks cost 15-72 MFLOPs ([TinyIO](https://arxiv.org/html/2507.15293v4)), and our own 2 s displacement net needs about 13 M fuel per call. Its post-hoc fusion gain (−17%) was tuned on the same flights it was evaluated on ([LOOP_LOG](../research/single_model/LOOP_LOG.md)). Hybrids do help during camera blackouts. ICD-Net with VINS-Fusion cut mean APE by 60.6% under 4-7 s blackouts, but that result rests on only three test sequences ([ICD-Net](https://arxiv.org/html/2512.00037v1)). A streaming GRU with 32 hidden units would cost an estimated ~37 k MACs per frame. It is worth building only if an offline regression first shows it beats a constant-speed prior on body velocity.

## Ranked implementation plan

| # | Step | Expected peak / fresh ATE | Test and adoption gate |
|---|---|---|---|
| 1 | **Lock T4uB** (t1m_T4uB.wasm): finish r2 and preflight, one-shot holdout, submit next to b17_exact as the safe fallback | 4.0 M / ~0.383 (server est. ~0.85 @ ~3.4 M) | 3-rep fresh paired vs B17; holdout ≤ ~0.60; preflight pass. Measured, not projected |
| 2 | **Delay-tolerant startup net**: (a) run gray0 and preprocessing in frames 1-4, convolutions in frames 5-10 where MSCKF rows are near zero; (b) postpone the movement-gate ZUPT and LI_GATENET decision until the net lands; (c) retrain the net at half input resolution (~4x fewer conv MACs) through the existing data loop | net done by frame ≤8 at ≤0.3 M/frame; target ≤ +0.01 vs unsliced net | sub48 sweep of landing frame vs ATE (must be flat to frame 8), then fresh-711 3 reps; retrained net must match lcJ on fold-3 within ±0.03 |
| 3 | **Cut row cost ~105 k → ~40 k**: 4-5 clones, f32x4 covariance blocks with symmetrize + diagonal floor, Givens null-space on sparse clone columns, gating on S only, second iteration only when \|dx\| > 0.1 | 2 M tier at ~0.40-0.43 (estimate) | profile instructions per row; fresh-711 3 reps; NEES check for f32 positive-definiteness loss; cl5 alone was measured at +0.024 |
| 4 | **1 M governor build**: steps 2+3 plus 25-30 int-KLT tracks at 20 Hz, green 160x120 pyramid, map tries sliced, reserve only for net and re-anchor | ~0.9-1.0 M / 0.42-0.50 (estimate) | must reach ≤0.49 fresh to beat T4uB in area; dev and confirm agree in sign; >3 m tails not above T4uB |
| 5 | **Starved-vision measurements**: gyro-derotated 80x60 block flow → focus-of-expansion direction update; 100-200 gradient points or edgelets with affine brightness; noise inflated from peak ratio and gradient energy | +0.1-0.25 M; target starved-class tails down | 31-flight starved stress set and the 27-flight bad pool first, then fresh-711 3 reps; adoption = stress tails down on dev and confirm, fresh mean not worse by +0.02 |
| 6 | **Tiny learned motion prior**: falsify first (offline: GRU h=32 body-velocity regression vs constant-speed prior); only if it wins, add a TLIO-style clone-to-clone displacement update with 10x covariance inflation and χ² gate | ~0.05-0.1 M | integrate only if offline error is clearly below the prior; otherwise drop |

Five things should not be revisited:

- 10 Hz or 5 Hz vision;
- per-frame detection budgets below about 12 cells;
- closed-form late init;
- FEJ/OC;
- drag pseudo-measurements.

All five are measured losses or inapplicable here ([fuel_b13 NOTES](../research/single_model/fuel_b13/NOTES.md), [lateinit NOTES](../research/single_model/lateinit/NOTES.md), [LOOP_LOG](../research/single_model/LOOP_LOG.md)). Every build change also re-rolls 1-2% of previously clean flights ([LOOP_LOG](../research/single_model/LOOP_LOG.md)), so each step needs 3 replicates before adoption.

## Conclusion

Our measurements show that both obstacles to 1 M fuel are scheduling and linear-algebra problems. Vision at 20 Hz with integer SIMD tracking is already cheaper than the MSCKF rows behind it. The real constraint is that our two most valuable accuracy features, the startup net and the iterated update, are also the two least deferrable costs. Making the net cheap enough to land early, and rows cheap enough to keep up at 20 Hz, is what turns the 1 M tier from a −1.48-point failure (T1v) into a plausible +0.4 to +0.6-point gain.

The 0.1 m aspiration is better read as a direction than a target. The error that remains is drift during vision starvation, which neither more compute nor learned inertial odometry addresses in a drag-free simulator. The one untested lever aimed at it, cheap gradient and flow measurements, also happens to fit inside the 1 M budget. That makes it the natural place for the fuel saved by steps 2-4 to go.
