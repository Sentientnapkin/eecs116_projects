# Sources per slide

Methods we built on are cited where the idea comes from published work. Lines marked **(ours)** are our own design or tuning, with no specific prior source. Citations are standard references written from memory: check the details (year, venue) before printing them on slides.

---

## Background / baseline estimator (slide 4, "How it works")

**Filter:**
- **MSCKF:** A. I. Mourikis and S. I. Roumeliotis, "A Multi-State Constraint Kalman Filter for Vision-aided Inertial Navigation," *ICRA* 2007.
- **Error-state EKF / IMU propagation:** J. Solà, "Quaternion kinematics for the error-state Kalman filter," arXiv:1711.02508, 2017.
- **Gaussian-process modelling (bias model):** C. E. Rasmussen and C. K. I. Williams, *Gaussian Processes for Machine Learning*, MIT Press, 2006.

**Front end:**
- **KLT tracking:** B. D. Lucas and T. Kanade, "An Iterative Image Registration Technique with an Application to Stereo Vision," *IJCAI* 1981; J.-Y. Bouguet, "Pyramidal Implementation of the Lucas Kanade Feature Tracker," Intel tech. report, 2000.
- **Corner detection:** J. Shi and C. Tomasi, "Good Features to Track," *CVPR* 1994.
- **Forward-backward track check (B7):** Z. Kalal, K. Mikolajczyk and J. Matas, "Forward-Backward Error: Automatic Detection of Tracking Failures," *ICPR* 2010.

**Reference systems we compared against and borrowed conventions from:**
- **OpenVINS:** P. Geneva, K. Eckenhoff, W. Lee, Y. Yang and G. Huang, "OpenVINS: A Research Platform for Visual-Inertial Estimation," *ICRA* 2020.
- **VINS-Mono:** T. Qin, P. Li and S. Shen, "VINS-Mono: A Robust and Versatile Monocular Visual-Inertial State Estimator," *IEEE T-RO* 2018.

**Metric:**
- **ATE:** J. Sturm et al., "A Benchmark for the Evaluation of RGB-D SLAM Systems," *IROS* 2012. Absolute trajectory error; we score it unaligned, as the course does.
- **Sim(3) alignment (diagnostic only):** S. Umeyama, "Least-Squares Estimation of Transformation Parameters Between Two Point Patterns," *IEEE TPAMI* 1991.

## Dataset slides (5A–5D)

**Simulator and scoring:** the course's viobench framework and its HyperDrone simulator. Cite the course repository: `github.com/jonas-eschmann/viobench`.

**Scene catalogs:**
- **ProcTHOR:** M. Deitke et al., "ProcTHOR: Large-Scale Embodied AI Using Procedural Generation," *NeurIPS* 2022.
- **HSSD:** M. Khanna et al., "Habitat Synthetic Scenes Dataset (HSSD-200)," *CVPR* 2024.

**Flight file format:** M. Burri et al., "The EuRoC micro aerial vehicle datasets," *IJRR* 2016.

**Ours:**
- **Planner speed-style overrides:** from the teammate's `eecs116_vio/gpu_kit/styles.txt`.
- **Our own work:** the train / tune / holdout split by scene, server calibration, and the hard-slice construction.

## Slide 1: Random guessing start / starting velocity learned net

**Static start:**
- **Static (hover) initialisation:** estimating gyro/accelerometer bias and gravity while still is standard practice. See OpenVINS's static initialiser (Geneva et al. 2020) and VINS-Mono's initialisation (Qin et al. 2018).
- **Motion detection from IMU magnitude:** standard zero-velocity / stationarity detection. I. Skog, P. Händel, J.-O. Nilsson and J. Rantakokko, "Zero-Velocity Detection—An Algorithm Evaluation," *IEEE T-BME* 2010.

**Learned velocity from images + IMU** (related learned odometry):
- W. Liu et al., "TLIO: Tight Learned Inertial Odometry," *IEEE RA-L* 2020. A learned displacement with uncertainty, fused as an EKF measurement. This is the closest prior work to our net-as-measurement design.
- S. Herath, H. Yan and Y. Furukawa, "RoNIN: Robust Neural Inertial Navigation in the Wild," *ICRA* 2020.

**Ours:**
- **The forward-flight prior.**
- **The specific 64×48 CNN:** architecture and C implementation.
- **Injection timing:** frames 5–6.

## Slide 2: Re-anchoring / further optimizations / fuel

**Re-anchoring and the second update pass:**
- **Iterated EKF (re-linearise and update again):** B. M. Bell and F. W. Cathey, "The Iterated Kalman Filter Update as a Gauss-Newton Method," *IEEE TAC* 1993.
- **Revisit map / patch matching with ZNCC:** zero-mean normalised cross-correlation, the standard template matching. See R. Szeliski, *Computer Vision: Algorithms and Applications*, 2nd ed., 2022, ch. 9. The idea of re-using old landmarks resembles map-based relocalisation in ORB-SLAM3: C. Campos et al., "ORB-SLAM3," *IEEE T-RO* 2021.
- **(ours) Trigger rule:** re-run the net when velocity uncertainty exceeds 0.25 m/s.

**Further optimizations:**
- **IMU sanitiser and watchdog:** standard robustness practice (outlier gating, divergence detection). No single source; general Kalman filter practice: Y. Bar-Shalom, X. R. Li and T. Kirubarajan, *Estimation with Applications to Tracking and Navigation*, Wiley, 2001.
- **(ours)** The ablation finding that the movement gate became harmful.

**Fuel:**
- **WebAssembly SIMD (128-bit integer/float vectors):** the WebAssembly SIMD proposal, W3C WebAssembly Community Group.
- **Fixed-point KLT:** fixed-point / integer image alignment is common in embedded vision, e.g. OpenCV's integer pyramidal LK implementation. Cite Bouguet 2000 for pyramidal LK.
- **(ours) Per-frame budget governor:** spreading deferred work across frames to cap the peak. Related idea: anytime / time-budgeted estimation. No specific source used.

## Slide 3: Using wall geometry / periodic learned velocity

**Wall geometry:**
- **Manhattan-world assumption:** J. M. Coughlan and A. L. Yuille, "Manhattan World: Compass Direction from a Single Image by Bayesian Inference," *ICCV* 1999.
- **Lines as features in VIO:**
  - D. G. Kottas and S. I. Roumeliotis, "Efficient and Consistent Vision-aided Inertial Navigation using Line Observations," *ICRA* 2013.
  - Y. He et al., "PL-VIO: Tightly-Coupled Monocular Visual–Inertial Odometry Using Point and Line Features," *Sensors* 2018.
- **Structural (Manhattan) lines in VIO:** D. Zou et al., "StructVIO: Visual-Inertial Odometry With Structural Regularity of Man-Made Environments," *IEEE T-RO* 2019. This is the closest prior work to our vertical/horizontal-line constraints.
- **Line parametrisation:** A. Bartoli and P. Sturm, "Structure-from-motion using lines: Representation, triangulation, and bundle adjustment," *CVIU* 2005 (Plücker / orthonormal line representation).
- **Line detector used in the illustration video:** R. Grompone von Gioi et al., "LSD: A Fast Line Segment Detector with a False Detection Control," *IEEE TPAMI* 2010.
- **Soft down-weighting of bad features (RSOFT):** robust M-estimation, P. J. Huber, "Robust Estimation of a Location Parameter," *Annals of Math. Statistics* 1964. Our specific 1/residual weight is ours.

**Periodic learned velocity:**
- **Learned measurement fused in an EKF with its own uncertainty:** TLIO (Liu et al. 2020), as above.
- **Uncertainty-calibrated training loss (beta-NLL):** M. Seitzer et al., "On the Pitfalls of Heteroscedastic Uncertainty Estimation with Probabilistic Neural Networks," *ICLR* 2022.
- **(ours)** The finding that frequent weak updates beat infrequent strong ones, and the 0.5 s period with 3× uncertainty.

## Student-teacher work (if mentioned)

- **Knowledge distillation:** G. Hinton, O. Vinyals and J. Dean, "Distilling the Knowledge in a Neural Network," arXiv:1503.02531, 2015.
- **Feature-hint distillation:** A. Romero et al., "FitNets: Hints for Thin Deep Nets," *ICLR* 2015.
- **Learned drone inertial odometry:** Y. Qiu et al., "AirIO: Learning Inertial Odometry with Enhanced IMU Feature Observability," 2025.
- **Teammate's implementation:** `research/single_model/disp_teacher/`, `research/single_model/proxy/`.

## Internal sources (our own repo)

- **Build history:** `reports/GP MSCKF build history explained.md`.
- **All numbers:** `research/single_model/LOOP_LOG.md`, plus the server results pasted from the course submission site.
- **Teammate's prototype tools and videos:** `eecs116_vio/`.
- **Original GP + MSCKF:** `Final Project/classical_vio/gp_msckf/JOURNAL.md`.
