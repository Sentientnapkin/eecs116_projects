# Feed-forward 3D foundation models and deep SLAM/dense methods as a front end for monocular+IMU drone odometry (as of Nov 2026)

Scope note. Every arXiv ID below was opened (abstract page) unless marked "SEEN-IN-SEARCH-ONLY" or "UNVERIFIED". Numbers come from the pages cited. Claims from my own memory that I could not open are listed under Gaps, not as findings. Project context (repo reports, read locally): server VINS-Mono 0.475 m and OpenVINS 0.553 m beat our learned family (about 4.5 m); learned error is dominated by yaw drift; geometric VIO has about 0.6 m medians but catastrophic initialization tails on our pool; the metric is the raw mean, so the worst ~10% of flights dominate. Hardware check: this host has 8 H100 80GB, 7 idle at the time of check. gpu_kit/ only generates simulated flights (VIOBench renderer), it does not run any model.

## 1. Which methods are causal/streaming, and what do they cost?

### Takeaway
Only a minority are truly causal: CUT3R, Spann3R, StreamVGGT, MASt3R-SLAM (frontend, with a non-causal backend), DPVO/DPV-SLAM and DBA-Fusion (sliding window). VGGT, pi3, DUSt3R/MASt3R and DA3 are bidirectional batch models that must be wrapped in sliding windows or chunking to be causal. Everything here needs a GPU and PyTorch; none is wasm-runnable as published.

### Cited Findings
- VGGT: single feed-forward transformer giving cameras, depth, point maps and 3D tracks from one to hundreds of images, "under one second" reconstruction; bidirectional over the whole input set (no causal mode in the abstract) — [arXiv 2503.11651](https://arxiv.org/abs/2503.11651)
- pi3: permutation-equivariant, predicts affine-invariant poses and scale-invariant local point maps with no fixed reference view; again a batch model — [arXiv 2507.13347](https://arxiv.org/abs/2507.13347)
- StreamVGGT: causal attention with cached keys/values, distilled from VGGT, faster online inference with competitive accuracy; this is a direct precedent for teacher-to-student distillation — [arXiv 2507.11539](https://arxiv.org/abs/2507.11539)
- CUT3R: recurrent model with persistent state, online pointmaps "metric-scale" in a shared frame per the abstract (the metric claim is image-only, so treat it as a learned prior, not measured physics) — [arXiv 2501.12387](https://arxiv.org/abs/2501.12387)
- Spann3R: DUSt3R-based, external spatial memory, processes ordered sequences "in real time", predicts per-frame pointmaps in a global frame without global alignment — [arXiv 2408.16061](https://arxiv.org/abs/2408.16061)
- DUSt3R (pairwise pointmaps plus global alignment, non-causal) [arXiv 2312.14132](https://arxiv.org/abs/2312.14132); MASt3R (adds matching features, fast reciprocal matching) [arXiv 2406.09756](https://arxiv.org/abs/2406.09756)
- MASt3R-SLAM: monocular, about 15 FPS (Table 8: 14.6 FPS average) on i9-12900K + RTX 4090; MASt3R encoder/decoder is about 64% of runtime; tracking above 20 FPS — [abstract](https://arxiv.org/abs/2412.12392), [HTML v2](https://arxiv.org/html/2412.12392v2)
- MegaSaM: DROID-style deep SLAM adapted to dynamic, low-parallax casual video, claims comparable or faster speed; offline pipeline, not streaming — [arXiv 2412.04463](https://arxiv.org/abs/2412.04463)
- DROID-SLAM: recurrent dense BA, monocular/stereo/RGB-D, repeated refinement of pose and per-pixel depth — [arXiv 2108.10869](https://arxiv.org/abs/2108.10869)
- DPVO: sparse patch tracking plus differentiable BA, "3x faster" and "a third of the memory" of DROID — [arXiv 2208.04726](https://arxiv.org/abs/2208.04726)
- DPV-SLAM: runs on one GPU, 5-7 GB memory, 1x-4x real time, accuracy comparable to DROID-SLAM on EuRoC/TartanAir at about 2.5x the speed — [arXiv 2408.01654](https://arxiv.org/abs/2408.01654)
- MAC-VO: learned matching uncertainty used for keypoint selection and covariance-weighted pose graph, but it is STEREO VO, so it does not fit a monocular camera — [arXiv 2409.09479](https://arxiv.org/abs/2409.09479)
- DBA-Fusion: DROID-style dense BA Hessian fed into a sliding-window factor graph with IMU (also GNSS, wheel); code on GitHub (GREAT-WHU); evaluation timing on RTX 3090 at 5 Hz images — [arXiv 2403.13714](https://arxiv.org/abs/2403.13714), [HTML](https://arxiv.org/html/2403.13714v1), [repo](https://github.com/GREAT-WHU/DBA-Fusion)
- "VI-DROID" as a name: I found no paper by that name; closest are DVI-SLAM (DROID-SLAM plus IMU factors, EuRoC) [arXiv 2309.13814](https://arxiv.org/abs/2309.13814) (SEEN-IN-SEARCH-ONLY) and DBA-Fusion — [search result](https://arxiv.org/html/2309.13814v2)
- Gaussian-splat SLAM: MonoGS runs live at 3 fps [arXiv 2312.06741](https://arxiv.org/abs/2312.06741); Splat-SLAM is RGB-only with global optimization and monocular-depth refinement, evaluated on Replica/TUM-RGBD/ScanNet, not drone VIO [arXiv 2405.16544](https://arxiv.org/abs/2405.16544); GS-ICP SLAM is RGB-D only (107 FPS) [arXiv 2403.12550](https://arxiv.org/abs/2403.12550); Photo-SLAM uses ORB-style explicit geometric features for localization, runs on Jetson AGX Orin [arXiv 2311.16728](https://arxiv.org/abs/2311.16728)
- VGGT-SLAM: VGGT submaps aligned on SL(4) manifold, indoor, uncalibrated mono, no IMU — [arXiv 2505.12549](https://arxiv.org/abs/2505.12549); VGGT-SLAM++ adds Sim(3) front end and DEM/VPR back end — [arXiv 2604.06830](https://arxiv.org/abs/2604.06830)
- Metric depth models are single-image: Depth Pro (2.25 MP in 0.3 s on a standard GPU, no intrinsics needed) [arXiv 2410.02073](https://arxiv.org/abs/2410.02073); UniDepth [arXiv 2403.18913](https://arxiv.org/abs/2403.18913); Metric3Dv2 [arXiv 2404.15506](https://arxiv.org/abs/2404.15506); Depth Anything V2 (25M to 1.3B parameters, can be fine-tuned with metric labels) [arXiv 2406.09414](https://arxiv.org/abs/2406.09414); Depth Anything 3 (any-view, claims +44.3% pose accuracy and +25.1% geometry over VGGT on its own benchmark) [arXiv 2511.10647](https://arxiv.org/abs/2511.10647)
- NeRF-SLAM: not researched or opened; no entry.

### Inferences
- At 320x240 the transformer cost drops roughly with token count, so VGGT/pi3/MASt3R windows should be several times faster than at their native 512-518 px; I have no measured number, so this is a to-be-tested hypothesis.
- Offline teacher use (8 H100) does not need any streaming property, so causality matters only for the student, which we write ourselves.

### Gaps
- No verified fps for CUT3R, StreamVGGT, VGGT or pi3 at any resolution; I did not open the papers' speed tables.
- NeRF-SLAM (iMAP/NICE-SLAM/Nerf-SLAM) not covered.
- DVI-SLAM and VGGT-Long IDs seen only in search results, not opened.

## 2. Reported accuracy: unaligned/metric vs Sim(3)-aligned on EuRoC / TUM-VI / Blackbird / TartanAir / UZH-FPV

### Takeaway
Almost all headline numbers for the foundation-model and deep-SLAM front ends are Sim(3) or scaled-aligned, so they say nothing about our unaligned metric. The only unaligned-style evidence is from the IMU-fused 2025-26 papers, and those are short clips or abstracts without numbers I could read.

### Cited Findings
- MASt3R-SLAM EuRoC: "scaled trajectory alignment" because all systems are monocular; calibrated average 0.041 m vs DROID-SLAM 0.022 m and DPV-SLAM 0.024 m; uncalibrated 0.164 m; TUM RGB-D calibrated 0.030 m; authors call EuRoC hard (aggressive motion, exposure) — [HTML v2](https://arxiv.org/html/2412.12392v2)
- DBA-Fusion (metric-scale VIO) on TUM-VI: translation error 0.42% of trajectory length vs 2.64% for visual-only DROID-SLAM (which was scaled using ground truth); magi3 1.02 m vs 38.82 m; outd1 DROID 220 m; weak IMU excitation at start gives early drift; no EuRoC numbers in the paper — [HTML](https://arxiv.org/html/2403.13714v1)
- VGGT-SLAM on EuRoC (third-party table in VGGT-SLAM++): 3.78/3.96/3.71 m on MH01-MH03, MH04/MH05 failed; VGGT-SLAM++ average 2.666 m; the paper notes VGGT odometry underperforms on grayscale EuRoC. Alignment not confirmed. SEEN-IN-SEARCH-ONLY (table text came from a search summary of [2604.06830](https://arxiv.org/pdf/2604.06830), not from a page I opened)
- VI3 (IMU grounding for 3DFMs): VGGT on TartanAirV2 8-frame clips, camera position RMSE 1.130 m to 0.358 m, trajectory scale 0.14 to 1.05; EuRoC V2-03 translation RMSE 0.078 to 0.062 m; UZH-FPV indoor-forward-9 shows less consistent scale recovery because of low parallax — [alphaxiv abstract page](https://www.alphaxiv.org/abs/2609.03824) (not arXiv-hosted; I opened it via alphaxiv)
- FoundationVIO (Oct 2026): feed-forward GFM predictions fused with IMU in a factor graph, odometry "competitive with classical VIO", near real time on a laptop GPU; datasets and ATE not visible on the page — [arXiv 2610.14951](https://arxiv.org/abs/2610.14951)
- MASt3R-Fusion: Sim(3) visual constraints inside a metric SE(3) factor graph with IMU/GNSS, claims better than visual-centered multi-sensor SLAM; no numbers on the abstract page — [arXiv 2509.20757](https://arxiv.org/abs/2509.20757)
- Cioffi and Scaramuzza: deep SLAM's gain comes from learned 2D data association and learned uncertainty, not recurrence — [arXiv 2607.06023](https://arxiv.org/abs/2607.06023)
- DPVO on UZH-FPV is reported in DEVO and in the 2607.06023 study; no numbers read — [search result](https://arxiv.org/pdf/2312.09800)
- Blackbird: no foundation-model or DROID-family number found.

### Inferences
- Our scale/yaw-sensitive unaligned ATE cannot be predicted from MASt3R-SLAM or DROID numbers; their 0.02-0.04 m EuRoC figures are a best case with one free scale per trajectory.
- Short-clip RMSE results (VI3) do not carry to 60 s chained odometry: chaining adds drift.
- The 2-3 m VGGT-SLAM EuRoC errors (if the table is right) suggest raw VGGT windows are not accurate enough on grayscale low-parallax flight without a strong inertial backbone.

### Gaps
- No source found giving unaligned ATE on EuRoC/TUM-VI/UZH-FPV/Blackbird for VGGT, pi3, CUT3R, StreamVGGT or MASt3R-SLAM.
- FoundationVIO and MASt3R-Fusion full tables not read.

## 3. How to inject IMU for metric scale and gravity-aligned yaw

### Takeaway
Three patterns exist: (a) factor-graph fusion where the network supplies relative pose/depth residuals and the IMU supplies metric SE(3) states (DBA-Fusion, MASt3R-Fusion, FoundationVIO); (b) post-hoc scale/gravity anchoring of a frozen 3DFM (VI3); (c) train-time conditioning (not found as published). Gravity gives roll/pitch and scale; world-frame yaw is NOT observable from a monocular camera plus IMU, so any front end leaves yaw to the IMU initial heading, which matches our observed yaw-drift dominance.

### Cited Findings
- DBA-Fusion: IMU provides metric scale and gravity direction; DBA Hessian goes into a sliding-window factor graph with marginalization — [HTML](https://arxiv.org/html/2403.13714v1)
- MASt3R-Fusion: Sim(3) alignment constraints added to a metric SE(3) factor graph, hierarchical real-time window plus global optimization — [arXiv 2509.20757](https://arxiv.org/abs/2509.20757)
- VI3: preintegrated gyro+accel gives metric gravity-aware trajectory; gyro bias, initial velocity and gravity estimated from IMU plus the 3DFM's up-to-scale motion; pose conditioning or test-time refinement of scale and final attention blocks (160 steps per clip, 48-128 s per clip on RTX 5090); fails when parallax is low or initial velocity magnitude is wrong — [alphaxiv](https://www.alphaxiv.org/abs/2609.03824)
- AMB3R adds a scale head to VGGT, LiDAR-VGGT uses LiDAR for metric scale; neither uses an IMU — SEEN-IN-SEARCH-ONLY, [search snippets](https://arxiv.org/html/2511.20343)

### Inferences
- For us the useful interface is small: feed the network's relative-rotation and relative-direction (unit translation) between keyframes into our EKF/guard, and take scale and yaw from the IMU, which is how VINS/OpenVINS already work.
- A foundation model gives no yaw information beyond relative rotation; it cannot fix the yaw drift the repo notes identify unless its relative rotation is more accurate than integrated gyro over 60 s.

### Gaps
- No paper found that trains a feed-forward front end with raw IMU tokens end-to-end and reports unaligned ATE on drones.

## 4. Failure behaviour in low texture / dark (our heavy-tail issue)

### Takeaway
Evidence is thin. Learned dense matchers are claimed more robust than corner tracking in low texture, but the same sources show failures on grayscale/blurred/fast-motion data, and nothing tests a 320x240 dark drone camera.

### Cited Findings
- MASt3R-Fusion's motivation: classical visual SLAM struggles in low texture and scale ambiguity — [arXiv 2509.20757](https://arxiv.org/abs/2509.20757)
- MASt3R-SLAM: ORB-SLAM fails on EuRoC V103 and V203 and on five TUM RGB-D sequences while MASt3R-SLAM does not; authors admit MASt3R was trained on pinhole images only, degrades with distortion, and uncalibrated EuRoC worsens 4x — [HTML v2](https://arxiv.org/html/2412.12392v2)
- VGGT-SLAM++ note: VGGT odometry underperforms on grayscale EuRoC (SEEN-IN-SEARCH-ONLY, [2604.06830](https://arxiv.org/pdf/2604.06830))
- DROID-family visual-only systems fail large on TUM-VI (outd1 220 m, magi3 38.8 m) but IMU fusion cuts that to about 1 m — [HTML](https://arxiv.org/html/2403.13714v1)
- Cioffi/Scaramuzza list low texture, motion blur and poor illumination as conditions where visual SLAM degrades even for deep methods — [arXiv 2607.06023](https://arxiv.org/abs/2607.06023)
- VI3: scale recovery needs translational parallax, so slow or hovering flight is weak — [alphaxiv](https://www.alphaxiv.org/abs/2609.03824)

### Inferences
- The heavy tail is mostly initialization and degenerate excitation (repo notes). A deep front end helps tails only if it gives usable relative rotation during the first seconds while VINS/OpenVINS are still initializing; that is a testable claim, not an established one.
- Dark or texture-free sim flights likely produce confidently wrong pointmaps (feed-forward models have no inlier test), so a guard still needs IMU-consistency checks.

### Gaps
- No quantitative low-light/low-texture benchmark for VGGT/pi3/CUT3R found.

## 5. Teacher-to-student distillation into a wasm-runnable student; what is distillable

### Takeaway
Distilling relative rotation, unit-direction translation, depth and tracks from a heavy teacher is the realistic path, and StreamVGGT already shows teacher-student distillation inside the family. Distilling absolute pose is not useful (scale and yaw come from IMU).

### Cited Findings
- StreamVGGT trained by distilling VGGT into a causal model — [arXiv 2507.11539](https://arxiv.org/abs/2507.11539)
- DA3 and Depth Anything V2 both use teacher-student training with pseudo-labels — [arXiv 2511.10647](https://arxiv.org/abs/2511.10647), [arXiv 2406.09414](https://arxiv.org/abs/2406.09414)
- VGGT outputs include camera parameters, depth, point maps and 3D tracks, all usable as labels — [arXiv 2503.11651](https://arxiv.org/abs/2503.11651)
- A 2025 Sensors paper distills a foundation depth model into a ViT-Small student for RGB+IMU VIO; I did not open it — [PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12431346/) (SEEN-IN-SEARCH-ONLY)
- DPVO and DBA-Fusion are patch/dense-flow trackers with differentiable BA, so their per-edge flow/uncertainty is distillable — [arXiv 2208.04726](https://arxiv.org/abs/2208.04726), [arXiv 2403.13714](https://arxiv.org/abs/2403.13714)

### Inferences
- Important caveat: we have unlimited simulated ground truth, so a teacher adds value only where its pseudo-labels beat what we can already supervise. Teacher labels are redundant for pose in sim; they matter mostly for (a) transfer to real/server images, and (b) as a hard-case miner (find flights where the teacher disagrees with our student/VIO).
- Our repo notes show learned architecture/data changes gave at most 1.2-1.5x; a distilled front end that is only as good as the teacher is unlikely to reach 0.5 m on its own.

### Gaps
- No published example of distilling a 3DFM into a sub-10 MB, int8, CPU/wasm tracker that preserves drone VIO accuracy.

## 6. Realistic speed at 320x240 and 8xH100 feasibility

### Takeaway
No source gives 320x240 timings. Published speeds: MASt3R-SLAM about 15 FPS on RTX 4090; DBA-Fusion about 1.5x real time at 5 Hz images on 3090; DPV-SLAM 1-4x real time. A 20 Hz stream (60 s = 1200 frames) is within reach of offline GPU processing on H100 for all of them; none runs on wasm.

### Cited Findings
- MASt3R-SLAM 14.6 FPS avg on 4090 — [HTML v2](https://arxiv.org/html/2412.12392v2)
- DBA-Fusion 1.47x/1.51x/1.62x real time at 5 Hz on RTX 3090, per-stage about 10-32 ms — [HTML](https://arxiv.org/html/2403.13714v1)
- DPV-SLAM 5-7 GB, 1-4x real time — [arXiv 2408.01654](https://arxiv.org/abs/2408.01654)
- Depth Pro 0.3 s per 2.25 MP image — [arXiv 2410.02073](https://arxiv.org/abs/2410.02073)
- VI3 test-time refinement 48-128 s per clip on RTX 5090 — [alphaxiv](https://www.alphaxiv.org/abs/2609.03824)
- Host check: 8x H100 80GB, 7 idle; gpu_kit only produces flights (README), so a model runner is new work — local repo

### Inferences
- A 20-flight test is 24,000 frames; VGGT/pi3 windows of 16-32 frames at 320x240 on one H100 should take minutes per flight; the cost is integration, not compute.
- DBA-Fusion runs at 5 Hz; our 20 Hz stream must be subsampled to keyframes, which is fine for a teacher but loses fast-motion information.

### Gaps
- No measured numbers for VGGT/pi3/CUT3R at 320x240.

## 7. Ranking by expected unaligned-ATE benefit, with honesty about evidence

Ranking is my judgment, estimates not results. "Benefit" is toward our guarded-VIO pipeline mean ATE.

1. DBA-Fusion (or DPVO plus our own IMU factors) as a fourth guard guest and teacher. Evidence: only tested method here that is metric, IMU-fused and shows large gains over visual-only on a handheld/car dataset (TUM-VI 1.02 m vs 38.82 m on magi3); open code; GPU-only but runs offline. Weakness: 5 Hz, no EuRoC/drone numbers in the paper, evidence level moderate. Expected benefit: small on median, possible on tail flights where VINS/OpenVINS fail init.
2. VGGT or pi3 windows with IMU anchoring (VI3-style scale/gravity, or a MASt3R-Fusion/FoundationVIO-style factor graph), used as relative-rotation/direction oracle and init helper. Evidence: weak, recent (Sep-Oct 2026), short-clip numbers, abstracts only for fusion papers. Highest upside if relative rotation beats gyro integration; unlikely to beat VINS median.
3. MASt3R-SLAM as monocular teacher for relative poses/tracks. Evidence: strong Sim(3) accuracy (0.041 m EuRoC) but no IMU, no metric scale, 15 FPS on 4090. Useful for diagnosing, not for unaligned ATE.
4. CUT3R/StreamVGGT/Spann3R as causal students. Evidence: no odometry accuracy read, no IMU; mainly interesting as distillation recipe (StreamVGGT).
5. Metric depth (Depth Pro, UniDepth, Metric3Dv2, DA2/DA3) for scale. Our scale comes from IMU, and our error is yaw-dominated; low expected benefit (inference).
6. Gaussian splat / NeRF SLAM (MonoGS 3 fps, Splat-SLAM, Photo-SLAM; GS-ICP needs RGB-D). Evidence is on indoor RGB-D benchmarks; not worth testing.
7. MAC-VO: stereo, not applicable.

### Recommended 1-2 day falsification test
Run on about 20 benchmark-like flights from the existing selected pool (gen/raw-fast/selected, read-only). Include the worst VINS/OpenVINS tail flights.
- Arm A: DBA-Fusion (or DPVO with our IMU) at keyframes; report raw (unaligned) mean ATE, per-flight, and tail behaviour versus VINS-Mono/OpenVINS on the same flights.
- Arm B: VGGT (and pi3) on 16-32 frame sliding windows at 320x240, IMU-anchored scale/gravity (VI3-style initial-velocity-free scale fit from preintegration), chained with IMU. Report window-level relative rotation error vs gyro integration and 60 s unaligned ATE.
- Falsification criterion: arm is dropped if the oracle-min with existing guests (0.759 m baseline in the repo plan) improves by under about 5% or if tails are not reduced.
Feasibility: compute is trivial on 8xH100; main risk is integration time (installing models, sim camera intrinsics/distortion, grayscale input, DBA-Fusion needs GTSAM build).

### Gaps
- Licenses (several weights are non-commercial) not checked; matters for deployment only if the student is distilled from them.
- I did not read the repo's own implementation files beyond the two report headers, so reuse of evaluation scripts is untested.
