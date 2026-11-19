# Approaches for VIOBench odometry: critical survey and ranked next experiments

2026-11-19, branch `odometry/approaches` (off `odometry/provided-openvins`). All accuracy numbers are **mean
unaligned ATE (m)** on the pinned evaluator (viobench `9b1b079`) unless labelled otherwise. "Public" is the
10 x 60 s ProcTHOR-Train-1 set; "campaign" is campaign dev, 120 replays (60 flights x crops 0/5 s, ProcTHOR
166-171 + 15 HSSD Val43 houses), full duration. Fuel is **peak Wasm fuel per frame** for the whole guest.

## 1. Bottom line

1. **The geometric estimator is already near the target when it works. The task is robustness, not accuracy.**
   The provided OpenVINS example, which is actually a 3-hypothesis Ceres fixed-lag smoother seeded by OpenVINS,
   scores **0.460 m median** on the 61 campaign replays where it initializes within 1.3 s. On the 34 HSSD replays in
   that group it scores **0.563 m mean**, versus 1.556 m for B-D0. Our learned velocity models cannot get there
   through our gyro attitude, which has a floor of 0.967 m campaign and 1.51 m public even with true velocity. The
   VIO's jointly estimated attitude and bias is the attitude fix we have been chasing.
2. **This session measured new evidence on where OpenVINS fails (section 3).** Its catastrophic tails come from two
   failures:
   - **A 1-3 s velocity transient, up to 25 m/s, after late initialization.** It appears when the smoother takes
     over about 1-1.5 s after a late static init. Afterwards OpenVINS tracks again. One example error trace is
     5.7 m → 76 m within 6 s, then flat.
   - **Slow linear runaways after early initialization.** ProcTHOR-169-04 reaches 2,232 m and 168-03 reaches 411 m,
     which looks like an unobservable accelerometer bias or gravity problem.

   The first-camera back-integration anchor was my first hypothesis. It is **refuted**: replacing it changes the
   campaign mean only from 32.64 to 32.48.
3. **A crude causal per-frame consensus already beats both guests. This is post hoc and decides nothing yet.**
   The rule takes OpenVINS' frame increment when it agrees with B-D0's increment to within 0.3 m/s, and B-D0's
   increment otherwise.

   | Guests and rule | Campaign mean | Campaign median | Public mean |
   |---|---:|---:|---:|
   | OpenVINS alone | 32.64 | — | 1.108 |
   | B-D0 alone | 1.843 | — | 1.996 |
   | Consensus, OpenVINS + B-D0 | **1.376** | 0.854 | 1.077 |
   | Consensus, OpenVINS + N2-s218-gated | — | — | **0.964** |

   All gates from 0.3 to 1.0 m/s land at 1.38-1.47, so the result is not knife-edge. The per-replay oracle minimum
   is 1.258, so a better fusion has at most about 0.12 m more to gain *from these two inputs*. Getting to 0.5 m
   needs OpenVINS itself to fail less often.
4. **Peak fuel for OpenVINS is a scheduling artefact.** Every 4th frame (the 5 Hz keyframe: 3 smoothers x 6 Ceres
   iterations) costs about 2.6e9. The other three frames cost about 2-3e8. Spreading the three independent smoother
   solves over the four frames should cut peak to about 1.0-1.2e9 with unchanged math.
5. **Recommendation:** stop investing in pure learned-velocity accuracy as the main line. Make the provided smoother
   robust using the learned network as a velocity prior and sanity reference, and amortize its keyframe work.
   Details are in section 5.

## 2. Constraints and what the measurements already rule in or out

| Fact (measured) | Consequence |
|---|---|
| True velocity through our gyro attitude: 1.51 public / 0.967 campaign (oracle bias 1.29 / 1.33 with model velocities; ideal yaw 0.209 campaign) | Pure velocity learning with our attitude cannot reach 0.5 m. Attitude (mostly yaw) must come from vision. |
| kf_grid visual gyro-bias (static window + KLT/essential every 0.5 s) ≈ oracle bias: public 1.936 → 1.359, campaign 1.631 → 1.355 | A bias-only visual correction has nearly saturated. The remaining error is velocity plus residual yaw. |
| Learned gyro-bias head A-D0 (3 seeds): dev 1.095 → 1.144, campaign 30 s 1.353 → 1.386, full 1.871 → 1.820 | Learned bias via displacement loss is weak. Do not reopen without a new signal. |
| Fixed EKF over learned velocity: 1.129 vs 1.095 dev; refinement 1.078; small visual attitude 0.79 % | Post-processing a velocity-only estimate without new geometric information yields ≤ 2 %. |
| Data and recipe: B-D0 → N2 dev 1.095 → 0.933, campaign full 1.871 → 1.391; 72 vs 36 epochs −5.5 % | Data and budget still help, but improvement is shrinking: ~25 % per big data step. |
| OpenVINS-consensus campaign: median 1.11, 27/120 > 5 m, init median 1.2 s, p90 9.4 s, 6 never | The median is excellent; the tails come from init timing and transients. |
| OpenVINS fuel: median 2.2e8, keyframe frames ~2.6e9, peak 3.55e9 public / 4.35e9 campaign | Peak, not mean, is the problem, and peak can be rescheduled. |
| Provided README: single smoother median ATE 1.535 vs consensus 0.849 on 8 x 120 s; p95 fuel 1.22e9 vs 2.65e9. VINS-Mono example: median 1.58, median fuel 4.7e8, p95 8.3e8 | Consensus is worth ~45 % ATE. VINS-Mono is cheaper but less accurate on this sim. |

The 0.5 m target is plausible only via a geometric VIO. The public median for OpenVINS is already 0.923, and its
early-init campaign median is 0.460. Learned components earn their place as **priors, gates and fallbacks**.

## 3. New measurement: anatomy of OpenVINS failures and an offline splice

Script: `research/approach_splice.py`. Arms and the reading rule were committed (`9e688fc`) **before** any spliced
number existed. The `diag_gate_*` arms were added after the predeclared arms had been scored and are labelled post
hoc. Output: `results/eval/approaches/splice.{json,log}`. No guest was re-run: the script combines the saved
`estimate.tum` of `baselines/runs/{public,campaign}-openvins` with `public-b-d0`, `public-n2-218-gated`,
`public-bd0-kfgrid` and `campaign-b-d0`, and scores the result with the evaluator's `evaluate_trajectory`.

| Arm (campaign 120 / public 10, learned = B-D0) | Campaign mean | Campaign median | Campaign n > 5 m | Public mean |
|---|---:|---:|---:|---:|
| OpenVINS (reproduces) | 32.642 | 1.112 | 27 | 1.108 |
| B-D0 (reproduces) | 1.843 | 1.321 | 6 | 1.996 |
| `handoff`: B-D0 until OpenVINS init, then OpenVINS relative motion | 32.476 | 1.248 | 26 | 1.103 |
| `handoff_guard`: + permanent switch back to B-D0 if 1 s displacement disagrees by > 0.5 m | 3.047 | 1.402 | 19 | 1.103 |
| `late_skip`: OpenVINS only if init ≤ 3 s, else B-D0 | 27.492 | 0.881 | 6 | 1.045 |
| post hoc `diag_gate_0.3`: per-frame increment from OpenVINS if within 0.3 m/s of B-D0 | **1.376** | **0.854** | 4 | 1.077 |
| post hoc `diag_gate_0.5` / `_1.0` | 1.424 / 1.473 | 0.864 / 0.993 | 5 / 4 | 1.106 / 1.103 |
| diagnostic `oracle_min` (truth-selected) | 1.258 | 0.824 | 1 | 1.039 |

With N2-s218-gated as the learned input on public, `diag_gate_0.3` gives **0.964** and `late_skip` gives 0.943. With
the B-D0 + kf_grid guest it gives 1.070. The campaign gate result by domain is ProcTHOR 1.591 and HSSD 1.162. It
scores 1.107 on early-init replays and 1.655 on late or never-init replays.

Predeclared verdict: `handoff_guard` **fails** its own rule, which required < 1.2 m campaign. Neither the anchor
fix nor a permanent switch is enough.

Error traces explain why:

- **Late-init replays.** OpenVINS outputs zero translation before init, which costs about 0.5 m/s x t_init.
  Initialization happens at a hover (|v| = 0.007 m/s, truth 0.02 m/s). Then, at full-VIO takeover, its speed spikes
  to 6-25 m/s for 1-3 s and returns to tracking truth at 0.2-0.5 m/s.
  - Example: `104348361-00-crop5` has init at 14.4 s and full VIO at 15.9 s. Its error goes 5.7 m → 26.9 m at
    15 s → 76 m at 20 s, then stays flat at about 76 m to the end.
  - The permanent switch trips 1 s too late, after tens of metres. The per-frame gate rejects exactly those
    increments and then re-admits OpenVINS.
- **Early-init runaways.** `169-04` has init at 0.9 s, and its estimated speed grows linearly: 0.8 → 12.8 → 231 m/s
  at 50 s. This is a classic accelerometer-bias or gravity runaway in a weakly constrained monocular window.
- **Where the gate fails.** On `168-04`, OpenVINS scores 1.92 but the gate scores 7.89: the learned net is wrong
  and vetoes good increments. A hard gate cannot know which side is wrong. Uncertainty-weighted fusion is needed.

Two late-init public flights show the same pattern. `0001` (init 3.3 s) is OpenVINS' worst flight at 2.71, and
`0002` initializes at 3.7 s.

## 4. Approach catalogue

Each entry covers: the idea, its expected effect *here*, fuel, C/C++/Wasm implementation cost, risk, and the
cheapest falsifying experiment. Fuel anchors used throughout:

| Component | Peak fuel per frame |
|---|---:|
| B-D0 CNN | 1.07e9 (8.6e8 with SIMD) |
| EMA guest | 1.7e7 |
| kf_grid KLT, every 0.5 s | +3.8e8 |
| OpenVINS non-keyframe | 2-3e8 |
| OpenVINS keyframe | ~2.6e9 |
| Hard limit | 2e10 |

### 4.1 Filter-based VIO

**MSCKF / OpenVINS ([Mourikis & Roumeliotis 2007](https://www-users.cse.umn.edu/~stergios/papers/ICRA07-MSCKF.pdf), [OpenVINS](https://github.com/rpng/open_vins), [docs](https://docs.openvins.com/))**
- **Effect here:** Our own native OpenVINS harness (`odometry/openvins`, pure MSCKF) scored 2.84 at 30 s
  campaign. Static initialization never fired on smooth starts: 117/120 had insufficient rotation for dynamic init,
  and zero-velocity updates wrongly fired on 17.5k moving frames. The provided example only became good by adding
  the fixed-lag smoother and consensus on top. Pure MSCKF alone is therefore **not** the vehicle.
- **Fuel:** 1-3e8 per frame without the smoother.
- **Cost:** Already built.
- **Risk:** Low-texture HSSD/ProcTHOR walls leave few features. MSCKF used a feature on only 11k of 29k update
  frames.
- **Falsifier:** Not worth one. The provided example already contains its EKF as the smoother's seed.

**ROVIO (direct-photometric EKF on patches, [Bloesch et al. 2015/2017](https://github.com/ethz-asl/rovio))**
- **Effect here:** Photometric patch errors use intensity gradients rather than corners, which suits low-texture
  rooms. Robocentric formulation, no init stage beyond a level-ish start: it handles moving starts gracefully. This
  is the only classic filter whose design directly attacks our two failure modes (init, low texture).
- **Fuel:** ~25 patches x multilevel x 3 iterations at 320x240 ≈ 5e7-2e8 per frame, flat with no keyframe spikes.
- **Cost:** High. It needs Eigen + kindr + lightweight_filtering (header-only Eigen code, no Ceres); about 3-5 days
  to port and wrap in the ABI. Single-threaded, deterministic.
- **Risk:** Scale drift without features moving in depth. ROVIO is known to be fragile with fast rotation and large
  initial bias. Accel bias init up to 0.2 m/s² is large for an EKF that is not given an initial window.
- **Falsifier:** Run upstream ROVIO natively (x86, ROS-free build exists in forks) on 20 campaign replays chosen to
  be **late-init / moving start**. Kill it if the median is above 1.5 m.

**EKF with learned measurements, our variant (`odometry/ekf`)**
- **Effect here:** Measured: 1.129 vs 1.095 dev. It adds nothing without independent geometric information. It
  only works as the *container* for 4.3 and 4.5.

### 4.2 Optimization-based VIO

**The provided consensus smoother itself (OpenVINS init + 3 Ceres fixed-lag graphs + geometric median)**
- **Effect here:** Already the best median. Section 3 shows its robustness gap is concentrated in about 30/120
  replays and at identifiable moments (init, smoother takeover, runaway).
- **Fuel:** Peak 3.55-4.35e9.
- **Cost:** Low marginal, because all fixes are local changes to `solution.cpp` / `fixed_lag_vio.h` /
  `consensus_output.h`.
- **Risk:** It is GPL-3.0, already accepted for the example. Ceres in Wasm is deterministic per binary.
- **Falsifier:** Section 5, items 1-3.

**VINS-Mono ([Qin et al. 2018, arXiv 1708.03852](https://arxiv.org/abs/1708.03852); provided example `native/vins_mono`)**
- **Effect here:** Provided measurements on 8 x 120 s: median 1.58 vs 0.849 for the consensus, with lower median
  fuel of 4.7e8 and p95 of 8.3e8. Its stationary-bootstrap rebuild is designed for exactly our settle-then-move
  starts.
- **Fuel:** Peak not reported. Its p95 is 3x below OpenVINS'.
- **Cost:** Zero to evaluate: build and run `wasm_eval.py` on public and campaign.
- **Risk:** Likely worse median.
- **Falsifier:** A one-command build plus one campaign run. If its tail count (> 5 m) is ≤ 6 with median < 1.0, it
  becomes a third consensus member or the robust fallback in place of the 1e9 CNN. **This is unmeasured and cheap.
  Do it.**

**ORB-SLAM3 mono-inertial ([Campos et al. 2021, arXiv 2007.11898](https://arxiv.org/abs/2007.11898); provided `native/orbslam3`, "partial run")**
- **Effect here:** ORB on 320x240 low-texture interiors gives few features. Its IMU init takes about 2-15 s and
  re-inits on tracking loss with map merging (Atlas), and it has loop closure.
- **Fuel:** Heavy and spiky: local BA plus loop closure every keyframe, likely > 5e9 peaks.
- **Risk:** High. The README itself reports only a partial run.
- **Falsifier:** Run the provided build on public only. Drop it if any episode fails or the peak is above 1e10.

**DSO / DM-VIO / Basalt**
- Links: [DSO, arXiv 1607.02565](https://arxiv.org/abs/1607.02565);
  [DM-VIO, arXiv 2201.04114](https://arxiv.org/abs/2201.04114);
  [Basalt, arXiv 1904.06504](https://arxiv.org/abs/1904.06504).
- **Effect here:** Direct methods use edges and gradients, which suits low texture, the same argument as ROVIO.
  DM-VIO's delayed marginalization plus pose-graph-BA IMU init is the best published *monocular* inertial init and
  handles our moving-start problem by design. Basalt has excellent fixed-lag numerics and a clean, single-threaded
  C++ core (TBB is optional).
- **Fuel:** DSO-class photometric BA at 320x240 with about 2000 points is roughly 1-3e9 per keyframe, so it needs
  amortization as in 5.3.
- **Cost:**
  - DM-VIO: 1-2 weeks (Pangolin, threads and GTSAM for init must be removed).
  - Basalt: about 1 week (no monocular mode upstream; mono-inertial forks exist).
- **Risk:** High engineering risk for an uncertain gain over a smoother we already have.
- **Falsifier:** Run native DM-VIO (x86, its own dataset reader) on 20 late-init campaign replays converted to
  images + IMU. Pursue only if its median *and* tails beat the consensus on that subset.

**Fixed-lag smoother with learned velocity factors (our own, inside the provided graph)**
- See 5.1. This is the most promising "optimization" item.

### 4.3 Learned inertial odometry

**TLIO / RoNIN / AI-IMU**
- Links: [TLIO, arXiv 2007.01867](https://arxiv.org/abs/2007.01867);
  [RoNIN, arXiv 1905.12853](https://arxiv.org/abs/1905.12853);
  [AI-IMU, arXiv 1904.06064](https://arxiv.org/abs/1904.06064).
- **Effect here:** These rely on motion priors (gait, car non-holonomy) that a drone lacks
  ([Cioffi et al. 2023](https://arxiv.org/abs/2210.15287) show the pedestrian models degrade on quadrotors). Our
  P-imu-blind ablation says IMU features are worth only ~5 %. An IMU-only network will not beat vision here.
- **Fuel:** Tiny, about 1e6-1e7.
- **Falsifier:** Not worth running.

**AirIO / AirIMU (body-frame features, attitude encoding, learned IMU correction + EKF)**
- Links: [AirIO, arXiv 2501.15659](https://arxiv.org/abs/2501.15659);
  [AirIMU, arXiv 2310.04874](https://arxiv.org/abs/2310.04874).
- **Effect here:** We already use body-frame features plus attitude. AirIMU's learned gyro/accel correction is
  related to our failed A-D0 head. [Brossard et al., "Denoising IMU gyroscopes", arXiv 2002.10718](https://arxiv.org/abs/2002.10718)
  showed learned gyro correction can rival VIO attitude, but on *real* IMU error structure. Our simulator's gyro
  error is white noise + constant-ish bias + random walk, and there is nothing learnable beyond the bias, which
  kf_grid already gets to oracle level.
- **Falsifier:** Not worth running. Measured negative.

**Drone dynamics / thrust-aided ([Cioffi et al. 2023](https://arxiv.org/abs/2210.15287); [VIMO, arXiv 1810.06566](https://arxiv.org/abs/1810.06566); drag-model aiding, Leishman et al. 2014)**
- **Effect here:** The rotor-drag model makes horizontal body velocity observable from horizontal specific force
  (a_xy ≈ −k v_xy). This is a real, cheap velocity measurement that does not need vision and directly attacks
  velocity drift during low-texture spells. **But it only exists if the simulator models drag.** Thrust commands are
  not in the ABI.
- **Fuel:** Negligible.
- **Cost:** 1 day.
- **Risk:** Hyperdrone may use an ideal rigid body, in which case accel carries no velocity information and the
  model is useless.
- **Falsifier (1 hour, offline):** On 20 training flights, regress de-biased body-frame horizontal specific force
  (accel minus gravity-in-body from truth attitude) on truth body velocity. If R² < 0.3, drop it. If R² > 0.7, add a
  drag factor to the smoother and to the learned EKF.

### 4.4 Learned visual odometry

**DROID-SLAM / DPVO**
- Links: [DROID-SLAM, arXiv 2108.10869](https://arxiv.org/abs/2108.10869);
  [DPVO, arXiv 2208.04726](https://arxiv.org/abs/2208.04726);
  [DPV-SLAM, arXiv 2408.01654](https://arxiv.org/abs/2408.01654).
- **Effect here:** These are the most accurate learned VO, but monocular-only (no scale), with a recurrent update
  operator over 96 patches x many frames.
- **Fuel:** DPVO is about 2-5 GFLOP per frame even at reduced size, so wasm fuel is roughly 1e10-3e10, at or
  over the hard limit.
- **Risk:** Too expensive. Scale must come from the IMU anyway.
- **Use:** Only as an **offline teacher** (pseudo-labels or relative-pose targets) for a compact student, and our
  training sim already has perfect labels. Not recommended.

**DeepVO / TartanVO (end-to-end relative pose)**
- Links: [DeepVO, arXiv 1709.08429](https://arxiv.org/abs/1709.08429);
  [TartanVO, arXiv 2011.00359](https://arxiv.org/abs/2011.00359).
- **Effect here:** This is what we already have, in better form (derotated inputs + SSM + IMU). Up-to-scale
  TartanVO adds nothing.
- **Falsifier:** None needed.

**SuperPoint / XFeat + LightGlue as the front-end of the smoother**
- Links: [SuperPoint, arXiv 1712.07629](https://arxiv.org/abs/1712.07629);
  [XFeat, arXiv 2404.19174](https://arxiv.org/abs/2404.19174);
  [LightGlue, arXiv 2306.13643](https://arxiv.org/abs/2306.13643).
- **Effect here:** Learned detectors find more repeatable points on low-texture walls than Shi-Tomasi.
  MSCKF used a feature on only 38 % of update frames, and on 37 of 573 on the worst crop.
- **Fuel:** XFeat at 320x240 ≈ 0.4-1 GFLOP, roughly 2-5e9 fuel scalar or 1-2e9 SIMD, only at keyframes. That
  competes with the smoother for the peak. LightGlue is too heavy. Use mutual-NN on XFeat descriptors plus KLT
  refinement.
- **Cost:** C++ CNN inference already exists (`native_odometry`), so about 3 days.
- **Risk:** Medium. Only low-texture replays benefit, and features alone do not fix init or runaway.
- **Falsifier:** Offline on campaign frames: count tracks surviving 0.5 s (KLT on Shi-Tomasi vs XFeat keypoints +
  KLT). If the median track count on the 20 worst-support replays rises < 1.5x, drop it.

**RAFT / SEA-RAFT flow, distilled**
- Links: [RAFT, arXiv 2003.12039](https://arxiv.org/abs/2003.12039);
  [SEA-RAFT, arXiv 2405.14793](https://arxiv.org/abs/2405.14793).
- **Effect here:** The separate `research/visual-motion` session compares frozen SEA-RAFT features with our CNN.
  Dense flow into our velocity head is still velocity-only, so it is bounded by the attitude floor unless it feeds
  rotation and bias too.
- **Fuel:** Distilled flow at 80x60 ≈ 2-5e8.
- **Verdict:** Medium value. Coordinate with that session rather than duplicate it.

### 4.5 Hybrids

**Learned velocity (+ calibrated uncertainty) as a factor/measurement inside the geometric smoother**
- **Effect here:** This is the principled version of section 3's gate. A velocity factor with sigma from an NLL
  head:
  - suppresses the 25 m/s takeover transient and the 169-04 runaway, because velocity is directly constrained
    and accel bias becomes observable;
  - keeps OpenVINS' attitude and position precision when the net is uncertain.
- **Bounds:** The upper bound from these two inputs is near the oracle-min 1.26 campaign. Done inside the graph,
  it can exceed oracle-min because it also improves OpenVINS' own state, e.g. by preventing the runaway rather
  than discarding it.
- **Fuel:** The velocity net's own fuel plus 13 extra residuals per smoother: negligible in Ceres.
- **Cost:** About 3-5 days: a Ceres factor in `fixed_lag_vio.h`, the C++ CNN from `native_odometry`, and an NLL head
  retrain (3 seeds x ~3 min each on the compiled recipe).
- **Risk:** Double counting (the net sees the same IMU), and overconfident sigma reintroduces learned-velocity error.
  Mitigate by inflating sigma 2x and gating by innovation.
- **Falsifier:** Section 5, item 1.

**Learned depth prior for scale and initialization ([Merrill et al., RSS 2023](https://roboticsproceedings.org/rss19/p072.html); [Depth Anything V2, arXiv 2406.09414](https://arxiv.org/abs/2406.09414); [Metric3D v2, arXiv 2404.15506](https://arxiv.org/abs/2404.15506))**
- **Effect here:** Merrill et al. initialize mono-VI from a 300 ms window using one learned depth map. That directly
  targets our late init (median 1.2 s, p90 9.4 s, 6/120 never).
- **Fuel:** A depth net that runs once at init (or every few seconds) can be large. 1e10 once is fine under the
  2e10 cap but sets the peak. Better: a small depth net (~1e9) or our CNN with a depth head.
- **Cost:** About 1 week.
- **Risk:** Our learned velocity already gives the same information (metric velocity at init) more cheaply.
  Prefer 5.2 first.
- **Falsifier:** Not before 5.2 fails.

**Gravity/heading-aware networks**
- **Effect here:** We already feed attitude. Heading is unobservable from gravity, and yaw is our main error
  (ideal yaw takes campaign true-velocity from 0.967 to 0.209). The only real yaw source is vision: VIO, or
  kf_grid's bias estimate. No network change helps yaw.

### 4.6 Compact / quantized models for the edge

- **Methods:** int8 CNN ([Jacob et al., arXiv 1712.05877](https://arxiv.org/abs/1712.05877)), narrower or
  lower-resolution CNN, depthwise separable layers.
- **Effect here:** The CNN is 99.5 % of B-D0's MACs. Int8 with i32x4.dot_i16x8 SIMD should give about 3-4x, and
  64x48 input about 4x more. The 1.7e7 historical EMA shows the floor.
- **Why it matters now:** In any hybrid, the velocity net is the *prior*, not the estimator, so it can be much
  cheaper than B-D0 with little loss. Section 3's gate tolerates sizeable velocity error.
- **Cost:** 1-2 days to a narrow fp32 SIMD variant; int8 another 1-2 days.
- **Risk:** Low.
- **Falsifier:** Train a 1/4-width, 64x48 N2 (3 seeds, compiled recipe), rerun the splice with its outputs. If
  `diag_gate_0.3` campaign moves by < 0.05 m vs N2-full, the cheap net is good enough.

### 4.7 Test-time adaptation ([Li et al., arXiv 2005.06136](https://arxiv.org/abs/2005.06136))

- **Effect here:** Self-supervised photometric adaptation per episode needs backprop in Wasm, which is very
  fuel-heavy, and our domain gap (proxy → native) was fixed with native data (N1/N2).
- **Verdict:** Not recommended.
- **Exception:** Online bias and scale estimation is a form of TTA, and the smoother already does it.

### 4.8 Ensembling / consensus

- **Measured:** The provided consensus is worth ~45 % median ATE over a single smoother. Our seed spread is
  0.29 m on dev.
- **Options:**
  - Seed-ensembling the learned net (3 seeds) costs 3x fuel for about 5-10 % (typical). Poor value at 1e9 per
    member.
  - Heterogeneous consensus (VIO + learned + VINS-Mono) is what section 3 measures: big gains because the failures
    are uncorrelated (oracle-min 1.258 vs 1.843 and 32.6).
- **Falsifier:** Section 5, item 1, plus VINS-Mono (4.2).

### 4.9 Zero-velocity / hover detection

- **Measured trap:** OpenVINS' ZUPT fired on 17.5k moving frames at > 0.2 m/s. The provided example disables the
  raw-disparity ZUPT for that reason.
- **Learned hover classifier:** A classifier on (IMU variance, derotated flow magnitude) is easy, and our velocity
  net already gives |v| (RMSE ~0.15 m/s). It would be useful only as a *gated* ZUPT when |v_learned| < 0.05 and
  flow is low, for the static segments the sim includes (hover 0.2/1/3 s).
- **Effect:** Small but cheap.
- **Falsifier:** On campaign truth, count frames with true |v| < 0.03 m/s. If they are < 5 % of frames, a ZUPT
  cannot matter much. Our flights are mostly moving.

### 4.10 Loop closure in small rooms

- **Effect here:** 30-120 s flights in single houses revisit views, and unaligned ATE punishes accumulated drift.
  A cheap BoW/descriptor place recognition ([DBoW2](https://github.com/dorian3d/DBoW2)) plus a pose-graph correction
  could remove the 0.5-1 m late drift.
- **Fuel:** Spiky (match + PnP + pose graph) unless amortized.
- **Cost:** About 1 week.
- **Risk:**
  - Low-texture walls give few distinctive keypoints, and false loops are catastrophic.
  - The causal requirement means corrections only help frames after the loop.
- **Falsifier:** On the 60 campaign parents, compute from truth how often the camera returns within 0.5 m / 20° of
  a pose ≥ 10 s older, and the fraction of frames after the first such revisit. If < 30 % of frames follow a
  revisit, the ATE upside is < ~15 %. Drop until the tails are solved.

### 4.11 Scale or velocity from depth priors

- Covered by 4.5. Learned metric depth plus flow gives velocity, which is just a different velocity net.
- **Verdict:** Not independent of our CNN. No separate experiment.

## 5. Ranked shortlist (top 5)

The ranking weighs expected mean-ATE gain on campaign and public, fuel at the peak, and days to a falsifying
answer.

1. **Uncertainty-weighted learned-velocity fusion with the provided smoother, as a C++ guest.** First as output-level
   fusion, then as a velocity factor inside the graph.
   - **Expected:** campaign 1.84 → ≤ 1.3, public 1.11 → ~0.95.
   - **Next experiment (offline, 1 day, before any C++):**
     - Retrain N2 with a Gaussian-NLL velocity head (3 seeds, compiled recipe).
     - Extend `approach_splice.py` with a predeclared arm that fuses per-frame increments with weights from (a)
       the net's sigma and (b) OpenVINS' innovation proxy, i.e. disagreement with its own 1 s-ago velocity.
     - Score on campaign and public with N2 outputs.
   - **Gate:** campaign < 1.30 **and** public ≤ 1.0, with no flight worse than max(OpenVINS, learned) + 0.5 m.
   - Then put the factor inside `fixed_lag_vio.h`.
2. **Amortize the OpenVINS keyframe solve to cut peak fuel about 2.5x.**
   - Solve hypothesis A at keyframe k, B at k+1, C at k+2, each reported with IMU propagation, and/or split the 6
     Ceres iterations across frames. Nothing changes about what is estimated, only *when*.
   - **Next experiment (0.5-1 day):** Patch `solution.cpp` behind a flag, build, and run public.
   - **Gate:** peak ≤ 1.3e9 with mean ATE within +3 % of 1.108.
   - This alone makes OpenVINS-consensus (1.108 at ~1.2e9) dominate our submitted B-D0 (1.996 at 1.07e9).
3. **Fix OpenVINS' late init and takeover transient at the source.**
   - (a) Seed the init with learned velocity on moving starts: initialize at about 1 s with v0 from the net and
     inflated covariance, instead of waiting for a hover.
   - (b) Add a velocity-consistency check at smoother takeover: reject or retry when the smoother's post-solve
     |v| exceeds 3x the EKF/learned speed.
   - **Next experiment (1-2 days):**
     - First instrument: log smoother vs EKF velocity at takeover on the 53 late-init replays (init > 1.3 s) to confirm the
       transient originates in the first smoother solves (the hypothesis from section 3).
     - Then implement (b) alone, which is a 20-line check, and run campaign.
   - **Gate:** replays > 5 m drop from 27 to ≤ 10, with no change on early-init replays.
4. **Measure the provided VINS-Mono example** (untested here; its p95 fuel 8.3e8 is 3x below OpenVINS).
   - **Next experiment (2-3 h):** `viobench bundle examples/native/vins_mono`, then `wasm_eval.py run` on public and
     campaign. Report median, n > 5 m, peak fuel, and its per-replay correlation of failures with OpenVINS'.
   - **Reading:** If its failures are disjoint from OpenVINS', add it as a consensus member or cheap fallback
     (rerun the splice with it as the "learned" input). If it also has a median < 0.9 at a peak < 1.5e9, it is a
     standalone candidate.
5. **Cheap velocity prior: a 1/4-width, 64x48, int8-ready version of N2.** The hybrid needs a sane velocity
   reference, not the best one.
   - **Next experiment (1 day):**
     - Train 3 seeds (compiled recipe, about 3 min per epoch-set).
     - Rerun the splice gate/fusion with it.
     - Export through `native_odometry` and measure peak.
   - **Gate:** splice result within 0.05 m of N2-full at ≤ 1.5e8 peak.
   - Then the fused guest's peak ≈ amortized OpenVINS (~1.1e9) + 1.5e8.

**Deprioritized, with reasons:**
- More pure-velocity data and recipe work: bounded by the attitude floor.
- Learned gyro bias: measured negative.
- Further EKF post-processing over velocity: measured ≤ 2 %.
- DPVO/DROID: fuel is over the cap.
- TLIO-style IO: wrong motion prior.
- TTA: fuel, and the gap is already closed by data.
- ORB-SLAM3: partial run, spiky fuel.
- Loop closure and learned features: worth revisiting after tails are fixed. Their falsifiers are listed above.

**Not yet checked here:** the drag-model R² check (4.3, 1 h) and the hover-fraction check (4.9, 15 min). They are
cheap enough to run alongside item 1.

## Reproduce

```bash
cd research   # this branch; data symlinked to the main checkout
R=/data/backups/rganapa/Sebastian/baselines/runs
env -i PATH=/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin:/usr/bin:/bin HOME=/data/backups/rganapa/Sebastian \
  TMPDIR=/dev/shm/sebastian-vio/tmp python approach_splice.py \
  --ov $R/public-openvins $R/public-openvins $R/public-openvins $R/campaign-openvins \
  --learned $R/public-b-d0 $R/public-n2-218-gated $R/public-bd0-kfgrid $R/campaign-b-d0 \
  --output results/eval/approaches/splice.json
```

The fuel pattern comes from `baselines/runs/public-openvins/sim-ProcTHOR-Train-1-0000/report/logs/*/fuel.npy`:
274 of 1,200 frames are above 1e9, spaced exactly 4 frames apart. Median 2.2e8, p90 2.5e9, max 2.95e9.
