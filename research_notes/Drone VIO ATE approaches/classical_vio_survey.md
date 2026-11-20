# Classical / optimization-based / hybrid VIO for a mediocre-IMU drone, ATE metric (state as of 2026)

Scope note: about 14 search/fetch calls. Numbers below were read from fetched pages or search snippets. Claims I could not source are in Gaps. Several 2026 arXiv IDs came only from search snippets and are flagged as unverified. Existing literature mostly reports aligned (SE3/yaw+pos) ATE on EuRoC, and the project metric is unaligned mean ATE on ~60 m flights, so published numbers are only a relative guide.

## Q1. Which methods report the best ATE on EuRoC / TUM-VI / UZH-FPV / Blackbird?

### Takeaway
On EuRoC, loop-closing optimization systems (OKVIS2, ORB-SLAM3) reach about 3-5 cm, and pure VIO sits at roughly 5-14 cm. These figures are the ceiling, not a drone-flight expectation. For UZH-FPV and Blackbird, which are fast and aggressive, errors are 10-100x larger (decimeters to metres). I found no clean public head-to-head UZH-FPV ATE table for OpenVINS, VINS-Fusion, Basalt and DM-VIO.

### Cited Findings
- EuRoC stereo-inertial ATE RMSE (m), alignment by position+yaw only. Averages: OKVIS2 non-causal 0.031, ORB-SLAM3 0.035, OKVIS2 causal 0.048, VINS-Fusion 0.138. Basalt per-sequence is 0.02-0.10 with V2_03 missing (no average). Basalt, VINS-Fusion and ORB-SLAM3 values are copied from the ORB-SLAM3 paper. Hardest sequences: MH_04/MH_05 (OKVIS2 causal 0.089/0.112, VINS-Fusion 0.28). — [OKVIS2 paper, ar5iv](https://ar5iv.labs.arxiv.org/html/2202.09199), [arXiv](https://arxiv.org/pdf/2202.09199)
- ORB-SLAM3 reports stereo-inertial 0.035 m and monocular-inertial about 0.043 m average on EuRoC (median of runs; secondary summary). An independent blog reports the public repo does not reproduce the published mono results. — [ORB-SLAM3](https://arxiv.org/pdf/2007.11898), [summary](https://raw.githubusercontent.com/changh95/visual-slam-roadmap/main/level-03-monocular-slam/orb-slam3.md), [reproduction critique](https://pkok.github.io/2021/05/06)
- DM-VIO (monocular, photometric, delayed marginalization plus pose-graph BA for IMU initialization) beats ROVIO, VINS-Mono, OKVIS and Basalt (stereo) on TUM-VI RMSE. Example: corridor5 0.16 m vs Basalt 0.37 and ROVIO 2.09. Basalt wins 2 sequences. No loop closure. Tested on EuRoC, TUM-VI, 4Seasons. — [DM-VIO paper](https://arxiv.org/pdf/2201.04114), [project](https://cvg.cit.tum.de/dm-vio)
- Basalt stereo-inertial ranges about 0.04-0.13 m on EuRoC and 0.02-0.42 m on TUM-VI, vs VINS-Fusion 0.07-0.30 and 0.04-1.56 (as tabulated in a secondary 2025 paper). — [SP-VINS](https://arxiv.org/pdf/2511.18756), [Basalt](https://github.com/VladyslavUsenko/basalt)
- OKVIS2-X (2025) is reported competitive with ORB-SLAM3 on EuRoC. V203 (motion blur/exposure) gives large error for both. — [OKVIS2-X](https://arxiv.org/pdf/2510.04612)
- Blackbird ATE (m) from the HDVIO paper, for the authors' own optimization VIO baseline: slow trajectories 0.17-0.20 m at 1-3 m/s, 0.9-1.8 m at 5-8 m/s (Egg 8 m/s: 1.79). A drone dynamics factor lowers these: VIMO 0.18-1.57, HDVIO 0.16-1.06. Real-world lemniscate with drag board: VIO 0.38 / VIMO 0.34 / HDVIO 0.30 m. — [HDVIO](https://arxiv.org/html/2306.11429v2)
- UZH-FPV: the OpenVINS authors evaluated on it, noting strong optical flow makes feature tracking hard, and used online time-offset, intrinsics and extrinsic calibration. — [OpenVINS Geneva et al.](https://udel.edu/~pgeneva/downloads/papers/r10.pdf), [dataset](https://fpv.ifi.uzh.ch/)
- UZH-FPV mean APE, indoor_forward sequences, VINS-Fusion average 4.59 m (max 9.60), vs the same plus learned inertial displacement constraints (ICD-Net) 2.79 m (max 5.35), a 39% mean reduction. Per sequence: fwd_6 5.30 to 1.70, fwd_3 3.11 to 1.98, fwd_9 5.35 to 4.69. Only one baseline compared. — [ICD-Net](https://arxiv.org/html/2512.00037v1)
- A learned-inertial-odometry paper claims its EKF ranks first among open-source systems on UZH-FPV (own framing; table not read, PDF unreadable). — [Learned Inertial Odometry for Drone Racing](https://arxiv.org/pdf/2210.15287)
- A 2026 RL-frontend paper lists OpenVINS default at 0.3148 on UZH-FPV; the columns and units were unlabeled in the snippet, so do not rely on it. — [arXiv 2603.21785](https://arxiv.org/pdf/2603.21785)

### Inferences
- For wasm, the practical ranking by accuracy-to-complexity is a stereo/mono sliding-window optimizer (OKVIS2/Basalt-like, or VINS-Fusion with fixes), with a filter (OpenVINS MSCKF) as the lightest alternative. DM-VIO is strongest in monocular accuracy on TUM-VI because of its initialization, but it is photometric and uses heavy SSE/threads (not verified for wasm).
- Published EuRoC ATE (3-14 cm) is for 50-100 m indoor flights at slow speed. Blackbird shows ATE grows with speed, and a ~0.5 m goal on ~60 m aggressive flights is plausible but nowhere guaranteed by these tables.

### Gaps
- Primary UZH-FPV/Blackbird ATE tables for OpenVINS, Basalt, DM-VIO, Kimera: not found. Several PDFs were unreadable via the fetch tool (Learned Inertial Odometry for Drone Racing; DM-VIO EuRoC numbers).
- Exact monocular-inertial EuRoC numbers for VINS-Mono, OpenVINS and DM-VIO: not retrieved.

## Q2. Which are most robust against initialization failure and catastrophic divergence?

### Takeaway
Initialization is the usual failure source for monocular VIO. The newest ideas are IMU-aware pose-graph initialization (DM-VIO), probabilistic normal epipolar constraints with a gyro-bias estimator (2024), and learned depth or feed-forward 3D priors (2022-2026). Stereo or depth removes the scale problem. Mean ATE is dominated by outliers, so rejecting and re-initializing on failure matters more than shaving the typical error.

### Cited Findings
- VINS-Mono style initialization aligns metric IMU preintegration with a visual-only SfM, and is fragile under low excitation. — [VINS-Mono](https://arxiv.org/pdf/1708.03852)
- DM-VIO: pose-graph bundle adjustment for IMU initialization, which captures the full photometric uncertainty and improves scale estimation. Delayed marginalization lets IMU information flow into already-marginalized states, and costs only 0.44 ms (0.8%) in the keyframe thread. — [DM-VIO](https://arxiv.org/pdf/2201.04114)
- PNEC-based initialization (Oct 2024): gyro-bias estimator via probabilistic normal epipolar constraint, then velocity/gravity/scale. Reported mean scale RMSE 0.118 and gravity error 1.03 deg on EuRoC 10-keyframe segments, about 29% lower gravity error (baseline unspecified). Compared only against VINS-Mono and DRT variants, so no ATE. Code: github.com/MUCS714/DRT-PNEC. — [arXiv 2410.19473](https://arxiv.org/html/2410.19473v2)
- Learned monocular depth priors in initialization make it faster and more robust in low-excitation cases. — [Google AR, 2204.09171](https://arxiv.org/pdf/2204.09171)
- Feed-forward 3D model initialization (RSS 2026, per snippet): over 90% success on hard scenarios, no feature association, code at github.com/Yuantai-Z/FF-VIO-Init (unverified, from snippet). — [arXiv 2605.17327](https://arxiv.org/pdf/2605.17327)
- Line-feature/vanishing-point structureless initialization exists (2026, snippet only). — [arXiv 2609.21186](https://arxiv.org/pdf/2609.21186)
- OKVIS2/ORB-SLAM3 hit V2_03 (blur/exposure) hardest, so failures concentrate on specific hard sequences. — [OKVIS2-X](https://arxiv.org/pdf/2510.04612)

### Inferences
- Wasm-friendly robust options: stereo (if available) or a monocular initializer that delays committing scale until sufficient parallax and acceleration excitation, plus a PNEC or DM-VIO-style gyro-bias-first step. Learned or foundation depth for init needs a neural net at runtime, which conflicts with no-GPU unless a small distilled model is used. An offline-trained heavy model can instead tune the thresholds.
- I found no paper that quantifies heavy-tail ATE across many runs for these methods. That heavy-tail claim is my inference.

### Gaps
- Direct comparative failure rates (init success) across VINS-Mono, ORB-SLAM3, OpenVINS and DM-VIO were not found.

## Q3. Best practices to reduce mean ATE on short (~60 m) aggressive flights with unknown scale

### Takeaway
Evidence supports: (1) online time-offset and calibration, (2) FEJ/observability-consistent estimation, (3) model-aided or learned inertial constraints (drag, learned velocity, learned covariance), (4) good initialization, and (5) structural priors where the scene allows. Learned front-ends give only modest gains.

### Cited Findings
- FEJ gave a significant precision gain on EuRoC in mono and stereo in a community OpenVINS ablation. Online intrinsic/extrinsic/dt calibration gave no clear gain there because EuRoC's calibration is good. In simulation with a bad initial calibration, online calibration restored ATE to 0.139 m, against 0.134 m with true calibration (fork README, not peer-reviewed). — [symao/open_vins](https://github.com/symao/open_vins), [OpenVINS](https://udel.edu/~pgeneva/downloads/papers/r10.pdf)
- Time offset matters for high dynamics: OpenVINS state-relevant temporal calibration is compared against a state-irrelevant variant on EuRoC and high-dynamic sequences. TON-VIO proposes learned online time-offset modelling. — [arXiv 2501.01788](https://arxiv.org/html/2501.01788v1), [TON-VIO](https://arxiv.org/pdf/2403.12504)
- Drag/dynamics aiding. VIMO adds point-mass dynamics residuals, but it neglects drag, which ends up in the external-force estimate. HDVIO adds a TCN of thrust and gyro history (about 180 Hz on a Jetson TX2, 7 conv layers, 100 ms buffer) and improves ATE up to 33% over VIMO (Blackbird, e.g. Mouse 1.10 to 0.76 to 0.36 m). Naively feeding the state into a drag model risks a feedback-loop divergence. — [HDVIO](https://arxiv.org/html/2306.11429v2), [HDVIO2.0](https://arxiv.org/pdf/2603.00597)
- Linear drag in the velocity dynamics improves estimation (Leishman, Jackson et al.). A loosely coupled EKF with linear propeller drag bounds the velocity error orthogonal to the propeller shafts and the attitude error. — [Xu & de Croon](https://repository.tudelft.nl/record/uuid:c07670f7-7ee4-4a18-a0f0-d3366d99ac8f), [HDVIO refs](https://arxiv.org/html/2306.11429v2)
- Learned inertial constraints inside the optimizer: ICD-Net (velocity-displacement plus log-variance heads fused as factors in VINS-Fusion) cuts mean UZH-FPV APE 4.59 to 2.79 m. — [ICD-Net](https://arxiv.org/html/2512.00037v1)
- Learned IMU bias prediction into an invariant MSCKF (2025). Learned IMU noise and uncertainty: AirIMU (2023), VIO-DualProNet (learned process noise covariance, 2023). — [2505.06748](https://arxiv.org/pdf/2505.06748v2), [AirIMU](https://arxiv.org/html/2310.04874v4), [DualProNet](https://arxiv.org/html/2308.11228v2)
- Learned front-ends: SuperVINS (SuperPoint+LightGlue in VINS-Fusion) mixed, with MH05 improved 39.6% but MH02 worse (0.046 to 0.097) and better in 6/11 sequences. DL-VINS-Factory (July 2026, snippet): ALIKED+LightGlue gives only 5% ATE reduction in mono and 7% in stereo with loops, vs GFTT+LK, and LightGlue helps more as inter-frame viewpoint change grows. — [SuperVINS](https://arxiv.org/pdf/2407.21348), [DL-VINS-Factory](https://arxiv.org/pdf/2607.01757)
- Learned depth priors: MDE-VIO (VINS-Mono + monocular depth as a prior, because raw depth has scale inconsistency vs IMU); FoundationVIO and VIDAR (2026, GPU) use foundation-model depth with scale-consistency factors. No ATE numbers retrieved. — [MDE-VIO](https://arxiv.org/html/2602.11323), [FoundationVIO](https://arxiv.org/pdf/2610.14951), [VIDAR](https://arxiv.org/pdf/2607.17171)
- Manhattan/structural: StructVIO (line features, Atlanta world), MLINE-VINS (2025), and vanishing points as rotation/yaw observations. Authors argue rotation drift dominates long-term error and the Manhattan assumption supplies the missing long-term yaw constraint. Quantitative results not verified. — [StructVIO](https://arxiv.org/pdf/1810.06796), [MLINE-VINS](https://arxiv.org/html/2503.01571v1), [PL-VINS comparison](https://arxiv.org/pdf/2105.04064)
- Loop closure: OKVIS2 non-causal (0.031 m) vs causal (0.048 m) vs VIO-only (about 0.07 m per snippet) shows loop closure/global optimization gives roughly 35-55%. Not applicable if the flight never revisits. — [OKVIS2](https://arxiv.org/pdf/2202.09199)

### Inferences
Ranked menu, feasibility for C/C++ wasm (no GPU), my judgment:
1. Sliding-window optimization VIO (OKVIS2/Basalt/VINS-Fusion style, Ceres-free custom Gauss-Newton). Fully C++ and wasm-feasible. Highest evidence for ATE.
2. Robust init plus failure recovery: delay scale commit until excitation, gyro-bias-first (PNEC), reinit on divergence, Mahalanobis gating, Huber/Cauchy on visual and IMU residuals. Highest leverage on heavy-tailed mean ATE (the tail claim is inference). Wasm-feasible.
3. FEJ/observability-consistent linearization plus online time offset. Cheap, wasm-feasible.
4. Linear drag/velocity aiding (rotor-drag term from Leishman/Jackson/Xu-de Croon) as an EKF or factor, with parameters tuned offline on GPU. Wasm-feasible and offline-trainable. A tiny TCN or MLP residual (HDVIO) is feasible in wasm only if small (HDVIO net runs on a TX2 embedded GPU; not verified on CPU).
5. Learned covariance or displacement factors (ICD-Net, AirIMU style): train offline, run a small net in wasm. Moderate evidence (39% APE on UZH-FPV, one baseline).
6. Hover/ZUPT detection (no source found; see gaps), and Manhattan/vanishing-point yaw priors (only if the environment is structured).
7. Learned front-end (SuperPoint/LightGlue) is a poor wasm fit, with only about 5-7% gain. Foundation depth is GPU-bound, so use only offline for training or tuning.

### Gaps
- No source found for zero-velocity/hover detection in drone VIO, RINS-W, robust-kernel benchmarks, or specific short-flight/unknown-scale guidance. The OpenVINS "tricks" list was not found as a document. Degeneracy handling for pure rotation or low parallax was not covered in any retrieved source.
- Whether wasm builds exist for any of these systems: not searched.
