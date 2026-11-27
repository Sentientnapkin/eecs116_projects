# Kalman-filter techniques for the startup and early-consistency phase of EKF/MSCKF VIO (moving start; mono 20 Hz camera + 200 Hz IMU)

Provenance note for the report writer: this session's web tooling could only return abstracts and search summaries. Every downloaded PDF (Jackson 2019, FEJ2-related NSF copy, Abeywardena 2016) was compressed binary, and there was no PDF-to-text tool. Claims marked **[verified]** were confirmed against an abstract or search snippet in this session. Claims marked **[canonical]** are standard, widely reproduced statements about well-known papers; I cite them by their primary URL, but I did not re-read the full text this session. I deliberately left out numeric results I could not confirm and listed them under Gaps.

## 1. Initial covariance selection: what happens when it is too small or too large

### Takeaway
Too small an initial P (especially on velocity, roll/pitch and gyro bias) makes the filter overconfident. It then down-weights or gates out correct visual measurements and stays inconsistent (NEES >> dof), and in some cases never recovers. Too large a P lets the first updates make big jumps that are computed from badly linearized Jacobians, and with FEJ those bad linearization points get locked in. The practical recipe is to initialize P from the covariance of the initializer's own solution (MLE or Hessian), then inflate the observable directions (roll/pitch, velocity) moderately.

### Cited Findings
- OpenVINS dynamic initialization (added in v2.6, based on Dong-Si & Mourikis 2012) uses a linear solve followed by Ceres MLE refinement, then recovers the covariance from that problem. The PR notes that the recovered covariance "still requires some inflation". **[verified]** — [OpenVINS PR #232](https://github.com/rpng/open_vins/pull/232); [ov_init DynamicInitializer source](https://docs.ros.org/en/api/ov_init/html/DynamicInitializer_8cpp_source.html)
- In OpenVINS issue #433, the maintainer explains that only the orientation covariance is inflated (parameter `init_dyn_inflation_orientation`) because roll and pitch are observable. A user reports that the recovered covariance was **overconfident with short initialization windows**. **[verified]** — [OpenVINS issue #433](https://www.github.com/rpng/open_vins/issues/433)
- A third-party reimplementation lists the OpenVINS dynamic-init pipeline as: data check, linear solve for features, velocity and gravity, gravity-magnitude constraint, Ceres MLE refinement, covariance recovery. **[verified; non-official]** — [int-smart notebook](https://int-smart.github.io/notes/notebooks/dynamic-initialization)
- Dong-Si & Mourikis (IROS 2012) give a closed-form linear initializer for velocity, gravity and feature positions from a short window, followed by MLE refinement. This is the basis of OpenVINS dynamic init. **[verified via PR]** — [OpenVINS PR #232](https://github.com/rpng/open_vins/pull/232)
- FEJ2 (Chen, Yang, Geneva, Huang, ICRA 2022) is motivated by FEJ's degradation when **first estimates are poor**. In practice that is exactly what an over-wide initial P causes, because large early corrections move the state far from its first linearization point. **[verified abstract]** — [IEEE Xplore 9811831](https://ieeexplore.ieee.org/abstract/document/9811831)
- Hesch et al. (TRO 2014) attribute standard-EKF VINS inconsistency to **spurious information gain** along unobservable directions (global yaw and position). This inconsistency compounds an over-tight P, because the filter becomes too confident about yaw. **[verified snippet]** — [Hesch et al. TRO 2014 (UMN copy)](https://fling.seas.upenn.edu/~afosr/wiki/uploads/Chaserepository/Repository/UMN-ST-TRO-VINS-Consistency.pdf)

### Inferences
- With an unknown moving start, initial velocity σ should cover realistic speeds (for example σ_v of about 0.5–2 m/s per axis if nothing better is known). Roll and pitch become observable within a few hundred ms of motion. Global yaw and position are unobservable, so their P only sets the reference frame. Start them at zero or a small value, and never let updates shrink yaw P artificially (see section 3).
- Gyro bias typically has the largest effect on attitude drift early on. A σ_bg of about 1e-2 rad/s is a common MEMS prior. A tight bias P combined with a bad bias guess causes slow tilt drift that the filter "explains" with wrong velocity.
- If a startup estimator (MLE, a learned prior, or similar) provides a covariance, use it, but inflate it 2–10x on orientation and velocity. OpenVINS's experience shows that covariances recovered from short windows are overconfident.

### Gaps
- I found no paper that sweeps the initial-P scale and reports ATE or NEES against it for VIO. Evidence on this point is anecdotal (OpenVINS issues) or rests on the theory from the FEJ/OC line.
- I could not extract the inflation factors OpenVINS uses by default (config values) in this session.

## 2. Iterated EKF / IEKF, relinearization, invariant EKF, iterated ESKF (FAST-LIO)

### Takeaway
Iteration (a Gauss-Newton re-solve of the measurement update) fixes linearization error in the update step. Its benefit is largest exactly when the prior is poor, as at startup. Cost scales with the number of iterations, typically 2–5x the update cost. Invariant/equivariant filters address the other problem: their error dynamics and Jacobians do not depend on the (possibly bad) estimate, so they keep the correct unobservable subspace without FEJ. They therefore give consistency "out of the box" and are much less sensitive to poor initial attitude. Direct numeric gains for VIO startup specifically are scarce in the literature I could access.

### Cited Findings
- ROVIO (Bloesch et al., IJRR 2017, vol. 36(10), pp. 1053–1072) uses an **iterated EKF** with photometric patch errors as innovations, and a robocentric formulation. It reports high robustness to low texture and motion blur on real datasets. **[verified abstract]** — [Bloesch et al. 2017, SAGE](https://journals.sagepub.com/doi/full/10.1177/0278364917728574); [open-access copy](https://folia.unifr.ch/global/documents/271860)
- FAST-LIO (Xu & Zhang, RA-L 2021) uses a tightly coupled **iterated EKF** "to mitigate linearization errors". It also introduces a Kalman-gain formula whose cost scales with state dimension rather than measurement dimension. This matters when there are many measurements (for VIO: many feature rows per frame). **[verified snippet]** — [FAST-LIO arXiv 2010.08196](https://arxiv.org/pdf/2010.08196.pdf)
- LINS (2019) uses a robocentric iterated ESKF and re-finds correspondences in each iteration, which reduces errors from wrong matches. It reports accuracy comparable to state-of-the-art LIO at much higher speed. **[verified snippet]** — [LINS](https://ar5iv.arxiv.org/html/1907.02233)
- RI-MSCKF ("An Invariant-EKF VINS Algorithm for Improving Consistency", arXiv 1702.07920, IROS 2017): in 50 Monte-Carlo runs, RI-MSCKF "clearly outperforms MSCKF especially for the consistency". **[verified snippet]** — [arXiv 1702.07920](https://arxiv.org/pdf/1702.07920)
- Yang, Chen, Lee, Huang (RA-L 2022) propose decoupled right-invariant error states that preserve VINS consistency. **[verified snippet]** — [arXiv 2205.01980](https://arxiv.org/html/2205.01980v3)
- EqVIO (van Goor & Mahony, an equivariant-filter VIO) reports "out-of-the-box consistency properties" as an alternative to the invariant EKF. **[verified snippet]** — [arXiv 2205.01980 related-work snippet](https://arxiv.org/html/2205.01980v3); [EqVIO arXiv 2205.01980 / T-RO 2023 context in T-ESKF](https://arxiv.org/pdf/2510.23359)
- The invariant EKF is a stable observer for problems with a group-affine structure. Barrau & Bonnabel (IEEE TAC 2017) show that the IEKF's linearized error dynamics are independent of the trajectory, which gives convergence guarantees from large initial errors. **[canonical]** — [Barrau & Bonnabel 2017, arXiv 1410.1465](https://arxiv.org/abs/1410.1465)
- The iterated EKF update is equivalent to Gauss-Newton on the MAP cost of a single update (Bell & Cathey 1993). **[canonical]** — [Bell & Cathey, IEEE TAC 1993](https://ieeexplore.ieee.org/document/220763)
- T-ESKF (2025) is another "transformed error-state" consistent VIO filter, which shows this remains an active design axis. **[verified title]** — [arXiv 2510.23359](https://arxiv.org/pdf/2510.23359)

### Inferences
- For the target system, a 2–3 iteration IEKF applied **only during the first roughly 1–3 s** (or only when the innovation is large relative to S) is a cheap way to cut the large first-update linearization error. It costs about 2–3 MSCKF update solves per frame for that period. Re-triangulating features inside each iteration (as LINS re-matches) gives most of the benefit for monocular depth.
- "Re-run the startup window": once a better estimate exists (for example after 1–2 s), re-propagating the IMU from t0 with the improved bias/velocity and redoing the updates is equivalent to a short batch smoother. It costs roughly window_length × per-frame cost once. This is the filter analogue of the VINS-Mono or OpenVINS hand-off described in section 6.
- A right-invariant error parameterization for (R, v, p) is a structural change, but it removes the need for FEJ and is reportedly robust to large initial attitude error. That makes it attractive when tilt is poorly known.

### Gaps
- I could not obtain numeric ablations (iterated vs single-pass) for ROVIO, FAST-LIO or MSCKF. FAST-LIO2's paper might have them, but I did not fetch it.
- I found no published "MSCKF iterated update" startup study with ATE numbers.

## 3. Observability-constrained EKF (OC-EKF) and First-Estimates Jacobian (FEJ); FEJ with a bad first estimate

### Takeaway
Standard EKF-VINS evaluates Jacobians at changing estimates. That gives the linearized system a spurious observable yaw direction, so the filter gains fake information and becomes overconfident and inconsistent. FEJ (evaluate Jacobians at first estimates) and OC (project Jacobians onto the correct nullspace) both fix this. MSCKF 2.0 (FEJ-based) was reported to be more accurate and consistent than an iterative sliding-window smoother. The startup pitfall: FEJ freezes linearization points at the first estimate. If that estimate is bad (bad initial velocity or tilt, a freshly triangulated low-parallax feature), the error persists. FEJ2 (2022) explicitly corrects for this.

### Cited Findings
- Huang, Mourikis, Roumeliotis (ISER 2008; published 2009) introduced the FEJ-EKF for SLAM: computing Jacobians at the first available estimate keeps the linearized system's observable subspace correct and improves consistency. **[verified]** — [Huang 2008 ISER](https://people.csail.mit.edu/ghuang/paper/Huang2008ISER.pdf); [Springer](https://link.springer.com/doi/10.1007/978-3-642-00196-3_43)
- Li & Mourikis (ICRA 2012; IJRR 2013, 32(6):690–711) present **MSCKF 2.0**. It ensures correct observability properties of the linearized model (via FEJ) and estimates camera-IMU calibration online. It reports "substantial consistency improvement" over existing EKF alternatives and **higher accuracy and consistency than a sliding-window iterative-minimization (fixed-lag smoother) algorithm** of comparable cost. **[verified abstract]** — [Li & Mourikis IJRR 2013](https://intra.ece.ucr.edu/~mourikis/papers/Li2013IJRR.pdf); [ICRA 2012](https://intra.ece.ucr.edu/~mourikis/papers/Li2012-ICRA.pdf)
- Hesch, Kottas, Bowman, Roumeliotis (TRO 2014, 30(1):158–176) gave the first report of VINS inconsistency due to spurious information gain from linearization. They propose OC-VINS, which enforces the unobservable directions in the Jacobians. An OC-MSCKF version appeared at ISER 2012. **[verified]** — [Hesch et al. TRO 2014](https://fling.seas.upenn.edu/~afosr/wiki/uploads/Chaserepository/Repository/UMN-ST-TRO-VINS-Consistency.pdf); [ISER 2012 OC-VINS MSCKF](https://www-users.cse.umn.edu/~stergios/papers/ISER-2012-OC-VINS-MSCKF.pdf)
- Huang, Kaess, Leonard (ICRA 2014), "Towards Consistent Visual-Inertial Navigation": the standard EKF-VINS propagation Jacobian violates the semigroup property of a state-transition matrix. STOC-VINS enforces both the observability constraints and that property. **[verified]** — [Huang et al. ICRA 2014](https://www.cs.cmu.edu/%7Ekaess/pub/Huang14icra.html); [TR](https://people.csail.mit.edu/ghuang/paper/tr/stocvins.pdf)
- **FEJ2** (Chen, Yang, Geneva, Huang, ICRA 2022) targets the gap between the "best" Jacobian (at the latest estimate) and the FEJ (at the first estimate). It keeps FEJ's observability property but models and compensates the linearization error caused by **poor first estimates**. The authors prove consistent covariance estimation during the update and report better robustness to poor first estimates and high measurement noise than prior consistent VINS. **[verified abstract]** — [IEEE Xplore 9811831](https://ieeexplore.ieee.org/abstract/document/9811831); [NSF PAR copy](https://par.nsf.gov/servlets/purl/10376064)
- FEJ has been extended to optimization-based VINS with marginalization (Chen, Geneva, Peng, Lee, Huang). **[verified snippet]** — [NSF PAR 10479086](https://par.nsf.gov//servlets/purl/10479086)
- OpenVINS uses FEJ by default and documents it as keeping the 4-DOF unobservable subspace from gaining information. **[verified snippet]** — [ov_core FEJ docs](https://docs.ros.org/en/api/ov_core/html/fej.html) (the page was bot-blocked on direct fetch; the content was confirmed via search snippet)

### Inferences
- **Startup pitfall, concretely:** in an MSCKF with FEJ, each clone's orientation and position FEJ value is its propagated estimate at clone time. Clones created in the first 0.5–1 s, before velocity and tilt have converged, carry bad FEJ points for the whole time they stay in the window (for example 11 clones ≈ 0.55 s at 20 Hz). The IMU-state FEJ (v, p) is reset on each propagation, so the damage is bounded by the window length. Mitigations, from cheapest to most expensive:
  1. Delay enabling FEJ (use standard Jacobians) for the first N frames, then switch to FEJ. This is cheap, but it trades consistency for accuracy during startup.
  2. After a large correction early on, reset the FEJ points of existing clones to their current estimates. Doing this once at the hand-off moment is cheap.
  3. FEJ2-style correction, which adds a noise inflation term for the first-estimate error. The cost is modest: extra Jacobian terms per update.
  4. Use an invariant error formulation (section 2), which avoids the need for FEJ.
- Over a short 17–60 m trajectory, the yaw-consistency benefit of FEJ/OC is real but second-order. The bad-first-estimate penalty can dominate in the first 1–2 s, so option 2 above is a good default.

### Gaps
- I could not extract NEES or RMSE numbers from FEJ2, MSCKF 2.0 or OC-VINS in this session; the PDFs were unreadable. The report should treat these consistency gains as qualitatively established and say that the magnitudes were not confirmed here.

## 4. Multiple-hypothesis filters and filter banks (MMAE, Gaussian-sum) over unknown scale, depth or initial velocity

### Takeaway
Multi-hypothesis methods have historically been used for monocular **feature depth** initialization: particles or Gaussian sums along the ray, pruned with a sequential probability ratio test (SPRT). Inverse-depth parameterization mostly replaced them in single-hypothesis filters. For **initial velocity, tilt or scale** in VIO, filter banks are rarely used in the literature. The cost grows linearly with the number of hypotheses (K full filters), which is usually prohibitive, but a bank of K reduced filters over the first 1–2 s is affordable.

### Cited Findings
- MonoSLAM (Davison et al., TPAMI 2007) initializes depth with a 1-D particle distribution (uniform over roughly 0.5–5 m) along the ray. The feature is promoted to a Gaussian 3-D point once the depth distribution is unimodal: delayed initialization by multiple depth hypotheses. **[canonical]** — [Davison et al. 2007, IEEE TPAMI](https://ieeexplore.ieee.org/document/4160954)
- Kwok, Dissanayake, Ha (ICRA 2005), "Bearing-only SLAM using a SPRT based Gaussian sum filter": a Gaussian sum over depth with SPRT pruning of hypotheses. **[canonical]** — [Kwok et al. ICRA 2005](https://ieeexplore.ieee.org/document/1570241)
- Solà et al. (IROS 2005), "Undelayed initialization in bearing only SLAM": a geometric series of Gaussians along the ray, with federated information sharing so that weak hypotheses are pruned cheaply. **[canonical]** — [Solà et al. 2005](https://ieeexplore.ieee.org/document/1545392)
- Civera et al. (TRO 2008) show that a single Gaussian in **inverse depth** covers the depth range from a near bound to infinity well enough that undelayed initialization no longer needs multi-hypothesis machinery (see section 5). **[canonical]** — [Civera, Davison, Montiel 2008](https://ieeexplore.ieee.org/document/4637878)

### Inferences
- For a moving start with unknown velocity: run K=3–5 short MSCKF hypotheses, for example velocity seeds from a learned prior, zero, and ± the forward direction. Weight them by innovation likelihood (the MMAE weight ∝ N(r; 0, S)) and collapse to the winner after about 0.5–1 s. Cost is K× the per-frame update for that period only. With roughly 100 feature rows per frame and a roughly 15+6·11 state, this is a few hundred microseconds per hypothesis per frame in C/C++.
- Scale is directly observable from the IMU only with sufficient acceleration excitation. A bank over scale is redundant if velocity is in the state, because velocity hypotheses implicitly cover scale.

### Gaps
- I found no published VIO/MSCKF paper that uses an MMAE or Gaussian-sum bank over **initial velocity** with quantitative results. This appears to be an open or unpublished idea.
- I did not verify the cost and accuracy numbers from Kwok 2005 and Solà 2005.

## 5. Delayed vs undelayed feature initialization; inverse depth; anchored inverse depth

### Takeaway
MSCKF is "delayed by design": features are triangulated only after their track ends, then marginalized through nullspace projection, so bad depth priors never enter the state. That is robust at startup, but it means **no visual information until the first tracks complete**. With 20 Hz and roughly 5–11-frame tracks, that is 0.25–0.55 s. Undelayed inverse-depth (and anchored inverse-depth) SLAM features give information from the second observation onward and handle low parallax (the typical case for a monocular start). They do cost state dimension (cubic in the EKF update).

### Cited Findings
- MSCKF (Mourikis & Roumeliotis, ICRA 2007) keeps a sliding window of camera poses. It uses each feature's track once it ends, projecting its measurements onto the left nullspace of the feature Jacobian so the feature need not be in the state. The cost is linear in the number of features. **[canonical]** — [Mourikis & Roumeliotis ICRA 2007](https://www-users.cse.umn.edu/~stergios/papers/ICRA07-MSCKF.pdf)
- Civera, Davison, Montiel (TRO 2008): inverse depth ρ=1/d plus the anchor's camera position and bearing angles (6-D per feature). The measurement equation is close to linear in inverse depth even for low parallax and distant points, which allows **undelayed** initialization. They use an initial ρ0 with a σ_ρ wide enough that the 95% region reaches infinity, and a linearity index for switching to XYZ (3-D). **[canonical]** — [Civera et al. TRO 2008](https://ieeexplore.ieee.org/document/4637878)
- OpenVINS supports SLAM features in anchored inverse-depth representations (anchored relative to a clone) alongside MSCKF features. New SLAM features are delayed-initialized into the state after a chi-square test on the track. **[canonical]** — [OpenVINS, Geneva et al. ICRA 2020](https://docs.openvins.com/) ; [OpenVINS paper](https://pgeneva.com/downloads/papers/Geneva2020ICRA.pdf)
- ROVIO uses a robocentric bearing-vector plus inverse-distance landmark parameterization directly in the IEKF state. **[verified snippet]** — [arXiv 2409.12074 (describing ROVIO)](https://arxiv.org/pdf/2409.12074)
- Abeywardena et al. (ICRA 2016) avoid feature depth entirely. They use the **epipolar constraint** between image pairs plus the quadrotor dynamic model, and run at 200 Hz IMU / 50 Hz camera on a 50 g computer. No depth state means no depth-initialization problem. **[verified abstract]** — [arXiv 1607.01486](https://arxiv.org/abs/1607.01486)

### Inferences
- For a moving-start monocular system, a hybrid works well: MSCKF features for bulk updates, plus a few inverse-depth SLAM features initialized after 3–4 frames, which give earlier velocity and scale information. Use 2-frame epipolar or rotation-compensated flow constraints in the first 0.25 s, before any track is long enough to triangulate.
- Low-parallax tracks at startup produce poorly conditioned triangulations. Gate MSCKF features on the triangulation condition number or minimum baseline. Otherwise early updates inject wrong depth, and therefore wrong velocity.

### Gaps
- I found no quantitative startup-latency comparison of delayed vs undelayed initialization in VIO. Civera 2008's results are for monocular-only SLAM.

## 6. Partial update / Schmidt-KF; fixed-lag smoothing or sliding-window batch over the first seconds handing off to a filter

### Takeaway
Partial updates (apply only a fraction β of the correction to weakly observable states such as biases) limit linearization damage early on. A Schmidt-KF freezes the mean of chosen states while keeping their cross-covariance consistent. The strongest demonstrated startup pattern, though, is **batch initialization (closed-form plus MLE or visual-inertial BA over 1–2 s) handed off to a filter or smoother with a recovered covariance**. OpenVINS, VINS-Mono and ORB-SLAM3 all do this. MSCKF 2.0's result (filter ≥ iterative fixed-lag smoother) shows that the filter can match a smoother once it is initialized well.

### Cited Findings
- Jackson, Nielsen, McLain, Beard (ICRA 2019), "Improving the Robustness of Visual-Inertial Extended Kalman Filtering": the **partial-update** formulation limits the effect of linearization errors in **partially observable states (for example, IMU biases)**. In the same paper, a **linear drag term** in the velocity dynamics improves accuracy. The evaluation is a Monte-Carlo simulation of accuracy and consistency. **[verified abstract]** — [IEEE Xplore 8794164](https://ieeexplore.ieee.org/document/8794164/metrics); [NSF PAR copy](https://par.nsf.gov/servlets/purl/10135575)
- OpenVINS dynamic initialization (v2.6) does a linear solve plus Ceres MLE over a window, then hands the state and recovered covariance to the MSCKF (with inflation; see section 1). **[verified]** — [PR #232](https://github.com/rpng/open_vins/pull/232); [issue #433](https://www.github.com/rpng/open_vins/issues/433)
- Schmidt-MSCKF: Geneva, Eckenhoff, Huang (ICRA 2019), "A Linear-Complexity EKF for Visual-Inertial Navigation with Loop Closures". It treats map features as "nuisance" states whose means are not updated, while their cross-correlations are tracked, which keeps the update cost linear in them. **[canonical]** — [Geneva et al. ICRA 2019](https://pgeneva.com/downloads/papers/Geneva2019ICRA.pdf)
- Li & Mourikis 2013: MSCKF 2.0 achieves higher accuracy and consistency than a sliding-window iterative-minimization estimator. So "filter after good initialization" is not inherently worse than a fixed-lag smoother. **[verified abstract]** — [Li & Mourikis IJRR 2013](https://intra.ece.ucr.edu/~mourikis/papers/Li2013IJRR.pdf)
- sqrtVINS (2025) is a square-root filter-based VINS that claims robust and "ultrafast" initialization and tracking. It is a recent example of the filter-side initialization pipeline. **[verified title]** — [arXiv 2510.10346](https://arxiv.org/html/2510.10346v1)
- Basalt (Usenko et al., RA-L 2020) is a fixed-lag VIO optimizer with nonlinear factor recovery. It is an example of a sliding-window smoother rather than a filter. **[canonical]** — [Usenko et al. arXiv 1904.06504](https://arxiv.org/abs/1904.06504)
- ORB-SLAM3's inertial initialization (Campos et al., ICRA 2020) is an inertial-only MAP estimation on top of up-to-scale visual SfM over about 2 s, followed by later refinement. **[canonical]** — [Campos et al. arXiv 1912.13464](https://arxiv.org/abs/1912.13464)

### Inferences
- Recommended pattern for a 0.5–3 s budget:
  1. Run a small batch problem from 0 to about 1 s (around 20 frames, about 15 velocity, gravity and bias unknowns plus features), Gauss-Newton with 3–5 iterations.
  2. Hand off with a Hessian-derived P, inflating orientation and velocity.
  3. Reset FEJ points at hand-off.
  4. Apply partial updates (β ≈ 0.2–0.5) to bias states for the first 1–2 s after hand-off.
- Until the batch is ready, the filter can run with wide P and inertial-only or model-aided propagation (section 8), so there is no output gap.

### Gaps
- I could not extract the β values used by Jackson et al. 2019, or their RMSE and NEES improvements; the PDF was unreadable.
- I did not verify ORB-SLAM3 init timing and scale-error numbers, so I left them out.

## 7. Robust gating and outlier handling at startup (chi-square gating with poor priors)

### Takeaway
Chi-square (Mahalanobis) gating uses S = HPHᵀ + R. Under a poor prior, the gate is too loose when P is large, so outliers get through and corrupt the poorly constrained state. It is too tight when P is overconfident, so the filter rejects the very measurements that would correct it (lock-out). Startup gating should be adaptive: either geometry-only outlier rejection that is independent of the state, or a gate tied to the actual consistency of P.

### Cited Findings
- OpenVINS gates every MSCKF and SLAM feature update with a chi-square test, using a configurable multiplier on the 95% chi-square threshold. It also uses a chi-square test when delayed-initializing SLAM features. **[canonical]** — [OpenVINS docs](https://docs.openvins.com/); [Geneva et al. ICRA 2020](https://pgeneva.com/downloads/papers/Geneva2020ICRA.pdf)
- Overconfident recovered covariances from short initialization windows (OpenVINS issue #433) make tight gates likely right after hand-off. **[verified]** — [issue #433](https://www.github.com/rpng/open_vins/issues/433)
- LINS' iterated filter re-establishes correspondences at each iteration, which reduces errors from wrong matches. This is an iterate-and-regate pattern. **[verified snippet]** — [LINS](https://ar5iv.arxiv.org/html/1907.02233)

### Inferences
- At startup, reject outliers with **state-independent** tests first: 2-point or 1-point RANSAC with gyro-compensated rotation (cheap), and forward-backward KLT checks. Then apply the χ² gate with a large multiplier (for example 3–5x) that decays to 1x as the trace of P shrinks.
- Track the rejection rate. If more than about 30–50% of features fail χ² in a frame, treat it as filter inconsistency (inflate P) rather than as outliers.
- Huber or Cauchy reweighting inside an IEKF iteration is a robust alternative to hard gating at modest extra cost.

### Gaps
- I found no paper that quantifies χ²-gate failure modes specifically during VIO startup.

## 8. Velocity priors, ZUPT, and motion-model pseudo-measurements for drones (drag models)

### Takeaway
For quadrotors, the accelerometer's body-x/y specific force is dominated by **rotor drag ∝ −μ·v_body**, because thrust is along body-z. A linear drag model therefore makes **horizontal body velocity observable from the IMU alone**, without vision. This is a strong, cheap pseudo-measurement for exactly the unknown-velocity moving-start problem. Several groups have demonstrated drift-free velocity, or VIO accuracy gains, from it.

### Cited Findings
- Abeywardena, Huang, Barnes, Dissanayake, Kodagoda (ICRA 2016): an EKF fuses a 200 Hz MEMS IMU, 50 Hz monocular images (epipolar constraints) and the quadrotor dynamic model. The paper states that combining the dynamic model with the epipolar constraint gives **drift-free velocity and attitude estimates, even with accelerometer and gyro biases**. It handles the unobservability that occurs in hover and runs in real time on a 50 g embedded computer. **[verified abstract]** — [arXiv 1607.01486](https://arxiv.org/abs/1607.01486)
- In Abeywardena's earlier work and thesis, the quadrotor dynamics alone give drift-free velocity from inertial sensors. That line of work also notes that inter-frame visual constraints become unobservable when the camera is stationary. **[verified snippet]** — [Abeywardena thesis, UTS](https://opus.lib.uts.edu.au/bitstream/10453/34465/2/02whole.pdf)
- Abeywardena et al. (model-aided VIF amid wind): a nonlinear observability analysis shows that vehicle pose and **two components of the wind velocity** are jointly observable, and the third is not. **[verified snippet]** — [UTS paper](https://opus.lib.uts.edu.au/bitstream/10453/30529/4/Model-aided%20State%20Estimation%20for%20Quadrotor%20Micro%20Air%20Vehicles%20amidst%20Wind%20Disturbances.pdf)
- Jackson et al. (ICRA 2019): adding a **linear drag term** to the VI-EKF velocity dynamics improves estimation accuracy. They cite Leishman et al., who showed that a linear drag model on a multirotor significantly improves estimation accuracy. **[verified snippet]** — [NSF PAR copy](https://par.nsf.gov/servlets/purl/10135575); [IEEE Xplore](https://ieeexplore.ieee.org/document/8794164/metrics)
- Leishman, Macdonald, Beard, McLain (IEEE Control Systems Magazine 2014), "Quadrotors and accelerometers: state estimation with an improved dynamic model": the body-frame horizontal accelerometer reading ≈ −(μ/m)·v_body (rotor drag). This contradicts the common assumption that accelerometers measure gravity tilt in quasi-static flight. **[canonical]** — [Leishman et al. 2014](https://ieeexplore.ieee.org/document/6712082)
- Cioffi, Bauersfeld, Scaramuzza (2023), "HDVIO: hybrid dynamics VIO", note that standard model-based VIO assumptions on drag "no longer hold" under strong wind or fast flight, and use a learned plus physical hybrid dynamics model. HDVIO2.0 (2025) adds wind and disturbance estimation. **[verified snippet]** — [arXiv 2306.11429](https://arxiv.org/html/2306.11429v2); [HDVIO2.0 arXiv 2504.00969](https://arxiv.org/html/2504.00969v2)
- A 2024 Sensors paper, "A Sensor Fusion Approach to Observe Quadrotor Velocity", works on the same problem. **[verified title]** — [PMC11175281](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11175281/)
- OpenVINS includes a zero-velocity update (ZUPT) module that uses an IMU-excitation and disparity test. It applies only to stationary starts, not to the moving-start case. **[canonical]** — [OpenVINS docs](https://docs.openvins.com/)

### Inferences
- **Highest value-to-cost item for this project.** Add the pseudo-measurement a_xy,meas − b_a,xy = −k_d·v_body,xy + noise. This is a 2-row update at IMU rate, or decimated to 20–50 Hz, and costs almost nothing. Because v_body = Rᵀ v_world, the update also constrains tilt. k_d can be estimated online as a state, or calibrated offline (typical k_d/m ≈ 0.1–0.5 s⁻¹ for small quads; this value is not verified here). It gives velocity information from t=0, before any visual track matures, which directly attacks the unknown-initial-velocity problem.
- Caveats: wind makes this measure **airspeed**, not ground speed (two components observable per Abeywardena). Aggressive maneuvers add nonlinear drag and induced-drag terms. Accelerometer bias in x/y trades off against velocity, which is why vision is still needed to separate them. Use a conservative noise level and χ²-gate the pseudo-measurement.
- If the data are simulated (for example ProcTHOR-like flights without rotor drag), this pseudo-measurement provides **no information and can bias the estimate**. Check the simulator's accelerometer model before relying on it.
- Other cheap priors: a thrust-aligned model (specific force ≈ thrust along body-z, so a_xy ≈ drag only), a bounded-speed prior (|v| < v_max as a soft constraint), and a learned velocity prior with an honest covariance used as an initial P / x0 rather than as a repeated measurement. Repeated use would double-count it.

### Gaps
- I could not extract the numeric gains (velocity RMSE, drift %) from Abeywardena 2016, Jackson 2019, Leishman 2014 or VIMO/VID-Fusion in this session.
- I did not verify any measured drag coefficient values.

## 9. Compute-cost summary (for a 20 Hz mono / 200 Hz IMU budget) and publication years

### Takeaway
Ordered roughly by gain per unit cost for a moving start: drag pseudo-measurement (about free), FEJ reset at hand-off (free), adaptive χ² plus state-independent RANSAC (cheap), partial updates on biases (free), a 2–3-iteration IEKF during startup only (2–3x update cost for 1–3 s), short batch init with covariance hand-off (one-off Gauss-Newton over about 20 frames), K-hypothesis bank (K× cost for about 1 s), and an invariant-EKF reformulation (refactor, no runtime penalty).

### Cited Findings
- MSCKF cost is linear in the number of features and cubic in the number of window clones (Mourikis & Roumeliotis 2007). **[canonical]** — [ICRA 2007](https://www-users.cse.umn.edu/~stergios/papers/ICRA07-MSCKF.pdf)
- The FAST-LIO gain formulation makes the cost depend on state dimension rather than measurement dimension. This is useful when iterating with many feature rows. **[verified snippet]** — [arXiv 2010.08196](https://arxiv.org/pdf/2010.08196.pdf)
- Abeywardena 2016 ran a model-aided EKF on a 50 g computer at 200 Hz IMU / 50 Hz camera. **[verified]** — [arXiv 1607.01486](https://arxiv.org/abs/1607.01486)
- Publication years: MonoSLAM 2007; MSCKF 2007; Civera inverse depth 2008; FEJ-EKF 2008/2009; MSCKF 2.0 2012/2013; OC-VINS 2012/2014; STOC-VINS 2014; Leishman drag 2014; Abeywardena model-aided VIO 2016; ROVIO IEKF 2015/2017; RI-MSCKF 2017; Barrau-Bonnabel IEKF 2017; Jackson drag + partial update 2019; Schmidt-MSCKF 2019; OpenVINS 2020; ORB-SLAM3 init 2020; Basalt 2020; FAST-LIO 2021; FEJ2 2022; decoupled RI-VINS 2022; OpenVINS dynamic init (v2.6) about 2022; HDVIO 2023; HDVIO2.0 2025; sqrtVINS 2025. — sources as cited in the sections above

### Inferences
- In C/C++ wasm with a small budget, all the techniques above except a full-state multi-hypothesis bank fit comfortably at 20 Hz. Even the bank fits if it is limited to the first 1 s with K ≤ 3.

### Gaps
- No source gave per-frame millisecond timings for IEKF iterations or startup batch init on embedded hardware.
- I found no paper that reports ATE or NEES specifically over the **first 0.5–3 s** for any of these techniques. Nearly all evaluations report full-trajectory metrics. The startup-window effect has to be measured locally.
