# Internal audit: everything tried in the VIOBench VIO/odometry project (as of 2026-11-20)

Conventions: all ATE = mean unaligned position RMSE (m), never Sim(3). "Source" links are repo-relative file paths under /data/backups/rganapa/Sebastian/eecs116_projects (abbrev. `R/`). Repo is read-only for this audit; no private server episodes were touched. Seeds 217/218/219 are the standard 3-seed set. HEAD = a9f29e0 (server-calibrated benchmark). Uncommitted: `APPROACHES.md` (adds structural-pipelines paragraph), `research/release_benchmark.py` (strips the "compact" guest and server_observed.json from the shipped benchmark), untracked `research/structural_pipelines/`, `research/native_manhattan/`, `research/configs/server_mid_smoke.json`, `research/results/eval/structural-pipelines/ready.json`.

Evaluation sets (never compare across them; see [R/APPROACHES.md](APPROACHES.md)):
- **original dev**: 14 replays / 7 parents / 6 scenes (prepared, 601 inclusive frames)
- **proxy-val 30 s**: 69 replays / 68 parents / 12 scenes (older generated-pool renders)
- **public**: 10 x 60 s flights, ONE scene (ProcTHOR-Train-1), 12,000 frames; scene IS in N2/campaign training so public is only a dev diagnostic for N2-family
- **campaign dev**: 120 resets = 60 parents x crop 0 s / 5 s, 21 scenes (6 ProcTHOR 166-171 + 15 HSSD Val43), 102,000 frames; "30 s" = capped (includes 25 s remainders), "full" = entire stored duration
- **server (course leaderboard)**: `private_stage2`, 12 episodes x 1200 frames, flights ~60 m path; only reported metrics available (never episodes)
- **server-calibrated benchmark** (new, HEAD commit): locally simulated 171-flight pool re-weighted to match server extent/path-length (see section on Server).

---

## Q1. What is the current best ATE on each eval set, and what is the architecture?

### Takeaway
Best local number is the frozen **N2 + kf_grid-input seed217 C++/Wasm guest ("RA-N2-kfgrid-x3", SHA 8b05b203...)**: public 0.888 (30 s: 0.621), campaign full 1.006 (30 s: 0.824), 1.658B peak fuel. But those local numbers do not transfer: on the server-calibrated simulated pool the same family scores only ~3.5 m (3.89 calibrated) and the server score of the earlier B-D0 guest was 4.55 m, vs 0.475 m (VINS-Mono) and 0.553 m (OpenVINS) for provided geometric baselines. The best actual server score of ours is the (unlocated-source) compact "camera direction + blended speed" at 3.98 m.

### Cited Findings
Per-set best (mean unaligned ATE, m):

| Eval set | Best number | Guest | Source |
|---|---:|---|---|
| Public (10x60 s) | **0.888** (30 s: 0.621) | frozen N2-kfinputs s217 Wasm | [R/research/NEWEST_MODEL_WASM.md] |
| Campaign dev full (120) | **1.006** (capped30 0.824; eligible60 1.353 on n=30) | same | NEWEST_MODEL_WASM.md |
| Campaign full, Python/reconstructed, 3-seed own-attitude | 0.9724 (kf_grid_native-input retrain, "RA-N2-kfgrid-x3"); public 1.0389 | not a whole-guest replay | [research/TRAINING_COMPLETION.md], CONTINUATION_20261119.md |
| Original dev (3-seed, prepared) | **0.7963** static08 input arm (ordinary 0.8163); kf_grid arm 0.9217; earlier N2 0.933; B-D0 1.095 | reconstructed-input Python | CONTINUATION_20261119.md |
| Proxy-30 | best N2 rolling control 1.0995 (static08 1.1750, kf_grid 1.1343 both WORSE); B-D2 1.128 earlier | | CONTINUATION_20261119.md, HANDOFF.md |
| Server (real, course) | ours: **3.98** (compact camera-direction+blended-speed, 16M fuel, source/binary not located, roster unverified); submitted B-D0 s217 **4.55** (public 1.996 for same binary; server/public = 2.3x). No server score exists for N2/kf_grid guests. | | memory server-baseline-anchors; CONTINUATION_20261119.md |
| Server anchors (provided baselines) | vins_mono 0.475 (3.40B fuel); openvins 0.553 (3.96B); cpp_minimal identity 4.694; tiny_cnn 5.825; dead_reckoning 9.065 | | `research/server_benchmark.py` SERVER dict; memory |
| Server-calibrated local pool (171 flights, weighted to extent 4.526/path 60.2 m vs server 4.694/59.6) | N2-kfinputs s217 pool 3.508 / calibrated **3.894** (12-episode 90% CI 3.18-4.76); N2-kfgrid 3.633/3.960; bd0_velfusion 3.767/4.142; bd0_kfgrid 3.829/4.193; B-D0 3.844/**4.196** (server actual 4.55: INSIDE CI); dead_reckoning 6.698/7.035 (server 9.07 outside); openvins 28.529/31.155 (server 0.553: outside; median 0.584, heavy tail); vins_mono 5.506/4.716 (server 0.475: outside; median 0.621) | | [research/results/eval/server-benchmark/calibration.txt], failure-pool.txt |

Historical / comparison rows (actual Wasm, official evaluator pinned VIOBench `9b1b079`, zero filled frames) [NEWEST_MODEL_WASM.md, CONTINUATION_20261119.md, BASELINE_FINISH_REPORT.md]:

| Guest | Public 30/60 s | Campaign capped30/full | Peak fuel |
|---|---:|---:|---:|
| B-D0 s217 (submitted) | 0.973/1.996 | 1.324/1.843 | 1.075B |
| N2 s218 + historical kf_grid integration | 0.687/1.292 | 0.927/1.146 | 1.643B |
| B-D0 s217 + kf_grid integ. | -/1.492 | 1.276/1.642 | 1.643B |
| **N2 kf-input s217 (frozen)** | 0.621/0.888 | 0.824/1.006 | 1.658B |
| Provided OpenVINS consensus smoother | -/1.108 | 6.714/32.642 | 4.350B |

Architecture of the best pipeline (frozen candidate) [research/NEWEST_MODEL_WASM.md; research/ODOMETRY.md; HANDOFF.md section 3]:
- Standalone C++17 Wasm guest, 1,286,355 FP32 params embedded, wasi-sdk 34, FP32 `simd-8x32-k2` conv, OpenCV 5.1.0 (isolated build, commit e4f78fb) for grid/KLT/essential/pose.
- Input: causal gyro integration with 3 gyro-bias Kalman states, bias from a static window plus KLT/essential-matrix visual rotation every 0.5 s on a native-resolution grid ("kf_grid_native" policy; RANSAC input mask); attitude used to (i) derotate/rewarp the 128x96 5-channel gray image history (current, 0.25 s, 1 s warped histories + 2 validity masks), (ii) rewrite 51 IMU features (gyro means, subpacket gyro, bias, activations), (iii) integrate velocities.
- Network: small CNN (438K) + local correlation volume + 51 IMU features -> projection (678K) -> selective-SSM head (145K) (+25K sensor/output) -> body-frame velocity every frame (20 Hz); loss smooth-L1 velocity + 0.25/1/3 s displacement residuals; EMA 0.995; 36 epochs (4,392 updates); N2 data = expanded proxy tiers + 592 native campaign parents.
- Pose = velocity integrated through estimated attitude R with camera lever arm; first camera is the origin; no truth/oracle in inference.
- Latest (uncommitted) work adds 4 seed-217 guests built on this exact net: `struct_control` (byte-identical rebuild), `struct_manhattan` (LSD line-based room-axis yaw anchor), `struct_direction` (calibrated two-view translation-direction correction of velocity), `struct_combined`. Built, ABI-checked, synthetic-tested only; **no dataset score exists** [research/structural_pipelines/README.md; results/eval/structural-pipelines/ready.json]. Synthetic peak fuel 1.071B / 1.175B / 1.275B / 1.360B.

### Inferences
- Local public/campaign numbers (~0.9-1.0) overstate real-world performance by ~4x: the calibrated server pool predicts ~3.9 m for the same net. The dominant factor identified by the repo is flight extent/path length (see Q6), not model quality.
- The 0.5 m goal is only reached on the server by the geometric baselines (VINS-Mono 0.475, OpenVINS 0.553), whose median on the local pool is ~0.6 m but whose means are destroyed by heavy tails in our pool (init failures).

### Gaps
- No server score for the frozen N2 kf-input guest (nothing submitted; submission requires the user).
- Strict Python/native/Wasm visual parity unresolved (native->Wasm 0.42 m max position separation on one public replay); frozen, work stopped by user instruction.
- Only seed 217 has full Wasm measurements; Python prepared scores 0.8926 public / 0.9973 campaign agree within ~1%.
- The 3.98 m compact submission's source is not in the repo.

---

## Q2. Every approach tried, with numbers, and why it failed

### Takeaway
Pure learned-velocity improvements saturated around 0.9-1.1 m locally (data, epochs, recipe: each step ~5-25%); post-processing (EKF, refinement, learned bias head, small visual attitude) gave <=2% or regressions; geometric VIO (provided OpenVINS) has excellent medians but catastrophic initialization/transient tails that wreck the mean.

### Cited Findings
Chronological/thematic inventory (set -> numbers):

1. **Classical dead reckoning / early KLT+IMU** [Final Project/classical_vio/README.md; APPROACHES.md]: `imu_avg5` 2.147 m public (Sim(3) in that README, historical, not a decision metric), 1.44M fuel; `imu_weighted_avg10` 2.153 / 1.63M; `klt_imu` Stage 6 1.713 / 132M; older Stage 5 EKF public unaligned 4.662. Server dead_reckoning 9.065. Failure: IMU double integration without velocity observation drifts.
2. **Compact camera direction + blended speed** (c_v2, id 67b8a4d97b9f161b): server 3.98 m, 16M fuel; per-episode 1.79-12.43 (episode e7aa5aee7fb7 outlier 12.43); rotation RMSE 0.146-0.463. Source not located [CONTINUATION_20261119.md; configs/server_observed.json].
3. **Early learned EMA/SSM/compact student** (original submitted EMA guest 32x24, SSM guest): dev 1.291 (EMA), 1.395 (SSM guest); D0-ssm 12 epochs 1.337; B-D0 (36 epochs) **1.095 dev / 0.921 ordinary / 1.276 proxy30 / 1.353 campaign30 / 1.871 campaign full** [HANDOFF.md s5; SESSION_REPORT.md].
4. **Robustness / moving-start / recurrent-state** [research/ROBUSTNESS.md]: reset at 5 s clean: SSM 1.348 vs EMA 1.096 (+0.252; with combined disturbances 1.369 vs 1.096). Zero initial SSM memory: 1.385 -> 1.020 at 5 s reset, 1.170 -> 0.881 at 12 s, at nominal cost. Orientation RMSE 0.283 rad clean, 0.389 rad stressed for both models. Expanded stress training improved stress but regressed nominal; reliability inputs added little; expanded SSM no point on frontier.
5. **Data scaling** [SESSION_REPORT.md; ODOMETRY.md]: Dev/ordinary/proxy30/campaign30/campaign-full: B-D0 1.095/0.921/1.276/1.353/1.871; N1 1.164/1.076/1.302/1.219/1.633; B-D2n 1.341/1.019/1.186/1.425/2.030; **N2 0.933/1.007/1.110/1.007/1.391**. N2 fails the declared guardrail (ordinary +9.2% > 5%). Backward/lateral subset 2.136 -> 1.690 with N1. Backward motion learned from proxy renders does not transfer to native (backward sign ~0).
6. **N2 early-window hard-motion resampling**: dev 0.9334 -> 1.0284; proxy30 1.1098 -> 1.2070; campaign30 1.0071 -> 1.1388; full 1.3906 -> 1.5163. Rejected [TRAINING_COMPLETION.md].
7. **Throughput / longer budget / HP search**: compiled recipe 103.02 -> 4.83 s/warm epoch (21.3x), dev 1.095 -> 1.091; 72 epochs dev 1.030 (-5.5%, misses 10% trigger; campaign full 1.832 -> 1.794); HP burn16 finalist 1.0905 -> 1.0767; lr1e-3 finalist 1.1847; narrow CNN 12-epoch screen 1.295 vs 1.312. Architecture (2/4-layer SSM, residual GRU, GRU->SSM) within seed noise; seed spread up to 0.29 m dev; IMU features worth ~5% (zeroing costs ~5%).
8. **Learned gyro-bias head A-D0**: dev 1.095 -> 1.144, ordinary 0.9215 -> 0.9811, proxy30 1.2765 -> 1.3249, campaign30 1.3534 -> 1.3862, full 1.8706 -> 1.8204. Rejected. Frozen bias-policy screens on campaign30: control 1.35336; zero-bias 1.36846; first-window freeze 1.36420 (both fail) [FROZEN_BIAS_ABLATION.md; CONTINUATION].
9. **Small visual attitude correction (frozen B-D0 velocity)**: dev 1.095 -> 1.086 (0.79%); campaign30 1.353 -> 1.345. Missed 10% gate [SESSION_REPORT.md].
10. **Fixed EKF over learned velocity**: dev 1.095 -> 1.129 (worse every seed), ordinary 0.921 -> 1.001, proxy30 1.276 -> 1.253 (only improvement), both campaign catalogs regress. Uncertainty (NLL head) follow-up never run.
11. **Iterative frozen-feature refinement**: dev 1.095 -> 1.078, proxy30 1.276 -> 1.269, campaign30 1.353 -> 1.351; kernel-only fuel ~229k (1 step) / 561k (3 steps), whole-guest unmeasured.
12. **Our own upstream OpenVINS/MSCKF wrapper** (campaign30, 120 crops) [SESSION_REPORT.md; research/openvins_native/README.md]: stationary-update off 2.843; on 2.837; inertial-only stationary detect 2.881; still-start initializer only 9.254. Why: dynamic init "insufficient rotation" on 117/120 crops and insufficient feature support on 103; ZUPT fired on 17,548 of 19,490 frames moving >0.2 m/s; MSCKF used a feature on only 11,116/29,000 update frames (37/573 on worst crop). Later flagged as a different implementation from the provided baseline.
13. **Provided OpenVINS example (3-hypothesis Ceres fixed-lag smoother, consensus; actual Wasm)**: public 1.108; campaign capped30 6.714 / full 32.642 (median 1.112; 27/120 > 5 m; 114/120 initialized, init median 1.2 s, p90 9.4 s, 6 never); peak fuel 4.350B (keyframe frame ~2.6e9 every 4th frame; median 2.2e8). On the 61 early-init campaign replays median 0.460; HSSD early-init mean 0.563 vs B-D0 1.556. Failures: (a) after a late static init (hover), smoother takeover produces a 1-3 s velocity transient up to 6-25 m/s (e.g. 104348361-00-crop5: 5.7 -> 76 m flat), (b) early-init slow runaways (169-04: 0.8 -> 12.8 -> 231 m/s, reaching 2,232 m; 168-03 411 m) consistent with unobservable accel bias/gravity. First-camera back-integration anchor hypothesis refuted (32.64 -> 32.48). Diagnostic worst-flight: gyro bias [-0.0823,-0.0193,0.0208] rad/s at init; smoothers diverge with zero active visual factors [APPROACHES.md (research) s1,3; BASELINE_FINISH_REPORT.md].
14. **OpenVINS + learned splice (offline, saved trajectories, not a guest)** [research/APPROACHES.md s3]: campaign mean/median/n>5m: handoff 32.476/1.248/26; handoff_guard 3.047/1.402/19 (predeclared gate <1.2 FAILED); late_skip 27.492/0.881/6; **post hoc** diag_gate_0.3 (take OpenVINS per-frame increment if within 0.3 m/s of B-D0) 1.376/0.854/4 (public 1.077); gate 0.5/1.0 1.424/1.473; oracle-min 1.258. With N2-s218-gated: public 0.964 (late_skip 0.943). By domain: ProcTHOR 1.591, HSSD 1.162; early-init 1.107, late/never 1.655. Gate failure example 168-04: OV 1.92, gate 7.89 (net wrong, vetoes good increments).
15. **Provided VINS-Mono**: built, ABI check passes, provided tests 7 pass / 1 fail (noisy hovering-turn RPE 0.23884 > 0.15). No matched public/campaign Wasm replay in the historical docs (CONTINUATION). BUT on the new server-calibrated pool it WAS scored: mean 5.506, median 0.621, p90 3.92, max 225.6, 11.7% >3 m, worst-10% carries 88.1% of error; init median 1.9 s; mean ATE if init <=3 s is 3.391 vs 9.841 later [results/eval/server-benchmark/failure-pool.txt]. Server actual 0.475.
16. **kf_grid visual gyro-bias/attitude integration (N2 s218 Wasm)**: public 1.292 / campaign full 1.146; B-D0+kf_grid 1.492/1.642. Ablation of bias estimators on public (60 replays, frozen B-D0 velocities, mean ATE): control 1.9359; static08 1.6448; kf 1.8562; kf_att 1.8217; **kf_grid 1.3828**; kf_grid_att 1.35; kf_grid_gated 1.5606; **oracle_bias 1.2887** [results/eval/attitude-bias/public/summary.json]. Campaign ~1.631 -> 1.355 (oracle 1.33) per research/APPROACHES.md. Parity review: historical C++ passed an empty mask to recoverPose (Python used RANSAC inliers); host.so built without ODO_KF_GRID; so measurements are real binaries but not a faithful port [KF_GRID_PARITY_REVIEW.md].
17. **Visual translation-direction fusion (Wasm)**: public 1.491581 -> 1.360556; campaign 1.642426 -> 1.380669 (-16.0%, 3 resets >5 m). Corrected traced variant public 1.27988 (corrected kf_grid) / 1.08677 (direction fusion) but fails Python4.12/Wasm4.12 accepted-update parity on all 10 flights (attitude diffs 8.7-27 deg); native4.13 vs Wasm4.12 0.0511 m. 650-replay/3-seed expansion stopped [FUSION_COMPLETION.md; CONTINUATION].
18. **Staged fuel (staged6r)**: campaign peak 1.643B -> 1.131B, mean 1.642433 vs 1.642426 (control); public peak 0.988B vs 1.452B; SHA 238f6901...; not parity-qualified.
19. **C++/Wasm port + SIMD**: B-D0 FP32 port matches PyTorch (1.0535247814 vs 1.0535247924); SIMD peak 1,074,754,835 -> 861,235,415 (-19.87%), bit-identical outputs; CNN = 99.5% of MACs.
20. **Input-attitude retraining (reconstructed inputs, 3-seed)**: campaign-full own / common-attitude, public60 own/common, dev own, proxy30 own -- rolling control 1.3751/1.1077, 1.7423/1.1844, 0.9157, 1.0995; static08 1.1548/0.9919, 1.2832/0.9992, 0.7963, 1.1750; kf_grid_native 0.9724/0.9724, 1.0389/1.0389, 0.9217, 1.1343. Both pass experimental gate (>=5% campaign common-att gain, <=5% ordinary regression) but regress proxy30 (+6.87%/+3.17% own). Degenerate-solver abort repaired by rejecting measurement.
21. **Full N2/kf_grid-input C++/Wasm port**: first build (OpenCV5 parent-ROI grid bug) public 1.006927 / campaign 1.074409 (1.741B); after cloning grid cells (border-filter semantics fix) 0.887995/1.005868 (1.658B). 96/120 campaign resets improve vs B-D0, 24 regress (worst regression ProcTHOR-166-00-crop5 1.425 -> 2.267; worst absolute dev-106366104_174226329-01 at 4.745 m).
22. **Structural pipelines (Manhattan yaw, direction)**: built/ABI-checked only (above). `native_manhattan/yaw_anchor.hpp` is an earlier placeholder prototype whose residual calculation is a stub (superseded by `structural_pipelines/structure.hpp`).

### Inferences
- Most failures share two causes: (1) heading/yaw drift that learned velocity cannot repair (Q6); (2) distribution shift in flight extent/speed (Q6/Server). Failed attitude post-processing (EKF, refinement, learned bias) lacked any *new* geometric information, which the repo itself states.
- OpenVINS/VINS failures are init/transient failures, so their means are dominated by a few flights (96.4% of error from the worst 10% on the pool for OpenVINS).

### Gaps
- Original-dev/proxy raw whole-guest guards for N2/kf_grid guests do not exist (raw original-dev archives unavailable).
- Historical docs contain superseded statements; the repo notes the latest report wins.

---

## Q3. What was proposed but never run (the repo's own untried-ideas list)

### Takeaway
The repo's ranked shortlist (research/APPROACHES.md s5) was never executed: uncertainty-weighted fusion of learned velocity with the provided smoother, amortizing its keyframe peak, fixing late-init/takeover transient, running VINS-Mono on public/campaign, and a cheap velocity prior. Many cheap falsifiers also remain unrun.

### Cited Findings
From [research/APPROACHES.md] (all unexecuted unless noted):
1. **Uncertainty-weighted learned-velocity fusion with the provided smoother** (NLL-head retrain, 3 seeds; output-level fusion then Ceres velocity factor in `fixed_lag_vio.h`). Gate: campaign < 1.30 AND public <= 1.0, no flight worse than max(OV, learned)+0.5 m. Expected campaign 1.84 -> <=1.3, public 1.11 -> ~0.95.
2. **Amortize OpenVINS keyframe solve** (spread 3 hypotheses over 4 frames; 6 Ceres iterations split): target peak <=1.3e9 with mean ATE within +3% of 1.108.
3. **Fix OpenVINS late init and takeover transient at source**: seed init with learned velocity (init at ~1 s with v0 from net); smoother-takeover velocity-consistency check (reject when |v| > 3x EKF/learned speed); gate: replays > 5 m from 27 to <=10; first instrument the 53 late-init replays.
4. **Measure provided VINS-Mono on public/campaign** (build + wasm_eval; 2-3 h). Partly superseded: it has now been scored on the server-calibrated pool only.
5. **Cheap velocity prior**: 1/4-width, 64x48, int8-ready N2 (3 seeds), target within 0.05 m of N2-full at <=1.5e8 peak.
6. Falsifier tests never run: drag-model R^2 check (regress de-biased body horizontal specific force on body velocity; drop if R^2<0.3, adopt if >0.7; only works if the simulator models rotor drag, thrust not in ABI); hover-fraction / ZUPT check on campaign truth (<5% of frames |v|<0.03 -> ZUPT irrelevant); loop-closure revisit-fraction analysis (<30% of frames after revisit -> <15% upside); XFeat/LightGlue track-survival count (drop if <1.5x); DM-VIO / ROVIO / ORB-SLAM3 / Basalt / DSO native trials on 20 late-init campaign replays (ROVIO kill if median >1.5; ORB-SLAM3 provided build only "partial run"); int8 quantization (3-4x fuel, half-day to a day pilot); depth-prior (Merrill et al. RSS 2023) init; seed-ensembling (3x fuel for 5-10%); test-time adaptation (not recommended). Deprioritized by the repo: DPVO/DROID (>=1e10 fuel), TLIO/RoNIN (wrong motion prior), more velocity data, learned gyro bias, more EKF.
7. Data proposals never generated: fresh **192 independent 60 s flights** stress set (4 conditions x catalog x start; 32-flight pilot first) and **64-flight training-only signed-lateral pilot** (lateral windows in first second: 2 ProcTHOR, 0 HSSD scenes) [EVALUATION_COVERAGE.md; SESSION_REPORT.md].
8. Next steps named in newest docs: score the 4 structural guests on a frozen dataset with `research/structural_pipelines/score.py` (Atlanta-world room switching not implemented; Manhattan gain 0.15, 0.5 deg/step, 10 deg gate; direction gain 25%, <=10 deg cap, 0.5 s decay); 144-epoch D0 arm (not triggered); 3-seed expansion of fusion arms (stopped); porting N2/kf-input policies to a 3-seed Wasm mean; ensembling VINS/OpenVINS/learned (heterogeneous consensus oracle-min 1.258).
9. ROBUSTNESS/earlier idea list: Rotor-drag aiding (Leishman 2014; Cioffi 2023), learned hover classifier gated ZUPT.

### Inferences
- The highest-upside item given Q1/Q6 evidence is not in the shortlist as such: the server-pool results show learned guests ~3.5-3.9 m while the geometric guests have ~0.6 m medians; the repo's shortlist (hybrid with provided smoother, fixing init tails) addresses exactly that gap but was never run.

### Gaps
- No decision record shows the structural pipelines were scored or what dataset the author intends (`server_mid_smoke.json` untracked config suggests a smoke on the mid-flight server pool).

---

## Q4. Hard constraints and sensors

### Takeaway
Guest must be C or C++ compiled to WebAssembly (wasi-sdk), causal, using only the VIOBench ABI; fuel hard limit 2e10/frame (user says ignore fuel for now); monocular camera 20 Hz + IMU 200 Hz (10 IMU samples per camera packet).

### Cited Findings
- **Language/goal**: every Wasm solution compiled from C or C++; target ~0.5 m mean unaligned ATE; much faster training iteration [memory project-targets; research/HANDOFF.md s1].
- **Metric**: mean unaligned ATE (m, log scale) only; no Sim(3) [memory metric-mean-ate-only].
- **Fuel**: hard limit 2e10 per frame (research/APPROACHES.md s4 table); frozen guest peak 1.658B; OpenVINS 3.96-4.35B; VINS-Mono 3.40B; compact 16M. User says fuel can be ignored for now.
- **Camera**: monocular; simulator 640x480 raw, nominal upstream camera, FOV 120 deg +/- 15 deg randomization [research/gen.py; research/server_benchmark.py docstring]; guest receives 320x240 RGB frames [ROBUSTNESS.md s29]; our net resizes to 128x96 gray; 20 Hz (frame interval ~50 ms; "T typically 50 ms" in classical README); intrinsics/extrinsics supplied through ABI (camera lever arm; first-camera defines pose origin).
- **IMU**: 200 Hz accelerometer (specific force) + gyro; ground truth 200 Hz; packets of ~10 samples per frame; timestamps with jitter modeled in robustness tests (<=1 ms); gyro model = white noise + near-constant bias + random walk; accel bias init up to ~0.2 m/s^2 (research/APPROACHES.md s4.3/4.1, repo's own characterization); upstream IMU noise default [gen.py, native_campaign.py L24].
- **Causality**: no truth, scene id, or future measurements in inference; ABI check = 5 steps; ABI IMU row bound 1024 [NEWEST_MODEL_WASM.md].
- **Flight spec**: default HyperDrone planner: 60 s, 48 waypoints, 1 s hover, cruise 0.45-0.8 m/s, MAX_ACC 0.7, MAX_JERK 2.0 (cannot exceed ~48 m path in 60 s). Server flights ~59.6 m mean path (39.5-80.4), mean speed ~1 m/s; public 18.2 m [memory server-flight-distribution; configs/server_observed.json].
- **Process rules**: seeds 217/218/219; declare gates before results; no pushing/submission by agents; reserved test scenes (ProcTHOR 162-165/172-175, 28 HSSD Val43, 84 campaign test flights) untouched; never fetch private server episodes [HANDOFF.md; memory].

### Gaps
- Exact IMU noise densities/bias magnitudes, intrinsics and baseline numbers are not stated in the repo docs read (they live in the simulator/viobench source); only the qualitative model above is documented.

---

## Q5. Compute / GPU setup, data generator

### Takeaway
One box with 8x H100 80 GB (GPU0 hosts someone else's ~2 GB service), ample NFS/tmpfs, an OptiX-based native simulator pipeline that has generated ~1,400+ flights; separately a "gpu_kit" for generating hidden-set-like varied-speed flights on any GPU machine.

### Cited Findings
- **Box**: 8x NVIDIA H100 80GB HBM3 (verified nvidia-smi now: GPU0 2,168 MiB used, others idle); root disk 100% full; work under `/data/backups/rganapa/Sebastian` (NFS ~14 TB free) or `/dev/shm` (~880 GB tmpfs). Python envs: `venv-teacher` (torch 2.15+cu132, cv2 5.1.0), `venv-viobench-9b1b079` (pinned evaluator), `venv-sim` (viobench[sim], hyperdrone/hyperlux 0.1.10, OptiX) via `/data/backups/rganapa/Sebastian/gen/env.sh`; wasi-sdk 34 [HANDOFF.md s2; NEWEST_MODEL_WASM.md].
- **Training speed**: compiled recipe 4.83 s/warm epoch on 1 H100 (original 103.02 s); DDP scaling 1->2->4 GPUs: 4.20/2.48/1.74 s, 60.5% efficiency at 4 -> better to run independent seeds per GPU; batched GPU replay evaluator (10.68 -> 4.46 s on 26 replays); NCCL P2P after disabling NVLS (CUDA error 802) [SESSION_REPORT.md].
- **Native campaign data**: `research/native_campaign.py` + `configs/native_campaign.json`; 600 train/60 dev/88 reserved flights requested (realized 592/60/84), 30/60/90 s, 25% independent-yaw autopilot; raw 640x480 + 200 Hz IMU archives in `/data/backups/rganapa/Sebastian/gen/raw/{train,dev,test}` (~100 GB); ProcTHOR scenes 121/124 and 2 HSSD houses crash the simulator; run `N=40 gen/run_campaign.sh` with simulator JIT cache on tmpfs; one process per leftover flight (`--ids`). Training set: 592 parents, 256 scenes, 29,460 s [HANDOFF.md; SESSION_REPORT.md].
- **Server-benchmark generator**: `research/server_benchmark.py` (pool roster; groups clean=ProcTHOR 150-161/176-179, dev, seen), `configs/server_fast_pool.json`, `server_fast_mid_pool.json` (mid-flight starts), `server_benchmark_pool*.json`, `server_speed_probe{,2,3}.json`; `bench_pipeline.sh` (self-driving: generate -> score all guests with `WORKERS=180` -> calibrate -> failure analysis -> private HF dataset -> queue watcher `/data/backups/rganapa/Sebastian/baselines/queue` that auto-scores any dropped .wasm), `bench_eval.py`, `failure_analysis.py`, `release_benchmark.py`. Selection: 882 flights, tilted by weights to 171 distinct (effective sample 90-159) matching server extent 4.694 and path 59.6 m [results/eval/server-benchmark/selection.txt]. Raw bench in `gen/raw-fast`, `gen/raw-bench`.
- **gpu_kit/** ([gpu_kit/README.txt], jobs_gpu.txt, styles.txt, make_flights.sh): kit for a Linux GPU machine that renders ~86 one-minute flights with an autopilot patch (`viobench_local.patch`); each flight draws its own top speed 0.3-4 m/s; styles `wide_gentle` (MAX_ACC 3.0, JERK 10), `wide_agile` (6.0/30), `wide_long` (6.0/30, roadmap spacing 4.0, connection 16 m); groups pt_gentle/pt_agile/pt_long (ProcTHOR), hssd_gentle/agile/long, mid_start (hover 0); output `flights_gpu/<group>/` (100-600 MB each; do not push to git). `flights_gpu/` in repo holds only `calib/table.txt` and 50 logs (flight data themselves not in the repo).
- **Prepared Hub data**: private HF `SentientNapkin/viobench-teacher-data` (shards, manifests, ledger), `viobench-teacher-lab` (checkpoints), `viobench-native-campaign` (metadata).
- **Original proxy generator**: `research/gen.py` (scene-disjoint 640x480 upstream camera, 200 Hz IMU/GT, 20 Hz frames; FOV 120+/-15).

### Gaps
- How many of the `gpu_kit` flights were actually rendered/used is not recorded in committed docs (only logs in `flights_gpu/logs`).

---

## Q6. Root causes of remaining error (diagnostics in repo)

### Takeaway
Error decomposition says attitude, mostly YAW, dominates once velocity is good: with TRUE body velocity our attitude path alone gives 0.967 m campaign full (1.51 public); perfect yaw cuts that to 0.209. Gyro bias is mostly fixed by kf_grid (reaches oracle-bias level). The velocity net contributes ~0.15 m/s RMSE. On the server-style long/fast flights the error grows with flight extent (Spearman(ATE, zero-ATE) 0.89-0.94), i.e. unbounded drift scaled by distance, plus a speed/extent distribution shift.

### Cited Findings
Error-decomposition diagnostics (oracle attitude / yaw / bias / scale):
- **Rotation floor (true velocity through our gyro attitude)**: dev 0.407 (ordinary 0.428), proxy30 0.348, campaign30 0.530, campaign full 0.967, public 1.51; at 90 s proxy ~1.04 [HANDOFF.md; ODOMETRY.md; SESSION_REPORT.md; research/APPROACHES.md s2]. Zero-output reference: dev 2.591, ordinary 2.669, proxy30 2.041, campaign30 2.843.
- **Truth-only oracle ablation, campaign dev (true velocity), 30 s / full**: baseline 0.530/0.967; **ideal yaw 0.144/0.209**; ideal tilt only 0.490/0.909; bypass rolling gyro calibration 0.478/0.783 [SESSION_REPORT.md]. => yaw is the "largest attitude error source".
- **Oracle bias with model velocities**: public 1.29 / campaign 1.33 (vs kf_grid 1.355-1.383 and control 1.936/1.631): kf_grid ~= oracle bias, so bias-only visual correction is saturated; remaining error is velocity + residual yaw [research/APPROACHES.md s2; results/eval/attitude-bias/public/summary.json].
- **Velocity error**: RMSE ~0.15 m/s (0.211-0.223 m/s on 5 s resets); orientation RMSE 0.283 rad clean at 5 s reset [HANDOFF.md; ROBUSTNESS.md]. Server per-episode B-D0 rotation RMSE 0.163-0.700 rad (compact c_v2 0.146-0.463); B-D0 vs compact ATE corr 0.71; corr(ATE, travel) 0.55/0.63; final drift 2.4-6.8 m for B-D0 [configs/server_observed.json; memory].
- **Reset/start effects**: 5 s crops reset both guest and origin; learned SSM first-memory bug (1.385 -> 1.020 with zero init); only 39/60 five-second crops start >0.1 m/s; actual initial speed >=0.2 m/s group 1.071 vs <=0.05 group 0.986 full for frozen guest [ROBUSTNESS.md; SESSION_REPORT.md; NEWEST_MODEL_WASM.md]. Motion groups for frozen guest: backward/lateral 1.504 full (n=10) vs ordinary 0.961.
- **Duration growth**: B-D0 raw replays 600 -> 1200 frames: 0.856->1.205, 0.926->1.289, 1.497->1.687, 5.037->7.509 (independent-yaw 60 s flight) [SESSION_REPORT.md]; frozen guest capped30 0.824 vs full 1.006 vs eligible60 1.353 [NEWEST_MODEL_WASM.md].
- **Spikes/resets in VIO guests**: OpenVINS 25 m/s takeover transient after late init, accel-bias runaways, 6/120 never initialize [research/APPROACHES.md s3]. On the server pool: OpenVINS mean if init <=3 s 0.982 vs 168.475 later; VINS-Mono 3.391 vs 9.841; 7.6% of flights where both OV and VINS exceed 3 m; failures correlate with catalog/scene darkness and low texture (Spearman with `dark` 0.56/0.49) and with vertical motion (0.33/0.28) [failure-pool.txt].
- **Server-pool failure analysis for learned guests** (882-flight pool for B-D0: mean 3.165, median 2.844, p90 4.93, max 10.30; worse than identity on 35.4% of flights; >3 m on 45.5%; ATE~zero-motion-ATE Spearman 0.91). On the 171-flight tilted pool: B-D0 3.844 (22.2% worse than identity), n2_kfinputs 3.508 (17.0% worse than identity, 59.1% >3 m), ATE vs extent terciles for n2_kfinputs 2.353 / 3.165 / 5.005 (B-D0 2.559/3.479/5.495). Spearman of ATE/zero-ATE with turning 0.05-0.38, lateral 0.13-0.32, hover -0.05..-0.30, speed ~0, flat-start offset 0.02-0.33. By catalog: n2_kfinputs HSSD-train 3.980, HSSD-val 4.206, ProcTHOR 3.041; by group clean 2.917, dev 3.888, seen 3.445. Worst 10% of flights carry ~20% of error for learned guests (so not heavy-tailed: broad scale-with-extent error) [failure-pool.txt, failure-selected.txt].
- **Speed/extent distribution shift**: server flights 59.6 m path vs our default pool 16.3 m (~18 m public); all ~1,400 locally generated flights <=33 m before the new fast pool; B-D0 server/public = 2.3x; the new fast pool (path 56-60 m) reproduces B-D0's server score (calibrated 4.196 vs 4.55 inside CI) [memory; server_benchmark.py; calibration.txt].
- **Scale**: no explicit scale-error diagnostic was found in the repo; scale errors are only implied through the displacement-loss/velocity RMSE and the ATE-vs-extent correlation. Learned depth/scale priors and drag aiding were never tested (Q3).
- **Public-vs-campaign gap**: public scene is in N2 training (so 0.888 is optimistic); campaign crops overlap (120 resets from 60 parents); campaign ProcTHOR 1.047 / HSSD 0.965 for frozen guest.
- **Parity limitations**: native->Wasm visual path differences (0.42 m max position, rotation element 0.17 on one public replay) may add error; the Python score ~ Wasm score within 1% in aggregate [NEWEST_MODEL_WASM.md].

### Inferences
- Dominant, repo-measured error source: attitude drift (yaw) integrated through the learned velocity. Yaw is unobservable from gravity; the only yaw source is vision (VIO) or Manhattan-type structure. This is the motivation for the uncommitted `struct_manhattan` and `struct_direction` guests. Prior bias-only correction is saturated at the oracle-bias level.
- On the server-calibrated (long, fast) pool the learned guests' error is proportional to extent (0.89-0.94 rank correlation with zero-motion ATE; ATE ~ 0.8x identity-pose error), implying roughly unbounded drift-per-distance rather than rare catastrophes; geometric VIO guests instead show rare catastrophic init/transient failures (heavy tails) but ~0.6 m medians.
- With frozen N2-kfinputs at ~3.5 m calibrated pool vs ~1.0 m local campaign, speed/path-length shift (not model overfit alone) accounts for most of the local/server gap; training data likely needs ~1 m/s flights of ~60 m (memory suggests this too).

### Gaps
- No oracle-attitude/yaw/bias decomposition has been computed on the server-calibrated pool (only on campaign/public/proxy/dev); no scale-vs-yaw split of the 3.5-3.9 m pool error.
- No score for the structural (Manhattan/direction) guests; their benefit is unmeasured.
- Server ATE of the N2 family is unknown.

---

## Appendix: key file paths
- Entry points: `R/APPROACHES.md`, `R/research/SOLUTIONS.md`, `R/research/CONSOLIDATION.md`, `R/research/CONTINUATION_20261119.md`, `R/research/NEWEST_MODEL_WASM.md`, `R/research/FUSION_COMPLETION.md`, `R/research/TRAINING_COMPLETION.md`, `R/research/BASELINE_FINISH_REPORT.md`, `R/research/HANDOFF.md`, `R/research/SESSION_REPORT.md`, `R/research/APPROACHES.md` (survey + ranked shortlist + splice), `R/research/ROBUSTNESS.md`, `R/research/KF_GRID_PARITY_REVIEW.md`, `R/research/FROZEN_BIAS_ABLATION.md`, `R/research/EVALUATION_COVERAGE.md`.
- Code: `research/native_odometry/` (frozen guest), `native_odometry_staged/`, `provided_baseline/`, `openvins_native/`, `vel_fusion.py`, `refine_c/`, `visual_motion/`, `structural_pipelines/{build,check_geometry,validate,package,score}.py + structure.hpp`, `native_manhattan/yaw_anchor.hpp` (stub), `attitude_bias.py`, `oracle.py`, `decompose.py`, `failure_analysis.py`, `server_benchmark.py`, `bench_pipeline.sh`, `gpu_kit/*`.
- Results: `research/results/eval/{server-benchmark,new-model-wasm,attitude-bias,attitude,visual-attitude,approaches,provided-comparison,structural-pipelines}/`; frozen binaries `research/artifacts/n2-kfinputs-frozen/package/` (SHA s217 8b05b203...2d60cf); structural guests `research/artifacts/structural-pipelines-v5/`.
- Classical: `Final Project/classical_vio/{imu_avg5,imu_weighted_avg10,klt_imu}`.
- Note: I did not open every per-flight JSON or the 130 attitude npz dumps; numbers above come from the docs and summary JSON/TXT files cited.
