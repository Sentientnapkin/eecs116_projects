# Learned velocity, inertial and visual priors for initializing and aiding VIO/EKF filters, and how to fuse them with proper uncertainty

Context for the reader: the target is a small embedded EKF with a 20 Hz monocular camera, a 200 Hz IMU, simulated drone flights, and a learned CNN (about 1.8 M MAC) that estimates velocity from two frames plus IMU. All numbers below come from the primary papers (PDF text read directly) unless marked otherwise.

## Q1. TLIO (Liu et al., RA-L 2020): learned displacement plus covariance fed into an EKF

### Takeaway
TLIO feeds a 1D-ResNet18's 3D displacement and its diagonal covariance (from 1 s of 200 Hz gravity-aligned IMU) into a stochastic-cloning EKF as a relative-position measurement, gated by a 3-DoF chi-square test. The learned per-sample covariance, not the MSE accuracy, is what makes the filter beat RoNIN-style integration. Training is two-stage (MSE, then Gaussian NLL), and the covariance was validated with 3-sigma coverage and Mahalanobis/chi-square statistics on about 60k test samples.

### Cited Findings
- TLIO is arXiv:2007.01867, IEEE RA-L 2020 (accepted June 2020), DOI 10.1109/LRA.2020.3007421. — [arXiv](https://arxiv.org/abs/2007.01867)
- Architecture: a 1D version of ResNet18. The input is N×6 IMU samples (N = 200 at 200 Hz, so 1 s), rotated into a gravity-aligned frame built from the orientation at the start of the window. Two independent fully connected heads output the displacement d̂ (3) and uncertainties û (3) that parametrize the diagonal of the covariance. — [TLIO PDF](https://arxiv.org/pdf/2007.01867)
- Loss: Gaussian NLL, L = ½ log det Σ̂ + ½‖d − d̂‖²_Σ̂. Training directly on the NLL "does not converge", so they train with MSE for 10 epochs and then switch to NLL for about 10 more epochs (about 4 h on an NVIDIA DGX). — [TLIO PDF](https://arxiv.org/pdf/2007.01867)
- Robustness to filter-fed inputs: the network gets "potentially inaccurate input from the filter, especially at the initialization stage". During training they add random bias perturbations (uniform ±0.2 m/s² accelerometer, ±0.05 rad/s gyro) and random gravity-direction perturbations. Models trained this way are measurably less sensitive to accelerometer bias and gravity error. — [TLIO PDF](https://arxiv.org/pdf/2007.01867)
- Covariance validation: on about 60,000 test samples taken at 5 Hz, over 99% of errors fall inside the network's ±3σ (0.70% outside for x/y, 0.47% for z). Only 0.30% of samples exceed the 99th-percentile χ² critical value of the 3D Mahalanobis distance, and all of those come from one known failure sequence. — [TLIO PDF](https://arxiv.org/pdf/2007.01867)
- Filter: a stochastic-cloning EKF over past states (at a 20 Hz update rate with a 1 s window, at most 21 past states). The measurement is p_j − p_i = d̂_ij with noise Σ̂_ij. A χ² gate discards an update when the normalized innovation exceeds 11.345, the 99th percentile of χ² with 3 degrees of freedom. — [TLIO PDF](https://arxiv.org/pdf/2007.01867)
- Ablation on learned vs. constant covariance: the best constant covariance was the test-set error std diag(0.051, 0.051, 0.013) m times a grid-searched factor. The MSE-only network is more accurate per sample in 3D-RoNIN concatenation. In the filter, though, fixed-covariance variants perform similarly to each other and do not reach 100% on the ATE/drift CDFs. TLIO with the regressed covariance is best. — [TLIO PDF](https://arxiv.org/pdf/2007.01867)
- Headline result: compared with the best RoNIN velocity-concatenation baseline, TLIO reduces average yaw drift by 27% and position drift by 33%. Data: 60 h and 400+ sequences of headset pedestrian data. The test set is 37 trajectories of 3–7 min each, with VIO as ground truth. — [TLIO PDF](https://arxiv.org/pdf/2007.01867)
- Window-length finding: lower per-window MSE (longer windows) did not give lower ATE, because overlapping windows produce correlated errors. ATEs were similar across window variants. — [TLIO PDF](https://arxiv.org/pdf/2007.01867)
- A failure mode they note is that "bad initialization in the filter" led to yaw drift (Fig. 4, case 2.b). — [TLIO PDF](https://arxiv.org/pdf/2007.01867)

### Inferences
- For the CNN velocity measurement, the TLIO recipe carries over directly: train MSE first, then NLL with a diagonal log-variance head, perturb inputs with filter-realistic errors (bias, gravity tilt, and for us velocity/attitude error), validate with 3σ coverage and χ² exceedance on held-out flights, and gate updates at the 99% χ² point (11.345 for 3 DoF, 7.815 at 95%).
- TLIO's correlated-error finding matters for a two-frame velocity CNN run every frame. Consecutive outputs share inputs, so treating them as independent measurements will make the filter overconfident unless the covariance is inflated or updates are decimated.

### Gaps
- The exact TLIO median ATE values (in metres) are only in plots (Fig. 8 CDFs). I did not extract a numeric table.

## Q2. RoNIN, IONet, AI-IMU, Cioffi et al. 2023 (IMO), DIDO, AirIO, and thrust/drag-based learned velocity for drones

### Takeaway
For pedestrians, RoNIN/IONet regress velocity or displacement from about 1–2 s IMU windows. AI-IMU instead learns only the measurement covariance, end-to-end through the filter. On drones there is no gait prior, so the useful signal comes from dynamics (thrust in IMO, rotor speeds in DIDO) or from a body-frame representation (AirIO). On Blackbird, AirIO-EKF gets 0.40 m ATE (seen) vs. 1.19 m for TLIO and 0.93 m for IMO. Of these, only DIDO and AirIO feed a learned covariance to the EKF; IMO uses a constant measurement noise.

### Cited Findings
- **RoNIN (Yan et al., ICRA 2020; arXiv 1905.12853):** a 42.7 h dataset from 100 subjects. ResNet, LSTM and TCN variants regress 2D velocity. On the RIDI dataset the ATE for unseen subjects is RoNIN-ResNet 1.67 m vs. IONet 12.50 m vs. RIDI 1.71 m. On OXIOD (seen) the ATE is ResNet 2.40 m, IONet 1.79 m, RIDI 4.12 m. RoNIN-LSTM updates parameters only when the initial velocity is over 0.1 m/s, because the initial state is ambiguous when stationary. — [RoNIN PDF](https://arxiv.org/pdf/1905.12853)
- **IONet (Chen et al., 2018):** an LSTM over accelerometer and gyro windows in the world frame. It is described in DIDO's related work. — [DIDO PDF](https://arxiv.org/pdf/2203.03149)
- **AI-IMU (Brossard, Barrau, Bonnabel, IEEE T-IV 2020; arXiv 1904.06064):** an invariant EKF uses car pseudo-measurements (near-zero lateral and vertical velocity). A small CNN over a window of IMU samples outputs the pseudo-measurement covariance N_{n+1}. It is kept small "to avoid over-fitting" and to stay interpretable, e.g. to show how far to inflate covariance in turns. The CNN is trained through the filter with a relative-translation-error loss, "disregarding the values actually taken by N_n". On KITTI it averages 1.10% translational error from IMU only, competing with LiDAR (IMLS) and stereo (ORB-SLAM2). — [AI-IMU PDF](https://arxiv.org/pdf/1904.06064)
- **IMO, "Learned Inertial Odometry for Autonomous Drone Racing" (Cioffi et al., RA-L 2023; arXiv 2210.15287):** a TCN takes 0.5 s of 100 Hz mass-normalized collective thrust plus gyro (rotated to the world frame) and outputs 3-DoF displacement. The EKF uses an IMU-propagated stochastic clone with a constant measurement noise σ_nij = 0.01 m (no learned covariance). Updates run at 20 Hz with at most 10 past states, and the whole system runs at about 180 Hz on a Jetson TX2. — [IMO PDF](https://arxiv.org/pdf/2210.15287v2)
- IMO results:
  - Blackbird ATE_T (m), as OpenVINS / SVO / TLIO / IMO: Clover 0.50 / 0.77 / 0.75 / 0.41; Egg 1.07 / 2.49 / 1.31 / 1.15; Half Moon 0.37 / 1.10 / 1.20 / 0.76; Star 2.78 / 2.78 / 2.04 / 1.22; Winter 0.12 / 0.29 / 1.13 / 0.22.
  - Racing (about 100 km/h class): OpenVINS 98.2 m and SVO 47.2 m (both diverge), Gate-IO (camera + known gates) 0.48 m, TLIO 1.21 m, IMO 0.56 m.
  - A pure-model EKF using commanded thrust (Model-EKF) gets 10.10 m vs. IMO's 0.56 m. Learning the commanded-vs-applied thrust mismatch is "essential".
  - The training data is only about 10 min of flight.
  — [IMO PDF](https://arxiv.org/pdf/2210.15287v2)
- **DIDO (Zhang et al., RA-L/IROS 2022; arXiv 2203.03149):** cascaded networks, namely a De-Bias Net for IMU biases, a Res-Dynamics net for unmodeled force with covariance from rotor speeds, and a GRU-based V-P Net for velocity and position. These feed a two-stage EKF (rotation stage, then translation stage). The dynamics net uses MSE until stable and then switches to NLL (the same pattern as TLIO). The authors "do not directly use the neural network covariances but scale the covariances in a similar way to TLIO", because EKF linearization makes them propagate inaccurately. They report outperforming TLIO, RoNIN-ResNet (given ground-truth rotation) and Dyn-UKF. It requires motor tachometers. — [DIDO PDF](https://arxiv.org/pdf/2203.03149)
- **AirIO (Qiu et al., arXiv 2501.15659, 2025):** predicts body-frame velocity plus a per-axis uncertainty (Gaussian NLL plus Huber loss), with an explicit attitude encoding, and uses Σ̂_v directly as EKF measurement noise. ATE in m (Blackbird):

  | Method | Seen | Unseen |
  |---|---|---|
  | TLIO | 1.189 | 3.478 |
  | IMO | 0.929 | 9.015 |
  | AirIO Net | 0.486 | 1.300 |
  | AirIO EKF | 0.403 | 1.309 |

  On EuRoC, AirIO EKF gets 3.18 m vs. TLIO 6.97 m. The EKF adds about 17% ATE improvement over the network alone. — [AirIO](https://arxiv.org/html/2501.15659v2)
- AirIO representation ablation (ATE, m):
  - Body vs. global frame: EuRoC 4.73 vs. 10.10; Pegasus 4.48 vs. 17.28; Blackbird-unseen 1.52 vs. 8.99.
  - Adding attitude to body frame improves a further 15–30%.
  - Removing the rotation-coupled gravity term raises ATE by 90–360%.
  — [AirIO](https://arxiv.org/html/2501.15659v2)
- HDVIO (Cioffi, Bauersfeld, Scaramuzza, arXiv 2306.11429, 2023) uses a neural network to refine the drone dynamics model inside a VIO pipeline. — [HDVIO](https://arxiv.org/html/2306.11429v2)

### Inferences
- IMO generalizes poorly to unseen Blackbird trajectories (9.0 m ATE) while AirIO's body-frame model does not (1.3 m). This suggests a velocity CNN for our simulated drones should express outputs and inputs in the body or gravity-aligned body frame, not the world frame.
- With thrust/drag available in simulation, a dynamics-aware input (thrust, attitude) is the documented win for drones. In IMO's racing test, learning the thrust mismatch gave an 18× improvement over the pure physics model.

### Gaps
- I found no learned "drag-only" (rotor-drag velocity observability) network paper with numbers. DIDO's Dyn-UKF baseline (drag plus thrust model) is reported to "not work well", but I have no numeric ATE.
- DIDO's ATE numbers are in figures (CDFs), not tables, so they were not extracted.

## Q3. Learned visual/depth priors for VIO initialization, and speed of convergence

### Takeaway
Learned monocular depth used only during initialization lets a VIO initialize from 0.3–0.5 s of data instead of about 2 s. In a downstream 10 s tracking test on EuRoC, mean position RMSE drops from 2.24 m to 0.35 m (−84%). This is the strongest quantitative evidence that a learned prior used only at startup improves accuracy.

### Cited Findings
- **Zhou et al., "Learned Monocular Depth Priors in Visual-Inertial Initialization" (Google AR, ECCV 2022; arXiv 2204.09171):**
  - The method adds learned mono-depth constraints (with a per-window scale/shift, a prior weight and outlier rejection) to the closed-form init plus VI-BA.
  - With 5 keyframes at 10 Hz (0.4 s latency) on EuRoC, compared with ORB-SLAM3's Inertial-only init it reduces scale error by 43%, position RMSE by 61% and gravity RMSE by 21%, and lowers the condition number.
  - Inertial-only "still requires around 2 seconds" and needs mean acceleration above 0.005 g.
  - It produced 1547 successful initializations out of 1680 attempts vs. 1078 for Inertial-only. Average init latency was 0.399 s vs. 0.592 s.
  — [PDF](https://arxiv.org/pdf/2204.09171)
- Zhou et al., downstream tracking (VIO at 10 Hz, 5-KF init, 10 s windows, EuRoC, Table 3): mean position RMSE 2.243 m (baseline init) → 0.351 m (with depth prior), −84.35%. Gravity RMSE 3.02° → 1.61° (−46.7%). Examples: MH01 1.560 → 0.543 m; MH02 0.604 → 0.071 m. — [PDF](https://arxiv.org/pdf/2204.09171)
- Zhou et al., ablation (5 KF): scale error is 31.2% for the full method vs. 37.6% without prior weight, outlier rejection and the rest. Cost on a Pixel 4 XL CPU: mono-depth 71.6 ms, closed-form 0.73 ms, VI-BA 39.8 ms vs. 16.2 ms for the baseline. — [PDF](https://arxiv.org/pdf/2204.09171)
- **Merrill, Geneva et al., "Fast Monocular Visual-Inertial Initialization Leveraging Learned Single-View Depth" (RSS 2023):**
  - The method replaces per-feature depths in the closed-form linear system with a single scale plus offset of the MiDaS v2.1-small depth map, with RANSAC. It uses an off-the-shelf model at about 0.2 s CPU inference, run once per 0.3–0.5 s window.
  - EuRoC scale error after VI-BA (5 KF, 0.5 s): 5.8% average vs. 57.6% for the Dong-Si 3D baseline. V202 goes 285% → 4.1%.
  - TUM-VI initialization works with a 0.3 s window, "the smallest ever reported".
  — [NSF PAR PDF](https://par.nsf.gov/servlets/purl/10479088)
- Learned depth was only weakly fisheye-compatible but "still able to produce reasonable scale-less depth predictions". — [Merrill PDF](https://par.nsf.gov/servlets/purl/10479088)
- TLIO-type networks also serve at startup in practice. TLIO explicitly perturbs training inputs because filter-fed inputs are inaccurate "especially at the initialization stage". — [TLIO PDF](https://arxiv.org/pdf/2007.01867)

### Inferences
- For a moving start, a learned velocity measurement plays the same role as these depth priors. It makes scale and velocity observable before IMU excitation accumulates. The 0.3–0.5 s init windows in these papers are a realistic target with a 20 Hz camera (6–10 frames).

### Gaps
- DM-VIO (delayed marginalization, von Stumberg & Cremers, RA-L 2022) was not fetched in this session, so its convergence numbers are not reported here. It is not a learned prior.
- I did not find a paper using a learned *inertial* or *velocity* network specifically for VIO initialization with numbers. The search surfaced only depth-based ones. IPNet (arXiv 2503.12527) learns a bias prior during tracking, not at init. — [search listing](https://arxiv.org/pdf/2503.12527)

## Q4. Uncertainty calibration: NLL heads, NEES, over/under-confidence, inflation, gating, mixtures

### Takeaway
The standard practice is a diagonal Gaussian NLL head (warm-started with MSE), validated by 3σ coverage and χ² exceedance, then used in the EKF with a χ² gate. Several groups still apply a scale factor in the filter (DIDO, citing TLIO) because filter linearization and correlated errors make raw covariances inaccurate. Alternatives are to learn the covariance end-to-end through the filter (AI-IMU, DFIO) or to learn a post-hoc calibration map (Tsuei et al.).

### Cited Findings
- TLIO validation protocol: 3σ coverage over 99%, with 0.30% of samples beyond the 99% χ²(3) Mahalanobis threshold. In the filter, the χ² gate at 11.345 rejects "occasional wrong network output". — [TLIO PDF](https://arxiv.org/pdf/2007.01867)
- DIDO: NLL-trained covariances are scaled rather than used raw, because "the covariances may propagate inaccurately due to the linear approximation of the process and measurement models". — [DIDO PDF](https://arxiv.org/pdf/2203.03149)
- AI-IMU learns covariance end-to-end to minimize filter error, not to match the error distribution. TLIO points out that such parameters "do not necessarily best capture the measurement error model". — [TLIO PDF](https://arxiv.org/pdf/2007.01867); [AI-IMU PDF](https://arxiv.org/pdf/1904.06064)
- IMO (the drone racing paper) uses a constant 0.01 m measurement noise and still beats TLIO. A learned covariance is not strictly necessary when the network is accurate and the noise is hand-tuned. — [IMO PDF](https://arxiv.org/pdf/2210.15287v2)
- DFIO, "Differentiable Filtering for Inertial Odometry" (arXiv 2611.13517, 2026), embeds the ESKF update in the training graph to train displacement and covariance through the measurement update. It reports −13.2% mean ATE and −39.6% 1 s RTE vs. TLIO. This is from the search-result abstract and was not verified in full text. — [DFIO](https://arxiv.org/pdf/2611.13517)
- Tsuei, Soatto, Tabuada, Milam, "Learned Uncertainty Calibration for Visual Inertial Localization" (arXiv 2110.02136): EKF means are accurate but covariances are "typically inaccurate" in a systematic way, so a nonlinear map from estimated to empirical covariance can be learned. They demonstrate it on a simulated EKF and real VIO. No numbers appear in the abstract. — [arXiv](https://arxiv.org/abs/2110.02136)
- VIO-DualProNet learns the *process* noise covariance from raw inertial data for VIO. — [arXiv 2308.11228](https://arxiv.org/html/2308.11228v2)
- A 2026 GINIO preprint reports raw NEES coverage of learned covariance heads without post-hoc scaling (ideal NEES equals the state dimension). A 2026 odometry-scoring paper finds the filters it tested "severely overconfident", with the 90% ellipsoid rarely containing the truth. Both are from search summaries only, not verified. — [GINIO](https://arxiv.org/pdf/2609.25338); [Properly Scoring Odometry](https://arxiv.org/pdf/2609.25900)
- Zhou et al.'s ablation shows that both a prior weight on the learned depth and outlier rejection measurably help. Removing them raises scale error from 31.2% to about 34–37%. — [Zhou PDF](https://arxiv.org/pdf/2204.09171)

### Inferences
- A practical recipe for our CNN velocity update:
  1. Use a log-variance head trained with NLL after an MSE warm-up.
  2. Check per-axis 3σ coverage and the χ²(3) exceedance rate on held-out flights. The target is about 1% beyond the 99% threshold. Much more means overconfidence.
  3. Apply one global inflation factor α (tuned on validation flights for NEES close to 3 or for best ATE).
  4. Use a χ² gate at the 99% point.
  5. Account for correlation between consecutive overlapping windows by inflating further or by decimating updates.

### Gaps
- I found no drone-VIO paper reporting mixture-of-Gaussian velocity outputs fused into an EKF. The topic is not covered by the sources I retrieved.
- I found no explicit NEES numbers for TLIO, IMO or AirIO filter outputs.

## Q5. Tiny networks: size vs. accuracy for learned inertial odometry under compute limits

### Takeaway
Learned inertial odometry has been squeezed onto microcontrollers. TinyOdom (2022) shrinks models 31–134× (to fit 128 KB RAM / 1 MB flash Cortex-M boards) at 2.5–12 m error over 60 s. AirIO's 0.175 MB "Light B" model (about 44k fp32 parameters) loses 44% ATE on Blackbird in the body frame vs. 82% in the global frame. A good representation choice matters more as models shrink.

### Cited Findings
- **TinyOdom (Saha et al., ACM IMWUT 2022):**
  - Uses hardware- and quantization-aware Bayesian NAS over a TCN backbone, with targets STM32F446RE/L476RG (128 kB SRAM), F407 (192 kB) and F746 (320 kB). It runs on the TFLite-Micro interpreter.
  - Models are reduced 31–134× vs. baselines, "with 2.5 m to 12 m error in 60 seconds".
  - Its barometric altitude filter uses 10 kB SRAM and 51.4 kB flash.
  - The authors claim no prior work had run neural-inertial models in real time at 128 kB RAM / 1 MB flash.
  — [TinyOdom (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10957141/); [search listing](https://par.nsf.gov/servlets/purl/10385251)
- AirIO compression: regular model 2.524 MB (256-dim latent), Light A 0.641 MB (128-dim), Light B 0.175 MB (64-dim). ATE degradation at Light B: Blackbird 44.0% (body) vs. 81.8% (global); Pegasus 225% vs. 301%. Inference takes 28.9 ms on an RTX 2060 and 74.2 ms on a Jetson Orin AGX (full model). — [AirIO](https://arxiv.org/html/2501.15659v2)
- IMO's TCN is lightweight enough that the full filter runs at about 180 Hz on a Jetson TX2. Network size is not stated in the text I read. — [IMO PDF](https://arxiv.org/pdf/2210.15287v2)
- AI-IMU deliberately uses a "relatively small number of parameters" CNN for the covariance adapter, to avoid overfitting. — [AI-IMU PDF](https://arxiv.org/pdf/1904.06064)
- TLIO uses a full 1D ResNet18. — [TLIO PDF](https://arxiv.org/pdf/2007.01867)

### Inferences
- A 1.8 M MAC velocity CNN is in the same compute class as TinyOdom-scale models and about AirIO-Light-B size. The literature suggests accuracy at that scale depends strongly on input representation (body frame, gravity or attitude encoding) and on including dynamics inputs, more than on depth.
- Quantization: TinyOdom's NAS is quantization-aware (int8 TFLM). I found no isolated fp32-vs-int8 accuracy delta for learned inertial odometry.

### Gaps
- No exact parameter or MAC counts were found for TinyOdom's selected models or for IMO's TCN in the text retrieved.
- No study gives a clean accuracy-vs-MAC curve for image-plus-IMU velocity networks.

## Q6. Evidence that a learned measurement at startup (vs. continuous use) improves accuracy

### Takeaway
The clearest evidence is from learned-depth initialization. Used only during the 0.4 s init, it cut downstream 10 s EuRoC tracking RMSE by 84% (2.24 → 0.35 m) and scale error after init by 43–90% vs. classical inits. For continuous use, learned IMU or dynamics measurements help mainly where vision fails (racing: VIO diverges at 47–98 m while learned IO stays at 0.56 m). On well-textured sequences OpenVINS still beats learned IO on some Blackbird tracks (Winter 0.12 m vs. 0.22 m).

### Cited Findings
- Zhou et al. 2022 Table 3: a startup-only learned depth prior gives −84% mean downstream position RMSE and −47% gravity RMSE on EuRoC. — [PDF](https://arxiv.org/pdf/2204.09171)
- Merrill/Geneva 2023: a startup-only MiDaS-small prior takes average EuRoC scale error from 57.6% to 5.8% (0.5 s window) and enables 0.3 s initialization. — [PDF](https://par.nsf.gov/servlets/purl/10479088)
- IMO 2023 (continuous use): beats OpenVINS on Star (1.22 vs. 2.78 m) and racing (0.56 vs. 98.2 m), but loses on Winter (0.22 vs. 0.12 m) and Half Moon (0.76 vs. 0.37 m). — [IMO PDF](https://arxiv.org/pdf/2210.15287v2)
- TLIO's bad-initialization failure case shows that errors at the start (yaw) persist through a learned-measurement filter. — [TLIO PDF](https://arxiv.org/pdf/2007.01867)

### Inferences
- The evidence favours using the learned velocity measurement heavily at startup, where it makes scale and velocity observable within a few frames, and then down-weighting or gating it once visual features and IMU excitation make the filter well-conditioned. Learned measurements underperform good VIO on some easy sequences and have correlated errors.
- A schedule such as an inflation factor that grows over the first N seconds, or continuous use only when the χ² test or visual-track count indicates degraded vision, is consistent with this evidence. It has not been directly tested in any paper found.

### Gaps
- No paper directly compares "learned velocity measurement at startup only" with "continuous" in the same VIO filter. That ablation appears to be unpublished.
- No drone-specific moving-start (non-static, non-hover) initialization study with a learned velocity prior was found.
