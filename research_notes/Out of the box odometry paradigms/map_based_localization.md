# Map-based / scene-specific localization as an alternative to odometry (simulated drone, known indoor scenes)

Scope note: ~13 tool calls of literature work. Every arXiv ID cited below was opened (abstract page or search-result page for that exact ID) and its title matched; items I did not open are in the Gaps sections. Project-internal facts come from read-only inspection of the repo and of one non-private local benchmark zip (`gen/raw-fast/selected/fast-102344193-01.zip`, episode.json and file listing only). No server episodes were touched. Many paper abstracts give no numbers, so numbers below are limited to what the fetch tools returned; the Inferences sections are my own reasoning, not results.

## 1. How are scenes shared between training and benchmark, and what is the pose/frame convention (does absolute localization need start-relative conversion)?

### Takeaway
The world frame is defined by the first camera (identity pose at frame 0), and the scene is placed in that frame by a random per-episode transform, so any map-based method must (a) localize in scene coordinates and (b) re-express every pose relative to its own first-frame pose estimate. Scene identity is available in training data (episode.json has a scene id) but nothing a deployed guest can read tells it which scene it is in, so scene recognition has to come from images.

### Cited Findings
- Local benchmark episodes carry `meta.scene` (e.g. "102344193"), `spawn.scene` (a hash), `spawn.scene_translation` (3-vector) and `spawn.scene_yaw` (2-vector, cos/sin), `spawn.poses` = [0,0,0,1,0,0,0] (identity), and `config.pose.frame = "camera0"`; the groundtruth file is `mav0/state_groundtruth_estimate0/data.csv`. Source: `/data/backups/rganapa/Sebastian/gen/raw-fast/selected/fast-102344193-01.zip` (episode.json).
- The selected 171 benchmark zips map to 168 distinct scene ids (filename-derived count), i.e. almost one flight per scene; HSSD ids look like `fast-103997460_171030507`, ProcTHOR flights are `fast-<id>`. Source: `ls gen/raw-fast/selected`.
- First camera defines the pose origin; a staged guest emits the exact origin with identity rotation at the first camera timestamp (0.045 s). Source: `/data/backups/rganapa/Sebastian/eecs116_projects/research/README.md` line 46; `research/FUSION_COMPLETION.md` line 21.
- Catalogs in scoring are `procthor`, `hssd-train`, `hssd-val`. Source: `research/results/eval/server-benchmark/failure-selected.txt`.
- Scene policy in HANDOFF: dev ProcTHOR 166-171, final test 162-165 and 172-175, confirmation 176-179 (quarantined), proxy validation 150-161, training everything else. Source: `research/HANDOFF.md` line 81. The implementation plan states the benchmark's clean scenes are ProcTHOR 150-161 and 176-179 (21 of 171 flights clean) and that the other flights are in scenes that training saw (stated in the task as 57+44 seen). Source: `reports/Drone VIO implementation plan.md` line 56.
- Metric is unaligned ATE with the first pose as origin (mid-flight starts also re-origin; see 171-flight benchmark with 86 mid-start flights, offsets 3.4-39.5 s). Source: `reports/Drone VIO ATE approaches.md`.
- Loop-closure headroom measured in the repo is small: frames revisiting a place seen >10 s earlier are 4.0% (ProcTHOR) and 3.5% (HSSD), zero flights above 30%. Source: `reports/Drone VIO implementation plan.md` line 3 (cites vio_fixes_and_yaw.md). This directly limits a self-built-keyframe-map approach.

### Inferences
- Conversion: if a map gives world-in-scene pose T_S<-C(t) for each frame, output T_C0<-C(t) = T_S<-C(0)^-1 * T_S<-C(t). The absolute error of the first-frame localization enters every output pose as a rigid transform (rotation error theta at frame 0 rotates the whole trajectory, giving an error growing with distance from the start, roughly extent*theta). So the first-frame localization must be much better than VIO drift (e.g. 2 deg on a 4.7 m extent is ~0.16 m) and should be averaged over the first N frames (jointly with IMU, since the drone hovers ~1 s at start) rather than taken from one image.
- Because ATE is unaligned, there is no gauge freedom: absolute map-referenced rotation and translation at frame 0 matter as much as per-frame accuracy. But the same property helps: a map yields drift-free pose after the start, so only the start-pose error remains.
- Mid-flight starts (offsets 3.4-39.5 s) are not a problem for map-based localization (arbitrary start in the scene) but they hurt VIO initialization, which is where VIO tails come from (OpenVINS mean 0.98 m if init within 3 s vs 168 m otherwise).

### Gaps
- Whether the server's scenes are in the training catalog is unknown (stated by task; the repo says the server spec is inferred only from path/extent). Whether the random `scene_translation`/`scene_yaw` is per-episode or fixed per scene (so a map built in scene frame is consistent across flights) was not verified beyond one zip. Verify by loading two flights of the same scene id.
- I did not verify that a guest cannot read the scene id from the episode input; assume it cannot (it receives images and IMU).

## 2. Scene coordinate regression family (ACE, ACE0, GLACE, ACE-G, DSAC*, ACE-SLAM)

### Takeaway
Per-scene ACE-style networks give centimetre-level absolute pose from RGB with 4 MB maps trained in about 5 minutes per scene, but only where the training and query views overlap and only for scenes the model was mapped on. With ~hundreds of known scenes and 8 H100s this is cheap to train; it is useless on unseen scenes unless the server allows a mapping phase.

### Cited Findings
- ACE (arXiv 2305.14059, CVPR 2023): "less than 5 minutes" mapping, up to 300x faster than prior scene coordinate regression, on par accuracy. Source: [arXiv 2305.14059](https://arxiv.org/abs/2305.14059).
- Numbers from the ACE paper text (ar5iv version): mapping 5 min (291 s on V100); map size 4 MB (backbone 11 MB trained once on 100 ScanNet scenes, shared; head = 8 1x1 conv layers width 512, fp16); 7-Scenes 97.1% of frames within 5 cm/5 deg with SfM pseudo-GT poses (80.8% with D-SLAM poses); Cambridge average median error 25 cm / 0.4 deg; DSAC* Full takes 15 h on V100 and has 28 MB map. Test-time fps not reported in the part read. Source: [ar5iv 2305.14059](https://ar5iv.labs.arxiv.org/html/2305.14059).
- DSAC*: arXiv 2002.12324 (Brachmann & Rother, TPAMI 2022): scene coordinate regression with differentiable RANSAC; RGB-only needs only RGB + GT poses at training and a single RGB image at test. Source: [arXiv 2002.12324](https://arxiv.org/abs/2002.12324v4) (search-result page; abstract page not directly fetched). NOTE: arXiv 2012.09654, which I first guessed, is an unrelated crop-stress paper; do not cite it.
- ACE0 (arXiv 2404.14351, ECCV 2024): incremental SfM by repeatedly training a scene coordinate relocalizer on unposed images; "accuracy close to feature-based SfM"; no metric-scale statement on the abstract page. Source: [arXiv 2404.14351](https://arxiv.org/abs/2404.14351).
- GLACE (arXiv 2406.04340, CVPR 2024): global+local pre-trained encodings in one small network; single model has 17% lower median position error than Poker (ACE ensemble) on Cambridge; low map size. Source: [arXiv 2406.04340](https://arxiv.org/abs/2406.04340).
- ACE-G (arXiv 2510.11605, ICCV 2025): scene-agnostic transformer pre-trained on tens of thousands of scenes plus a per-scene map code of a few MB fit in minutes from posed RGB; aimed at generalizing from mapping views to unseen query views (lighting, viewpoint). Source: [arXiv 2510.11605](https://arxiv.org/abs/2510.11605).
- ACE-SLAM (arXiv 2512.14032, Dec 2025): RGB-D neural implicit SLAM with SCR as the map, built online by self-supervision/continual learning, "strict real-time"; RGB-D (depth), monocular support not stated. Source: [arXiv 2512.14032](https://arxiv.org/abs/2512.14032). A search snippet said ~11 ms/frame localization (third-party summary, not verified in the primary).
- SACReg (arXiv 2307.11702): scene-agnostic cross-attention regressor from database images with 2D-3D annotations to query coordinates, PnP after retrieval; no per-scene training. Source: [arXiv 2307.11702](https://arxiv.org/abs/2307.11702).

### Mechanism, yaw/scale, frame, wasm, compute, legitimacy
- Mechanism: the network regresses per-pixel 3D scene coordinates; RANSAC-PnP gives pose in scene frame. Yaw/scale: it solves both in absolute terms (metric, since training poses are metric GT from our simulator), so no drift in any DOF; error is per-frame noise (cm to ~dm, my estimate for indoor sim at 320x240 with 122 deg FOV; not measured by me). Frame: as in section 1, convert via first-frame estimate.
- Wasm fit: a 512-wide 8-layer 1x1 conv head is ~2 M MACs-per-pixel-feature... concretely ~8x(512x512)=2.1 M MACs per feature sample, x (320/8 x 240/8=1200 positions)~2.5 G MACs/frame if all positions used, which is heavy against our repo's measured fuel budgets (peak 3.4-4.5 B per frame vs 2e10 cap). ACE's 11 MB backbone adds more. Subsampling to ~200 positions and a smaller backbone is required; PnP-RANSAC in C++ is cheap. Feasible but needs a custom small SCR, not the stock ACE. This is my estimate.
- Where the maps live: weights are in the wasm package; 168+ scenes x 4 MB is ~700 MB, which likely exceeds practical package limits (unknown; check the submission size limit). Mitigation: shared trunk with per-scene small codes (ACE-G style) or a distilled single multi-scene network.
- Training compute: ACE ~5 min per scene on 1 GPU, so ~170 scenes = ~15 GPU-hours, trivial on 8 H100. Training views from unlimited simulated flights.
- Legitimacy/overfitting: if server scenes are in the training catalog the map is a legitimate "learned prior of the environment" (training on the training scenes is the project's normal data policy); if unseen, accuracy collapses and a naive scene classifier can give confidently wrong poses (a guard is mandatory). May be useless if server scenes are unseen: ACE-G/SACReg-type scene-agnostic variants address this only if mapping images from the scene exist, which they do not at test time unless built from the flight itself (section 6).

### Inferences
- Highest ceiling of everything here for the seen-scene fraction (~101/171 flights seen), but nothing in the literature I opened tests it on 122 deg FOV, 320x240, sim-renderer images, motion blur at 3-6 m/s planner speeds, or textureless walls, and the project's own tests show VIO failing on textureless/dark views (Spearman flat fraction +0.59 to +0.61), which will also hurt SCR.

### Gaps
- No numbers on ACE test-time fps or indoor synthetic results; ACE-G map-code size/transformer size not in the abstract; none opened for GLACE training time.

## 3. Absolute pose regression (PoseNet-family, DFNet) and map-relative regression (marepo)

### Takeaway
Plain APR is mostly image retrieval in disguise and is not accurate enough; marepo/DFNet-style variants narrow the gap but are not the best option over SCR for our purpose.

### Cited Findings
- Sattler et al. (arXiv 1903.07504, CVPR 2019): pose regression behaves more like image-retrieval-based approximation than 3D-geometry estimation and does not reliably beat a handcrafted retrieval baseline. Source: [arXiv 1903.07504](https://arxiv.org/abs/1903.07504v1) (via search result page).
- DFNet (arXiv 2204.00559, ECCV 2022): direct feature matching + exposure-adaptive novel view synthesis; up to 56% better than existing single-image APR, "comparable to 3D structure-based methods". Source: [arXiv 2204.00559](https://arxiv.org/abs/2204.00559).
- marepo (arXiv 2404.09884, CVPR 2024): pose regressor conditioned on a scene-specific map (ACE-style map representation), trained across hundreds of scenes, adaptable to new maps immediately or after minutes of fine-tuning; "outperforms previous pose regression methods by far". Source: [arXiv 2404.09884](https://arxiv.org/abs/2404.09884).

### Mechanism, yaw/scale, frame, wasm, compute, legitimacy
- Single forward pass; yaw/scale: absolute but accuracy limited (APR typically metre-ish in large scenes, my recollection, unverified); frame: same conversion; wasm: a small CNN is easy, so APR is the easiest to ship; compute: cheap; legitimacy: pure memorization of seen scenes, no generalization (Sattler finding), so fully dependent on server scenes being seen.
- A useful use of APR/retrieval here is as a coarse prior to gate/seed an SCR or a filter, not as the sole localizer.

### Gaps
- No indoor-simulator accuracy numbers found for APR. PoseNet original (arXiv 1505.07427) not opened; not cited.

## 4. Place recognition / retrieval against a pre-rendered image bank (NetVLAD, MegaLoc, AnyLoc, DINOv2)

### Takeaway
Retrieval gives scene identification and a coarse (~metre-level, my estimate) position; it is excellent for deciding which scene/map to use and for loop-closure candidates, but it does not by itself give the sub-0.5 m, few-degree pose needed.

### Cited Findings
- NetVLAD (arXiv 1511.07247, CVPR 2016): trainable VLAD layer, weakly supervised ranking loss. Source: [arXiv 1511.07247](https://arxiv.org/abs/1511.07247). (pre-2021; baseline only.)
- AnyLoc (arXiv 2308.00688, RA-L 2023/ICRA 2024): off-the-shelf self-supervised features plus unsupervised aggregation, no VPR training, up to 4X higher performance than existing approaches across structured/unstructured environments including indoor. Source: [arXiv 2308.00688](https://arxiv.org/abs/2308.00688). The abstract page did not name DINOv2/VLAD; that is from my recollection (unverified here).
- MegaLoc (arXiv 2502.17237, 2025, Berton & Masone): merges retrieval methods, training techniques and datasets; SOTA on many VPR datasets and on LaMAR localization when swapped in as the retrieval stage. Backbone not stated on the abstract page. Source: [arXiv 2502.17237](https://arxiv.org/abs/2502.17237).
- DINOv2 (arXiv 2304.07193): 1B ViT distilled into smaller models. Source: [arXiv 2304.07193](https://arxiv.org/abs/2304.07193).
- Reloc3r pairs query with NetVLAD-retrieved top-10 database images by default. Source: [arXiv 2412.08376 html](https://arxiv.org/html/2412.08376).

### Mechanism, yaw/scale, frame, wasm, compute, legitimacy
- Mechanism: global descriptor nearest neighbour in a bank rendered from known scenes (we have GT poses from training flights, so the bank is the training flights' own frames with poses). Yaw/scale: the retrieved neighbour's pose is absolute, so it bounds drift; but retrieval error ~ bank spacing; one can refine with relative pose from a small matcher. Frame: first-frame conversion as above. Wasm: ViT backbones (DINOv2-B/MegaLoc) are far too large for the repo's fuel budget; a tiny CNN descriptor (MobileNet-sized, distilled from DINOv2) is plausible; run it at 1-2 Hz not 20 Hz. Compute: ~hours on 8 H100 for distillation or contrastive fine-tuning on sim frames. Legitimacy: same seen-scene caveat; useless if scenes are unseen, except for the self-built keyframe bank case (section 6) which needs no scene knowledge.

### Gaps
- No indoor-sim retrieval accuracy; the few-percent revisit statistic (3.5-4%) suggests retrieval hits against the flight's own history are rare, which is a separate matter from retrieval against a training-scene bank.

## 5. Render-and-compare against a known mesh / Gaussian splat / NeRF

### Takeaway
Accurate but slow and fragile, needs the scene model in the deployed binary, and a splat/NeRF/mesh renderer in C/C++ wasm within the fuel budget is not realistic; best treated as an offline teacher to generate labels, not as a runtime method.

### Cited Findings
- iNeRF (arXiv 2012.05877, IROS 2021): gradient descent on pixel difference between NeRF render and image from an initial pose guess. Source: [arXiv 2012.05877](https://arxiv.org/abs/2012.05877).
- Loc-NeRF (arXiv 2209.09050): Monte Carlo localization with a pretrained NeRF; real-time claim; works without initial pose; no quantitative accuracy on the abstract page. Source: [arXiv 2209.09050](https://arxiv.org/abs/2209.09050).
- 6DGS (arXiv 2407.15484, ECCV 2024): single-image pose from a 3DGS model by inverting rendering, no initial guess, 15 fps on consumer hardware, +12% rotation / +22% translation accuracy vs NVS baselines. Source: [arXiv 2407.15484](https://arxiv.org/abs/2407.15484).
- STDLoc (arXiv 2503.19358, CVPR 2025): Feature Gaussian map; sparse landmark matching for initial pose, then rendered dense feature/depth refinement; scene-specific detector trained per scene. Source: [arXiv 2503.19358](https://arxiv.org/abs/2503.19358) (search result page).
- Drift-free Visual SLAM using Digital Twins (arXiv 2412.08496, RA-L 2024, Scaramuzza group): aligns the VIO sparse point cloud to a 3D digital twin by point-to-plane matching, producing a 6-DoF global measurement tightly fused into VIO; no numbers on the abstract page. Source: [arXiv 2412.08496](https://arxiv.org/abs/2412.08496).

### Mechanism, yaw/scale, frame, wasm, compute, legitimacy
- Directly relevant idea: the Digital Twin method is "VIO + map alignment as global measurement", exactly the hybrid we want; it needs the mesh at runtime. If the server runs our wasm with no mesh file, the mesh would have to be embedded; ProcTHOR/HSSD house meshes are MBs each, 170 scenes could be compressed to coarse geometry, but the repo's package limits are unknown.
- Yaw/scale: absolute and drift-free (global measurement). Frame: first-frame conversion. Wasm: point-to-plane ICP against a coarse mesh/occupancy grid is C++-friendly and cheap if the VIO already provides sparse points; the repo's own VIO is the issue (OpenVINS/VINS tails), and the N2 learned model gives no point cloud. Alternatively align the odometry trajectory to the floorplan with free-space constraints (my idea, not in cited papers): a particle filter that penalizes trajectory points passing through walls; because the flight stays in a ~4.7 m extent in a house, wall/free-space constraints give weak but absolute yaw information only near walls.
- Compute: building splats per scene is ~10-30 min on 1 GPU each (my estimate), cheap for 8 H100. Legitimacy: same seen-scene dependence.

### Inferences
- Render-and-compare as a runtime component is the least wasm-compatible option; as an offline tool it can provide pseudo-labels, e.g. to train the SCR on rendered novel views that fill the sparse GT-flight coverage (the sim already has GT, so this is mostly unnecessary).

### Gaps
- No accuracy numbers for 6DGS/Loc-NeRF/STDLoc retrieved (abstract only).

## 6. Scene-agnostic relocalization against the flight's own first seconds (self-built keyframe map) and learned relative pose (Reloc3r, SACReg, MASt3R-SLAM)

### Takeaway
This is the only family that works on unseen scenes, but it is weaker than the repo's headline assumption suggests: the measured revisit fraction is only 3.5-4% of frames (>10 s apart), so a keyframe map built from the first seconds bounds drift only for the minority of revisits; and the available scene-agnostic models are far too large for wasm.

### Cited Findings
- Reloc3r (arXiv 2412.08376, CVPR 2025): relative pose regression network + minimalist motion-averaging for absolute pose; trained on ~8 M posed pairs; ViT-Large encoder (frozen) + ViT-Base decoder, ~0.43 B parameters; 25 ms per pair at 512 resolution on an RTX 4090 (Table 3; text elsewhere says 42 ms; conflicting); 7-Scenes 0.04 m / 1.02 deg; Cambridge 0.55 m / 0.56 deg (all five scenes, 512). Relative translation is direction-only, metric scale comes from triangulating over at least two database images; fails when query and all references are collinear. Source: [arXiv 2412.08376 html](https://arxiv.org/html/2412.08376) and [abs](https://arxiv.org/abs/2412.08376).
- Map-free relocalization (arXiv 2210.05494, ECCV 2022): metric pose relative to a single reference image; baselines are relative pose regression and feature matching with single-image depth; authors conclude it remains challenging. Source: [arXiv 2210.05494](https://arxiv.org/abs/2210.05494).
- MASt3R-SLAM (arXiv 2412.12392, CVPR 2025): real-time dense SLAM, 15 FPS, with 3D reconstruction priors, calibration optional; SOTA across benchmarks per abstract. Source: [arXiv 2412.12392](https://arxiv.org/abs/2412.12392).
- ACE0 (see section 2) does incremental SCR from unposed images, i.e. a self-built map without priors, but it is an offline multi-minute GPU process.
- Repo: revisit frames 3.5-4.0% (>10 s earlier). Source: `reports/Drone VIO implementation plan.md` line 3.

### Mechanism, yaw/scale, frame, wasm, compute, legitimacy
- Mechanism: keep keyframes from the first seconds (or all), estimate relative pose to the best-matching keyframe, and feed it as a loop constraint to a filter fused with IMU. Yaw: bounds only on revisit; scale: a monocular keyframe map has no scale unless IMU-anchored (the IMU gives metric scale, so a VIO-based keyframe map has it). Frame: the map is in the start frame by construction, which is the nicest property: no conversion error at all. Wasm: Reloc3r/MASt3R scale models cannot run; a tiny learned relative-pose or classical ORB/BA keyframe loop closer (VINS-Mono already has loop closure) is the wasm-feasible equivalent, and the repo found loop closure under its 30% kill line.
- Compute for training a small scene-agnostic relative-pose net from sim: 8 H100 for days is fine; the scientific risk (generalization of a small net) is higher than the compute risk.
- Legitimacy: fully legitimate and scene-agnostic, which is its strength; its weakness is the low revisit rate and weak gain, so the ceiling is small.

### Inferences
- Because the flight covers ~60 m path inside a ~4.7 m extent, many frames are near previously seen places in space, but the 3.5-4% statistic (measured by the repo, likely via view overlap or position proximity; definition not verified) suggests that revisits with enough viewpoint overlap are rare; verify with the falsification test below before investing.

### Gaps
- Definition of "revisit" in the repo analysis was not inspected; no wasm-sized relative-pose model found in the literature opened.

## 7. Hybrid with IMU (map measurement inside a filter) and ranked list with falsification experiments

### Takeaway
The best design is an error-state filter (e.g. N2/VIO as the process model) with absolute map poses as sparse, gated measurements, initialized by a first-seconds localization that fixes the start pose; this removes yaw/scale drift only to the extent the map is in-catalog and the gate is reliable. The ranking assumes the seen-scene fraction is substantial; if the server scenes are unseen, items 1-4 are useless and only item 5 (self-built map) and the existing guard remain.

### Cited Findings
- 2021 work fusing VIO with a georeferenced 2D map via pose graph for drift-free geolocalization (arXiv 2107.05851, surfaced by search only; not opened, unverified). Source: search result [arXiv 2107.05851](https://arxiv.org/pdf/2107.05851v1), UNVERIFIED.
- Digital-twin drift-free SLAM (arXiv 2412.08496) is the opened precedent for map-as-global-measurement inside VIO; see section 5.
- Repo: yaw drift dominates learned error, error scales with extent (Spearman 0.88-0.93 with identity-pose error); learned errors are uncorrelated with VIO errors (~0.0); oracle-min of VINS/OpenVINS/N2 is 0.759 m; the planned guard gives an honest expectation of 1.8-2.5 m. Source: `reports/Drone VIO ATE approaches.md`, `reports/Drone VIO implementation plan.md`.

### Ranked list (value if scenes are seen / wasm feasibility), each with a cheap falsification experiment
1. **Per-scene ACE-style SCR as a gated absolute measurement in the N2/VIO filter (seen scenes).** Highest ceiling: removes yaw and scale drift outright. Falsification (1 day, CPU+1 GPU): take 10 seen scenes, render/collect ~2k training frames each from existing training flights, train stock ACE (5 min each), and evaluate on the existing benchmark flights of those scenes at 320x240: report per-frame pose error and fraction with <0.5 m/<5 deg. Kill if median position error >0.5 m or inlier rate <50% on non-textureless frames; also compute the ATE if localization at 1 Hz replaces N2 output (offline replay on saved trajectories), kill if <20% gain over N2's 3.5 m. Separately test on 4 clean (unseen) scenes to quantify the failure mode and the gate's false-accept rate.
2. **Scene-ID + coarse-pose retrieval with a small distilled descriptor, used to pick the map and gate item 1.** Falsification (0.5 day): extract DINOv2-S descriptors from the first 5 s of each benchmark flight, retrieve against a bank from training flights; kill if scene top-1 accuracy <90% on seen scenes or if the unseen scenes are not rejected (AUROC <0.9). This also measures how much of the "seen" assumption is exploitable.
3. **Start-pose-only localization (use the map once, in the first ~5 s, to fix frame-0 pose, then odometry).** Cheapest hybrid because it needs only a few localizations; error is rigid-transform: ATE ~ extent x start rotation error. Falsification (hours, offline): inject Gaussian yaw error of 1, 2, 5 deg into the GT start pose on the 171 flights using the saved N2 trajectories; if ATE improvement from a perfect start pose is under ~0.3 m the gain is capped and the idea dies. (My estimate: start yaw error is not the dominant term; drift accumulates along the flight, so this likely caps well below the target. Unverified.)
4. **Digital-twin style map alignment (coarse mesh/occupancy free-space constraint) in the filter.** Mechanism from arXiv 2412.08496. Falsification (1-2 days): with GT scene meshes, run a particle filter or optimization that penalizes N2 trajectory samples in occupied space on 20 flights; kill if corrected ATE doesn't drop >15% or if wall constraints fire on <10% of frames (4.7 m extent in a larger house may mostly be free space).
5. **Self-built keyframe map with learned/classical loop closure (scene-agnostic).** The legit-for-unseen-scenes option. Falsification (hours, no training): count frames with enough co-visibility to the first 10 s keyframes using ORB or SuperPoint matches on benchmark flights; the repo already measured 3.5-4% of frames revisiting >10 s earlier, below its 30% kill line, so expect to kill this unless a looser (viewpoint-tolerant) revisit definition raises it above ~30%.
6. **Render-and-compare against meshes/splats at runtime.** Lowest wasm fit; use only offline. Falsification: none worth running before 1-4; skip unless 1 works and needs better labels.
7. **Plain APR (PoseNet/DFNet) and marepo.** Falsification (half day): train a small CNN APR on seen scenes and check whether it beats nearest-neighbour retrieval on bank (Sattler's finding predicts it will not); kill if not.
8. **Scene-agnostic large relative-pose nets (Reloc3r, SACReg, MASt3R-SLAM) inside the wasm guest.** Not deployable (0.43 B params for Reloc3r); use only as an offline pseudo-labeler or distillation teacher for a small net. Falsification: run Reloc3r offline on the first-5-s frames vs GT relative poses to see if its ceiling would even help; kill if rotation error >3 deg on these wide-FOV frames.

### Inferences
- The whole map-based branch hinges on one measurable unknown: the fraction of server scenes in our catalog. Cheapest resolution is not to fetch server data (forbidden) but to use the ratio of seen/unseen performance on our own benchmark as the calibration anchor and ensure a catalog guard so unseen scenes fall back to the existing VIO/N2 guard; the downside then is bounded by guard false-accept rate. With the project's server flights ~60 m path vs ~17 m local, and the metric dominated by worst flights, an erroneously accepted wrong-scene localization (several metres off) could hurt more than the average gain; gate hard.
- A key hidden risk: ACE-like methods need the mapping views to cover the query viewpoints (ACE-G's own motivation); 122 deg FOV flights at 3-6 m/s with varied heights may differ from the mapping distribution; generate mapping data with the same planner.

### Gaps
- No literature found on SCR with strong motion blur / very wide FOV / simulated drone indoor flights; HSSD appears only as a relocalization testbed in one 2026 paper (arXiv 2606.24767, surfaced by search, not opened, UNVERIFIED).
- arXiv 2107.05851 (VIO + georeferenced 2D map) and 1505.07427 (PoseNet) were not opened; labeled unverified. NaviLoc, PiLoT, AeroMap3D (2607.14009) surfaced in search only and were not opened; not used.
- Ranking numbers (expected gains) are my estimates, none measured.
