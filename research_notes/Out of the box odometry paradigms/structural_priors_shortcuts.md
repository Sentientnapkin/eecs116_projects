# Structural and physical shortcuts for indoor multirotor odometry (alternatives or additions to full VIO)

Measurement provenance: all "MEASURED" numbers come from my scratch scripts (`m2.py`..`m5.py` in the session scratchpad, run with the viobench venv python `-I`, read-only on the repo) over 24 flights sampled with stride from `/data/backups/rganapa/Sebastian/gen/raw-fast/selected` (171 zips; flights are `fast-*` / `fastmid-*`, mean path 58.9 m, 1200 frames at 20 Hz). Truth = the reader's `Flight` object in `research/common.py` (frame-rate truth, IMU windows). Caveats: n = 24 flights, 20 Hz truth, acceleration from finite differences of truth velocity. No private server episodes were touched.

Citation status: [VERIFIED] = I opened the arXiv abstract page. [SEARCH-ONLY] = appeared in a search result with a snippet, page not opened. [UNVERIFIED] = recollection or secondary summary only.

## Q1. Planar / constant-height priors and ground-ceiling homography velocity (optical-flow-sensor style)

### Takeaway
Constant-height is false on this benchmark (z std 0.52 m per flight, peak-to-peak 1.8 m), the camera looks forward (so floor and ceiling occupy the image periphery, not the centre), and body speed is already the learned model's strength; I rank this low (gain on yaw ~0, gain on scale small, wasm-feasible but real engineering). A soft "floor-plane homography with gravity-known normal" velocity term is the only variant worth a falsification test.

### Cited Findings
- MEASURED: per-flight height std 0.52 m (peak-to-peak 1.8 m median-ish, range 0.9 to 3.5 m), mean |vz| 0.24 m/s versus mean horizontal speed 0.92 m/s; mean tilt 6 deg, max tilt 16 to 35 deg. A constant-height or planar-motion prior would be violated by ~25% of the speed budget.
- Camera geometry (from the episode K): fx = 88.4 px at 320x240, so HFOV ~122 deg and VFOV ~107 deg, with the optical axis along body +x (T_body_camera maps camera z to body x). The floor plane is in the lower image half only for a short band of the view; flow-sensor style methods assume a down-facing camera. [local data]
- Flow alone gives only velocity/height ratio; a height measurement is needed for metric scale, normally sonar or barometer. [WebSearch summary of TUM lecture notes and sonar-based papers, SEARCH-ONLY](https://autonav.in.tum.de/handouts/lecture_7_part_2.pdf)
- Continuous-homography ego-motion from optical flow using the IMU gravity direction as ground-plane normal (Grabe et al., ICRA 2012). [SEARCH-ONLY](https://www.irisa.fr/lagadic/pdf/2012_icra_grabe.pdf)
- A rigid-body planar-motion model reduces RMSE in a down-facing VIO for nano-UAVs, up to 3.65x over their baseline pipeline with ORB; PX4FLOW matches ORB accuracy below 24 px/frame. Note this is down-facing hardware, not our forward camera. [VERIFIED](https://arxiv.org/abs/2509.10021)
- A planar-motion constraint makes roll/pitch observable in VIO with velocity-control kinematics, but global position and yaw stay unobservable. [VERIFIED](https://arxiv.org/abs/2204.06651)

### Inferences
- Planar constraints cannot fix yaw by theory (yaw unobservable with gravity-only structure). Gain target is scale of the vertical/horizontal axis only. Estimated gain on mean ATE: under 5%.
- Falsification test: take N2's own velocity, compute a floor-homography scale from the lower image band using known gravity and the learned depth height, and test whether the ratio improves speed-binned bias. If speed-binned bias drops by under 20% in the 0.5 to 1.5 m/s bins, drop it.
- wasm: cheap (4-point DLT/ RANSAC on a patch), but depends on texture of the floor.

### Gaps
- I did not measure floor visibility fraction or floor-plane homography quality on frames (needs image reading plus a plane fit; not done).

## Q2. Learned gravity / attitude networks (roll, pitch, yaw rate)

### Takeaway
Roll/pitch is not the bottleneck (project measurement: ideal tilt gives 0.909 versus 0.967 m), and in this simulator the accelerometer carries no tilt information at all (see Q5), so a learned gravity network can only learn it from motion statistics, which are the cheap part. Only yaw-rate/gyro-z matters and the gyro-z is already at truth bias (mean bias ~0). Rank low.

### Cited Findings
- Project figure: feeding true body velocity through our own gyro attitude gives 0.967 m; ideal tilt alone 0.909; perfect yaw 0.209. [reports/Drone VIO ATE approaches.md, local]
- MEASURED: per-frame mean gyro z minus truth w_z has mean ~ -1e-4 rad/s and std 0.029 rad/s per 20 Hz average (so yaw random walk is mostly white noise, not bias); bias is already saturated per the project's kf_grid result.
- TLIO uses the filter's own rotation estimate (not an AHRS) as gravity-aligned input; RoNIN uses device orientation. [SEARCH-ONLY](https://arxiv.org/abs/2007.01867)
- EqNIO learns a gravity-aligned canonical frame; the authors note yaw is unobservable from IMU and must be learned from data. [VERIFIED](https://arxiv.org/abs/2408.06321)

### Inferences
- A learned attitude net would not close the 0.967 to 0.209 yaw gap, because yaw is unobservable from inertial data alone. Expected gain: tilt-only ~0.06 m (0.967 to 0.909) at best.
- Falsification: already done in project (ideal tilt barely helps).

### Gaps
- No evidence found of a neural method that estimates absolute yaw from IMU alone without a map or magnetometer.

## Q3. Magnetometer-free absolute yaw cues (vanishing point beyond Manhattan, layout, lights, sun, floor pattern)

### Takeaway
The only cues with a literature basis are building-fixed vanishing directions / structure compass (Manhattan or Atlanta-world). The project already measured Manhattan anchoring as weak here (R4 0.12-0.19), and a trajectory-heading Manhattan prior is also weak (below). Layout networks (HorizonNet, LGT-Net) are panorama-based; no evidence they transfer to 320x240 forward frames with 120 deg FOV. Rank mid-low; the best sub-idea is a single-direction (Atlanta/ceiling-line) yaw filter used as a soft prior, not an anchor.

### Cited Findings
- Yaw remains unobservable in gravity-aligned VIO and drifts even with gravity known; a visual compass (Kim, Li, Joo, ICRA 2022) corrects it. Reported via search snippet; PDF link 404 on fetch. [UNVERIFIED primary](https://aigs.unist.ac.kr/filebox/item/1917192674_66fb1ff8_2022_ICRA_Manhattan_official.pdf)
- Drift-free 3-DoF rotation from a single line and plane in a Manhattan world (RGB-D, Kim, Coltin, Kim CVPR 2018). [SEARCH-ONLY](https://openaccess.thecvf.com/content_cvpr_2018/papers/Kim_Indoor_RGB-D_Compass_CVPR_2018_paper.pdf)
- Vanishing directions as scene-fixed compass to correct odometry (Schwarze and Lauer, IPIN 2015). [SEARCH-ONLY](https://www.mrt.kit.edu/z/publ/download/schwarze_ipin15.pdf)
- MSC-VO couples points, lines and Manhattan axes for RGB-D VO. [SEARCH-ONLY](https://arxiv.org/pdf/2111.03408)
- "Camposeco et al. inertial-guided vanishing point updates" came only from a secondary encyclopedia entry. [UNVERIFIED](https://encyclopedia.pub/entry/56250)
- HorizonNet (arXiv 1901.03861) and LGT-Net (arXiv 2203.01824) estimate room layout from 360 panoramas; both IDs appeared in search with matching titles (ar5iv pages listed). [SEARCH-ONLY](https://arxiv.org/abs/1901.03861), [SEARCH-ONLY](https://arxiv.org/abs/2203.01824)
- MEASURED (trajectory-level Manhattan test): velocity heading mod 90 deg across 24 flights has mean 4-fold concentration R4 = 0.28 (median per-flight deviation from the best 4-fold axis 14.6 deg versus 22.5 deg for uniform; only 38% of moving samples within 10 deg). Half-vs-half dominant-axis offset within a flight averaged 13 deg. The planner does not follow axis-aligned corridors tightly, so "trajectory is axis-aligned" cannot be used as a yaw drift detector. Max single flight R4 = 0.89 (one corridor-like flight).

### Inferences
- Expected gain from a soft single-axis yaw prior: if it halves yaw drift on 20-30% of flights where lines are visible, mean ATE gain ~5-10% (my estimate, extending the project's finding that perfect yaw cuts 0.967 to 0.209 m). Because R4 on lines was weak (0.12-0.19), the realistic gain is lower.
- Sun, windows, ceiling-light patterns, and floor patterns: I found no literature on using them for monocular yaw; ProcTHOR/HSSD scene randomization of textures and lights is unmeasured. Treat as speculative. A cheap check is to measure whether ceiling-light blob positions (bright blobs in the upper image) persist across revisits; no data collected.
- Falsification: compute, per flight and from truth poses plus rendered frames, the dominant 2D line direction in the upper-image band transformed to world yaw; require circular concentration R>0.5 across a flight and std < 5 deg after gravity alignment. Otherwise abandon.
- wasm: LSD/EDLines-style detection is already available in OpenCV C++; vanishing point estimation is cheap.

### Gaps
- No verified paper for layout networks on narrow-FOV forward frames; none on sun/ceiling-light yaw cues.

## Q4. Relaxed loop closure and local-map re-observation

### Takeaway
Evidence in the project: strict revisits are 3.5-4%. Relaxing to short time gaps (2-10 s) and larger view change enlarges the revisit set mainly in the local-map sense: persistent landmarks over a few seconds are what any VIO already uses via sliding-window tracking, so a separate mechanism adds little unless it spans yaw changes of 90+ deg. Rank low to mid; the idea has value only as a yaw-drift bound through long-baseline feature re-observation (global bundle adjustment with keyframes).

### Cited Findings
- MEASURED: drone yaw rate is ~32-40 deg/s for most of the flight (median |w_z| 32, p99 40 deg/s; a rate cap near 40 deg/s). A 6 s window thus sweeps ~200 deg of heading; features are visible for only 1-3 s. This makes short-gap re-observation of the same wall rare, while forward-facing flight re-sees the same wall only after a full yaw rotation of ~9-11 s.
- Project numbers: loop revisits 3.5-4% under strict criteria (within 1.5 m, under 45 deg view change, over 10 s later). [task background]

### Inferences
- With the camera spinning at ~35 deg/s, a 120 deg HFOV sees any given point for ~3.4 s at most while it is rotating through; "re-observation over a few seconds" therefore reduces to the existing sliding window. Gain on yaw drift is probably under 10%.
- Falsification: from truth poses, count frame pairs with gap 2-10 s, distance under 2 m and view angle 45-120 deg, and the fraction with shared 3D points visible in both (use rendered depth if available). If the extra pairs under 10 s give under 10% coverage, drop.
- wasm: learned global descriptors (NetVLAD/DINO-class) are too heavy; classical ORB/ BoW is feasible.

### Gaps
- I did not compute the relaxed-revisit rate; no per-pair visibility data read.

## Q5. ZUPT-like, thrust, and drag velocity constraints from the IMU

### Takeaway
The simulator's physics falsifies the drag idea: the drag-model R-squared is 0.0002 (truth) and 0.01 (IMU), with fitted k ~ 0.006 per s (noise). Truth specific force in body xy is ~0 (median |f_xy|/g = 3.5e-4), i.e. an ideal drag-free, thrust-along-body-z quadrotor. This also implies the accelerometer carries no gravity/tilt information beyond noise. This is a decisive negative for the HDVIO/Leishman/Xu-de Croon style aiding on this benchmark, and it closes the project's open "drag R2 falsifier".

### Cited Findings
- MEASURED (24 flights, ~28.8k frames pooled): regression of body-frame IMU specific force x on body velocity x gives R2 = 0.0107, slope 0.019; y gives R2 = 0.0016, slope -0.012. Using truth-derived specific force (R^T(a - g) from truth acceleration): x R2 = 1.8e-4, y R2 = 1.6e-4, slopes 0. Per-flight R2 at most 0.01.
- MEASURED: IMU specific force std (x, y, z) = 0.133, 0.150, 0.584 m/s^2; the residual of IMU against R^T(a - g) from truth has std 0.134, 0.151, 0.319, i.e. x and y are essentially all sensor noise, while truth fb_xy std is 0.007 and 0.006 m/s^2. z mean 9.845 m/s^2 (thrust, ~g).
- MEASURED: truth world acceleration from IMU vs finite-difference truth: RMSE 0.14-0.16 m/s^2 per axis.
- Linear rotor drag model for quadrotors is differentially flat; effect small but dominant in the accelerometer in horizontal flight. [VERIFIED abstract](https://arxiv.org/abs/1510.03249) (inertial-only observer with drag, Martin and Sarras); [SEARCH-ONLY](https://arxiv.org/abs/1712.02402) (Faessler et al. flatness with rotor drag)
- HDVIO: point-mass model plus learned aerodynamics from thrust and IMU history, up to 33% better motion estimation and 40% force estimation. [VERIFIED](https://arxiv.org/abs/2306.11429)
- MA-VIF: quadrotor dynamics plus epipolar constraints give "drift free velocity and attitude" with biases; I could not confirm the drag form from the abstract page. [VERIFIED abstract, drag detail UNVERIFIED](https://arxiv.org/abs/1607.01486)
- ZUPT: only 8.9% of frames have speed under 0.2 m/s (MEASURED), and the planner has no hover phases; speed percentiles 5/25/50/75/95 = 0.10/0.45/0.87/1.39/2.27 m/s.

### Inferences
- Drag aiding gain on velocity: none on this simulator (R2 ~ 0). The server flights use the same simulator per the project's calibration anchors, so I expect the same.
- A usable consequence: "f_x = f_y = 0 up to noise" is an exact structural constraint (thrust-only body acceleration). It makes horizontal body acceleration observable as zero, but it cannot constrain velocity because velocity integrates acceleration. It does give a clean gravity relation: a_world = T R e_z + g, so tilt is tied to world acceleration (differential flatness): (R e_z)_h = a_h / T. Visual velocity derivatives with error of 0.1 m/s^2 give tilt to ~0.6 deg. Tilt is not the bottleneck (Q2), so I rate this as a regularizer, not a yaw fixer.
- Speed floor test: ZUPT gives gain on 9% of frames only; negligible.
- Falsification already executed for drag: a real server-style check would need non-private server data, which was not touched; the local flights are the proxy.

### Gaps
- No thrust channel is in the ABI (project note), so HDVIO-type thrust input is unavailable; accelerometer z substitutes (std 0.58 m/s^2, noise-limited).

## Q6. Planner structure: yaw versus velocity-heading coupling

### Takeaway
Coupling is real but loose: median |yaw - velocity heading| is 11 deg, 60% of moving samples within 20 deg, 75% within 45 deg, 5% beyond 125 deg, and yaw lags velocity heading by ~0.5-1 s with a yaw-rate cap ~40 deg/s. This does NOT give absolute yaw (the velocity direction in the world frame is itself computed with the same drifting yaw, so it is circular); it gives only a soft prior on the body-frame velocity direction.

### Cited Findings
- MEASURED (24 flights, samples with horizontal speed > 0.3 m/s): |yaw - velocity heading|, percentiles 5/25/50/75/95 = 0.6 / 3.6 / 11.0 / 43.2 / 125.5 deg; mean 31 deg; per-flight mean 16 to 47 deg. Fraction within 20 deg 0.60; within 45 deg 0.76.
- MEASURED lag sweep (yaw[t] versus velocity heading shifted by lag frames at 20 Hz): the fraction within 20 deg peaks at 0.73 when heading is taken 10 frames (0.5 s) earlier, versus 0.61 at lag 0 and 0.28 at 20 frames later. Yaw follows the velocity heading with a delay of ~0.5-1.0 s; heading is not predicted ahead.
- MEASURED: body-frame lateral to forward velocity ratio v_by/v_bx has percentiles 50/75/90/95 of 0.106/0.263/0.658/1.03 (angles 6/15/33/46 deg). So lateral slip is common.
- MEASURED: yaw rate |w_z| median 32, p90 38, p99 40.1 deg/s; mean 24 deg/s (about 40 deg/s cap, constantly turning in bursts). Mean speed 0.92 m/s; after the first 6 s (ramp: 0.74 m/s in the first 6 s) speed is flat at 0.97-1.07 m/s in 6 s bins, a constant cruise profile.
- MEASURED (NHC yaw-rate test): estimating w_z = (a_body_y + w_x v_bz)/v_bx from truth-kinematics gives correlation 0.41 and R2 0.17 with true w_z overall (slope 0.25), improving with speed: corr 0.56 / 0.55 / 0.63 for v_bx in 0.8-1.2 / 1.2-2 / 2-5 m/s, residual 28 / 19 / 9 deg/s. Even with perfect knowledge it explains little. Not a usable gyro-z substitute.
- Non-holonomic constraints improve roll/pitch estimates for land vehicles and planar motion in the literature; no paper found applying them to quadrotor yaw. [VERIFIED for planar case](https://arxiv.org/abs/2204.06651)

### Inferences
- Where this could help: a heading-from-trajectory yaw prior would need a world-frame velocity direction that is independent of the attitude estimate. None exists inside a monocular VIO; the map direction from feature motion is again in the drifted frame. So the constraint cannot cut global yaw drift. Estimated yaw gain: ~0.
- It can still regularize learned velocity: a prior that body velocity points forward within ~35 deg (90% of samples) is a very weak bound (lateral component std large).
- Yaw-rate saturation at ~40 deg/s gives a bounded-rate prior for the gyro z: gyro z clip errors. Little value because gyro-z is noise-limited, not biased.
- Falsification: test whether the learned model's v_by/v_bx distribution matches the truth distribution (6/15/33/46 deg percentiles); if the model predicts narrower lateral slip it is wasting information. Cheap.

### Gaps
- I did not measure the planner's source code; the claim "roadmap planner with yaw-rate limit" is from the task statement; the 40 deg/s cap and 0.5-1 s lag are inferred from truth.

## Q7. Anything else (extrinsics, rolling shutter, motion blur, exposure)

### Takeaway
Two cheap observations from measurements are worth keeping: (a) the extrinsic and sim structure is exactly orthogonal axis-aligned (camera z = body x; T_cam_imu is a pure axis permutation), so no extrinsic calibration is needed; (b) constant cruise speed (~1.0 m/s after a 6 s ramp, std small across 6 s bins) is a strong prior for global scale and would let an absolute scale be locked to cruise speed distribution rather than flow. Motion blur or rolling shutter cues: no evidence that the simulator renders them; unmeasured.

### Cited Findings
- MEASURED: T_body_camera = [[0,0,1,0],[-1,0,0,0],[0,-1,0,0]], zero translation; camera-to-IMU lever arm is zero, so no lever-arm coupling terms.
- MEASURED: mean speed per 6 s bin (24 flights): 0.74, 1.03, 1.00, 1.01, 1.02, 0.97, 1.07, 0.99, 1.02, 0.98 m/s. Speed profile percentile spread 0.10-2.27 m/s overall (5-95%), thus per-flight speed varies by trajectory segment (sharp turns slow).
- Rolling shutter / blur: simulators typically render global shutter frames; I have no verified evidence for this simulator. [UNVERIFIED]

### Inferences
- A scale prior from the cruise speed (mean path / 60 s = 0.98 m/s) would bound scale drift: if the learned model's mean speed over a flight deviates from ~1.0 m/s the scale should be renormalized. The flight-level scale error is then bounded by the spread of per-flight mean speed (measured 0.54 to 1.17 m/s across 24 flights, i.e. +/-30%), so it is a weak absolute prior, not a precise one. Gain on scale drift: low (the project says extent shift, not scale, is the error driver).
- Falsification: compute the per-flight mean speed of N2's prediction versus truth; if its mean-speed error is under 5%, the speed prior is useless.

### Gaps
- Exposure and blur not measured from frames.

## Q8. Ranking (gain on yaw/scale drift, feasibility, test)

### Takeaway
Nothing in this family beats the guard/fallback and retraining plans; the structural ideas either target the wrong axis (tilt, scale) or are circular for yaw. The only ones with positive expected value are a soft single-axis line/vanishing-direction yaw prior and a speed-profile scale check; the drag/thrust/NHC ideas are falsified by measurement.

### Cited Findings
Ranked list (estimates are mine, labelled as such):

| Rank | Idea | Yaw gain (est.) | Scale gain (est.) | wasm | Status / falsification |
|---|---|---|---|---|---|
| 1 | Soft single-direction line / vanishing-direction yaw prior (Atlanta-style), gated by line concentration | up to 5-10% of mean ATE if lines are concentrated on 20-30% of flights | 0 | easy (OpenCV C++) | test R>0.5 line concentration per flight; project R4 0.12-0.19 suggests likely fail |
| 2 | Cruise-speed scale renormalization (flight-level) | 0 | small, bounded by +/-30% per-flight speed spread | trivial | check N2 mean-speed error; if under 5% drop |
| 3 | Floor-plane homography velocity with gravity normal | 0 | small | moderate | speed-binned bias test; low prior |
| 4 | Relaxed loop closure (2-10 s, view change up to 120 deg) | <10% | 0 | heavy for learned descriptors | pair-count test |
| 5 | Flatness tilt correction from visual acceleration | 0 | 0 (tilt barely matters, 0.909 vs 0.967 m) | easy | skip |
| 6 | Drag / thrust model aiding | 0 | 0 | easy | FALSIFIED: R2 0.0002 truth, 0.01 IMU |
| 7 | NHC / heading-from-velocity yaw | 0 | 0 | easy | FALSIFIED as yaw source: circular; NHC yaw-rate R2 0.17 |
| 8 | Layout nets (HorizonNet/LGT-Net) | unknown | 0 | too heavy | no narrow-FOV evidence |
| 9 | Learned gravity/attitude net | <=0.06 m (tilt only) | 0 | moderate | project ideal-tilt test already negative |
| 10 | ZUPT | 0 | 0 | trivial | only 8.9% of frames under 0.2 m/s |

### Inferences
- The sim is exactly rigid-body, drag-free, zero-lever-arm. That removes physical-prior routes (drag, thrust model) that help on real drones, so literature gains from HDVIO-type aiding (33% on Blackbird) should not be assumed here.
- The persistent bottleneck is absolute yaw (0.967 to 0.209 m). Of everything here, only external structure (lines/vanishing directions, loop closures) can supply it, and both are weak in these scenes per the project's own measurements.

### Gaps
- No measurement of gravity-aligned vertical line yaw cues, floor-plane homography quality, or relaxed-revisit rates; those need image-level scripts beyond the scope here.
- Server-flight statistics were not used (privacy rule); only the local fast pool.
