# Big-compute, different-philosophy strategies for monocular+IMU drone odometry (8xH100, unlimited sim ground truth, as of 2026-11)

Conventions: ATE = mean unaligned position RMSE in metres (the project metric; Sim(3)/yaw-aligned numbers in the literature are NOT comparable). "Pool-171" = the server-calibrated selection. Repo facts come from read-only looks at the Drone VIO reports, research_notes/.../learned_optimization.md, research/ODOMETRY.md and gpu_kit. Web facts were checked by opening the arXiv/CVPR page (abstract level only; full-paper tables were NOT opened, so no per-table numbers below unless stated). "(est.)" = my estimate, not a result. IDs I did not open are labelled UNVERIFIED. No private server episodes were touched.

Repo context used (all from the reports above): N2 seeds correlate 0.966-0.976 per flight on Pool-171 (3.508/3.544/3.567 m), so ensembling is worth ~0.2 m at most (oracle best-of-3 = 3.32). N2 ATE ~0.87x of zero-motion ATE on the pool (vs ~0.33x on local dev): the learned family barely beats "no motion" on 60 m flights. Training speed p90 0.51 m/s vs pool 1.58 m/s; training windows ~4.8 s vs 60 s inference. VINS-Mono/OpenVINS server scores 0.475/0.553 m, B-D0 4.55 m. Existing N2 wasm fuel ~1.7e9 per frame (reports), i.e. ~12x headroom under the 2e10 cap. Current model: small CNN + correlation encoder -> GRU/selective-SSM head -> body-velocity, integrated through gyro attitude (research/ODOMETRY.md).

---

## Q1. Pretrain a large visual-inertial sequence model on sim data, long context, then distill to a wasm student

### Takeaway
No published evidence shows a large sim-pretrained VI sequence model beating classical VIO on unaligned ATE for drones; the closest are inertial-only foundation models (Tartan IMU, AirIO, AI-IO) with 22-67% gains over smaller *learned* baselines, not over VIO. For us the large-model lever mainly addresses H1 (speed/extent distribution shift + 4.8 s vs 60 s window mismatch), and the evidence says distillation of regression works but the student cannot be assumed to inherit long-horizon drift behaviour; expected gain on Pool-171 is 10-30% on the learned guest (est.), nowhere near 7x.

### Cited Findings
- Tartan IMU (CVPR 2025): "light" foundation model pretrained on >100 h of multi-platform data, ~36% ATE improvement over specialised models, LoRA adaptation with ~1.1M trainable parameters, online test-time adaptation at 200 FPS; total parameter count not stated on the page. No arXiv preprint found. — [CVPR page via mlanthology](https://mlanthology.org/cvpr/2025/zhao2025cvpr-tartan); [CVPR open access](https://openaccess.thecvf.com/content/CVPR2025/html/Zhao_Tartan_IMU_A_Light_Foundation_Model_for_Inertial_Positioning_in_CVPR_2025_paper.html) (direct fetch 403; content from search summary/mlanthology).
- AirIO (arXiv 2501.15659): body-frame representation gives 66.7% average accuracy increase over global-frame input across three datasets; explicit attitude encoding adds 23.8%; paired with AirIMU and an uncertainty-aware EKF. The prior repo note that the abstract/text and table percentages disagree is unresolved; I did not open the tables. — [arXiv](https://arxiv.org/abs/2501.15659)
- AirIMU (arXiv 2310.04874): learned IMU correction + uncertainty; 31.6% improvement in IMU-GPS pose-graph ablation; tested to 262 km. — [arXiv](https://arxiv.org/abs/2310.04874)
- AI-IO (arXiv 2603.00597, ICRA 2026): transformer quadrotor inertial odometry with rotor speed input: +36.9% velocity accuracy from rotor speed, further +22.4% from the transformer; real flight dataset, not sim-only; model size not stated. — [arXiv](https://arxiv.org/abs/2603.00597)
- DPVO (arXiv 2208.04726): sparse patch recurrent VO, about 3x faster and a third of the memory of DROID-SLAM, no accuracy numbers in abstract. — [arXiv](https://arxiv.org/abs/2208.04726)
- VGGT (arXiv 2503.11651): feed-forward transformer for cameras/depth/point maps/tracks from 1 to hundreds of views, SOTA on camera estimation; parameter count and training scale not on the abstract page. — [arXiv](https://arxiv.org/abs/2503.11651)
- VGGT-SLAM (arXiv 2505.12549): aligns VGGT submaps with 15-DoF SL(4) homographies for uncalibrated monocular video; no numbers in abstract; no inertial input. — [arXiv](https://arxiv.org/abs/2505.12549)
- Distilling a deep pose regressor (ICCV 2019, arXiv 1908.00858): regression has no soft labels, so the teacher's own loss is used as a confidence weight (attentive imitation loss + attentive hint training); student kept near teacher with up to 92.95% fewer parameters and ~2.12x speedup on KITTI/Malaga visual odometry (search-result summary; paper body not opened). — [arXiv](https://arxiv.org/abs/1908.00858)

### Inferences
- Distillation recipes that fit regression: (a) teacher-loss-weighted imitation of pose/velocity (above); (b) distill on *unlabelled* or relabelled sim data with teacher outputs plus ground truth mixed; (c) distill the integrated trajectory (window-level displacement), not only per-frame velocity, so the student sees drift; (d) feature-hint on the encoder. With unlimited ground truth, distillation adds little over just training the student on more data, except for (c)-style soft long-horizon targets and for putting the teacher's error structure on hard flights. So the big-compute value is the teacher's long-context training, then regenerating pseudo-targets on cases the generator cannot label cheaply (not our case).
- Our binding constraint is not capacity but the horizon/distribution mismatch (errors proportional to path at ~6.2% of path; 7x reduction needed). A bigger teacher trained on 5 s windows inherits it.
- Student capacity: N2 is already small; wasm fuel headroom (~12x) lets the student be ~4-8x larger, but the CNN front-end dominates cost.

### Gaps
- No full-paper table was opened (Tartan IMU, AirIO, AI-IO, VGGT) so absolute errors and baseline definitions are missing.
- No evidence found for student/teacher capacity-gap behaviour specific to inertial/VI regression.

---

## Q2. Massive domain-randomized sim data design and scaling-law evidence for odometry

### Takeaway
No direct power-law scaling study for odometry was found. What exists: TartanVO showed synthetic-only training generalises when intrinsics and up-to-scale loss are handled; a Jan 2026 navigation paper (per search summary) argues diversity matters more than quantity. Our own project history (data scaling saturated at ~0.9-1.1 m locally, 5-25% per step) is the best local scaling evidence, and it was collected on slow short flights; the missing axis is speed/extent coverage, not volume.

### Cited Findings
- TartanVO (arXiv 2011.00359): trained only on synthetic TartanAir, generalises to KITTI and EuRoC without fine-tuning, outperforms geometry-based methods on "challenging trajectories"; attributes it to an up-to-scale loss and intrinsics input; abstract has no numbers. — [arXiv](https://arxiv.org/abs/2011.00359)
- ZeroVO (arXiv 2506.08005): >30% improvement over prior methods on KITTI/nuScenes/Argoverse 2, GTA-derived synthetic dataset, semi-supervised adaptation on unlabeled data, no calibration assumptions. — [arXiv](https://arxiv.org/abs/2506.08005)
- NeuRIO (arXiv 2609.21707): streaming neural relative inertial odometry trained purely in a simulator with varied motion, device sensor characteristics and temporally persistent corruption; zero-shot on 24 real sequences, 14.1 cm position RMSE, 3.9 deg rotation, <20 ms update at 400 robots in sim. Multi-robot relative pose, not single-drone ATE; parameter count/compute not on the abstract page. — [arXiv](https://arxiv.org/abs/2609.21707)
- A search for "scaling laws visual odometry synthetic" found no paper measuring such a law; PerceptionLM (arXiv 2504.13180, UNVERIFIED beyond search snippet) reports synthetic data helps mainly established tasks (vision-language, not VO). — [search result](https://arxiv.org/pdf/2504.13180)
- Repo: pool flights are 62% p90 speed >1.5 m/s while campaign training has 0%; path/extent 12x; ~1,400 local flights all <=33 m path before the fast pool (reports).

### Inferences
- Randomization axes ranked by expected payoff (est.): (1) speed and path length/extent (cruise 1-6 m/s, 60 s flights, mid-start) -- matches measured shift; (2) IMU bias random walk, noise density, and *persistent* bias per flight (NeuRIO emphasises persistent corruptions); (3) scene/texture/lighting (VIO failures correlate with flat/dark views, Spearman +0.6); (4) motion blur/rolling shutter (only if the benchmark renderer has them -- check before spending).
- Expect a scaling curve in *extent-matched* data size, not total frames. A falsification run (Q9) can measure it directly.

### Gaps
- No published odometry scaling law (loss vs data/params/compute) found; the Jan 2026 diversity-vs-quantity paper was only seen as a search snippet (UNVERIFIED, no ID).

---

## Q3. Self-supervised / photometric / test-time training at deployment

### Takeaway
TTT layers and LoRA-style online adaptation exist and Tartan IMU claims 200 FPS online adaptation, but adaptation without ground truth in a causal wasm guest risks self-reinforcing drift; the useful, safe form is adapting *nuisance* parameters (IMU bias, scale/frame offsets) rather than weights. Gain on Pool-171: low, 0-10% (est.), and weights-adaptation can regress.

### Cited Findings
- TTT layers (arXiv 2407.04620): hidden state is itself a model updated by self-supervised learning at test time; TTT-Linear/MLP keep reducing perplexity with context past 16k tokens where Mamba does not (125M-1.3B). Language-model result; none for odometry. — [arXiv](https://arxiv.org/abs/2407.04620)
- Tartan IMU: LoRA (1.1M params) + online test-time adaptation at 200 FPS; supplement claims new motion patterns learned in ~90 s (search summary of supplement; not opened). — [CVPR](https://openaccess.thecvf.com/content/CVPR2025/html/Zhao_Tartan_IMU_A_Light_Foundation_Model_for_Inertial_Positioning_in_CVPR_2025_paper.html)
- ZeroVO's semi-supervised adaptation on unlabeled target data is the VO analogue. — [arXiv](https://arxiv.org/abs/2506.08005)
- Repo: a gyro-bias head regressed (1.144) and kf_grid visual bias already matches oracle bias (1.38 vs 1.29), so bias is saturated.

### Inferences
- Photometric self-supervision needs depth/scale; monocular photometric loss cannot fix metric scale or yaw (the dominant errors, yaw perfect -> 0.967 to 0.209 m on dev). TTT inside the 60 s episode could only exploit consistency across the episode (e.g., revisit, since the drone covers ~12x its extent). That is a loop-closure-like signal and is the only version I find promising, but it is a research bet.
- Wasm cost of a TTT-Linear update is small (a 64x64 inner-model update ~1e4-1e5 MACs per token); fuel is not the obstacle, stability is.

### Gaps
- No odometry paper with measured gain from online weight adaptation in a causal, no-GT, 60 s setting was found.

---

## Q4. Learned residual on top of geometric VIO vs learned replacement

### Takeaway
Residual/correction designs have the most consistent literature record (filters or factor graphs with learned measurements), and in our repo only additions that bring real geometry worked; learned replacement has plateaued. Best-supported variant: learned velocity+uncertainty as an EKF/graph measurement, not a free-form neural correction. Est. gain depends on the VIO tail, not the net.

### Cited Findings
- TLIO: network predicts 3D displacement and uncertainty from IMU windows, fused as an EKF update in a stochastic-cloning filter with biases; beats velocity integration; pedestrian headset data. — [arXiv](https://arxiv.org/abs/2007.01867)
- Learned inertial odometry for drone racing (Cioffi et al., arXiv 2210.15287, RA-L 2023): thrust-input learned module inside a model-based filter, IMU-only, reported to beat filter- and optimization-based VIO (qualitative in abstract). — [arXiv](https://arxiv.org/abs/2210.15287)
- AirIMU: learned correction and uncertainty into pose graph, 31.6% gain in the ablation. — [arXiv](https://arxiv.org/abs/2310.04874)
- Repo: fixed-covariance EKF over learned velocity regressed (1.095 -> 1.129); learned gyro-bias head regressed; kf_grid and direction fusion gained 16-30%; untried: NLL-uncertainty fusion with the provided smoother (reports).

### Inferences
- A frontier-style version: a large network predicts *calibrated per-axis velocity covariance* (heteroscedastic NLL on sim ground truth), trained with long windows, then used as the measurement update for VINS/OpenVINS-style estimator. This is the repo's untried item 1 and is the natural home for big compute.
- Because errors of learned models and VIO are uncorrelated (~0.0 measured) and VIO is spiky, a residual that only *bounds* VIO tails is worth more than one that refines its median.

### Gaps
- No published unaligned-ATE comparison of NN-corrected VIO vs plain VIO on long fast monocular flights found.

---

## Q5. Large network as guard / uncertainty / mixture of estimators

### Takeaway
A learned failure predictor is cheap to train with unlimited sim (label = per-window estimator error) and is directly aimed at the dominant cost (VIO tail: three flights carry 52-77% of the error). Literature on conformal switching between VIO estimators is essentially absent; expect to build it. Est. pool gain: the guard ceiling is the per-flight minimum; realistic capture 50-70% of oracle gap.

### Cited Findings
- Search found no paper combining conformal prediction, VIO failure detection and estimator switching; related pieces: conformal VO bounds (Stutts et al., via search summary), adaptive geodesic conformal pose prediction noting fixed-threshold CP covers only ~60% of the hardest 25% of frames at 90% nominal (2026 arXiv 2605.00233 appears in the result list; UNVERIFIED, not opened). — [search results](https://arxiv.org/html/2605.00233)
- LVI-SAM switches to IMU initial guesses when the VIS subsystem reports failure (rule-based). — [arXiv](https://arxiv.org/abs/2104.10831)
- Repo: VIO failures track init time (OpenVINS mean 0.98 m if initialised within 3 s vs 168 m otherwise), ProcTHOR, flat/dark views; N2 vs VIO error correlation ~0.0 (reports).

### Inferences
- Guard training data: re-run VINS/OpenVINS on every simulated flight, label windows by whether VIO error exceeds learned-model error; features = VIO internals (init flag, feature count, innovation, |v_vio - v_learned|) plus a small image/IMU embedding. Exchangeability for conformal is plausible within sim, not across sim-to-server shifts, so calibrate on a held-out scene split and treat the threshold as a hedge.
- Cost: running three estimators is ~1e10 fuel (VINS 3.4B + OV 4.0B + N2 1.7B from reports) -- under the cap, not free.

### Gaps
- Guard accuracy on the server's distribution is unknowable offline; the repo's oracle-min number (Stage 0) bounds it and should be computed first.

---

## Q6. Pose-graph-like learned long-horizon models (transformer regressing full-window trajectory refinements)

### Takeaway
Feed-forward multi-frame geometry transformers (VGGT) are the 2025-26 template, but they are scale-ambiguous without IMU and run on GPUs; for a causal 20 Hz guest the viable version is a small windowed refiner (the repo already has `Refiner` in odometry_models.py and reported iterative refinement under 2% gain). Est. gain: 5-15% on the learned guest; the benefit would come mostly from long-window supervision.

### Cited Findings
- VGGT: hundreds of views to cameras/depth in one pass, under 1 s reconstruction. — [arXiv](https://arxiv.org/abs/2503.11651)
- VGGT-SLAM: chunks VGGT output and aligns submaps on SL(4), optimising loop closures; designed for GPU-limited long videos. — [arXiv](https://arxiv.org/abs/2505.12549)
- DPVO/DROID: learned bundle adjustment; DPVO 3x faster/third memory of DROID. — [arXiv](https://arxiv.org/abs/2208.04726), [DROID-SLAM](https://arxiv.org/abs/2108.10869)
- DPV-SLAM (arXiv 2408.01654): cited by the repo reports for EuRoC, scale-aligned 0.02-0.1 m; NOT re-opened by me, UNVERIFIED here.
- Repo: iterative refinement and small visual attitude correction gave <2%.

### Inferences
- Deep BA systems are scale-aligned in the literature; DROID-style fuel >=1e10 per reports and GPU assumptions make them teachers/diagnostics, not guests.
- Best use: train a bidirectional long-context transformer teacher offline on 60 s windows (non-causal, sees future), then distill *causal* students with teacher trajectory targets (privileged-information distillation). The causal constraint caps what transfers.

### Gaps
- No evidence found of a learned windowed refiner beating geometric VIO on unaligned ATE.

---

## Q7. Quantization / compile / pruning to run a bigger net in wasm without GPU (budget and fuel)

### Takeaway
Budget arithmetic (est., no web source): a 2e10 per-frame cap allows very roughly 2-5e9 multiply-accumulates in scalar-ish wasm, i.e. ~10-25x N2's reported 1.7e9 fuel. Parameters are not the limit; image-resolution convolutions are. A 20-50M-parameter model is feasible only if its spatial compute stays <~3e9 MACs/frame; transformers over a long token history are cheap per frame if cached (KV or SSM state).

### Cited Findings
- Repo fuel anchors: VINS-Mono 3.4B, OpenVINS 4.0B, N2 1.7B per frame; hard cap 2e10 (reports).
- Distillation compression evidence: up to 92.95% fewer parameters with ~2.12x speed at near-teacher accuracy for pose regression (KITTI/Malaga). — [arXiv](https://arxiv.org/abs/1908.00858)
- DPVO is the efficiency reference for learned VO (3x faster than DROID). — [arXiv](https://arxiv.org/abs/2208.04726)

### Inferences
- int8 and wasm SIMD: if the runtime exposes wasm SIMD128, int8 dot products give ~4-8x fewer instructions than f32 scalar (est.); if fuel counts instructions, quantization buys ~3-5x headroom. Quantization-aware training (not post-training) is needed for velocity regression; expect 1-5% ATE penalty (est., repo has not run int8: listed "never run").
- Cost scale: 8xH100 training of a 100M-param teacher over millions of frames is hours-to-days, wasm student up to a few 1e9 fuel; per-frame fuel stays 10x below the cap.
- Ranking of fuel spend (est.): extra estimators (guard) > larger temporal head (cheap) > larger encoder (expensive).

### Gaps
- Whether the wasm runtime counts SIMD ops as one fuel unit is not established here; check `NEWEST_MODEL_WASM.md` and the fuel report before planning around int8.

---

## Q8. Benchmarks where a large sim-only model beats classical VIO in unaligned ATE

### Takeaway
I found none. Evidence is adjacent: synthetic-only VO (TartanVO) beats geometry on "challenging trajectories" qualitatively; NeuRIO zero-shot sim-to-real on relative inertial odometry; Cioffi/AirIO-type learned inertial methods beat VIO on racing/aggressive data but train on real data. The scale-drift study cited in the repo notes states aligned metrics hide the failures we care about.

### Cited Findings
- TartanVO claim as above. — [arXiv](https://arxiv.org/abs/2011.00359)
- NeuRIO zero-shot sim-to-real result as above. — [arXiv](https://arxiv.org/abs/2609.21707)
- Cioffi et al. claim to beat VIO with a learned thrust-aided filter, trained on real data. — [arXiv](https://arxiv.org/abs/2210.15287)
- Repo: the server's classical VIO already scores 0.475/0.553 m while our learned family scores 3.5-4.5 m; learned methods' "wins" are in regimes where VIO fails (aggressive, textureless).
- Scale-drift study (arXiv 2602.18174) and PRISM-SLAM discussion (2603.26740): UNVERIFIED snippets in the repo notes; not opened by me.

### Inferences
- Expect "large sim-trained model beats VIO on mean unaligned ATE" to be false on friendly flights and true only where VIO diverges. Since the metric is a mean and VIO diverges on ~10% of pool flights, it can win on the pool mean without winning the median; it is the guard role again.

### Gaps
- No direct evidence; this is an open question the falsification test (Q9) addresses for our pool.

---

## Q9. Ranking, estimated gain on our pool, GPU-hours, and a <1 day falsification test

### Takeaway
Rank by (est. Pool-171 mean gain) / (risk): (1) learned guard + calibrated-uncertainty fusion of N2 with VIO (est. pool mean 28.5/5.5 -> 1-2 m, the oracle-min bound decides); (2) server-matched long-window large-teacher training and extent-matched data (N2 3.5 -> 2.3-3.0 m, i.e. 15-35%); (3) calibrated NLL velocity-covariance net as EKF/VIO measurement (est. 10-30% on VIO tails); (4) privileged-information distillation of causal students from a non-causal long-context teacher (5-15%); (5) int8/bigger head (<=5% alone); (6) TTT/online adaptation (0-10%, risky); (7) seed ensembling (<=0.2 m, near-zero given 0.97 correlation). Pure sim-large-model replacing VIO to hit 0.5 m: not supported by any evidence found.

### Cited Findings
- (Repo, from reports) N2 3.508 m on Pool-171, ATE ~0.79*zero-motion+0.25, mean ATE/path 6.2%, seed correlation 0.97, training/pool speed mismatch, 21x faster compiled training, 4.83 s/epoch warm, DDP only 60% efficient at 4 GPUs so independent runs win, GPU0 hosts another service (reports). `nvidia-smi -L` in this environment lists H100 80GB devices (checked).
- Repo trainer entry points available: research/odometry_train.py (Accelerate, EMA, args --head gru|ssm|ema, --epochs, --seed, --set KEY=JSON overrides), research/launch.py (--gpu N --tag), research/odometry_eval.py, research/native_campaign.py, gen.py/odometry_gen.py; gpu_kit/make_flights.sh makes ~86 one-minute flights with 0.3-4 m/s top speeds (gpu_kit/README.txt).

### Inferences
Compute (est.): teacher with ~10-50x N2 params on 60 s windows: 8-40 GPU-hours/run; student distillation 2-8 GPU-hours; guard-labelling needs CPU time for VINS/OV reruns on ~1000 flights; unlimited sim is bottlenecked by OptiX rendering/generation, not training.

Falsification test (<1 day, 8 H100, existing code). Hypothesis H-scale: "N2-family error on Pool-171 is data/horizon-limited, so more extent-matched data plus a bigger model with long windows reduces ATE >=25%." Alternative H2: "drift is path-proportional, size/data won't help."
1. Hold out: Pool-171 and the reserved campaign-test flights untouched. From the 882-flight raw-fast pool take the 711 non-selected flights but split by *scene* so no scene appears in both train and Pool-171 (otherwise leakage; if scene overlap makes this impossible, use fresh flights from gen.py with the existing K2 speed override instead).
2. 2x2 grid, one run per GPU (7 GPUs free; GPU0 is shared): {N2 as-is width, 4x width/heads} x {5 s windows, 30-60 s windows via the WindowPlan group size/window overrides} on identical data, plus 2 runs at 25% vs 100% of the data for the best config (a scaling slope with two points; 4.83 s/epoch warm per N2 run in reports means each cell fits in a few hours at 4x width, est.). Same 3 seeds are unaffordable; use 2 seeds on the winning cell only.
3. Eval with odometry_eval.py / bench_pipeline.sh on Pool-171, report mean, median, 95%-trimmed.
4. Kill criteria (declare before running): if long-window + server-speed data at 1x width gives <10% over N2 (3.5 m) -> H1 mostly false, stop big-model plans and spend on guard/VIO fixes. If 4x width adds <5% beyond that -> capacity is not the limit, do not distill. If the 100% vs 25% data slope is flat (<5%) -> data volume not the limit. Continue to teacher-student distillation only if long-window + data give >=25%.
5. Zero-cost companion (CPU, hours): compute oracle-min(N2, VINS, OpenVINS) on existing per-flight scores to bound the guard; a yaw/scale/bias decomposition of N2 using truth oracles (decompose.py/oracle.py) to choose between H1 and H2.

### Gaps
- GPU-hour numbers are estimates; no timing for 4x-width or 60 s windows on this code was measured.
- Server calibration is based on one learned anchor; all pool gains transfer to the server only approximately.
- Unverified IDs mentioned but not opened: 2408.01654 (DPV-SLAM), 2602.18174, 2603.26740, 2504.13180, 2605.00233, 2104.10831 (LVI-SAM, only seen via search snippet).
