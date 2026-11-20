# Learned and hybrid learned VIO/IO for drones (2022-2026): ranked approaches to minimise mean ATE

Scope note: about 17 searches/fetches, mostly abstract-level. Many numbers below come from search summaries, not full-paper tables. Items not verified in a primary table are flagged. Project context (from the caller's memory): the metric is mean unaligned ATE (metres, no Sim(3) alignment), the goal is ~0.5 m on ~60 m flights, the runtime is C/C++ wasm, and training compute is large.

## Q1. Which approaches give the best reported ATE and generalise, with numbers and citations?

### Takeaway
Two families matter. (a) Drone-specific learned inertial odometry (AirIO, AI-IO, Cioffi's TCN-EKF) with body-frame input, attitude encoding and an EKF is the strongest IMU-only option, but its reported ATE (~0.4 m seen, ~1.3 m unseen on Blackbird, ~3 m on EuRoC) is not yet at the 0.5 m mean level on unseen data. (b) Deep dense or patch VO/SLAM trained only on synthetic data (DROID-SLAM, DPVO, DPV-SLAM) gets ~0.02-0.1 m on EuRoC, but those figures are scale-aligned. Metric scale needs IMU or a metric-depth prior, which is exactly the part that determines unaligned ATE.

### Cited Findings
- AirIO (RA-L; Qiu, Scherer et al.) keeps IMU data in the body frame and encodes attitude explicitly. It claims 66.7% average gain from the body-frame change alone, a further 23.8% from attitude encoding, and up to 86.6% over prior art, using IMU only. — [arXiv abstract](https://www.arxiv.org/abs/2501.15659), [project page](https://air-io.github.io)
- AirIO ATE (m), from the paper's Table II as extracted by a fetch tool, so verify against the PDF. Blackbird seen: AirIO net 0.486, AirIO+EKF 0.403, TLIO 1.189, RoNIN 2.193, IMO 0.929, AirIMU 7.084, raw baseline 27.475. Blackbird unseen: AirIO 1.300 (EKF 1.309), TLIO 3.478, IMO 9.015, RoNIN 13.487. EuRoC test: AirIO 3.846 (EKF 3.177), RoNIN 6.75, TLIO 6.969. — [arXiv v2](https://arxiv.org/html/2501.15659v2)
- The same fetch says the EKF helps on seen data and EuRoC but not on unseen Blackbird. The text claims 52.9% and 54.4% gains over RoNIN and TLIO on EuRoC, while the table averages imply about 43% and 45%, so the paper is internally inconsistent. — [arXiv v2](https://arxiv.org/html/2501.15659v2)
- AirIO architecture (fetch summary): CNN attitude encoder plus a body-frame IMU encoder, bidirectional GRU, MLP heads for body-frame velocity and its uncertainty. Model size is 2.5 MB (regular), 0.64 MB or 0.175 MB (light variants). Training windows are 1000 IMU frames. Inference takes 29 ms on an RTX 2060 and 74 ms on a Jetson Orin. Closed-loop flight is listed as future work. — [arXiv v2](https://arxiv.org/html/2501.15659v2)
- AI-IO (ICRA 2026) is a transformer velocity estimator for quadrotors with an uncertainty-aware EKF. Adding rotor-speed measurements improves velocity accuracy by 36.9%, and the transformer adds a further 22.4%. It comes with a real agile-flight dataset (baseline not named in the abstract; no ATE found). — [arXiv 2603.00597](https://arxiv.org/abs/2603.00597)
- Cioffi et al., "Learned Inertial Odometry for Autonomous Drone Racing" (RA-L 2023): a TCN inside a model-based filter, IMU plus thrust as inputs. It beats filter and optimisation VIO and TLIO on a racing quadrotor, and is comparable to VIO that knows gate positions. Code is public and the network is trained on Blackbird. Numeric ATE was not retrievable. — [arXiv](https://arxiv.org/abs/2210.15287), [code](https://github.com/uzh-rpg/learned_inertial_model_odometry)
- Tartan IMU (CVPR 2025): foundation model pretrained on over 100 h of multi-platform data (car, human, dog, drone) with per-platform heads. Claims 36% ATE gain over specialised models. LoRA adaptation with ~1.1M parameters; online test-time adaptation reported at 200 FPS. The HF card gives a ResNet-1D plus 2-layer LSTM backbone, weights non-commercial. — [CVPR](https://openaccess.thecvf.com/content/CVPR2025/html/Zhao_Tartan_IMU_A_Light_Foundation_Model_for_Inertial_Positioning_in_CVPR_2025_paper.html), [HF](https://huggingface.co/Tartan-IMU/TartanIMU)
- AirIMU: differentiable preintegration with learned noise correction and learned covariance. 17.8% better preintegration on Subt-MRS, 31.6% better IMU-GPS pose-graph accuracy from learned uncertainty. This is a module, not a full odometry system. — [arXiv 2310.04874](https://arxiv.org/html/2310.04874v4)
- DROID-SLAM is trained once on synthetic TartanAir only and applied zero-shot to EuRoC. A secondary source puts monocular EuRoC average ATE at 0.022 m. DPVO is ~0.105 m and DPV-SLAM (loop closure) 0.024 m. The alignment is scale-aligned in the DPVO tables. — [DROID-SLAM](https://arxiv.org/pdf/2108.10869), [DPVO](https://arxiv.org/pdf/2208.04726), [DPV-SLAM](https://arxiv.org/pdf/2408.01654), [secondary summary](https://raw.githubusercontent.com/changh95/visual-slam-roadmap/main/level-05-deep-learning/droid-slam.md)
- DBA-Fusion (RA-L 2024) feeds DROID-style dense BA Hessians into a GTSAM factor graph with IMU (plus GNSS and wheel speed), giving real-time metric-scale VIO. The abstract gives no ATE in the retrieved text. — [arXiv 2403.13714](https://arxiv.org/abs/2403.13714v1), [code](https://github.com/GREAT-WHU/DBA-Fusion)
- MegaSaM builds on DROID-SLAM, adds monocular-depth priors, motion probability maps and uncertainty-aware global BA. Strong robustness on casual video. Scale and ATE on drone data were not found. — [arXiv 2412.04463](https://arxiv.org/abs/2412.04463)
- Newer learned VIO: DB-VIO claims 33.5% (37.4% with depth cues) better EuRoC ATE than SS-VIO. A dual-agent RL VIO (Nov 2025) claims the best average ATE among GPU VO/VIO systems. A plug-and-play learned IMU-bias factor reports 46% ATE gain when added to VIO. All self-reported against the authors' own baselines, and the DB-VIO arXiv ID (2607.22123) looks anomalous and should be verified before citing. — [DB-VIO](https://arxiv.org/pdf/2607.22123), [RL VIO](https://arxiv.org/pdf/2511.21083v2), [IMU bias factor](https://arxiv.org/pdf/2503.12527)
- VIFT (causal transformer VIO, with RPMG rotation loss) claims SOTA among learned monocular VIO on KITTI. Car-domain, not drone. — [arXiv 2409.08769](https://arxiv.org/abs/2409.08769v1)
- Feed-forward 3D models: VGGT-SLAM needs SL(4) alignment because VGGT has no metric scale. MASt3R-Fusion adds IMU/GNSS for metric scale. A Feb 2026 study of DROID/MASt3R/VGGT-SLAM reports intra-session scale drift hidden by Sim(3)-aligned ATE. No EuRoC ATE found. — [VGGT-SLAM](https://arxiv.org/html/2505.12549v2), [MASt3R-Fusion](https://arxiv.org/html/2509.20757v3), [scale-drift study](https://arxiv.org/pdf/2602.18174)
- Classical drag-aided IMU velocity observability on multirotors: drag is first-order dominant in the accelerometer, making body velocity observable from IMU alone. No learned-drag-model paper was found. — [Martin and Sarras](https://arxiv.org/abs/1510.03249), [Wang et al. IROS 2017](https://drone.sjtu.edu.cn/static/assets/pdfs/2017IROS-Aerodynamic.pdf)

### Inferences
- The strongest idea for a drone is probably a hybrid: a deep VO/BA front end (DROID/DPVO-style, trained on synthetic data) for geometry, plus a drone-specific learned inertial velocity prior (AirIO/AI-IO-style) for metric scale and gravity/velocity constraints, fused in a filter or factor graph (DBA-Fusion-style).
- IMU-only networks at ~1.3 m on unseen Blackbird (~3-4 min flights) imply roughly that scale of error on unseen 60 m flights. They are unlikely to hit 0.5 m mean alone, but they are a good velocity and scale prior.
- Reported EuRoC numbers for deep SLAM are scale-aligned and not comparable to the unaligned metric used here.

### Gaps
- Primary-table ATE for Cioffi et al., AI-IO and DBA-Fusion were not retrieved.
- No unaligned (non-Sim(3)) ATE for DROID/DPVO/MegaSaM was found.
- No learned-drag-model or MIMU-specific paper was found. DeepVIO/SelfVIO/Kimera-VIO and CoTracker/LightGlue/SEA-RAFT were not searched; this scope was not covered.

## Q2. Which give the largest gains from extra compute (data/model scaling, ensembling, distillation)?

### Takeaway
The evidence is that synthetic-data scale and multi-domain pretraining are the best-supported compute sinks (DROID-SLAM zero-shot from TartanAir, Tartan IMU 36% from multi-platform pretraining). No paper found gives a clean scaling law for inertial or VIO for drones, so that is an open bet and should be measured on the project's own simulator.

### Cited Findings
- DROID-SLAM trained only on synthetic TartanAir generalises zero-shot to real EuRoC and other benchmarks. — [DROID-SLAM](https://arxiv.org/pdf/2108.10869)
- Tartan IMU: 100+ hours of multi-platform pretraining gives 36% ATE gain over specialised models. LoRA with 1.1M parameters adapts to new tasks. — [CVPR 2025](https://openaccess.thecvf.com/content/CVPR2025/html/Zhao_Tartan_IMU_A_Light_Foundation_Model_for_Inertial_Positioning_in_CVPR_2025_paper.html)
- Architecture swaps are cheap gains: AI-IO's transformer gives 22.4% over previous results and rotor speed adds 36.9%. AirIO's representation change gives 66.7%. — [AI-IO](https://arxiv.org/abs/2603.00597), [AirIO](https://www.arxiv.org/abs/2501.15659)
- RIO uses deep ensembles for predictive uncertainty and test-time training. EqNIO notes that the ensemble TTT is computationally heavy. — [RIO](https://arxiv.org/pdf/2111.11676), [EqNIO](https://arxiv.org/html/2408.06321v2)
- Mixture-of-experts: MosaicIMU (2606.09355) composes carrier experts for cross-platform generalisation (abstract-level only). — [arXiv](https://arxiv.org/pdf/2606.09355)

### Inferences
- Model size is not the bottleneck: AirIO is 0.17-2.5 MB, so distilling a big teacher (ensemble or transformer) into a small GRU/TCN student for wasm is plausible. No cited distillation result for IO was found.
- Because the simulator can scale arbitrarily, domain randomisation (IMU noise/bias, drag, mass, motor dynamics, wind, rendering) is probably the highest-return use of compute, but this is untested in the sources found.

### Gaps
- No sim-to-real scaling study for learned IO on drones (a search for it found none; NeuRIO, arXiv 2609.21707, is a possible lead on zero-shot sim-to-real relative IO but was not read).
- No published distillation of deep VIO into small networks was found.

## Q3. Which are most robust to heavy-tail failures, and what reduces mean rather than median ATE?

### Takeaway
Little direct evidence on heavy tails exists. The usable tools are learned uncertainty with an EKF gate, robust (Huber-style) uncertainty-aware losses, ensembles, and test-time adaptation, but each has caveats.

### Cited Findings
- AirIO's EKF helps on seen data (0.486 to 0.403 m) but not unseen (1.300 to 1.309 m), so filtering does not fix out-of-distribution failures. — [arXiv v2](https://arxiv.org/html/2501.15659v2)
- X-IONet's Huber-Gaussian uncertainty loss: ablation removing uncertainty-awareness raises ATE/RTE by 16.7-69.9%. — [arXiv 2511.08277](https://arxiv.org/pdf/2511.08277)
- KISS-IMU: GMM-based motion balancing and uncertainty-aware inference to reduce bias toward dominant patterns. — [arXiv 2603.06205](https://arxiv.org/pdf/2603.06205)
- RIO: velocity variance from the ensemble decides when to update or restore parameters in test-time training; inappropriate updating causes drift. — [RIO](https://arxiv.org/pdf/2111.11676)
- UL-VIO test-time adaptation updates only BatchNorm parameters with pseudo-labels from inertial output. — [arXiv 2409.13106](https://arxiv.org/abs/2409.13106v1)
- AirIMU: learned covariance improves downstream pose graph accuracy by 31.6%. — [arXiv 2310.04874](https://arxiv.org/html/2310.04874v4)
- MegaSaM's uncertainty-aware global BA targets cases where camera parameters are poorly constrained. — [arXiv 2412.04463](https://arxiv.org/abs/2412.04463)
- DROID-SLAM reported zero failures on EuRoC (secondary source). — [summary](https://raw.githubusercontent.com/changh95/visual-slam-roadmap/main/level-05-deep-learning/droid-slam.md)

### Inferences
- Mean ATE is dominated by the few worst flights. Priorities that follow: (1) mine hard sim scenarios (aggressive manoeuvres, drag/wind outliers, vision dropout) and oversample them; (2) use trajectory/velocity-integral losses on windows near the flight length so errors accumulate during training; (3) a vision-IMU consistency check, falling back to the more reliable channel when ensemble variance spikes; (4) loss on log-error or a tail-weighted objective. These are suggestions drawn from the cited mechanisms, not from a paper that tested them for mean ATE.

### Gaps
- No paper found that explicitly optimises mean over median ATE or studies heavy-tail ATE for drones.
- Ensemble gains in numbers were not found.

## Q4. Realistic expectations for ~0.5 m mean ATE on ~60 m flights?

### Takeaway
0.5 m on 60 m is ~0.8% drift. This is plausible with a visual-inertial hybrid. IMU-only is borderline and risky, with the published numbers suggesting ~1.3 m or worse on unseen data, though those flights are longer and different.

### Cited Findings
- Best IMU-only drone result found: 0.40 m (seen) and 1.30 m (unseen) mean ATE on Blackbird; 3.2-3.8 m on EuRoC (unaligned, short indoor flights). — [AirIO](https://arxiv.org/html/2501.15659v2)
- Deep SLAM scale-aligned EuRoC: 0.022-0.105 m. — [DPV-SLAM](https://arxiv.org/pdf/2408.01654)
- Sim(3)-aligned ATE can hide scale distortion. — [scale-drift study](https://arxiv.org/pdf/2602.18174)

### Inferences
- Scale-aligned deep VO error of 0.02-0.1 m is tiny compared with 0.5 m, so under unaligned scoring the dominant error is scale and gravity-alignment/yaw, not shape. Fixing scale with an IMU-based or learned metric prior is therefore the key lever. This is an inference, not a measured result.
- A realistic target: ~0.3-0.7 m mean for a well-tuned hybrid on in-distribution sim flights, and a 1-2x degradation on real or out-of-distribution flights. Treat it as an estimate, not a sourced figure.

### Gaps
- No benchmark with 60 m drone flights and unaligned ATE for learned methods was found; the repo's own server-calibrated anchors should be the reference.

## Ranked menu (inference-based; ranking is mine, evidence cited above)

1. Hybrid: DROID/DPVO-style deep VO or BA, trained on large synthetic data, fused with learned body-frame velocity and uncertainty from an AirIO/AI-IO-style net, in an EKF or factor graph (DBA-Fusion pattern). Best expected ATE; the heaviest part to distil to wasm. Distils: IO net directly (<3 MB); the VO front end partially (small flow/patch net plus a classical solver).
2. Drone-specific learned inertial velocity net (body-frame input, attitude encoding, uncertainty head, GRU or small transformer) plus EKF. Cheap, wasm-friendly, a strong scale prior. Largest unknown is out-of-distribution robustness.
3. Large-scale sim pretraining with domain randomisation, then heavy-tail oversampling. Compute-friendly; evidence is indirect (DROID, Tartan IMU).
4. Teacher-student distillation: large transformer/ensemble teacher to a small GRU/TCN student. Plausible given tiny AirIO sizes; no direct citation.
5. Learned preintegration/covariance (AirIMU) as a drop-in module for an existing VIO. Gains 17.8-46%, documented in different settings.
6. Test-time adaptation (RIO/Tartan IMU/UL-VIO). Risky: can drift if updates are wrong; use only with a variance gate.
7. Foundation depth/pose priors (MegaSaM, MASt3R/VGGT): good as teachers or scale priors; heavy, with unproven metric scale on drones.
