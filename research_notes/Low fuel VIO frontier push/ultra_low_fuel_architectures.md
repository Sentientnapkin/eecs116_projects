# Ultra-low-fuel VIO architectures (plain-C wasm, MAX per-frame ops vs mean unaligned ATE)

Scope note: web research was limited (about 12 tool calls, no PDF text extractor in the sandbox, so several classic papers were not read in full). Items marked "(own estimate)" are first-principles op-count arithmetic by the researcher, not published figures; they sit under Inferences. Cited findings contain only what a fetched source said.

## 1. What published / open-source low-power VIO systems exist, and what compute do they need?

### Takeaway
Published ultra-low-power VIO either uses dedicated silicon (Navion, 2 mW at 20 fps) or a parallel RISC-V SoC (GAP9: LEVIO ~17 M cycles/frame multicore, ~104 M single-core, ~3-4 m ATE). The cheapest published design is a PX4Flow-style block-matching front end plus a tiny EKF, which costs about 0.15 M cycles/frame on 160x120 images and gives ~0.3-1.6 m RMSE indoors. No published figure was found for an MSCKF at about 1 M ops/frame on a general CPU.

### Cited Findings
- Navion (MIT, 65 nm): processes 752x480 stereo EuRoC at 20 fps at 2 mW average, and up to 171 fps at 24 mW average. It saves on-chip memory 4.1x via compression and by exploiting structured and unstructured sparsity. — [Navion RLE page / arXiv 1809.05780](https://arxiv.org/html/1809.05780)
- Navion was motivated by the fact that processors able to run state-of-the-art VIN need up to 10 W. — [RSS 2017 Navion](https://dspace.mit.edu/bitstream/1721.1/109522/1/2017_rss_navion.pdf)
- LEVIO (GAP9 RISC-V, 160x120 QQVGA input, ORB + pose-graph/BA, not an MSCKF): about 20 fps under 100 mW. Per-frame cycles (8 cores, kcycles): ORB extraction 2,926; frame matching 1,033; world matching 2,128; EPnP RANSAC 10,899 or 8-point RANSAC 10,323 (single-core: 57,324 and 50,391). IMU preintegration is 2.42 kcycles per IMU sample. Up to 700 descriptors/frame, 8 keyframe window. The single-core total is about 104 Mcycles per iteration. The multi-core front end plus EPnP is about 17 Mcycles. — [LEVIO arXiv 2602.03294](https://arxiv.org/html/2602.03294v1)
- LEVIO accuracy on EuRoC MH01-05 without loop closure: 0.96, 0.92, 3.69, 8.33, 3.38 m ATE RMSE (mean 3.46 m), versus VINS-Mono 0.20-0.47 m. The paper's text says "0.9-3.5 m", which conflicts with its own 8.33 m table entry. — [LEVIO arXiv 2602.03294](https://arxiv.org/html/2602.03294v1)
- Downfacing VIO on GAP9 (Kuhne, Vogt, Magno, Benini), 160x120 images, GAP9 at 370 MHz, 9 cores: tracker kcycles per frame (multi-core) are PX4FLOW-style 81.3, ORB 2,899, SuperPoint 30,975. The modified PX4FLOW front end totals 148.2 kcycles (81.3 + 66.9 rigid-body fit); the Kalman filter is 156 kcycles in float. That gives 1,216 fps max for PX4FLOW versus 118 for ORB and 12 for SuperPoint. Power is 64-68 mW. ORB is about 10x PX4FLOW in cost. — [arXiv 2509.10021 (html)](https://arxiv.org/html/2509.10021)
- Same paper, accuracy (indoor RMSE, m, sequences 02-08): PX4FLOW-ours 0.275, 0.394, 0.464, 0.320, 1.631, 0.554, 1.130; ORB mean 0.752 m; original PX4FLOW mean 2.743 m. Assumed a hypothetical 100 fps camera. Outdoors, 50 m relative error is 6.8% (hardcourt) for PX4FLOW and 5.9% (grass) for ORB. It assumes planar, downfacing geometry. PX4FLOW search range +-4.5 px per frame; doubling it to +-8.5 px roughly quadruples cycles. — [arXiv 2509.10021 (html)](https://arxiv.org/html/2509.10021)
- Improved MSCKF (FMSCKF, MATLAB, EuRoC, 10 Hz): window up to 20 poses, up to 350 Harris corners tracked with KLT, min tracked features 8. Linear algebra is about 10% of cost and image processing about 90%. Update rate rises from ~25-32 Hz to ~85-118 Hz (3.3-3.9x; the abstract's "6x" does not match the table). Final position error 0.25% versus 0.49% on MH_01. — [arXiv 2210.08117](https://arxiv.org/html/2210.08117v2)
- Default S-MSCKF-VIO needs roughly 550-600 ms/frame on a Raspberry Pi Zero; a grid-based detection variant halves that. — [search result summarizing Bahnam et al. 2021 S-MSCKF on RPi Zero](https://repository.tudelft.nl/file/File_c01490bd-7a5e-4734-8c58-faaab8118e44) (secondary summary, not read in full)
- ROVIO's iterated EKF update is its main load; one paper reports a 40% average cost cut on a Jetson TX2 using sparse matrices and reports running on an RPi Zero 2 W. — [TU Delft repository paper](https://repository.tudelft.nl/file/File_75bf4695-943f-4251-ae65-6749912cb4fa?preview=1) (summary only)
- TinyVIO is a bare-metal LARVIO/MSCKF on an i.MX RT1170 MCU using Eigen. TinyCVIO states OpenVINS is not suitable for bare-metal on its MCU, and cites a Cortex-M7 bare-metal VIO at 1 GHz / 3 MB RAM. Another paper notes single-precision dense MSCKF covariance updates can lose positive definiteness. — [TinyVIO](https://www.github.com/simengangstad/TinyVIO), [TinyCVIO](https://arxiv.org/pdf/2609.30358), [arXiv 2510.10346](https://arxiv.org/html/2510.10346v1) (snippet-level; ops/frame not found)
- Santamaria-Navarro et al.: IMU + optical flow from at least 2 features as a metric body-speed sensor at 40 Hz within an EKF, used to cut main-CPU load, reaching 100 Hz; the flow itself is computed on smart-camera hardware at up to 200 Hz. — [IRI UPC scidoc 1675](https://www.iri.upc.edu/download/scidoc/1675), [scidoc 1960](https://www.iri.upc.edu/download/scidoc/1960)
- PX4 optical-flow docs: flow is reported as integrated angular motion (rad), fused in EKF2 with a gyro-based rotation correction and a range/height estimate; low-resolution flow can cause slow hover oscillations above about 20 m. — [PX4 docs](https://docs.px4.io/main/en/sensor/optical_flow)

### Inferences
- Rough unit conversion: the GAP9 PX4FLOW pipeline is about 0.15 Mcycles/frame + 0.16 Mcycles for the EKF, so ~0.3 M ops/frame is a published-feasible order of magnitude for flow + small EKF on 160x120. Our 320x240 frame has 4x the pixels, so downsample to 160x120 (or smaller) before any matching.
- The 20-fps ORB/BA path (LEVIO) is not a candidate: its 17 Mcycles/frame is above our current 7 M, and its ATE is 1-8 m. The only published way below 1 M cycles is block-matching flow, which the paper validated mostly for downfacing planar scenes. Our forward/general-motion 60 s flights are a different regime; ATE of 0.3-0.8 m there is unproven by sources.
- The 90%/10% split (image processing vs linear algebra) in the FMSCKF paper implies the first target is the front end, not the filter, as long as clones are about 10-20.

### Gaps
- No source gives measured wasm-op or instruction counts per frame for MSCKF/OpenVINS/ROVIO. Did not read the S-MSCKF (Sun et al.), OpenVINS or ROVIO papers in full (PDF text not extractable here).
- Nothing found for Crazyflie-class VIO numbers, NanoMap, or event-camera methods beyond TinyDEVO (~1.2 fps on a 9-core MCU, from the search summary only, uncited above).
- TinyVIO/TinyCVIO per-frame timing and ATE were not retrieved.

## 2. Which design choices dominate cost, and what can be cut cheaply?

### Takeaway
In published MSCKF work the image front end (pyramid, KLT, detection) is about 90% of cost and covariance/linear algebra about 10% at 20 clones. Under our 7 M/17 M figures, the cheapest cuts are: downsample/restrict KLT to prior-predicted small windows, rotate detection over cell subsets, cap tracked features, then use sparse null-space projection and a smaller window.

### Cited Findings
- FMSCKF: image processing about 90% and linear algebra about 10% of total cost; raising/lowering the minimum tracked feature count trades feature-extraction frequency against pruning frequency. A smaller N_fmin gave both a higher update rate and slightly better accuracy because features track longer. — [arXiv 2210.08117](https://arxiv.org/html/2210.08117v2)
- Grid-based detection with detection only in under-populated cells halved S-MSCKF time on an RPi Zero while keeping competitive accuracy. — [Bahnam et al. summary](https://repository.tudelft.nl/file/File_c01490bd-7a5e-4734-8c58-faaab8118e44)
- Block-matching search range dominates tracker cost: doubling +-4.5 px to +-8.5 px roughly 4x the cycles. — [arXiv 2509.10021](https://arxiv.org/html/2509.10021)
- In the GAP9 downfacing paper, ORB detection 7.7 Mcycles single-core is ~36% of ORB total (21.2 M), extraction 7.05 M, matching 4.7 M, blur 1.8 M. — [arXiv 2509.10021](https://arxiv.org/html/2509.10021)

### Inferences (own estimates, ops = scalar wasm ops, SIMD op = 1)
These are rough first-principles numbers to be verified by profiling the current binary.
- Pyramid: 320x240 = 76.8 k px. A 2x2-box level 1 is ~4-6 ops per output pixel, about 80-115 k ops scalar (about 20-30 k with SIMD128 u8 averaging); level 2 adds ~25%. Building only levels you actually search, or skipping the pyramid by tracking with an IMU-predicted prior, removes it entirely.
- KLT: per feature per level per iteration with a 7x7 window (49 px), about 25-40 ops/pixel (bilinear sample, gradient, residual, accumulate) = 1.2-2 k ops. 3 levels x 2-3 iters = 7-18 k ops per feature. 40 features = 0.3-0.7 M. With a gyro/IMU-predicted start and a single level at 160x120, 1-2 iterations: ~2-4 k per feature, so 20 features = ~50-80 k.
- Detection: dense FAST/Shi-Tomasi on 76.8 k px is ~10-20 ops/pixel = 0.8-1.5 M ops. Run it on one cell of a 4x3 grid per frame (about 1/12) or at 160x120: ~60-120 k per frame, with each cell refreshed every 12 frames (0.6 s at 20 Hz).
- EKF dimensions: n = 15 + 6c (c clones; extras for GP bias states add more). Propagation with a sparse Phi (only the 15x15 block touches the clone cross-covariance): ~ 2*15*15*(n) ≈ tens of k ops at c = 10 (n = 75).
- Update with m stacked rows after null-space projection: P H^T about 2 n^2 m, H P H^T about 2 m^2 n, Cholesky m^3/3, gain about 2 n m^2, covariance update about 2 n^2 m. For n = 75, m = 40: 0.45 M + 0.24 M + 0.02 M + 0.24 M + 0.45 M, about 1.4 M. For n = 45 (c = 5), m = 24: about 0.1+0.03+0.005+0.05+0.1 ≈ 0.3 M. Cost scales as n^2 m, so halving both clones and rows is about 5-8x.
- Null-space projection per feature with k observations: A^T (2k-3 x 2k) times [Hx] (2k x n) done densely is about 2*(2k-3)*2k*n, ~50 k ops at k = 10, n = 75. Hx only has 6k+ nonzero columns plus a few; using Givens rotations on the 2k x 3 feature Jacobian and applying them only to the sparse columns is about 5-10x cheaper (~5-10 k). Triangulation Gauss-Newton: 3-5 iterations x ~60 ops/observation, about 2-3 k per feature.
- Doing 20 features densely is ~1 M just in projection, so sparsity or Givens is likely worth more than any other filter-side trick.
- QR compression of the stacked H to at most n rows: costs about 2 m n^2 (m = 40, n = 75: 0.45 M) which is not cheaper than the direct form unless m greatly exceeds n; it only pays off for m >> n. With small m (under ~30) skip it; use sequential scalar/2-row updates with only the needed rows of P.
- Roughly, the current 7 M median likely splits (guess) about 4-5 M front end, 2-3 M filter; a target near 1 M needs both sides cut by ~5-7x.

### Gaps
- Measured profile of the current binary by stage was not available to this researcher (it lives in the repo); the estimates above should be replaced by it.

## 3. Vision-rate reduction and time-slicing for a MAX-over-frames score

### Takeaway
Because the score is the max per frame, flatten the cost profile: never run detection, projection, and a full update on the same frame. The literature found does not report this specifically; the recommendations below are design inferences. Keeping IMU propagation (cheap, ~10-30 k ops) every frame and vision only on a subset of frames reduces the mean but not the max unless the vision frame itself is cheap, so slicing within the vision step matters more than decimation.

### Cited Findings
- LEVIO is an example of explicit multi-rate design: pose-graph optimization is run up to three times per iteration and IMU preintegration (24.2 kcycles per 10 samples) is under 0.15% of cost. — [arXiv 2602.03294](https://arxiv.org/html/2602.03294v1)
- Grid/cell-based detection only in sparse cells was shown to halve S-MSCKF cost. — [Bahnam et al. summary](https://repository.tudelft.nl/file/File_c01490bd-7a5e-4734-8c58-faaab8118e44)
- Resource-aware online parameter adaptation for computationally constrained VINS exists (Resource-aware, arXiv 2106.00289), but its numbers were not extracted (PDF unreadable). — [arXiv 2106.00289](https://arxiv.org/pdf/2106.00289)

### Inferences
- Round-robin KLT: track a fixed set of F features, but only F/k each frame (k = 2-4), using the IMU-propagated pose to predict the others' positions; each feature gets a measurement every k frames (still one 2-row residual per observation). Frame cost drops by k; the max is flat.
- Round-robin detection: one image cell per frame (rotating), using the 4x3 or 3x3 grid; detect only when the cell is under quota (a per-cell quota gives uniform coverage, which also helps conditioning).
- Split the update: per-frame budget of B feature updates (e.g. 4-6 features whose tracks have ended or reached max length) rather than all at once; sequential EKF updates are valid because each completed feature is independent after null-space projection. Priority queue by track length / parallax. The covariance update cost becomes B-dependent and bounded.
- Add a hard per-frame op governor: count op estimates in C (cheap counters), skip optional work (extra KLT iterations, extra features) if projected above budget. This turns the max into a design parameter and removes the 17 M tail (which is probably frames where many tracks finish at once, or detection + large update coincide; verify).
- Clone cadence: cloning only every second frame (10 Hz keyframes) halves the window cost for the same time span; with 1200 frames at 20 Hz and a slow drone this is probably the cheapest accuracy-neutral change, but needs testing.

### Gaps
- No source quantified accuracy loss from round-robin tracking or clone decimation in an MSCKF. This needs ablation on our eval loop.

## 4. Optical-flow-style velocity measurement as a minimal-fuel alternative

### Takeaway
Published flow+IMU filters do reach sub-meter indoor RMSE at ~0.3 Mcycles/frame on tiny images, but results are for downfacing planar scenes with known height; a forward/general-motion monocular camera lacks the metric scale from a range sensor, so scale must come from IMU integration. Reaching 0.3-0.8 m over 60 s is plausible but unproven in the literature found.

### Cited Findings
- Downfacing GAP9 VIO (flow-style tracker + EKF over rigid-body motion and IMU): indoor RMSE 0.275-1.63 m, mean about 0.68 m across seven sequences for the modified PX4FLOW (own mean of the table's 7 values: (0.275+0.394+0.464+0.320+1.631+0.554+1.130)/7 = 0.67 m), at ~0.15 Mcycles tracker + 0.16 Mcycles EKF per frame. — [arXiv 2509.10021](https://arxiv.org/html/2509.10021)
- Outdoor: 5.9-6.8% of 50 m travel for the best methods; PX4FLOW best on hardcourt, ORB best on grass and sand. — [arXiv 2509.10021](https://arxiv.org/html/2509.10021)
- PX4 EKF2 fuses flow as rate measurements corrected by gyro and scaled by range/height. — [PX4 docs](https://docs.px4.io/main/en/sensor/optical_flow)
- Santamaria-Navarro et al.: IMU turned into a metric body-speed sensor from optical flow of at least 2 features, EKF at 40 Hz, large main-CPU saving versus VIO. — [IRI UPC](https://www.iri.upc.edu/download/scidoc/1675)

### Inferences
- A sparse-patch design for our case: N = 8-20 patches, 8x8 or 7x7 windows, tracked on a 160x120 level with IMU-predicted displacement (gyro derotation removes rotation flow; remaining flow is translation/depth). Each patch yields a bearing-rate measurement. With no range sensor, depth is unknown, so use one of: (a) a per-patch inverse-depth state (ROVIO-like, 8-20 extra states, n about 30-50, update cost about 2 n^2 m = 2*45^2*24 about 0.1 M); (b) MSCKF-lite with 3-5 clones only (about 0.3 M); (c) the epipolar-only constraint between 2 frames (no landmark states) plus IMU preintegration, which resolves scale only from accelerometer excitation.
- Scale observability is the weak point: without range or loops, velocity comes from IMU integration corrected by direction-only flow; accuracy depends on trajectory excitation. Our drone flights have ~17 m paths in our set versus ~60 m on the server (project memory), so drift-per-path matters more on the server set.
- Realistic ordering by fuel: flow + EKF (0.1-0.3 M) < ROVIO-like sparse-patch EKF (0.3-0.6 M) < 5-clone MSCKF with 15 features (0.7-1.5 M) < current. Expect ATE to degrade moderately between each tier; no published number supports 0.3-0.8 m for the first two tiers, so treat them as hypotheses to test.

### Gaps
- No direct sources on monocular, forward-looking sparse-patch flow+IMU ATE over 60 s flights. Didn't find PX4Flow/EKF2 or Crazyflie flow-deck velocity accuracy numbers (the search returned none).
- No numeric ROVIO ops/frame from a primary source.

## 5. Numerical tricks

### Takeaway
Sources found support only qualitative points: single-precision dense covariance updates can lose positive definiteness on embedded targets, and an MCU-class VIO is feasible with float. Specific ops-saving tricks below are engineering inferences.

### Cited Findings
- Single-precision-only embedded platforms make dense MSCKF covariance update instability more serious (loss of positive definiteness, divergence). — [arXiv 2510.10346](https://arxiv.org/html/2510.10346v1) (snippet-level)
- The GAP9 VIO uses integer arithmetic for ORB (16-bit blur, 32-bit Harris) and floating point for the Kalman filter. — [arXiv 2509.10021](https://arxiv.org/html/2509.10021)
- Rigid-body estimation in that paper uses integer outlier rejection then 2x2 SVDs in floating point (66.9 kcycles). — [arXiv 2509.10021](https://arxiv.org/html/2509.10021)

### Inferences
- Use integer/u8 SIMD128 for all image code (pyramid, gradient, SSD): i8x16/i16x8 ops give 8-16 pixel ops per wasm op, the largest fuel lever per line of code since fuel counts a SIMD op as 1. KLT in fixed-point Q8 with SIMD16 patch residuals could be about 5-10x cheaper than scalar float.
- Use f32x4 for the filter: pad rows to multiples of 4; P H^T and the P update become 4-wide and cost about 1/3-1/4 the ops. Symmetric updates (update only the upper triangle, P -= K S K^T via Joseph form not needed if you use sequential scalar updates with clamping and a diagonal jitter) halve the n^2 m term.
- Sequential scalar updates (process each row of H after whitening with fixed sigma): avoids the m x m Cholesky and S inverse; cost per row about 4 n^2 total (compute P h, innovation, K, rank-1 update) ~ 4*45^2 = 8 k for n = 45, vs row cost in batch of ~2 n^2 + ... similar, but it allows a hard per-frame row cap and exploits known fixed noise. With the simulated IMU noise known and fixed, no noise estimation or online tuning is needed; use constant Q and hard-coded Phi structure.
- Reduced state: drop camera-IMU extrinsics, time offset, and scale states if the simulation gives known calibration (verify from the task); drop GP bias states if they cost more than they return (each extra state adds about 2n m ops per update plus 2n^2 per propagate); use 6 bias states only (random walk).
- Schmidt/consider states: put the extrinsics (if any must be kept) as consider states so P rows for them are not updated; saves about 2 n_c n per update.
- Sparsity: the clone-clone covariance is dense, but the IMU-block propagation touches only 15 rows/columns; implement P = [Pii Pic; Pci Pcc] propagation explicitly (cost 15*15*n*2 ~ 2n*225 ops instead of n^3).
- Fixed-size, compile-time n (templates/macros for c <= 8) lets the compiler unroll and avoid index overhead, which matters because every loop-control op counts as fuel in wasm.
- UD/square-root: improves stability but costs more ops than plain P (roughly 1.5-2x); use plain float32 with symmetrization and a diagonal floor unless divergence is observed. Marginal benefit for fuel; not recommended first.

### Gaps
- No sources found with measured op counts for UD, square-root, or Schmidt MSCKF variants. The op-count scalings are from standard linear-algebra cost formulas, not measurements.

## Suggested experiment order (own synthesis, ordered by expected fuel saved per accuracy lost)
1. Profile current binary by stage (front end vs filter vs worst frames) to confirm the 17 M peak source.
2. Replace dense null-space projection with Givens-on-sparse columns; cap rows per update (B features/frame).
3. SIMD128 integer pyramid/KLT on a 160x120 base level, IMU-predicted starts, 1-2 pyramid levels, 20-30 features, round-robin tracking.
4. Rotating-cell detection (one cell per frame) with per-cell quota.
5. Window 5-8 clones, clone every 2nd frame; drop optional states.
6. Per-frame op governor in C to enforce a hard cap (the score is MAX).
7. Only then consider the flow+EKF/ROVIO-like tier for the ~0.1-0.3 M ops regime.
