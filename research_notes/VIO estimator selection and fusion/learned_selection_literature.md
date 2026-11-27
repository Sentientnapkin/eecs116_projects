# Learned and analytic methods for choosing, switching, or fusing multiple VIO/SLAM estimators online, and predicting estimator failure

Scope note: research was done by web search and abstract/HTML reading (about 20 tool calls). Several full PDFs could not be parsed, so some per-paper details (exact feature lists, precision/recall) are missing and are listed under Gaps rather than filled in from memory.

## Q1. What published work does online estimator selection, switching, or mixture-of-experts for odometry/SLAM, and which signals does it use?

### Takeaway
Published "which estimator to trust" systems fall into three groups. (a) Hand-designed supervisors that use a priority order or switch on health checks: HeRO/JPL, DAMS-LIO, Selective KF, VINS-Mono failure detection, legged IEKF switching. (b) Learned per-context error regressors or gates over an ensemble: Holtz et al. 2015 random forest, MIXO gating network, UNO Gumbel-softmax decoder selection. (c) Learned introspection or uncertainty that reweights measurements inside one estimator: IV-SLAM, ICD-Net, Statistical Uncertainty Learning, SEESys. The signals in practice are cheap internal ones: feature counts (MSCKF/SLAM features), output-rate gaps, covariance trace or max velocity std, pose jumps, bias/extrinsic jumps, image intensity statistics, and degeneracy eigenvalues for LiDAR. Learned gates add image features (e.g. DINOv2 embeddings in UNO), which are far more expensive.

### Cited Findings
**Learned selection or switching over an ensemble**
- Holtz, Maturana, Scherer, "Learning a Context-Dependent Switching Strategy for Robust Visual Odometry," FSR 2015, pp. 249–263. A random forest regressor predicts each VO algorithm's accuracy from features of the sensor input, and the system switches to the algorithm with the lowest predicted error. Gains: 3.5% lower translational RPE and 4.3% lower angular RPE than the *single best* algorithm, and 39.4% / 20.1% lower than the worst. Data: 4 environments, 8 runs, about 25 min. — [CMU RI](https://publications.ri.cmu.edu/learning-a-context-dependent-switching-strategy-for-robust-visual-odometry)
- MIXO (IEEE Trans. Consumer Electronics, 2023): a gating network selects the locally best "experts" (per-camera VO) for current conditions and weights their contributions. It is described as a lightweight module that sits on top of any VO. It targets multi-camera rigs, not mono+IMU. — [MIXO PDF (PoliTo)](https://iris.polito.it/bitstream/11583/2974785/1/MIXO_TCE_Final.pdf) (summary seen only via search snippet)
- UNO (arXiv 2506.07013, June 2025; venue unconfirmed): monocular VO with 8 decoders (1 epipolar SIFT/essential-matrix decoder and 7 Sc-SfMLearner-style learned decoders). A Gumbel-softmax categorical selector picks one decoder per frame pair from a frozen DINOv2 encoder, a temporal RNN, and a correlation volume over a sliding window. The selection is hard: indicator-weighted, so only one expert's output is used, even though the text calls it "fusing." EuRoC ATE 0.04–0.11 m on the reported sequences. No compute is reported, and the DINOv2 backbone alone is far beyond a few-Mops budget. — [arXiv 2506.07013](https://arxiv.org/html/2506.07013v1)
- Kulkarni, Du, Huang, "Online Learning of Robust Legged Odometry with Minimal Exteroceptive Supervision," arXiv 2606.21669 (2026). An IEKF takes body-frame velocity from either VINS (MSCKF) or a learned proprioceptive ESN.
  - Health score H ∈ [0,1] = 0.45·(MSCKF feature-count ramp, N_ok=5, N_good=20) + 0.20·(SLAM-feature ramp, 0–10) + 0.35·(max velocity std ramp, σ_good=0.05 m/s, σ_bad=0.30 m/s), with an optional 10-sample moving average.
  - States: healthy H≥0.70, degraded 0.40–0.70, unusable <0.40. It switches to the learned module when the state is unusable.
  - VINS supervises the learned module's online updates only while VINS is healthy.
  - Results are qualitative only (backlit hallway, lights-off room).
  - Compute: 0.43 ms for ESN uncertainty propagation and 6.3 ms per readout update on an RTX 2000 Ada.
  - — [arXiv 2606.21669](https://arxiv.org/html/2606.21669)

**Rule-based supervisors over heterogeneous odometry**
- HeRO (Santamaria-Navarro, Thakker, Fan, Morrell, Agha-mohammadi, NASA JPL, "Towards Resilient Autonomous Navigation of Drones," arXiv 2008.09679, ISRR 2019/2020). Runs ORB-SLAM2 stereo+EKF (60 Hz), Qualcomm Snapdragon mono VIO (25 Hz), and LiDAR-IMU odometry (20 Hz) in parallel on a drone.
  - Health checks: output-rate gaps (feature-tracking failure in fast motion or featureless scenes), a covariance-trace threshold (VIO divergence), and sudden position change (inconsistency the covariance misses).
  - Sensor-level checks: image intensity and its variation, rate, LiDAR return spacing.
  - Feature counts and inlier quality are mentioned as possible checks but are not used in the experiments.
  - Selection uses a fixed priority ranking, with voting when ≥3 sources are available.
  - Quality is binary Good/Bad and maps to mobility modes: Global (position), Local (velocity+attitude), Attitude-only (landing).
  - Results are qualitative, from a SubT STIX mine flight.
  - — [arXiv 2008.09679](https://ar5iv.labs.arxiv.org/html/2008.09679)
- Team CoSTAR's NeBula system used HeRO-style redundant heterogeneous odometry: visual, LiDAR, thermal, radar run in parallel "so that their failure scenarios do not overlap." — [NeBula arXiv 2103.11470](https://arxiv.org/pdf/2103.11470)
- DAMS-LIO (arXiv 2302.01703): runs as LIO normally and fuses pose measurements from another odometry only when LiDAR degeneracy is detected. — [arXiv 2302.01703](https://arxiv.org/pdf/2302.01703v2.pdf)
- Selective Kalman Filter (arXiv 2412.17235): fuses visual measurements into LiDAR SLAM only when degeneracy is detected, and only in the degenerate direction. It cites LION as earlier work that switches away from LiDAR odometry on any degeneracy. — [arXiv 2412.17235](https://arxiv.org/html/2412.17235v1)
- AIMS (arXiv 2601.01561, Jan 2026): quadruped LiDAR-IMU-leg odometry. A degeneracy-aware reliability score weights each sensor's contribution, and leg-odometry reliability is coupled to the estimated LiDAR degeneracy severity. Needs LiDAR. — [arXiv 2601.01561](https://arxiv.org/html/2601.01561v1)
- IMM over multiple tracking cameras: Kuruppu Arachchige and Lee, AIAA SciTech 2024. An IMM framework weights and fuses odometry from several RealSense T265 units (each a stereo VIO) by accuracy, and reportedly beats a single camera in texture-poor or poorly lit scenes. Details were not verified beyond the project page. — [project page](https://sasakuruppuarachchi.github.io/projects:%20robotic/arrf/2023/05/30/robust-navigation-system-based-on-interacting-multiple-model-method-using-multiple-tracking-cameras.html)

**Within-estimator failure criteria, the standard mono+IMU baseline**
- VINS-Mono (T-RO 2018) declares failure on:
  - tracked features below a threshold
  - a large jump in position or rotation between consecutive outputs
  - a large change in bias or extrinsic estimates

  It then re-initializes and starts a new pose-graph segment. — [arXiv 1708.03852](https://arxiv.org/pdf/1708.03852)

**Learned introspection or uncertainty inside one estimator**
- IV-SLAM (Rabiee and Biswas, IROS 2020): self-supervised learning of a context-dependent reprojection-error noise model from images, used for feature selection and weighting. Reports >70% fewer tracking failures than standard V-SLAM on challenging real-robot data. Stereo/V-SLAM based, and it uses single images only, with no temporal information. — [arXiv 2008.02760](https://arxiv.org/pdf/2008.02760v2); extended in [Introspective Perception for Mobile Robots, arXiv 2306.16698](https://arxiv.org/pdf/2306.16698)
- Daftry, Zeng, Bagnell, Hebert, "Introspective Perception: Learning to Predict Failures in Vision Systems," IROS 2016. A learned model predicts failure of the perception module from input sensor data, on a MAV flying in outdoor natural environments, and triggers remedial actions. The abstract gives no metrics. — [arXiv 1607.08665](https://arxiv.org/abs/1607.08665)
- CMU RISS 2015 poster: random forest on luminance-saliency image measures to predict feature-based VO failure about two frames ahead. Failure modes include sudden exposure change and rapid motion. — [poster](https://riss.ri.cmu.edu/wp-content/uploads/2015/10/2015-RISS-Poster-Lee-Mike.pdf)
- SEESys (Hu et al., SenSys 2024): online SLAM pose-error estimation without ground truth, from a runtime monitor of sensor-input and internal-pipeline features fed to an attention-based multimodal network (DeepSEE). Results: 0.235 cm RMSE of error estimation (15.8% better than baseline), 37.3 ms end-to-end latency, and a 25% tracking-error reduction in a user-advisory case study. Visual SLAM only; VI extension is claimed but not shown. — [TU Delft record](https://research.tudelft.nl/en/publications/seesys-online-pose-error-estimation-system-for-visual-slam/); [NSF PAR](https://par.nsf.gov/biblio/10554272)
- ICD-Net (arXiv 2512.00037, 2025): learns displacement plus a covariance from IMU data and adds it as a residual in VINS-Fusion. Reports >38% mean APE improvement on high-speed drone sequences. — [arXiv 2512.00037](https://arxiv.org/html/2512.00037v1)
- De Maio and Lacroix, "On learning visual odometry errors," IROS 2019 workshop: learns VO biases and attaches an error model, tested on driving and MAV data. — [PDF](https://nikosuenderhauf.github.io/roboticvisionchallenges/assets/papers/IROS19/deMaio.pdf)

### Inferences
- The only quantified learned-switching result for classical VO (Holtz 2015) beat the single best algorithm by just 3.5% translational RPE. Most of the gain is avoiding the worst algorithm (39%). Expect a selector between two decent estimators to help mainly by dodging catastrophic segments, not by improving the average.
- For a mono+IMU drone on a few-Mops budget, the realistic selector inputs are signals the estimators already compute:
  - feature/inlier counts
  - covariance trace or max velocity std
  - NIS / χ² innovation statistics
  - output-rate gaps
  - pose/bias jump magnitude
  - inter-estimator disagreement
  - IMU excitation (accelerometer norm deviation, gyro norm)
  - cheap image statistics (mean intensity, intensity change)

  The Kulkarni 2026 health score is a ready-made, almost free template (three ramps, a weighted sum, and hysteresis bands).
- Learned gates on image embeddings (UNO, SEESys's attention network) are well outside a few-Mops budget.

### Gaps
- Could not read the Holtz 2015 full text for its exact feature list or which VO algorithms were switched.
- Could not read MIXO's gating inputs or numbers. They are known only from a search snippet.
- No paper found that does learned per-frame selection between two full mono-VIO back ends (e.g. MSCKF vs optimization-based) on a drone and reports ATE gains.

## Q2. How well do learned failure predictors work (precision/recall, lead time), and how is the switching discontinuity handled?

### Takeaway
Quantified precision/recall for VIO failure predictors is scarce. Most papers report downstream gains (IV-SLAM: >70% fewer failures; SEESys: 0.235 cm error-estimation RMSE) or only qualitative flights (HeRO, Kulkarni 2026). The one lead-time figure found is "two frames ahead." Discontinuity is handled in three ways, the main one being relative-motion composition onto the current fused state, which the other two depend on.

### Cited Findings
- **Discontinuity method 1: relative-motion composition (re-anchoring).** HeRO builds its output by composing each source's *incremental* motion onto the previous HeRO state. A source that restarts at its own origin is concatenated to the last HeRO state, and a transform manager tracks discontinuities for IMU-fused sources. The paper notes the output "does not always match" any individual estimator. — [arXiv 2008.09679](https://ar5iv.labs.arxiv.org/html/2008.09679)
- **Discontinuity method 2: switching at the measurement level (velocity, not pose).** Kulkarni et al. feed either VINS velocity or learned velocity into one IEKF as the same body-frame velocity measurement with its own covariance, so the fused pose never jumps. The paper does not discuss discontinuity explicitly. — [arXiv 2606.21669](https://arxiv.org/html/2606.21669)
- **Discontinuity method 3: degeneracy-gated partial fusion.** Selective KF and DAMS-LIO add the second source as a measurement only when needed, and Selective KF restricts it to the degenerate directions. — [arXiv 2412.17235](https://arxiv.org/html/2412.17235v1); [arXiv 2302.01703](https://arxiv.org/pdf/2302.01703v2.pdf)
- **Lead time:** the CMU RISS 2015 luminance-saliency random forest targeted predicting feature-based VO failure two frames ahead. No precision/recall was available on the poster summary. — [poster](https://riss.ri.cmu.edu/wp-content/uploads/2015/10/2015-RISS-Poster-Lee-Mike.pdf)
- **Drift detection on drones:** Ibrahimov, Yang, Mueller (Berkeley HiPeRLab, 2025) propose a Kalman-filter residual test on VIO x/y/z position with a χ² statistic to flag drift, validated offline on real UAV flight data. There is no real-time mitigation yet. — [PDF](https://hiperlab.berkeley.edu/wp-content/uploads/2025/03/2025_Ibrahimov_DriftDetection.pdf) (summary from search snippet; full PDF exceeded fetch size)
- **NIS detector design:** NIS is approximately χ²(dof) for a calibrated filter, and the threshold comes from the inverse CDF at a chosen significance. Add a stall gate, an uncertainty gate, and debounce/hysteresis: healthy → suspect → fault after K_f consecutive triggers. — [arXiv 2603.14622](https://arxiv.org/pdf/2603.14622)
- **SEESys error estimation:** 0.235 cm RMSE, 15.8% better than baseline, 37.3 ms latency. — [TU Delft](https://research.tudelft.nl/en/publications/seesys-online-pose-error-estimation-system-for-visual-slam/)

### Inferences
- For a frame-by-frame selector, avoid emitting the chosen estimator's *absolute* pose. Instead do one of the following:
  - integrate the chosen estimator's per-frame relative motion or velocity into a running output state (HeRO style)
  - feed the chosen source's velocity or relative pose as a measurement to a light fusion filter (Kulkarni style)
  - blend relative increments with soft weights

  Any of these removes jump artifacts. The cost is that output error becomes path-integrated: a wrong switch permanently bakes in that frame's increment error.
- Hysteresis bands and moving-average smoothing (Kulkarni: 0.40/0.70 bands, 10-sample average; NIS debounce K_f) are the standard way to prevent chattering between sources. A learned per-frame selector likely needs the same, either as a minimum dwell time or a penalty on switch frequency in training.
- Because covariance can stay small while the estimate is wrong, HeRO adds a jump check on top of the covariance check. Covariance-only signals are insufficient for VIO divergence.

### Gaps
- No paper found reporting precision/recall/ROC or lead time for learned VIO failure prediction on mono+IMU drone data.
- No paper found that compares hard switching vs soft blending vs relative-motion fusion head-to-head on the same data.

## Q3. Known pitfalls: correlated failures, hindsight-oracle vs causal gap, training-data needs, domain shift

### Takeaway
The literature explicitly motivates *heterogeneous* estimators because failures of similar estimators co-occur. HeRO/NeBula pick sensors "so that their failure scenarios do not overlap." For two estimators on the same mono camera, failures are largely shared: both lose texture, both are hit by exposure change and fast rotation. That caps the oracle gain. Domain shift is a documented problem for learned VIO components. No source was found that directly measures the hindsight-oracle vs causal-selector gap for odometry.

### Cited Findings
- HeRO and NeBula run heterogeneous odometry (visual, LiDAR, thermal, radar) specifically so failure modes do not overlap. — [NeBula arXiv 2103.11470](https://arxiv.org/pdf/2103.11470); [HeRO](https://ar5iv.labs.arxiv.org/html/2008.09679)
- Holtz 2015's learned switching gives only a 3.5% gain over the single best VO, versus 39.4% over the worst. That is consistent with modest causal gains when the ensemble's errors are correlated. — [CMU RI](https://publications.ri.cmu.edu/learning-a-context-dependent-switching-strategy-for-robust-visual-odometry)
- Domain shift: in Pan et al. (2511.21083), a driving-trained learned VIO component (VS-VIO) transferred poorly to EuRoC and was excluded. Their RL agents were fine-tuned on one sequence per dataset, and cross-dataset generalization was only lightly tested. — [arXiv 2511.21083](https://arxiv.org/html/2511.21083v2)
- IV-SLAM's introspection uses only single images, not temporal context, which the authors flag as a limitation. — [arXiv 2008.02760](https://arxiv.org/pdf/2008.02760v2)
- Self-supervision trick for training data:
  - IV-SLAM labels training data autonomously, with no manual labels. — [arXiv 2008.02760](https://arxiv.org/pdf/2008.02760v2)
  - Kulkarni 2026 trains the fallback only while the primary is healthy. — [arXiv 2606.21669](https://arxiv.org/html/2606.21669)
  - UNO trains its gate self-supervised from photometric losses. — [arXiv 2506.07013](https://arxiv.org/html/2506.07013v1)
- Learned introspection systems typically see few real failure events. Holtz used about 25 minutes over 8 runs. — [CMU RI](https://publications.ri.cmu.edu/learning-a-context-dependent-switching-strategy-for-robust-visual-odometry)

### Inferences
- **Winner's curse / oracle gap.** A per-frame hindsight oracle ("pick whichever estimator had lower error this frame") exploits noise. Its gain is upward-biased, especially when the two estimators' per-frame errors are similar and noisy. Measure the gap by training the selector on causal features only and evaluating on held-out flights. Compare against (i) the best single estimator and (ii) a segment-level oracle (e.g. 1–5 s windows), which is a more achievable target than a per-frame oracle. This is an inference; no odometry paper was found quantifying it.
- **Label leakage.** Labels derived from future ground truth (e.g. "which estimator ends with lower ATE") correlate with drift that has not happened yet. Causal features may not predict them, so prefer labels on local increment error (RPE over a short window).
- **Data needs.** Failures are rare events. With a few dozen flights, a tiny model (logistic regression, shallow tree, or a hand-weighted health score as in Kulkarni) on ~5–10 internal signals is more defensible than a deep gate. The 2015 random forest worked with about 25 minutes of data.
- **Correlated failures.** Two mono-camera estimators fail together on textureless, dark, or blurred segments. There, the useful "second opinion" is IMU-only dead reckoning or a learned inertial velocity model (Kulkarni, ICD-Net), not a second visual estimator.

### Gaps
- No source found that quantifies the hindsight-oracle vs causal-selector gap for odometry selection.
- No source found that gives data-size vs accuracy curves for learned estimator selectors.

## Q4. Examples of a cheap estimator running continuously and an expensive one on demand, and how history or warm start is handled

### Takeaway
There are several examples: learned skip policies for the visual branch (ECCV 2022, 78.8% compute reduction), RL scheduling of the full VO/BA pipeline from IMU-only cues (2025), and resource-aware parameter adaptation (2021). In each, the IMU (cheap) runs continuously and the visual or BA stage (expensive) runs on demand. The weak point in all of them is how the expensive estimator keeps its history across skipped frames. Papers either propagate the fused state with IMU and restart the visual stage from it, or they leave it unspecified. HeRO-style re-initialization in flight is the classic fallback but needs parallax (mono) or stereo.

### Cited Findings
- Yang, Chen, Kim, "Efficient Deep Visual and Inertial Odometry with Adaptive Visual Modality Selection," ECCV 2022. A policy network uses motion state and IMU readings, with Gumbel-softmax training, to switch the visual feature extractor off on the fly. Up to 78.8% compute reduction on KITTI with "similar or even better" accuracy than the full-modality baseline. Evaluated on driving, not drones. — [arXiv 2205.06187](https://arxiv.org/abs/2205.06187v2)
- Pan, Zheng, Yin, Dou, "Dual-Agent RL for Adaptive and Cost-Aware VIO," arXiv 2511.21083 (2025).
  - Select Agent: decides run/skip for the whole VO pipeline (encoder, correlation, BA) from IMU-only inputs (pre-integrated Δp, Δq, Δv, time since last VO update) before any visual computation.
  - When skipped: fusion weights go to zero and the last fused state is IMU-propagated. The fused pose seeds the next VO cycle, but how VO patches or keyframes persist through skips is not explained.
  - Select reward: A/(ATE+ε) − B·(#VO calls).
  - Fusion Agent inputs: VO confidence from parallax and BA residuals, and IMU confidence from the bias estimator and integration horizon.
  - Results: EuRoC ATE 0.092 m vs DPVO 0.106. Throughput 39 vs 22 FPS on an RTX 3090. BA is 12.77 ms per keyframe. Still worse than ORB-SLAM3 (0.041) and DM-VIO (0.069).
  - Caveats: not trained for hard re-initialization, and offline log-driven evaluation only.
  - — [arXiv 2511.21083](https://arxiv.org/html/2511.21083v2)
- Mathur, Khedekar, Alexis, "Resource-aware Online Parameter Adaptation for Computationally-constrained Visual-Inertial Navigation Systems," arXiv 2106.00289 (2021). Adapts parameters of S-MSCKF, VINS-Mono, and OKVIS online to fit a compute budget, reaching comparable accuracy at a fraction of the cost on EuRoC. — [arXiv 2106.00289](https://arxiv.org/abs/2106.00289v1)
- HeRO re-initializes failing estimators in flight while another source navigates. ORB-SLAM2 stereo re-initializes without parallax, while the mono QSF VIO was modified to allow in-flight re-init. Landing made re-init more likely to succeed, and the new estimate is concatenated onto the current HeRO state. — [arXiv 2008.09679](https://ar5iv.labs.arxiv.org/html/2008.09679)
- VINS-Mono re-initializes after failure and starts a new pose-graph segment, which can be merged later via loop closure. — [arXiv 1708.03852](https://arxiv.org/pdf/1708.03852)
- Kulkarni 2026: the cheap learned proprioceptive model runs continuously and is trained online from the expensive VINS whenever VINS is healthy. This is a teacher-student hand-off in the opposite direction. — [arXiv 2606.21669](https://arxiv.org/html/2606.21669)

### Inferences
- **Peak-ops budget.** All "on-demand" schemes cut *average* compute, not *peak* per-frame compute: the frame where the expensive estimator runs still costs the full amount. Under a peak-ops budget, on-demand scheduling only helps if the expensive estimator's per-frame cost already fits the peak budget.
- **Warm start for an intermittently run mono VIO.** It needs the current pose, velocity, gravity direction, and biases, which the cheap estimator can provide. It also needs a feature or landmark history with parallax for scale, which an estimator that was off cannot have. Practical options:
  - keep the expensive estimator's front end (feature tracking) running continuously and skip only its back end, as in Pan et al., which skips BA but keeps a fused state
  - seed its state from the cheap estimator and accept a short re-convergence window
  - keep a small keyframe buffer so it can re-triangulate on activation
- **Simplest robust pattern for a two-estimator mono+IMU system:**
  1. Run both continuously only if both fit the peak budget; otherwise use a priority primary plus a dead-reckoning fallback.
  2. Fuse via relative increments or velocity (HeRO/Kulkarni) gated by a hysteresis health score built from feature counts, max velocity std / covariance trace, NIS, and jump checks.
  3. Re-seed the failed estimator from the fused state.

### Gaps
- No drone paper found that keeps a heavy mono VIO "cold" and warm-starts it on demand, with measured re-convergence time or error.
- IMM and covariance intersection: no source found that applies them to fusing two full VIO estimators online on a mono+IMU drone. Only the AIAA 2024 multi-T265 IMM project (stereo trackers) surfaced. The general CI caveats also lack a solid source: it is conservative under unknown cross-correlation (relevant because two VIOs on the same camera and IMU have highly correlated errors, so naive Kalman fusion of their outputs would be overconfident), assumes a single source model, and is not outlier-robust. The only source seen for these caveats was a patent snippet ([USPTO 7298868](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7298868)), so treat them as background knowledge, not a sourced finding.
