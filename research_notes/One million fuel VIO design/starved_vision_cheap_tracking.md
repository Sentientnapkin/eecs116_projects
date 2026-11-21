# Cheap visual measurements for vision-starved conditions (mono+IMU, 320x240 @20 Hz, <=0.5 M wasm ops/frame)

Scope: which visual front ends still give useful motion constraints in low-texture or dark indoor scenes, what they cost per frame, and how to detect when vision should be ignored. Source caveats: several primary PDFs (PX4Flow ICRA 2013, SVO ICRA 2014, ROVIO IROS 2015 / IJRR 2017, UCR photometric MSCKF) could not be fetched or text-extracted in this session. Claims about them come from secondary summaries and are marked as such. All op-count estimates are my own arithmetic, listed under Inferences, not taken from sources.

## 1. Direct and semi-direct sparse methods (SVO, DSO, ROVIO patches, edgelets) vs corners: low-texture behaviour and per-patch cost

### Takeaway
Direct methods put the residual on gradient pixels (edges, weak gradients), not only on corners. DSO's authors report they track through very-low-texture scenes where indirect methods fail, and that a FAST-corners-only variant performs significantly worse. Per point, DSO uses an 8-pixel residual pattern and ROVIO an 8x8 patch per pyramid level. At our budget, a few hundred 8-pixel points or about 20-40 small patches per frame are affordable. The direct model's main risk is geometric noise (rolling shutter, bad intrinsics), not low texture.

### Cited Findings
- DSO point selection: about 2000 candidate points per keyframe. The image is split into 32x32 blocks, each with an adaptive threshold (median absolute gradient + g_th = 7). One pass picks the highest-gradient pixel per dxd cell; two more passes use lower thresholds and cells of 2d and 4d, so the points include edges and weak-gradient pixels, not just corners. — [DSO, Engel et al. (ar5iv 1607.02565)](https://ar5iv.labs.arxiv.org/html/1607.02565)
- DSO residual: each point uses 8 pixels "arranged in a slightly spread pattern". A 3x3 neighbourhood did slightly worse, and larger patterns added cost without benefit. — [DSO](https://ar5iv.labs.arxiv.org/html/1607.02565)
- DSO claims it "is able to track through scenes with very little texture, whereas indirect approaches fail", but gives no quantitative low-texture comparison. Restricting it to FAST corners "significantly decreases performance". — [DSO](https://ar5iv.labs.arxiv.org/html/1607.02565)
- DSO limitation: the direct model is "ill-suited in the presence of strong geometric noise" (rolling shutter, poor intrinsics). Optimization fails entirely when geometric noise δg > 1.5 px, where indirect methods are more robust. — [DSO](https://ar5iv.labs.arxiv.org/html/1607.02565)
- DSO reduced settings (800 points, 6 active keyframes, 320x240, at most 4 Gauss-Newton iterations) ran about 5x faster than real time on a laptop CPU. Recovery tracking on the coarsest pyramid level costs about 0.5 ms per attempt. — [DSO](https://ar5iv.labs.arxiv.org/html/1607.02565)
- ROVIO puts the pixel-intensity errors of image patches directly into the EKF as the innovation. Each landmark has a multilevel patch of 8x8 pixels on each level of a factor-2 pyramid: 256 intensity errors per feature with 4 levels. The IJRR version reports high robustness to low scene texture and motion blur. — [search summary of Bloesch et al. 2015/2017](https://journals.sagepub.com/doi/full/10.1177/0278364917728574); patch details from a [secondary roadmap summary](https://raw.githubusercontent.com/changh95/visual-slam-roadmap/main/level-06-vio-vins/rovio.md)
- ROVIO uses bearing vectors on the S2 manifold, runs on a single standard CPU core, and estimates IMU biases and camera-IMU extrinsics online. It needs per-environment tuning (number of features, initial covariances, inverse depth). — [Sa et al., "Build Your Own Visual-Inertial Drone" (arXiv 1708.06652)](https://arxiv.org/pdf/1708.06652)
- Secondary summary of ROVIO: features with large predicted uncertainty get a patch-based pre-alignment before the EKF update, which improves the linearisation point. — [roadmap summary (secondary)](https://raw.githubusercontent.com/changh95/visual-slam-roadmap/main/level-06-vio-vins/rovio.md)
- SVO, per a secondary summary that I could not verify against the paper: sparse model-based image alignment of 4x4 patches around features with known depth, then 8x8 affine-warped patches for feature refinement. Reported timing is about 3 ms per frame on an i7 laptop and 18 ms on an Odroid-U2. — [roadmap summary of SVO (secondary)](https://raw.githubusercontent.com/changh95/visual-slam-roadmap/main/level-03-monocular-slam/svo.md); the [SVO 2.0 project page](https://rpg.ifi.uzh.ch/svo2.html) claims up to 100 fps on a smartphone-class processor (Odroid XU4).
- Zheng et al. (ICRA 2017) build photometric patch-based VIO on the MSCKF, as an alternative to a ROVIO-style EKF over patches, and compare it with point-feature MSCKF. The PDF server refused the connection, so I have no numbers. — [Zheng et al. ICRA 2017 (UCR)](https://intra.ece.ucr.edu/~mourikis/papers/ZhengetalICRA2017.pdf)
- DSOL (arXiv 2203.08182) is a faster direct sparse odometry scheme and a potential source of further speedups; not fetched. — [DSOL](https://arxiv.org/pdf/2203.08182)

### Inferences
- Per-point cost (my estimate): one Gauss-Newton iteration of a DSO-style 8-pixel point costs about 8 x (bilinear sample ~8 ops + residual/weight ~4 + JᵀJ/Jᵀr accumulation ~10) ≈ 180 scalar ops. With 4-wide SIMD lanes across points, about 50-60 ops. 300 points x 3 iterations ≈ 50-160 k ops, which is within budget.
- ROVIO-style 8x8 patch on 2 levels = 128 px per patch per iteration, about 2-3 k scalar ops including the 2-D alignment Jacobian. That is about 7 k ops for 3 iterations. 30 patches ≈ 200 k ops; 4 levels doubles it. Use 2 levels at 320x240.
- "Edgelets" (SVO's gradient-only features) can be had cheaply: run DSO-style block-max gradient selection on a 160x120 or 320x240 gradient image (about 1-2 ops per pixel with SIMD, roughly 20-40 k ops). Constrain each edgelet only along its gradient normal (a 1-D residual), which is the well-conditioned direction in low texture.
- Since our pipeline already has an MSCKF (gp_msckf), the lowest-integration-cost option is to keep MSCKF and add gradient-pixel patches as extra feature types tracked by direct alignment rather than KLT on corners. This is in the spirit of Zheng 2017 and ROVIO. Under the MSCKF nullspace projection, an edgelet contributes a 1-D measurement.
- Rolling shutter or bad calibration on the competition camera would hurt direct methods more than corners (per DSO). This should be checked on the data before committing.

### Gaps
- No primary-source per-patch timing or low-texture ATE numbers for ROVIO or SVO (PDFs not retrievable here).
- No numbers from Zheng et al. 2017 on photometric vs point MSCKF.

## 2. Whole-image or coarse optical flow (PX4Flow SAD, phase/correlation flow, coarse LK) as a velocity constraint

### Takeaway
Global or coarse flow is the cheapest constraint that keeps working when corners vanish. A rotation-compensated global shift on a 64x64 to 128x96 image costs well under 0.5 M ops. The literature numbers are all for downward cameras with a range sensor, where flow x height = velocity: horizontal-velocity RMSE was about 0.07 m/s for FFT correlation flow vs about 0.15 m/s for PX4Flow-style SAD. For our forward/oblique camera, the flow only gives translational velocity divided by depth, so a depth or plane hypothesis is needed.

### Cited Findings
- PX4Flow: MT9V034 global-shutter sensor (752x480 native). Flow is computed at 400 Hz on a 4x binned, cropped region. It has an on-board 16-bit gyro for rotation compensation and works indoors and in low outdoor light without an LED, thanks to 24x24 µm binned super-pixels and AEC/AGC. Quality is filtered by a pattern-quality threshold (BFLOW_F_THLD = 40) and a correlation threshold (BFLOW_V_THLD = 5000). — [PX4 docs: PX4FLOW](https://docs.px4.io/v1.13/en/sensor/px4flow)
- PX4Flow is based on SAD block matching, choosing the best match in the search area. — [Correlation Flow, Wang et al. ICRA 2018 (arXiv 1802.07078)](https://arxiv.org/pdf/1802.07078)
- Honegger et al. (ICRA 2013) is the original PX4Flow paper. Per the search snippet, it compares the sensor against a mouse sensor and GPS and validates against VICON. Full numbers were not retrievable. — [Honegger et al. 2013 (scispace copy)](https://typeset.io/pdf/an-open-source-and-open-hardware-embedded-metric-optical-kuvbhck417.pdf)
- Correlation Flow computes translation flow as the argmax of a kernel cross-correlation done with FFTs, at O(N log N). Scale and rotation come from a log-polar variant. Results are reported as robust to noise, motion blur and image distortion. — [Correlation Flow](https://arxiv.org/pdf/1802.07078)
- Correlation Flow vs PX4Flow, horizontal velocity on 5 Vicon flights (m/s): CF mean RMSE 0.072 / MAE 0.057; PX4Flow mean RMSE 0.146 / MAE 0.118. Per-test CF RMSE ranged 0.069-0.076. — [Correlation Flow, Table I](https://arxiv.org/pdf/1802.07078)
- Correlation Flow processes full 320x240 images in real time on an Intel x5-Z8350 (2 W SDP) with spare CPU. Comparable flow systems use only 64x64 (PX4Flow) and 128x96 (EdgeFlow) images to reach high update rates. — [Correlation Flow](https://arxiv.org/pdf/1802.07078)
- EdgeFlow / Edge-FS (McGuire et al., RA-L 2017) computes optical flow and stereo disparity by matching histograms of image gradients summed along the two image axes. It runs at 20 Hz on a 168 MHz STM32F4 with 192 kB RAM and enabled autonomous flight of a 40 g pocket drone. — [McGuire et al. arXiv 1612.06702](https://arxiv.org/abs/1612.06702); the histogram description is from the [Correlation Flow related-work section](https://arxiv.org/pdf/1802.07078)
- Crazyflie Flow deck (PMW3901 mouse-type sensor): Bitcraze notes problems over low-texture areas and uses the sensor's squal (feature count) and shutter-time outputs to explain error spread. — [Bitcraze blog](https://www.bitcraze.io/?p=9292)
- BatDeck (arXiv 2412.10048): on a flat, featureless table, their ultrasonic ego-velocity (0.019 m/s error) outperformed optical flow even when the flow was fused with IMU. — [BatDeck](https://arxiv.org/html/2412.10048v1)
- An unconfirmed forum report measured about 100 ms delay on raw PMW3901 output. — [Bitcraze forum](https://forum.bitcraze.io/viewtopic.php?p=18193)

### Inferences
- Cost estimates (mine, wasm SIMD128, 1 op per instruction):
  - 2x2 box pyramid 320x240 -> 160x120 -> 80x60 via u8 averaging (`i8x16.avgr_u` plus shuffles): about 10-15 k ops.
  - Global SAD shift search on 80x60 (4800 px = 300 vectors), ±4 px (81 candidates), about 5 ops per vector (load, `sub_sat` both ways or `abs`, widen-add): about 120 k ops. With gyro de-rotation predicting the shift, ±2 px (25 candidates) is about 40 k ops. Sub-pixel accuracy comes from a parabola fit on the 3x3 SAD neighbourhood.
  - Block SAD on a coarse grid (e.g. 12 blocks of 16x16 on 80x60, ±3 px): about 12 x 49 x 16 x 5 ≈ 47 k ops. This gives a local flow field, not one shift, which is necessary for a forward camera.
  - Translation-only LK on 80x60 with precomputed gradients: about 15-20 ops per pixel per iteration in scalar code, about 5 with SIMD. 3 iterations ≈ 70 k ops. Per-block LK on a 4x3 grid costs the same, plus a 2x2 solve per block.
  - Phase correlation on 64x64 (two forward FFTs and one inverse; 2-D complex FFT ≈ 5 N log2 N ≈ 245 k flops each, about 60-80 k f32x4 ops each): about 200-250 k ops in total, which is the most expensive option here. Unless the noise robustness of the kernel/phase variant is needed, use SAD or LK.
- Forward-camera geometry: after gyro de-rotation, each block's flow equals (projection of v) / depth(block). One global shift is meaningless when depth varies across the image. Workable options:
  - (a) Use the block flows to estimate the focus of expansion (FoE). This gives the direction of the camera-frame velocity, with no scale needed, as a 2-DoF unit-vector measurement in the EKF.
  - (b) Attach a depth to each block from the last good MSCKF/SLAM features or a fitted floor/wall plane, then fuse v/d as a velocity measurement.
  - (c) Treat each block as a short-lived "feature" with an inverse-depth state (ROVIO-like) so the filter estimates depth.
  - Option (a) is cheapest and robust. Velocity-direction drift is a main ATE driver when vision drops out, because the accelerometer integrates errors in v.
- The published accuracy (≈0.07-0.15 m/s with known height) bounds what global flow can deliver. At ~0.1 m/s random error over a 5 s blackout, position error is ≈0.2-0.5 m if it is not averaged down. That is still far better than coasting on the IMU alone with an uncertain velocity bias.

### Gaps
- No published evaluation of coarse or global flow for a forward-looking camera fused with IMU in low texture. All the numbers are for downward camera + rangefinder.
- PX4Flow's original VICON error figures could not be extracted.

## 3. Line and edge features (PL-VIO, PL-VINS, point-line MSCKF) and their cost

### Takeaway
Lines improve accuracy only modestly (12-16% ATE on EuRoC for PL-VINS vs VINS-Mono) and line extraction is expensive. LSD costs 62-70 ms per frame on a laptop i7, and even the modified LSD costs 20 ms, far beyond a 0.5 M-op budget. Full LSD/LBD line pipelines are out. A cheap edgelet or gradient-direction residual captures most of the low-texture benefit.

### Cited Findings
- Original LSD: 62 ms to detect 647 lines in a 782x480 image. On EuRoC MH-04 (i7-10710U @1.1 GHz), line detection takes 70 ms with LSD (PL-VIO) vs 20 ms with modified LSD (PL-VINS). Line tracking takes 15 / 12 ms, and point detection+tracking 15 ms. The PL-VIO front-end thread is about 100 ms per frame, so PL-VIO runs at a 5 Hz pose rate. — [PL-VINS (ar5iv 2009.07462), Table IV](https://ar5iv.labs.arxiv.org/html/2009.07462)
- Accuracy (EuRoC ATE RMSE without loop closure): VINS-Mono 0.247 m vs PL-VINS 0.208 m on average (−16%). MH-04 improved 0.375 -> 0.270 (−28%); V1-02 got worse, 0.095 -> 0.105. — [PL-VINS Table II](https://ar5iv.labs.arxiv.org/html/2009.07462)
- PL-VIO cannot run in real time because line extraction is expensive. — [PL-VINS](https://ar5iv.labs.arxiv.org/html/2009.07462)
- Trifo-VIO argues that low-texture environments "contain planar elements that are rich in linear shapes" and that edge detection is less sensitive to lighting changes. It uses LSD + LBD, with point reprojection and point-to-line distance as MSCKF innovations, at a cost linear in the number of features. It reports "significantly better results" than S-MSCKF on a fast-motion, low-texture sequence (PI_3058), but no ms timings and no point-only ablation. — [Trifo-VIO (ar5iv 1803.02403)](https://ar5iv.labs.arxiv.org/html/1803.02403)
- LBD-style handcrafted line descriptors lose discriminability in low-texture or repetitive regions, which makes data association fragile. — [OTPL-VIO (arXiv 2603.09653)](https://arxiv.org/html/2603.09653v1)
- Line-augmented cuVSLAM (2026) targets low-texture environments, which suggests lines remain an active direction (GPU-based, not fetched). — [arXiv 2610.20958](https://arxiv.org/pdf/2610.20958)

### Inferences
- 20 ms on a 1.1 GHz laptop is roughly 20-40 M ops, 40-80x over budget. Even a heavily simplified line detector (gradient -> region growing -> fit) on 160x120 is likely 0.2-0.5 M ops on its own.
- A budget-compatible substitute:
  - Pick about 50-100 high-gradient edge pixels on a coarse grid (block max, as in DSO).
  - Track each along its gradient normal with a 1-D search (e.g. ±4 px, 8-pixel pattern: about 8 x 9 x 3 ≈ 200 ops per edgelet).
  - Feed each into the MSCKF as a 1-D measurement.
  - This costs about 20-40 k ops and keeps the "lines in textureless rooms" benefit without line fitting or descriptors.

### Gaps
- No published op/ms costs for an edgelet-only MSCKF front end. No ablation isolating edgelets vs corners in VIO.

## 4. Photometric robustness for dark images (gain/exposure compensation, normalisation, NCC/census)

### Takeaway
Exposure and gain changes are the main photometric failure mode for direct methods. DSO shows that plain brightness constancy is the worst choice, and that an affine brightness model (2 parameters per frame) recovers most of the benefit even without exposure metadata. Cheap remedies:
- per-frame or per-patch mean/gain normalisation (ZNCC-like),
- an affine a,b per frame,
- census or sign-of-gradient matching for SAD.

All are O(pixels) and fit easily in the budget.

### Cited Findings
- DSO models I = G(t·V·B) (response, vignetting, exposure) and adds an affine brightness term e^(-a)(I − b) with a log-parametrised gain. If exposure times are unknown, a and b absorb the changes. Exposure in a test sequence varied more than 500x (0.018-10.5 ms). — [DSO](https://ar5iv.labs.arxiv.org/html/1607.02565)
- DSO ablation: exposure calibration had little effect, removing vignette/response calibration slightly reduced accuracy, and naive brightness constancy performed worst. LSD-SLAM and SVO "consistently fail on most of the sequences" because they assume brightness constancy. — [DSO](https://ar5iv.labs.arxiv.org/html/1607.02565)
- DSO triggers a new keyframe when the relative brightness factor changes significantly. — [DSO](https://ar5iv.labs.arxiv.org/html/1607.02565)
- PX4Flow handles low light in hardware: 4x binning to large super-pixels plus AEC/AGC/HDR. — [PX4 docs](https://docs.px4.io/v1.13/en/sensor/px4flow)
- Trifo-VIO argues that edges and line segments are less sensitive to lighting change than intensity. — [Trifo-VIO](https://ar5iv.labs.arxiv.org/html/1803.02403)
- Correlation Flow reports a Gaussian-kernel cross-correlator that is robust to noise and distortion. — [Correlation Flow](https://arxiv.org/pdf/1802.07078)

### Inferences
- Cost estimates (mine):
  - Per-frame mean/std over 80x60 or 160x120: about 2-5 k ops with SIMD.
  - Per-patch zero-mean normalisation (ZNCC) on an 8-pixel pattern: about 30 extra ops per point.
  - A 3x3 census (8 compares) on 80x60: about 8 x 300 x 3 ≈ 7 k SIMD ops. Matching becomes Hamming distance via XOR + popcount (`i8x16.popcnt` exists in wasm SIMD).
  - All are negligible next to the 0.5 M budget.
- Binning is also a "free" low-light SNR gain in software: averaging 2x2 or 4x4 pixels reduces shot/read noise by 2-4x. Coarse-level tracking in dark frames is therefore not only cheaper but also more reliable than full-res corner detection.
- Low-gradient dark frames lose corners before they lose coarse gradients. A coarse census- or gradient-based flow at 80x60 probably keeps producing a valid peak after FAST and KLT have failed. This is an inference, untested.

### Gaps
- No quantitative study found comparing SAD vs NCC vs census flow error as a function of illumination at low resolution.

## 5. Detecting vision unreliability, IMU coasting with good covariance, zero-velocity/hover detection

### Takeaway
Use explicit quality metrics to decide when to gate visual updates:
- number of tracked/selected points,
- SAD/correlation peak sharpness,
- texture or gradient energy,
- exposure.

OpenVINS's ZUPT recipe provides a cheap stationarity detector: a chi-squared test on IMU residuals with noise inflated 50-100x, combined with a mean-disparity check. During hover or stillness this anchors velocity even when no features exist.

### Cited Findings
- OpenVINS ZUPT measurement: a = 0, ω = 0, with residuals in accelerometer/gyro bias and gravity-rotated terms. Jacobians are −⌊R g×⌋ for orientation and −I for both biases. The page notes this really enforces constant velocity, not zero velocity, so a velocity-magnitude check is added against false positives. — [OpenVINS ZUPT docs](https://docs.openvins.com/update-zerovelocity.html)
- Detection uses z̃ᵀ(HPHᵀ + αR)⁻¹z̃ < χ², with IMU noise inflated α ∈ [50, 100] for reliable real-world detection. Disparity-based detection (mean feature displacement < Δd) "seems to work reasonably well" but can fail in dynamic scenes, so combine the two. — [OpenVINS ZUPT docs](https://docs.openvins.com/update-zerovelocity.html)
- ZUPT helps monocular systems that cannot triangulate features when stationary. — [OpenVINS ZUPT docs](https://docs.openvins.com/update-zerovelocity.html)
- Flow-sensor quality indicators: PX4Flow uses pattern-quality and correlation thresholds ([PX4 docs](https://docs.px4.io/v1.13/en/sensor/px4flow)). The PMW3901 reports squal (number of features) and shutter time, which Bitcraze relates to error spread ([Bitcraze blog](https://www.bitcraze.io/?p=9292)).
- DSO re-tracks on the coarsest pyramid level for about 0.5 ms per attempt to recover from tracking loss. — [DSO](https://ar5iv.labs.arxiv.org/html/1607.02565)

### Inferences
- Proposed gating signal, cheap to compute from the coarse pyramid:
  - (i) total gradient energy and selected-point count on 80x60,
  - (ii) SAD/census peak ratio (best vs second-best, or curvature at the minimum),
  - (iii) mean intensity / estimated exposure,
  - (iv) gyro magnitude, since blur risk grows with ω.
- Map these to a measurement-noise inflation rather than a hard on/off switch, so the filter's covariance during "coasting" stays honest.
- For an FoE/velocity-direction measurement, weak flow (near-zero translation) makes the direction ill-defined. That same condition is the disparity half of the ZUPT test: low flow magnitude + IMU chi-squared pass -> apply ZUPT; low flow + IMU fail -> pure rotation, so no translational info.
- Note that with mean unaligned ATE as the metric, the costly event is velocity error accumulating during blackouts. Even a weak velocity-direction or ZUPT constraint bounds the quadratic growth.

### Gaps
- No published guidance found on tuning coasting covariance specifically for vision dropouts on drones.

## 6. Published evaluations of VIO in textureless or dark sequences

### Takeaway
Direct, numeric, side-by-side dark-sequence ATE for ROVIO / VINS-Mono / OpenVINS was not found. What exists is qualitative failure reports, plus datasets built for the purpose (OIVIO, UMA-VI, TUM-VIE). Low light commonly causes outright failure or divergence of OpenVINS, ORB-SLAM3 and DSO. Treat dark segments as "expect frequent total loss" and design for graceful degradation.

### Cited Findings
- A 2026 low-light SLAM project report on LaMARia sequences: filter-based OpenVINS, ORB-SLAM3 and DSO fail or diverge on most of the harder and low-light sequences. OpenVINS produced no usable initial interval on the hard sequence and one low-light sequence. — [SLAM in Low-Light Environments (arXiv 2607.17699)](https://arxiv.org/html/2607.17699)
- VINSEval compares OpenVINS, VINS-Mono and ROVIO under synthetic low illumination. Its summary says the algorithms generally keep low ARMSE in dark scenes; per-method numbers were not visible. — [VINSEval (ResearchGate)](https://www.researchgate.net/publication/350459482_VINSEval_Evaluation_Framework_for_Unified_Testing_of_Consistency_and_Robustness_of_Visual-Inertial_Navigation_System_Algorithms). This partly conflicts with the LaMARia report above; the likely reason is synthetic darkening vs real low light (my inference).
- In a drone-racing VIO comparison, ROVIO and VINS-Mono failed on both sequences while LARVIO, OpenVINS and SVO performed well. This is fast motion, not dark. — [arXiv 2512.20475](https://arxiv.org/pdf/2512.20475)
- OIVIO dataset: 36 sequences in mines/tunnels with on-board illumination, >145 min of stereo+IMU. The same trajectories were recorded at about 100%, 50% and 15% light intensity, suitable for controlled darkness studies. — [OIVIO](https://arpg.colorado.edu/oivio/)
- UMA-VI: 32 sequences targeting low texture and dynamic illumination, with ground truth only at sequence start and end. — [UMA-VI paper](https://mapir.uma.es/papersrepo/2020/2020_The_UMA-VI_dataset_Visual%E2%80%93inertial_odometry_in_low-textured_and_dynamic_illumination_environments.pdf)
- TUM-VIE provides low-light and HDR sequences with event cameras. — [TUM-VIE (arXiv 2108.07329)](https://arxiv.org/pdf/2108.07329)
- PL-VINS's largest gain over VINS-Mono (−28% ATE) was on MH-04-difficult, a dark/fast EuRoC sequence. — [PL-VINS](https://ar5iv.labs.arxiv.org/html/2009.07462)
- DSO (direct) claims tracking through very-low-texture scenes where indirect methods fail, though it is qualitative. — [DSO](https://ar5iv.labs.arxiv.org/html/1607.02565)

### Inferences
- The most transferable evidence for our setting is PL-VINS's MH-04 gain and DSO's low-texture claim. Both say that adding gradient/edge information beyond corners helps most on dark or difficult sequences. Combined with the cost analysis above, the recommended budget allocation per frame (my proposal) is:
  - about 15 k ops for a 2-level 2x2 pyramid,
  - about 40-60 k ops for a gyro-predicted coarse block flow on 80x60 (4x3 blocks, SAD or census), giving FoE/velocity direction and a quality score,
  - about 50-150 k ops for 100-300 DSO-style 8-pixel gradient points or edgelets aligned directly against the previous frame (affine brightness), feeding the MSCKF,
  - the remainder for existing corner/KLT on whatever texture exists.
  - This sums to roughly 0.2-0.3 M ops plus the corner path, within 0.5 M.

### Gaps
- No numeric ATE/RPE found for ROVIO / VINS-Mono / OpenVINS on real dark sequences (TUM-VI dark rooms, OIVIO 15% light) in a single table. VINSEval's numbers were not accessible.
- UZH-FPV low-light results were not found in this session.
