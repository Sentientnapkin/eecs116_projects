# Visual-inertial (VI) initialization methods and moving (mid-motion) starts

Context: monocular camera at 20 Hz plus IMU at 200 Hz on a drone, feeding a small embedded MSCKF/EKF. A "moving start" means frame 0 is already in motion, so there is no static period to level gravity or estimate biases.

Source access: arXiv HTML/ar5iv pages, GitHub source, and conference abstract pages were readable. Several PDFs (Campos 2020 raw PDF, Geneva tr_init.pdf, Merrill 2024 IJRR mirror, CVPR 2023 He et al. PDF (403)) could not be parsed, so some numbers come from secondary tables. Those tables are flagged below, mostly from Cerezo et al. 2025, which re-benchmarks VINS-Mono, ORB-SLAM3-style, and DRT.

---

## Q1. Martinelli closed form and its extensions (Kaiser et al. 2017; Dong-Si & Mourikis 2012)

### Takeaway
The Martinelli-family closed forms solve one linear system for velocity, gravity, and feature depths/positions, which removes scale as a separate unknown. They need no prior SfM. Their main weakness is that they assume known biases. Kaiser et al. (RA-L 2017) showed gyro bias "significantly affects" accuracy, and adding it makes the problem iterative and nonlinear. Dong-Si & Mourikis (IROS 2012) is the same linear idea plus MLE refinement, and it is what OpenVINS implements. Cost is small (a dense least squares over a few poses and about 50 features), but conditioning depends on parallax and acceleration excitation.

### Cited Findings
- Martinelli (TRO 2011; IJCV 2014) gives closed-form solutions for attitude, speed, scale, and biases, but "assume[s] partial knowledge of the states, specifically of the sensor biases." — [Cerezo et al. 2025, arXiv 2511.18910](https://arxiv.org/html/2511.18910v2)
- Kaiser, Martinelli, Fontana & Scaramuzza, "Simultaneous State Initialization and Gyroscope Bias Calibration in Visual Inertial aided Navigation", IEEE RA-L 2(1):18-25, 2017 (DOI 10.1109/LRA.2016.2521413). It shows that the gyroscope bias, which the earlier closed form did not model, significantly hurts performance, and it adds automatic gyro-bias estimation. — [UZH Merlin record](https://www.merlin.uzh.ch/publication/show/13323); [HAL](https://hal.archives-ouvertes.fr/hal-01423550)
- Kaiser et al. jointly initialize the state and calibrate gyro bias by nonlinear optimization (iterative). Cerezo et al. classify it as "non-closed-form" in their Table I. — [Cerezo et al. 2025](https://arxiv.org/html/2511.18910v2)
- A secondary summary says Kaiser et al. also enforce the gravity magnitude, solve the result iteratively, and report real drone data with initialization in under 3 s. I could not verify this against the primary text. — [search summary of arXiv 2511.18910 / 2103.03389](https://arxiv.org/html/2511.18910v1)
- Cost: Campos et al. (ICRA 2020) quote about **60 ms** for the closed-form Martinelli-Kaiser solution as used in their earlier joint init. Their own joint method (Campos et al. ICRA 2019, "Fast and robust initialization for VI-SLAM") worked in only **about 20% of trajectory points**, initializing in about 2 s with about 5% scale error. — [Campos et al. 2020 (ar5iv)](https://ar5iv.labs.arxiv.org/html/2003.05766); [arXiv 2003.05766](https://arxiv.org/pdf/2003.05766)
- Joint VI-SfM closed forms "suffer from numerical stability problems and require the same features across all initialization frames." — [Zuñiga-Noël et al. 2021 (ar5iv)](https://ar5iv.labs.arxiv.org/html/2103.03389)
- Dong-Si & Mourikis, "Estimator initialization in vision-aided inertial navigation with unknown camera-IMU calibration", IROS 2012, pp. 1064-1071. It computes the observable quantities (attitude, velocity, feature positions, camera-IMU calibration) directly from measurements. Its key contribution is a convex-optimization method for the camera-IMU rotation (one variant needs 5 or more features), and an iterative maximum-likelihood estimator then refines the result. — [UCR PDF](https://intra.ece.ucr.edu/~mourikis/papers/DongSi2012IROS.pdf); [IEEE](https://ieeexplore.ieee.org/abstract/document/6386235); [dblp](https://dblp.org/rec/conf/iros/Dong-SiM12)
- OpenVINS DynamicInitializer implements Dong-Si 2012 in two steps. First, "a linear system [...] to recover the velocity, gravity, and feature positions." Second, a full optimization (MLE) "to allow for covariance recovery." — [OpenVINS ov_init docs](https://docs.openvins.com/namespaceov__init.html)
- Cerezo, Lee & Civera (arXiv Nov 2025, Univ. Zaragoza), "An Efficient Closed-Form Solution to Full Visual-Inertial State Initialization", call theirs "the first closed-form initialization method" that estimates all states, including both biases. Under small-rotation and constant-velocity approximations, R_ij and b_g come from the first two frames, then t, v, b_a, g and feature depths come from one linear least-squares (SVD) solve. — [arXiv 2511.18910](https://arxiv.org/html/2511.18910v2)

### Inferences
- For an MSCKF, the Dong-Si/OpenVINS linear system is the natural fit. Its unknowns are v0, g (3 values, or 2 with the norm constraint), and 3 per feature, using gyro-integrated rotations. It needs no SfM and no per-frame tracking of the full window, only features seen in several of about 5-6 poses.
- The known-bias assumption is the main practical hazard. Gyro bias corrupts the integrated rotations, which then enter every row. Accelerometer bias is nearly confounded with gravity over short windows (see Q7).

### Gaps
- I could not read the Kaiser 2017 and Dong-Si 2012 numerical results (accuracy versus window length, simulation and real data) because the PDFs were not parseable or the pages were bot-protected.
- I have no primary numbers on condition number versus window length for the Martinelli system.

---

## Q2. VINS-Mono visual-inertial alignment (Qin, Li & Shen, TRO 2018)

### Takeaway
VINS-Mono needs a full window of 10 frames (WINDOW_SIZE=10 keyframes plus 1 newest), and a vision-only SfM must succeed first. That requires at least 20 correspondences and more than 30 px average parallax (at a 460 px virtual focal length) between some frame and the newest one. Gyro bias is solved first, then a linear LS gives velocities, gravity, and scale, with gravity then refined on its 2-DoF tangent space. Accelerometer bias is ignored. With low parallax it simply keeps sliding the window and retrying. Re-benchmarked, it reaches about 0.11 m/s velocity and 1.5° gravity error at about 31 ms total cost, but its scale is poor at short windows (22% mean scale error in Campos 2020's test).

### Cited Findings
- 100-300 features per image. SfM is triggered by stable tracking of more than 30 features and more than 20 rotation-compensated pixels of parallax. The SfM pipeline is the 5-point algorithm, triangulation, PnP for the other frames, then global BA. — [VINS-Mono paper (ar5iv)](https://ar5iv.labs.arxiv.org/html/1708.03852)
- Gyro bias is estimated first from rotation residuals, then preintegration is re-propagated. The accelerometer bias "is ignored" during initialization. Velocities, gravity (c0 frame), and scale s are solved by linear LS, then gravity is refined with fixed magnitude as g·ĝ + w1 b1 + w2 b2, iterated. — [VINS-Mono (ar5iv)](https://ar5iv.labs.arxiv.org/html/1708.03852)
- Metric scale needs acceleration excitation, so VINS-Mono cannot initialize from stationary. The paper gives no numeric excitation threshold. Under rotation-only motion, features cannot be triangulated. — [VINS-Mono (ar5iv)](https://ar5iv.labs.arxiv.org/html/1708.03852)
- Code facts (estimator.cpp):
  - Initialization is attempted only when `frame_count == WINDOW_SIZE` and more than 0.1 s has passed since the last attempt.
  - The IMU excitation check (`var < 0.25`) only logs; its `return false` is commented out.
  - `relativePose` needs `corres.size() > 20` and `average_parallax * 460 > 30`, plus a successful `solveRelativeRT`.
  - On failure it logs "Not enough features or parallax; Move device around" and calls `slideWindow()` to try again later.
  - `visualInitialAlign` calls `VisualIMUAlignment` to get gravity and scale, rescales depths and positions, sets velocities, and removes the initial yaw.
  — [VINS-Mono estimator.cpp](https://raw.githubusercontent.com/HKUST-Aerial-Robotics/VINS-Mono/master/vins_estimator/src/estimator.cpp)
- In Campos et al. 2020's EuRoC test, VINS-Mono init took about 1.3 s (t_Init) and about 2.0 s total, with **22.05% mean scale error**, because it assumes zero accelerometer bias. "Many initial solutions have scale near zero." — [Campos et al. 2020 (ar5iv)](https://ar5iv.labs.arxiv.org/html/2003.05766)
- Re-benchmark over 2248 EuRoC init tests: VINS-Mono velocity error 0.11 m/s, gravity 1.47°, accel-bias column 0.104 m/s². Total init time is **30.94 ms**, of which about 30 ms is the SfM stage. It fails or is missing on V103 and V203. — [Cerezo et al. 2025](https://arxiv.org/html/2511.18910v2)

### Inferences
- At 20 Hz with keyframes taken only on parallax, the minimum is 11 frames (0.55 s) if every frame is a keyframe. In practice, the keyframe parallax gate (a few px; MIN_PARALLAX=10 px in the default config, from memory and not verified here) stretches this to roughly 1-2 s for a slow drone, consistent with Campos's ~1.3 s.
- Mid-motion start: VINS-Mono does not need a static start, and the motion direction does not enter the math. However, forward or backward flight along the optical axis gives little parallax near the focus of expansion. Sideways motion gives the most parallax, so it passes the 30 px gate fastest.
- I could not confirm whether the 460×parallax gate in `relativePose` is rotation-compensated. If it is not, rotation alone could pass it while the 5-point solve stays degenerate.

### Gaps
- VINS-Mono's success rate versus excitation level is not reported in the paper.

---

## Q3. ORB-SLAM3 inertial-only MAP initialization (Campos, Montiel, Tardós, ICRA 2020; ORB-SLAM3 TRO 2021)

### Takeaway
The method runs 1-2 s of monocular ORB-SLAM (10 keyframes at 4 Hz, about 2.16 s), then a small inertial-only MAP with poses fixed (solving for scale, gravity direction, biases, and velocities). It takes about 5 ms per run, run 3 times with different scale seeds. Full VI-BA follows. Scale error is 5.3% at about 2.2 s (9.1% at 1.25 s), refined to about 1% by VI-BA at 5 s and 15 s. Total cost is about 160 ms, dominated by VI-BA.

### Cited Findings
- Pipeline:
  1. Vision-only MAP: monocular ORB-SLAM for about 1-2 s, keyframes at 4-10 Hz.
  2. Inertial-only MAP with keyframe poses fixed. It estimates scale s, gravity direction R_wg (2 angles, known |g|), accel and gyro biases (6), and up-to-scale velocities. Biases are constant over the window, with a prior on b_a to keep it near 0. Scale is seeded at median depths of 1, 4, and 16 m and the lowest residual is kept. Gravity is seeded from the mean accelerometer reading.
  3. Full VI-BA.
  — [Campos et al. 2020 (ar5iv)](https://ar5iv.labs.arxiv.org/html/2003.05766)
- Windows of 10 KFs at 4 Hz (about 2.16 s) or 10 Hz (about 1.25 s). Mean scale error after VI-BA: **5.29% at 2.16 s** and about **9.09% at 1.25 s**. Inertial-only alone gives 11.69%. Total time to a usable init is under 4 s. — [Campos et al. 2020 (ar5iv)](https://ar5iv.labs.arxiv.org/html/2003.05766); abstract: "initialize in less than 4 seconds in almost any point of the trajectory, with a scale error of 5.3%" — [arXiv 2003.05766](https://arxiv.org/abs/2003.05766v1)
- Timing on V1_02: inertial-only 3 × 5.24 ms, map update 11.18 ms, VI-BA 132.78 ms; **total 159.68 ms mean (228 ms max)**. — [Campos et al. 2020 (ar5iv)](https://ar5iv.labs.arxiv.org/html/2003.05766)
- Windows with mean acceleration below 0.5% of g are discarded as "almost constant velocity". Bad inits are detected and retried with the next batch. — [Campos et al. 2020 (ar5iv)](https://ar5iv.labs.arxiv.org/html/2003.05766)
- ORB-SLAM3 reports 5% scale error at 2 s on EuRoC, refined by VI-BA at 5 s and 15 s to about 1%. In some slow-motion cases it does not converge within 15 s, so ORB-SLAM3 adds a periodic inertial-only scale refinement. — [ORB-SLAM3, arXiv 2007.11898](https://arxiv.org/pdf/2007.11898)
- The ORB-SLAM3 init is reported to be "highly sensitive to the scale factor". — [EDI, arXiv 2308.02670](https://arxiv.org/pdf/2308.02670)
- Re-benchmark: the window for Campos et al. is 2.16 ± 0.01 s. — [Cerezo et al. 2025, Table X](https://arxiv.org/html/2511.18910v2)

### Inferences
- The inertial-only step itself is cheap (about 5 ms) and suits a filter. The expensive parts are the monocular SfM/BA it depends on and the VI-BA refinement, neither of which an MSCKF has.

### Gaps
- No numbers on success rate for the 2020 method itself ("almost any point" only).

---

## Q4. OpenVINS dynamic initialization (Geneva et al.; Dong-Si-style linear system plus MLE)

### Takeaway
OpenVINS's dynamic initializer is off by default (`init_dyn_use: false`) and is used only when the platform is not stationary. It takes a short window (EuRoC config: 2.0 s, 6 evenly spaced poses, at least 10° of accumulated rotation) and solves a linear system for v, g, and features. A Ceres MLE capped at 50 iterations or 0.05 s then refines it, and the covariance is recovered and inflated (orientation ×10, velocity ×100). It is the closest existing match to an MSCKF.

### Cited Findings
- Static path: wait for stationarity, then align orientation to gravity. Dynamic path: implements Dong-Si 2012, with a linear system for velocity, gravity, and features followed by a full MLE for covariance. Factors are `Factor_ImuCPIv1` (continuous preintegration), `Factor_ImageReprojCalib`, and `Factor_GenericPrior`. — [OpenVINS ov_init docs](https://docs.openvins.com/namespaceov__init.html)
- Header defaults:
  - `init_window_time` = 1.0 s; `init_dyn_num_pose` = 5 (must be ≥ 4); `init_dyn_min_deg` = 45°
  - `init_max_features` = 50 (≥ 15)
  - `init_dyn_mle_max_iter` = 20; `init_dyn_mle_max_time` = 5 s
  - Bias guesses default to 0 and are optimized.
  — [InertialInitializerOptions.h](https://raw.githubusercontent.com/rpng/open_vins/master/ov_init/src/init/InertialInitializerOptions.h)
- EuRoC config values:
  - `init_window_time` = 2.0; `init_imu_thresh` = 1.5 (accel variance "jerk" detector); `init_max_disparity` = 10 px
  - `init_dyn_num_pose` = 6; `init_dyn_min_deg` = 10.0
  - `init_dyn_mle_max_iter` = 50; `init_dyn_mle_max_time` = 0.05 s; 6 threads
  - Inflation: ori 10, vel 100, bg 10, ba 100; `init_dyn_min_rec_cond` = 1e-12
  - `init_dyn_mle_opt_calib` = false ("not recommended")
  — [euroc_mav estimator_config.yaml](https://raw.githubusercontent.com/rpng/open_vins/master/config/euroc_mav/estimator_config.yaml)
- Merrill/Geneva (RSS 2023) describe the "standard" methods of this family as typically waiting for a 2-second window. — [RSS 2023 abstract](https://roboticsconference.org/2023/program/papers/072/)

### Inferences
- The rotation threshold (10-45°) acts as a gyro-bias observability gate. The reciprocal-condition threshold rejects ill-conditioned windows. A straight, non-rotating moving start may therefore wait until the drone turns.
- MLE with a 0.05 s cap and 6 threads is affordable on a companion computer but likely too heavy for a "tiny per-frame budget". The linear step alone (about 6 poses, at most 50 features, so about 150+6 unknowns, or fewer if features are eliminated) is cheap.

### Gaps
- I could not parse Geneva's tr_init.pdf to confirm whether the linear system treats gyro and accel biases as known (at the initial guess). I also found no published robustness or success-rate numbers for the OpenVINS dynamic init.

---

## Q5. Rotation-only / rotation-translation-decoupled initialization (Zuñiga-Noël et al. 2021; He et al. CVPR 2023; DOGE 2024)

### Takeaway
Decoupling first estimates gyro bias from rotation alone (camera relative rotations versus gyro), then solves velocity and gravity linearly without 3D points or SfM. DRT (He et al. CVPR 2023) is 8-72× faster than prior methods on 10 frames. In re-benchmarks it is about 5 ms, with 0.11 m/s velocity and 1.03° gravity error, but it does not estimate accelerometer bias. Zuñiga-Noël's analytic solve still needs ORB-SLAM poses, but it gives a closed form for scale, gravity, and b_a at 0.19 ms.

### Cited Findings
- He, Xu, Ouyang & Li, CVPR 2023, pp. 739-748. Stage 1 is a rotation-only problem that tightly couples gyro and camera to estimate gyro bias. Stage 2 recovers initial velocity and gravity from linear translation constraints "without reconstructing 3D point clouds." It is claimed to run 8-72× faster on a 10-frame set. Code: boxuLibrary/drt-vio-init (GPLv3; only tightly and loosely coupled versions released). — [CVPR open access](https://openaccess.thecvf.com/content/CVPR2023/html/He_A_Rotation-Translation-Decoupled_Solution_for_Robust_and_Efficient_Visual-Inertial_Initialization_CVPR_2023_paper.html); [CVPR poster page](https://cvpr.thecvf.com/virtual/2023/poster/21117); [GitHub](https://github.com/boxuLibrary/drt-vio-init)
- Re-benchmark (EuRoC):
  - DRT-tight: velocity 0.11 m/s, gravity 1.03°, no accel-bias estimate, total time **5.18 ms**, fixed window **2.50 s**.
  - "Decoupled approaches still require nonlinear optimization" (gyro bias).
  — [Cerezo et al. 2025](https://arxiv.org/html/2511.18910v2)
- DOGE (arXiv 2412.08135, He co-author) extends decoupling to estimate the extrinsic rotation as well. — [arXiv 2412.08135](https://arxiv.org/html/2412.08135v1)
- Zuñiga-Noël et al., RA-L 2021, "An Analytical Solution to the IMU Initialization Problem for VI Systems":
  - Method: gyro bias by Levenberg-Marquardt from zero. Accel bias, gravity direction, and scale analytically, as a quadratic cost with a quadratic |g| constraint, reduced to a 6th-order polynomial solved by companion-matrix eigenvalues. Needs accurate up-to-scale visual poses (ORB-SLAM2 mono).
  - Ground-truth-pose errors (proposed vs. inertial-only baseline):
    - 1.25 s: scale 4.61% vs 6.23%; gravity 7.6° vs 1.11°
    - 2.5 s: scale 2.57% vs 3.18%
    - 5 s: scale 1.60% vs 2.64%
  - With ORB-SLAM2 poses (20 KF, 5 s): solve **0.19 ms** vs 1.29 ms; scale 10.4% vs 14.6%; gravity 3.44° vs 2.17°.
  - Accel-bias errors are huge (≥100%) at short windows.
  - The speedup claim is inconsistent within the paper: "77×" in the text against about 7× in its table.
  — [Zuñiga-Noël et al. (ar5iv)](https://ar5iv.labs.arxiv.org/html/2103.03389)
- Cerezo et al. treat AS-MLE (Zuñiga-Noël-based) as a baseline: velocity 0.17 m/s, gravity 2.66°, total time 30.54 ms (dominated by about 30 ms of SfM). — [Cerezo et al. 2025](https://arxiv.org/html/2511.18910v2)

### Inferences
- The gyro-bias-first step is ideal for a moving and rotating start, because rotation is observable immediately and needs no translation or parallax. A drone with yaw or attitude motion gets b_g quickly, then v and g follow from the linear translation step.

### Gaps
- I could not read DRT's own tables (PDF 403), so its success rate versus VINS-Mono is unverified here.

---

## Q6. Recent 2023-2025 fast/robust init (learned depth, gyro-bias-first, closed form)

### Takeaway
Two lines push below 0.5 s. The first adds learned monocular depth (Merrill, Geneva et al., RSS 2023 and IJRR 2024), reaching about 0.5 s and as little as 300 ms on TUM-VI. The second is fully closed-form, as in Cerezo et al. (Nov 2025): an adaptive window averaging 0.48 ± 0.27 s at **0.96 ms** total, with 10-20% lower error than VINS-Mono, DRT, and AS-MLE.

### Cited Findings
- Merrill, Geneva, Katragadda, Chen & Huang, "Fast Monocular Visual-Inertial Initialization Leveraging Learned Single-View Depth", RSS 2023:
  - Standard methods wait for about 2 s of data; prior depth-aided work reaches 0.5 s.
  - Their linear step needs only one depth image (the first frame), reducing each feature's depth to a per-image scale and offset.
  - It achieves a **300 ms** window on TUM-VI, "the smallest ever reported."
  — [RSS 2023 page](https://roboticsconference.org/2023/program/papers/072/); [RSS proceedings](https://roboticsproceedings.org/rss19/p072.html); [NSF PAR copy](https://par.nsf.gov//servlets/purl/10479088)
- The journal version, "Fast and robust learned single-view depth-aided monocular VI initialization" (IJRR 2024), gives a smaller minimal problem (scale plus bias of learned depth), reports Jetson Orin timing, and achieves init under 1 s. — [IJRR / SAGE](https://journals.sagepub.com/doi/full/10.1177/02783649241262452); [NSF PAR](https://par.nsf.gov/servlets/purl/10549173)
- Zhou et al. (Google AR, ECCV 2022) use scale/shift-invariant mono-depth tightly coupled in VI-SfM, targeting low-excitation cases. — [arXiv 2204.09171](https://arxiv.org/abs/2204.09171v2)
- Cerezo, Lee & Civera 2025:
  - Window 0.48 ± 0.27 s vs 2.16 s (Campos) and 2.50 s (He).
  - Velocity 0.09 m/s, gravity 0.90°, b_a 0.084 m/s².
  - Total 0.96 ms vs 5.18 ms (DRT) and about 31 ms (VINS-Mono, AS-MLE).
  - Gyro-bias solve costs 19-94 µs closed-form vs 3687 µs nonlinear.
  - A two-stage observability test (a parallax gate, then a Hessian test that costs about 15× the parallax test) triggers init.
  - Tests ran every 0.5 s (10 frames) across 2248 EuRoC tests.
  - Assumes small rotation, constant bias, and constant angular velocity over the window; outlier ratio about 0.15.
  — [arXiv 2511.18910](https://arxiv.org/html/2511.18910v2)
- Other relevant names: EDI (ESKF-based Disjoint Init, arXiv 2308.02670); PNEC-based init (arXiv 2410.19473); XR-VIO fast init (arXiv 2502.01297). — [EDI](https://arxiv.org/pdf/2308.02670); [PNEC init](https://arxiv.org/html/2410.19473v1); [XR-VIO](https://arxiv.org/pdf/2502.01297)

### Inferences
- Cerezo 2025's approach (closed-form b_g from two frames, then one SVD) is the cheapest full-state formulation found. It suits a per-frame embedded budget and could run every few frames until its observability test passes.

### Gaps
- I did not find a learned-IMU (inertial network) initialization paper with init-specific numbers. I did not read EDI, PNEC, or XR-VIO in detail.

---

## Q7. Minimum duration and excitation for observable scale and gravity; anything under 0.5 s?

### Takeaway
Scale needs non-zero acceleration (not constant velocity), and the ORB-SLAM3-line methods reject windows with mean acceleration below 0.5% of g. Gravity direction is observable quickly. Accelerometer bias is effectively unobservable in windows of 1-5 s (errors ≥100%), so the practical recipe is to fix b_a at 0 with a prior. Under 0.5 s has been reported only by Cerezo 2025 (0.48 s mean, adaptive) and by learned-depth methods (300 ms on TUM-VI). Classical methods sit at 1.25-2.5 s.

### Cited Findings
- Near-constant-velocity windows are unobservable; windows with average acceleration under 0.5% g are rejected. — [Zuñiga-Noël 2021](https://ar5iv.labs.arxiv.org/html/2103.03389); [Campos 2020](https://ar5iv.labs.arxiv.org/html/2003.05766)
- Error versus window (ground-truth poses, inertial-only baseline): scale 6.23% at 1.25 s, 3.18% at 2.5 s, and 2.64% at 5 s; gravity about 1.1° at 1.25 s. Accel bias stays at about 99% error up to 18.75 s with a strong prior. — [Zuñiga-Noël 2021](https://ar5iv.labs.arxiv.org/html/2103.03389)
- VINS-Mono ignores b_a at init because it is hard to observe and couples with gravity. — [VINS-Mono](https://ar5iv.labs.arxiv.org/html/1708.03852)
- Sub-0.5 s results: 0.48 ± 0.27 s ([Cerezo 2025](https://arxiv.org/html/2511.18910v2)); 300 ms on TUM-VI with learned depth ([Merrill RSS 2023](https://roboticsconference.org/2023/program/papers/072/)).

### Inferences
- At 20 Hz, 0.5 s is 10 frames, or 100 IMU samples. With up-to-scale poses, scale observability scales roughly as (acceleration × T²) / (feature depth noise). A drone accelerating at 0.5-1 m/s² over 0.5 s moves only about 6-12 cm from acceleration. At several metres of depth with 1-px noise at 20 Hz, scale will likely be ±20-50% unless the drone manoeuvres hard. This is my estimate, not a sourced figure.
- For a moving start, velocity at frame 0 is a direct unknown in every one of these linear systems (v0 or v_k per keyframe). Non-zero initial velocity is not a problem. What fails is zero acceleration together with low parallax.
- Moving backwards or sideways: no formulation assumes forward motion. Sideways motion gives the best parallax. Forward or backward motion along the optical axis gives weak parallax for features near the focus of expansion or contraction, which slows SfM- or parallax-gated methods.
- Rotation while moving helps gyro-bias observability (OpenVINS requires 10-45°). However, Cerezo's small-rotation approximation and VINS-Mono's parallax measures may degrade under fast rotation. Pure rotation gives no translation information.

### Gaps
- No paper found gives an explicit Fisher-information or condition-number curve versus window length for a drone-like trajectory at 20 Hz.

---

## Q8. Cheapest formulations for a tiny per-frame compute budget

### Takeaway
From cheapest to most expensive:
1. Cerezo 2025 closed form: about 1 ms total; gyro bias in about 20-90 µs.
2. Zuñiga-Noël analytic step: 0.19 ms, but it needs SfM poses.
3. Inertial-only MAP: about 5 ms per seed, also needing SfM.
4. DRT decoupled: about 5 ms.
5. VINS-Mono alignment: about 31 ms, mostly SfM.
6. OpenVINS linear system plus MLE: up to 50 ms by config.
7. ORB-SLAM3 full init with VI-BA: about 160 ms.

For an MSCKF with no SfM, the realistic choices are Cerezo 2025 or a Dong-Si/OpenVINS linear solve with gyro-bias-first (DRT-style), b_a fixed at 0, and inflated covariances handed to the filter.

### Cited Findings
- Timings: Cerezo 0.96 ms; DRT-tight 5.18 ms; VINS-Mono 30.94 ms; AS-MLE 30.54 ms (EuRoC). — [Cerezo et al. 2025](https://arxiv.org/html/2511.18910v2)
- Zuñiga-Noël analytic 0.19 ms vs inertial-only 1.29 ms (excluding about 3.5 ms per keyframe of preintegration). — [Zuñiga-Noël 2021](https://ar5iv.labs.arxiv.org/html/2103.03389)
- ORB-SLAM3-style total 159.68 ms; Martinelli-Kaiser closed form about 60 ms. — [Campos 2020](https://ar5iv.labs.arxiv.org/html/2003.05766)
- OpenVINS MLE budget is 0.05 s on 6 threads; covariance is inflated afterwards. — [OpenVINS config](https://raw.githubusercontent.com/rpng/open_vins/master/config/euroc_mav/estimator_config.yaml)

### Inferences
- Reported times are desktop or Jetson-class. A WASM or embedded target may be 3-10× slower, which is still sub-10 ms for the closed-form or linear options.
- A filter-native alternative to any batch init is to start the EKF at frame 0 with gravity from the accelerometer mean (biased by the platform's acceleration), v0 unknown with large covariance, and to let the MSCKF updates observe v and scale. That only works if the first 0.5-2 s carry enough acceleration or parallax, which is the same observability constraint as above.

### Gaps
- None of the papers report microcontroller or WASM timings.
