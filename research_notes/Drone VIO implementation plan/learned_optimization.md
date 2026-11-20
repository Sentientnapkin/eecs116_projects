# Squeezing the lowest mean unaligned ATE out of the learned N2/kf_grid family on long, mid-start, server-style flights (8xH100 plan)

Conventions: all ATE is mean unaligned position RMSE in metres. R = /data/backups/rganapa/Sebastian/eecs116_projects, `research/` = R/research. Seeds 217/218/219. "Pool-171" = the server-calibrated selection (86 mid-start, 85 static), scores in /data/backups/rganapa/Sebastian/baselines/bench-fast/selected/<guest>/scores.json. Numbers marked "(mine)" are my own computation from those per-flight scores and the sidecar audit JSONs in /data/backups/rganapa/Sebastian/gen/raw-fast/bench/. Gains marked "est." are my estimates, not results. No private server episodes were touched; the repo was read-only (scratch only).

## Q0. What is actually limiting N2 on 60 m flights? (determines which levers are worth pulling)

### Takeaway
N2 on Pool-171 is barely better than outputting no motion (ATE about 0.87x identity-pose error, versus about 0.33x on local campaign dev). Two things changed at once between local and pool flights: speed (campaign-train speed p90 0.51 m/s vs pool 1.58 m/s) and path-to-extent ratio (path ~56 m inside an RMS extent of ~4 m). No yaw/scale/speed decomposition exists on the pool; running it (Stage 0 below) is the first thing to do, because it chooses between "retrain on server-style data" (speed-OOD hypothesis H1) and "needs a drift-bounding geometric anchor" (H2).

### Cited Findings
- Training-data speed coverage (mine, from audit JSONs): campaign train (592 flights) mean path 13.7 m, per-flight speed p50 0.27 / p90 0.51 m/s, max p90 0.74; pool `fast` 441 flights path 46 m, p50 0.65 / p90 1.58 m/s (max p90 2.28), 62% of flights with p90 > 1.5 m/s; the campaign has 0% such flights. Source: /data/backups/rganapa/Sebastian/gen/raw/train/*.json and raw-fast/bench/*.json (audit.speed_p10_p50_p90). The proxy tiers (R/research/gen.py `TIERS`: mid cruise 1-2, agile 2-3.5 m/s) are low-resolution proxy renders; backward motion learned from them did not transfer to native renders (R/research/ODOMETRY.md).
- N2 kf-input s217/218/219 on Pool-171: 3.508 / 3.544 / 3.567 (mine); per-flight correlation between seeds 0.966-0.976, per-flight std across seeds 0.19 m, oracle best-of-3 per flight 3.32, so seed errors are nearly common-mode (mine).
- ATE ~ 0.79 x zero-motion ATE + 0.25 (least squares, mine); mean ATE/path = 6.2% (median 5.7%); mean ATE/zero-motion ATE = 0.87. Campaign dev identity-pose reference is 2.84-3.05 m against N2 ~1.0 (R/research/results/eval/server-benchmark/failure-selected.txt; NEWEST_MODEL_WASM.md). Path/extent on the server is 59.6 m / 4.69 m (R/research/configs/server_observed.json), i.e. the drone covers ~12x its own extent, so a flight revisits the same few metres many times.
- Mid-start is not a separate problem for N2 once extent is controlled: static ATE 3.303 / extent 3.868 = 0.854, mid ATE 3.710 / extent 4.362 = 0.850 (mine).
- Structural yaw/direction guests are now scored on Pool-171 (files exist in bench-fast/selected, `sp5_*`, written 2026-11-20 02:32, newer than the project notes that say "no dataset score"): combined 3.505, direction 3.505, manhattan 3.507 vs control 3.508; max per-flight change 0.038 m, mean absolute change 0.002-0.009 m (mine). Their gates almost never fire on this pool. (Guest spec: R/research/structural_pipelines/README.md.)
- Repo-measured error floor on campaign dev: true velocity through our own gyro attitude 0.967 m, ideal yaw 0.209, ideal tilt 0.909, oracle gyro bias with model velocities 1.33 vs kf_grid 1.355 (R/research/SESSION_REPORT.md, APPROACHES.md; summarised in research_notes/Drone VIO ATE approaches/project_history.md Q6).
- Deep SLAM EuRoC figures in the literature are Sim(3)-aligned, which hides scale and yaw; metric scale needs IMU or metric depth ([PRISM-SLAM comparison discussion via search](https://arxiv.org/pdf/2603.26740); [scale-drift study](https://arxiv.org/pdf/2602.18174)). I only saw snippets for the first link.

### Inferences
- If H1 is true (speed/scene OOD), server-style data is the biggest learned-family lever (est. 20-35% on Pool-171). If H2 is true (yaw/scale drift proportional to path), data helps only 5-15% and the 0.5 m goal needs a geometric yaw/position anchor (loop/revisit, VIO) regardless of what we train.
- With ~12x path/extent, per-metre-of-path drift of 6% is already the same size as the extent itself. To reach 0.5 m on 60 m the effective drift must fall to ~0.8% of path (7x). No data-and-loss change to a velocity net has produced more than ~1.2-1.5x in this project; the structural-guest null result is further evidence that heading corrections tuned on 17 m flights do nothing here.
- Realistic floor for the learned family alone on Pool-171: ~2.3-3.0 m (est.); a stretch of ~1.8 m needs both H1 true and a working revisit anchor. Its role in the final system is the bounded-error fallback and velocity prior.

### Gaps
- No yaw/scale/speed-bin decomposition of N2 on the pool exists; no per-flight predicted velocities are stored. Revisit fraction on the pool is not computed. Stage 0 tests (below) close both.

## Q1. Training data: long (~60 m), speed-matched, mid-start flights at scale

### Takeaway
Generate 1,000 flights first (about 1.2 h wall), then 3,000-4,000 (about 4-5 h wall) with the existing `native_campaign.py generate` + `gen/run_speed.sh` path, in scenes disjoint from the benchmark's clean/dev groups and the reserved test split. Estimated generation cost is a few GPU-hours of wall on 8 GPUs, not days; the real cost is preparing shards (kf_grid_native input derivation) and keeping the held-out set honest.

### Cited Findings
- Generator: R/research/native_campaign.py (`generate`, `prepare`), roster configs R/research/configs/server_fast_pool.json and server_fast_mid_pool.json; entry script /data/backups/rganapa/Sebastian/gen/run_speed.sh (`N ROSTER TAG RAWDIR`, one worker per index, `CUDA_VISIBLE_DEVICES=w%8`, simulator JIT cache on /dev/shm). Overrides used: CRUISE_SPEED_MIN/MAX 3.0-4.5 (setting K) or 4.0-6.0 (K2), MAX_ACCELERATION 6-8, MAX_JERK 30-40, MAX_YAW_RATE 2.0, ROADMAP_SPACING 1.0, CONNECTION_DISTANCE 6.0; mid-start flights are generated 66-82 s long and the first `crop_start_s` (3.4-39.5 s in the selection) is cropped.
- Throughput: all 882 pool flights logged `ok`, mean 214 s and median 135 s per flight per worker (max 1,371 s) with 48 workers (/data/backups/rganapa/Sebastian/gen/raw-fast/generated.jsonl); file mtimes show most of the pool written in ~20 minutes bursts between 00:20 and 00:37, the rest trailing for ~1.5 h (stragglers); pipeline status shows the second pool finishing ~80 minutes after queueing (/data/backups/rganapa/Sebastian/baselines/bench-pipeline/STATUS).
- Storage: raw ~285 MB/flight (249 GB for 882 flights); prepared shard ~16-20 MB per record (hub-cache listing, mine); the NFS volume has ~13 TB free, /dev/shm ~880 GB; box has 192 cores, 2 TB RAM.
- Scene policy in the repo: reserved test = ProcTHOR 162-165/172-175 plus 28 HSSD Val43 houses (never touch); benchmark `clean` = ProcTHOR 150-161, 176-179 (in no training split); `dev` = ProcTHOR 166-171 + 15 HSSD Val43; `seen` = 36 ProcTHOR + 30 HSSD-train scenes sampled from campaign-train scenes; simulator crashes in ProcTHOR 121/124 and one HSSD house (R/research/server_benchmark.py; configs/native_campaign.json).
- Pool composition: 441 flights each in fast/fastmid; per list: clean 16 scenes x 12, dev ProcTHOR 6 x 6, dev HSSD 15 x 3, seen ProcTHOR 36 x 3, seen HSSD 30 x 2 (R/research/server_benchmark.py `build_pool`). So the 711 pool flights NOT in Pool-171 include ~475 in clean/dev scenes, usable as a held-out validation set (that is my arithmetic from the plan counts and the selection's group counts: clean 21, dev 49 selected).
- N2's training set: 592 native campaign parents (29,460 s) + expanded proxy tiers; training windows are 64 scored + 32 burn-in frames (~4.8 s) with 0.25/1/3 s displacement horizons (R/research/configs/odometry.json; odometry_train.py `loss_fn`). The prior data-scaling evidence: B-D0 1.871 -> N2 1.391 campaign-full when proxy tiers + native campaign were added (project_history.md).
- Mid-start targeting experiment already failed in the other direction: moving existing native windows earlier ("early native resampling") regressed every set, e.g. campaign full 1.3906 -> 1.5163 (R/research/TRAINING_COMPLETION.md). That changes window position within slow flights; it is not the same as new fast mid-start flights.

### Inferences
Concrete data plan (est. costs; wall hours use the measured 214 s/flight mean and 48 workers, so flights/h ~ 48*3600/214 ~ 800 at best; budget 500-650/h realised):

| Tier | Flights | Wall (est.) | Raw disk | Use |
|---|---|---|---|---|
| T0 pilot | 200 (100 static + 100 mid) | 0.4 h | 57 GB | smoke the full chain, falsify H1 (see Q0 and falsifier below) |
| T1 | 1,000 | 1.5-2 h | 285 GB | main screens |
| T2 | 3,000 | 5-6 h | 0.85 TB | scaling point |
| T3 | 6,000 | 10-12 h | 1.7 TB | only if the scaling curve (250/500/1k/2k/4k flights) is still log-linear |

- GPU-hours: generation is render-bound on the 8 GPUs shared with training; call it ~8 GPU-h per 1,000 flights of wall-clock occupancy (est.), preparation is CPU (`native_campaign.py prepare --workers 40`, plus `input_attitude.py derive --policy kf_grid_native --workers 40`; time per flight not measured in the docs, so treat as unknown, est. 1-3 CPU-min per record).
- Roster design (new `configs/server_train_pool.json`, modelled on server_fast_pool.json): 50% static, 50% mid (offset 3-40 s, same as the pool) ; speed settings K, K2 and a third lighter setting (cruise 1.5-3) so speeds are not a single mode; ids prefixed `ftrain-` with seeds from a new range (>= 950000; the pool used 800000-801000 and 930000+, check collisions); include the HSSD-train scenes (the pool's `seen` catalog) because the pool's HSSD shows the worst N2 flights (all large-extent mid-start HSSD, 8.9-10.4 m).
- Held-out scene split (proposed; never generate training flights in these): (a) benchmark `clean` 150-161/176-179 and `dev` 166-171 + 15 HSSD Val43 (= 70 of the 171 gate flights plus ~475 unselected pool flights as the validation set); (b) additionally hold out ~15 ProcTHOR train scenes and ~12 HSSD-train scenes drawn at random from those not in the benchmark `seen` sample, as `ftrain-val` (generate 300 fast flights there as a second held-out set); (c) the reserved test split stays untouched. Train only on the remaining ProcTHOR (0-9, 46-149 minus 121/124, 180-199) and HSSD-train scenes. Expect the `seen` group (101 of the 171) to become optimistic after training on same-scene fast flights, so gate on clean+dev (70 flights) and report all 171.
- Also add 64 signed-lateral/backward pilot flights (the repo's own never-run proposal; native lateral windows in the first second exist in only 2 ProcTHOR and 0 HSSD scenes) and use `crops_s` [0, 5] as today (mid-start parents already start moving).
- Falsification (H1, cheap): generate T0 (200 flights), train N2 recipe with them added 50/50 to the existing sampler, evaluate on the held-out pool flights. Kill the "server-style data is the lever" claim if pool-clean+dev mean improves by less than 10%. Also measure speed-binned velocity bias of the current N2 on pool flights beforehand (Stage 0 D2); if the model under-predicts speed above 1 m/s by under 5% the data hypothesis loses most of its support.
- Scripts to modify: `native_campaign.py` (add a `--roster` default for `ftrain`, plus a `--raw`/split option for `prepare` so it can read raw-fast style directories; `prepare` currently reads `RAW/<split>` and refuses only the test split), `server_benchmark.py` (a `train_pool` builder reusing `build_pool` with the split rules above and a collision check against the 882 pool ids/seeds), `odometry_pool.py`/`odometry_store.py` (compose a new manifest `n3-fast-tiers` = n2-campaign-tiers + `ftrain` records, with `domain` = "native-fast" so `domain_share` can weight it), `input_attitude.py` (run `derive --policy kf_grid_native` on the new raw archives; the degenerate-solver repair is already in).

### Gaps
- Real per-flight prepare/derive time, and how many shards `odometry_store compose` can add before cache sizes become an issue (RAM preload of ~30 GB for the current set will not scale to 6k flights x 2 crops; see Q6).
- Whether the server flights actually start mid-route is unknown (the pool tilts on extent and path only).

## Q2. Training changes aimed at extent- and yaw-driven error

### Takeaway
The current objective only supervises short (<=3 s) displacements inside 4.8 s windows while inference runs 60 s of recurrent state on position-integrated output, so there is a clean train/test mismatch to attack: long stateful windows with long-horizon position residuals. Expected gain is modest (5-15%, est.), because the net cannot observe yaw error, which is the repo's measured dominant error. Yaw-aware training is only worth it if a yaw observation (vision) is fed in.

### Cited Findings
- Loss: smooth-L1 (beta 0.1) on body velocity, plus smooth-L1 on camera-displacement residuals over horizons [0.25, 1, 3] s computed through the INPUT attitude `R`; optional NLL head (`nll_weight`) exists but was never trained for fusion (R/research/odometry_train.py `loss_fn`). Windows: `window_frames` 64, `burn_in` 32, SSM state starts at zero at the window start; deployment carries state for 1,200 frames.
- Prior long-window screen was negative at matched scored frames: w96 1.446, w128 1.459 (with horizon 6 s 1.457), vs base 1.312 mean-of-two-seeds at 12 epochs (R/research/TRAINING_COMPLETION.md screen table; hp_search.py `TRIALS`). ODOMETRY.md notes "12 s context at matched scored frames hurts (fewer updates)". Those runs used equal scored frames per epoch, i.e. fewer optimizer updates, so they do not test long context at equal updates.
- Training length: 36 epochs (4,392 updates) beat 12 epochs by ~18% (dev 1.337 -> 1.095), 72 epochs only another 5.5% (dev 1.091 -> 1.030; campaign full 1.832 -> 1.794) (TRAINING_COMPLETION.md; ODOMETRY.md).
- Input-attitude retraining already gave 10-12% on campaign full at common attitude (control 1.108 -> kf_grid 0.972), so input-side geometry has measurable effect (TRAINING_COMPLETION.md).
- Learned gyro-bias head (A-D0) regressed (dev 1.095 -> 1.144); fixed EKF on velocity regressed; iterative refinement <2% (project_history.md Q2). Prior oracle: ideal yaw with true velocity 0.209 vs 0.967.
- SSM length generalization: failure of long-sequence generalization is tied to the distribution of initial states seen in training, and "state passing" (initialising training states from the final states of other sequences) enabled generalization from 2k to 128k with ~500 post-training steps in language models ([Understanding and Improving Length Generalization, arXiv 2507.02782](https://arxiv.org/html/2507.02782v2)); Mamba Modulation links failure to the state-transition spectrum ([arXiv 2509.19633](https://arxiv.org/pdf/2509.19633)). Language-model evidence, not odometry.
- AirIO: body-frame IMU encoding (66.7% average gain claimed), attitude encoding (23.8% more), training windows of 1,000 IMU frames; Blackbird unseen 1.30 m ([AirIO](https://arxiv.org/html/2501.15659v2)); the paper's own text and tables disagree in places (see previous report). AI-IO: rotor speeds +36.9% on velocity, transformer +22.4% ([arXiv 2603.00597](https://arxiv.org/abs/2603.00597)). IMU features: zeroing the 51 direct IMU features costs ~5% (ODOMETRY.md); thrust/rotor speed is not in the ABI (APPROACHES.md).
- Our velocity head already outputs BODY-frame velocity from derotated images and gravity-aligned/ rewritten IMU features, so the AirIO "body-frame" change is mostly in place; explicit attitude encoding (gravity direction in body frame, R^T g, accelerometer minus gravity) is not listed among the 51 features in the docs I read.

### Inferences
Ranked changes (gain = estimated effect on Pool-171 mean for the N2/kf_grid model, relative):

| # | Change | Est. gain | GPU-h | Eng-h | Files | Falsifier |
|---|---|---|---|---|---|---|
| 2a | Server-style data (Q1) in the existing sampler, `domain_share` native-fast 0.5-0.7, same arch, 36-72 epoch compiled recipe | 20-35% if H1, 5-12% if H2 | T1: ~2 per seed set; T3 ~10 | 8-12 | `odometry_data.py` (`domain_share` already exists), `configs/experiments.json` (new `N3-*-x3` entries), `odometry_pool.py` | held-out pool-clean+dev mean improvement <10% -> drop |
| 2b | Long stateful windows: `window_frames` 300-600 with TBPTT state carry between consecutive windows or random initial states from other windows (state-passing), batch 1-2, bf16, equal OPTIMIZER UPDATES to base (not equal frames) | 3-10% | ~0.5/run, 8-10 runs | 12-16 (state carry in `PlannedWindows` + `replay`-style stateful loader; `odometry_models.py` already returns state) | `odometry_train.py`, `odometry_data.py`, `odometry_models.py` | at equal updates, long-window arm not better than base by >=3% on pool-held-out over 3 seeds -> drop |
| 2c | Long-horizon position residuals: add horizons 10/20/40 s and a window-final position term (with truth-attitude-free input R, as now) with horizon-weighted smooth-L1; requires 2b | 2-6% | in 2b | 2 | `loss_fn` (`horizons` is already a config list) | removal ablation within seed noise (0.06 on pool) -> drop |
| 2d | Tail/path-weighted loss: weight windows or flights by path length or extent (the error scales with them), plus log-ATE selection | 2-5% | ~0.2 | 3 | `PlannedWindows` mixture, `evaluate`/selection score in `odometry_train.py` | selection by pool-val ATE vs dev ATE gives the same checkpoint -> no gain |
| 2e | Replace checkpoint selection (14 short original-dev replays, 601 frames) by held-out 60 s fast flights; consider SWA over last epochs | 2-5% (selection on the right distribution) | trivial | 3 | `odometry_train.py` main loop (`records = manifest["datasets"]["development"]`) | selected epoch identical -> drop |
| 2f | Input features: explicit gravity-in-body and accel-minus-gravity channels, speed-scale augmentation (time-warp +-30%, which scales velocity and acceleration consistently) | 0-5% | ~0.3 | 6 | `features.py`, `streaming.py`/`input_attitude.py` (C++ twin `native_odometry/new_model_inputs.hpp` must change, so deployment cost is high) | no gain at 2 seeds, 12 epochs -> drop |
| 2g | Yaw-drift-aware loss/aug: inject synthetic constant heading offset rates into `R` during training and supervise a learned yaw-rate correction | 0-5%; likely null (A-D0 learned bias head regressed; net has no yaw observation) | ~1 | 10 | `odometry_models.py` (`gyro_bias_correction` path exists) | repeat of A-D0: no gain over control on pool-val -> stop |
| 2h | Rotor/thrust features | not available (no thrust in ABI) | - | - | - | n/a; the accelerometer already carries thrust and drag in body-z/x/y specific force |

Multi-window curriculum (2b+2c): 64 -> 160 -> 320 -> 600 frames over the schedule, with horizon set growing in step; start from the already-trained N2 weights for the last 25% of updates so the CNN/features stay fixed (cheaper and avoids the w128 regression). Cheapest way to test long context before touching the full net: use the frozen-encoder tooling `learned_probe.py`/`seq_heads.py` (frozen CNN embeddings, 128 per frame, full 1,200-frame sequences; heads trained in seconds) to compare SSM-zero-init, state-passing and GRU/transformer heads. That needs ~2.5 GB of cached embeddings for 4,000 flights and costs <1 GPU-h per head family.

### Gaps
- Whether the 51 IMU features contain a gravity-in-body vector; I did not open `features.py`/`streaming.py` in detail. Whether the N2 C++ twin can take new input channels without a re-port (the retrained `static08`/`kf_grid` input policies are not fully deployed per TRAINING_COMPLETION.md).
- No published result on trajectory-level losses for mean-over-median ATE (noted in the prior survey).

## Q3. Model-side: bigger teacher + distillation, ensembles, snapshot/EMA/SWA, TTA, uncertainty heads

### Takeaway
All of these are small levers here because the error is systematic (seed-to-seed errors correlate 0.97) and the net is not capacity-limited; uncertainty heads matter mainly as guard inputs. Expected total from this group: 3-8% on Pool-171, plus guard value.

### Cited Findings
- Seed variation on Pool-171 is small and common-mode (Q0): oracle per-flight best of 3 seeds is 3.32 vs 3.51 mean, so a velocity average cannot realistically exceed a few percent (mine).
- EMA 0.995 is already used; EMA 0.99/0.999 and wd/clip screens were within noise or worse; `cnn-wide` (embedding 192) 1.249 vs base 1.312 at 12 epochs (about -5%, within the 2-seed noise); `cnn-narrow` 1.295 (TRAINING_COMPLETION.md screen table). Architecture swaps (2/4-layer SSM, GRU variants) landed within the 0.29 m dev seed spread (ODOMETRY.md).
- Model is 1.286M params, CNN 99.5% of MACs, peak fuel 1.66B (limit 2e10 per frame, user says ignore fuel) (NEWEST_MODEL_WASM.md; project_history.md Q1).
- Existing uncertainty support: `model.uncertainty=true` (3 extra log-variance outputs), `training.nll_weight`, mean detached in the NLL term (`odometry_train.py`, `odometry_models.py`); never trained for fusion (APPROACHES.md untried item 1).
- Literature: RIO uses ensemble variance to decide updates and test-time training ([RIO](https://arxiv.org/pdf/2111.11676)); X-IONet Huber-Gaussian uncertainty ablation 16.7-69.9% ATE/RTE change ([arXiv 2511.08277](https://arxiv.org/pdf/2511.08277)); AirIMU learned covariance 31.6% pose-graph improvement ([arXiv 2310.04874](https://arxiv.org/html/2310.04874v4)); UL-VIO BatchNorm-only TTA ([arXiv 2409.13106](https://arxiv.org/abs/2409.13106v1)); AirIO EKF helps seen data (0.486 -> 0.403) but not unseen (1.300 -> 1.309) ([AirIO](https://arxiv.org/html/2501.15659v2)). Tartan IMU multi-platform pretraining 36% claimed ([CVPR 2025](https://openaccess.thecvf.com/content/CVPR2025/html/Zhao_Tartan_IMU_A_Light_Foundation_Model_for_Inertial_Positioning_in_CVPR_2025_paper.html)).

### Inferences

| Item | Est. gain on Pool-171 mean | GPU-h | Eng-h | Scripts | Falsifier |
|---|---|---|---|---|---|
| 3a Deep ensemble, 3-5 seeds (or 3 data-bag variants), average velocities in body frame before integration | 1-3% (seed errors 0.97 correlated; bagging over data subsets/hyperparameters decorrelates more, up to ~5%) | 0.3 per member at base data | 4 python + 6 C++ (3 nets in one guest; fuel ~3x, ~5B, below 2e10) | `learned_matched_replay.py`/`odometry_eval.py` for offline average, `native_odometry/export.py`, `guest.cpp` | offline average of 3 existing seeds' predicted velocities improves pool mean <1.5% -> drop (needs per-flight predicted velocities from `odometry_eval.py --runs`) |
| 3b Bigger teacher (wide CNN, 2-4x width, 6+ layers or transformer over full context, bidirectional/noncausal allowed) distilled to the current 1.29M student with GT + teacher velocity targets | 2-6% (est.; sim GT labels already exist, so KD mainly smooths noise and transfers long-context behaviour) | 2-6 for the teacher on T2/T3 data | 10-14 | `odometry_models.py` (new head kinds exist: gru_res, gru_ssm), new `distill` weight in `loss_fn` (the old `distillation_weight` field is in `configs/odometry.json`, with the implementation removed per train.py comment "legacy") | teacher not better than student by >=10% on held-out pool -> no point distilling |
| 3c Snapshot/SWA of the last 20% epochs + EMA | 0.5-2% | ~0 | 2 | `odometry_train.py` (AveragedModel already used for EMA; add SWA window) | no gain -> drop |
| 3d Test-time adaptation (BN-only or scale-calibration on the fly, variance-gated) | 0-3%, risky; the repo already deprioritised it | 1 | 8 | new; requires C++ backprop for deployment (infeasible) or closed-form scale/bias update only | sim-held-out no gain -> stop; **do not pursue in wasm** |
| 3e Uncertainty (NLL) head, retrained on server-style data, used (i) to weight learned velocity against VIO velocity in a filter or gate, (ii) to flag unreliable flights | direct gain ~0; enables the guard (other researchers' rank 1/2) | 0.5 for 3 seeds | 6 | `configs/experiments.json` (`--set model.uncertainty=true --set training.nll_weight=0.5`), `odometry_train.py` | Spearman between per-flight mean predicted sigma and ATE <0.5 on held-out pool, or NLL worse than constant-sigma baseline -> no guard value |

### Gaps
- No distillation precedent for odometry networks found in the previous survey; 3b rests on general-ML expectations.
- Per-flight predicted-velocity dumps for the pool do not exist yet (needed for 3a offline test); the Wasm scoring only stores ATEs.

## Q4. Post-hoc: visual yaw correction, kf_grid extensions, window smoothing

### Takeaway
Current heading corrections (Manhattan, direction, kf_grid bias) are saturated or inactive on the pool; the untried geometric lever that matches the pool's 12x path-to-extent ratio is a keyframe/revisit rotation anchor that bounds yaw drift instead of only estimating bias. Window smoothing is low value.

### Cited Findings
- kf_grid visual gyro bias reached oracle-bias level (public 1.383 vs oracle 1.289; campaign 1.355 vs 1.33), so bias-only visual correction is saturated (APPROACHES.md s2; results/eval/attitude-bias/public/summary.json).
- Structural guests on Pool-171: Manhattan 3.507, direction 3.505, combined 3.505 vs 3.508 (Q0, mine). The Manhattan version keeps one room frame, needs 8 supporting lines, gain 0.15, 0.5 deg/step cap, 10 deg gate, no Atlanta-world room switching; direction: 2 Hz, 25% gain, 10 deg cap, 0.5 s decay (structural_pipelines/README.md).
- Existing parity problems: the kf_grid port of historical builds passed an empty mask to `recoverPose`; the corrected variants fail Python/Wasm accepted-update parity (KF_GRID_PARITY_REVIEW.md; FUSION_COMPLETION.md).
- Fixed EKF on velocity regressed dev 1.095 -> 1.129 and ordinary 0.921 -> 1.001; proxy30 was the only improvement (project_history.md Q2 item 10).
- The server's identity-pose ATE (4.69) vs path (59.6 m) means heavy revisiting (Q0). Revisit-fraction analysis and loop-closure trials were proposed in the repo and never run (project_history.md Q3 item 6).

### Inferences
| Item | Est. gain | GPU-h | Eng-h | Files | Falsifier |
|---|---|---|---|---|---|
| 4a Keyframe/revisit rotation anchor: store keyframes (grid/ORB features + estimated attitude) roughly every 1 m or 20 deg; on a revisit match features and use the essential-matrix relative rotation to reset the heading of the current estimate against the stored keyframe (relative rotation is metric-free) and add a position pull toward the keyframe position scaled by predicted-velocity uncertainty | 10-40% if the revisit fraction is high (very uncertain); also the only item here that bounds rather than slows drift | 0 | 25-40 (new C++ in `native_odometry/kf_grid.hpp`/`structural_pipelines/structure.hpp`, Python reference first, parity) | as listed; OpenCV 5.1 already isolated | (i) revisit test on truth: fraction of pool frames within 1.5 m and 60 deg of an earlier keyframe; kill if <30% of frames (the repo's own threshold); (ii) oracle test: snap yaw to truth at revisit frames in a Python replay of N2 velocities; kill if the improvement is <15% |
| 4b Manhattan/Atlanta extensions (room switching, more lines) | <2% on the pool (guest changed ~0.003 m); HSSD/ProcTHOR rooms are not clean boxes | 0 | 15 | `structural_pipelines/structure.hpp` | already falsified at current scale; revisit only if a diagnostic shows lines are present but gated out |
| 4c Learned visual yaw-rate correction (head predicts yaw drift from derotated image pairs over multi-second baselines; trained on server-style data) | 3-10%, uncertain | 1-2 | 12 | `odometry_models.py` (`gyro_bias_correction` exists), new loss on yaw error | A-D0 analogue: no pool gain -> stop |
| 4d Window smoothing/learned smoother of velocity, bias-free scale calibration | 0-2% | 0 | 4 | `vel_fusion.py`, `ekf_experiment.py` | EKF history says regression |
| 4e kf_grid at higher rate/native resolution everywhere, parity fixes | 0-3% | 0 | 10 | `native_odometry/kf_grid.hpp`, `input_grid_attitude.hpp` | not worth it unless parity is already needed for deployment |

### Gaps
- No trajectory-based revisit analysis was run; I did not open the raw zips for ground truth. The rotation-only loop-closure benefit also depends on the camera features surviving large viewpoint change at 60 m of flight.

## Q5. A DROID/DPVO-style deep VO teacher (offline)

### Takeaway
As a pseudo-label source it is redundant (the simulator provides exact velocity and pose); its value is as a ceiling diagnostic for visual yaw/scale accuracy and, at most, as a distillation teacher of relative-rotation/yaw features. It cannot be deployed (fuel and GPU), and published numbers are Sim(3)-aligned. Expected direct gain on the learned family: 0-5%; value mainly informational (it sets the ceiling for 4a/4c).

### Cited Findings
- DROID-SLAM zero-shot EuRoC monocular ATE ~0.022 m (secondary source), DPVO ~0.105, DPV-SLAM 0.024, all scale-aligned ([DROID-SLAM](https://arxiv.org/pdf/2108.10869), [DPVO](https://arxiv.org/pdf/2208.04726), [DPV-SLAM](https://arxiv.org/pdf/2408.01654)); DBA-Fusion adds dense BA to an IMU factor graph for metric scale ([arXiv 2403.13714](https://arxiv.org/abs/2403.13714v1)); MegaSaM adds depth priors ([arXiv 2412.04463](https://arxiv.org/abs/2412.04463)). A recent search result states that methods relying on Sim(3) alignment do not yield true metric trajectories ([search hit, abstract-level](https://arxiv.org/pdf/2603.26740)).
- The repo deprioritised DPVO/DROID for fuel (>=1e10) and the earlier ranked report gave them rank 10 (reports/Drone VIO ATE approaches.md). Frozen-encoder/probe infrastructure exists (`learned_probe.py`, `seq_heads.py`).

### Inferences
- Use: run DPVO (or DROID with monocular + camera intrinsics) on 20-30 pool flights (clean/dev, mixed static/mid), then compute (i) Sim(3)-aligned ATE, (ii) 4-DoF (yaw+translation) alignment with scale from truth, (iii) scale-only alignment, (iv) fully unaligned after fixing the first-frame gauge. Cost: <3 GPU-h (1,200 frames per flight; est.), 12-20 eng-h to set up environment and cameras. If yaw-only alignment error is `<<` 1 m, vision yaw is available and 4a/4c have a high ceiling; if the teacher itself fails on the pool's textureless HSSD flights, that is also a result for the VIO guard.
- Pseudo-labels have no use on simulated data with exact labels; they would only matter for adapting to real video, which is not in scope.
- Falsifier: DPVO scale-only-aligned (unknown scale per flight) error not `<<` 1 m median on 20 flights -> drop DROID/DPVO entirely.

### Gaps
- I did not verify any DROID/DPVO unaligned numbers on drone data; none found. The 2026 arXiv ids in search hits (e.g., 2603.26740) came from snippets only.

## Q6. Parallelising experiments over 8 GPUs, seeds, and evaluation gates

### Takeaway
A full N2 36-epoch run costs ~3 minutes of training plus ~75 s of compile on one H100 (4.83 s warm epoch; the data is the bottleneck), so thousands of runs are feasible and the scarce resources are data generation, held-out data hygiene, and decision discipline. Use independent runs per GPU, not DDP.

### Cited Findings
- 4.83 s per warm epoch (21.3x faster than the original recipe), DDP efficiency 60.5% at 4 GPUs (4.20/2.48/1.74 s at 1/2/4), so independent runs win (SESSION_REPORT.md; ODOMETRY.md). `hp_search.py` already schedules runs onto GPU "slots" (`--slots 1,1,2,2,3,3,7,7`, two runs per GPU) and `launch.py --gpu N --tag gpu` pins consecutive runs to consecutive devices, each with its own shard cache (R/research/hp_search.py, launch.py).
- GPU 0 currently hosts ~2.2 GB of another service (nvidia-smi); earlier workstreams used GPUs 2-7 for training and GPU 5 for evaluation, and left 0 and 1 alone (TRAINING_COMPLETION.md).
- Gen workers are placed `CUDA_VISIBLE_DEVICES=w%8` including GPU 0 (gen/run_speed.sh). Data in /data/backups/rganapa/Sebastian is on NFS (~13 TB free); /dev/shm is ~880 GB; preloading shards into RAM is available via `training.preload` (decompresses all records into RAM per run) (odometry_train.py).
- Seed noise: 12-epoch D0 runs differ up to 0.29 m on dev; 36-epoch N2-family seeds on Pool-171 differ by ~0.06 m on the mean (3.508/3.544/3.567; mine). Gates are declared in advance in this repo and `bench_pipeline.sh` scores any `.wasm` dropped in /data/backups/rganapa/Sebastian/baselines/queue on the 171 flights with 180 workers (bench_pipeline.sh), reports raw mean, median, p90, trimmed means via failure_analysis.py (failure-selected.txt).
- Existing guard sets: original dev (14 replays, 6 scenes), campaign dev (120 resets/21 scenes; 30 s capped and full), public (10 x 60 s, one scene in training), proxy-val 30 s (68 replays) with historical guard: ordinary original-dev regression <=5% (N2 failed it at +9.2%) (project_history.md; TRAINING_COMPLETION.md).

### Inferences
**GPU allocation (steady state)**
- Generation phase (Q1): all 8 GPUs, `N=48` workers (6 per GPU), as run_speed.sh does; if GPU0's service is sensitive, set `N=42` and skip w%8==0, i.e. patch the `CUDA_VISIBLE_DEVICES` mapping to `1 + w % 7`. Prepare/derive on 40-80 CPU workers concurrently (192 cores).
- Training phase: GPUs 1-7 take 2 runs each (14 slots; mirror `hp_search --slots 1,1,2,2,...,7,7`); GPU0 only for evaluation/diagnostics (<=20 GB) while the foreign service lives there. For data >1,000 flights do not preload per run: put prepared shards on /dev/shm (880 GB; 4,000 flights x 2 crops x ~18 MB ~ 150 GB fits once) and use DataLoader workers on the local store; otherwise 14 preloading runs would need >2 TB RAM (est.).
- Lanes: A (GPUs 1-2): server-style data scaling (250/500/1k/2k/4k flights, 3 seeds each at 36-72 epochs-equivalent); B (3-4): long-window/horizon/selection changes at T1 data; C (5): frozen-encoder head tests plus ensemble/SWA offline; D (6): teacher/distill; E (7): uncertainty head + hold-out evaluation for the guard; GPU0: Stage-0 diagnostics, DPVO ceiling test.

**Seeds and screening.** Screens at 12 epochs with seeds 217/218 and a 10% prior bar for promotion (to keep with the repo's rule); promote to 36-72 epochs x 3 seeds (217/218/219, paired with the control) only the top 1-2 arms per lane. Every comparison is paired by flight and bootstrapped by scene (scene-paired bootstrap, as in the repo).

**Evaluation gates (declare before running; do not tune on the gate set)**
1. Model selection and hyperparameters: held-out pool flights not in Pool-171 (clean+dev, ~475 flights) and `ftrain-val` (300 flights); python/GPU batched replay (`odometry_eval.py`, ~4.5 s per 26 replays). Never select on Pool-171.
2. Primary gate: Pool-171, raw mean unaligned ATE (official) with 3-seed mean; also report median, p90, count >10 m, 95%-trimmed mean, 5/95 winsorized mean, worst-10% share and a 12-episode bootstrap range (the 90% range is about +-0.8 m, so differences below ~0.4 m are not decision-grade for a single 12-flight server draw; on the 171 flights the 3-seed spread is ~0.06 m). Accept an arm if the 3-seed mean improves >=5% (about 0.18 m) with every seed better, and the clean+dev subset (70 flights) improves by a similar margin.
3. Guards (no-regression, <=5% each, as in the repo): original dev (14), campaign dev 30 s and full (120), public (10); report proxy-val 30 s but note N2 variants already regress it. A guard failure is documented and weighed against the server-regime benefit rather than silently accepted, since the server regime is the target.
4. Deployment gate (separate): weight-only changes (same architecture: data, loss, EMA/SWA, distillation) can reuse `native_odometry/export.py` and `guest.cpp`; ABI check 5 steps; Python-vs-Wasm ATE within 1% on 10 flights; queue the `.wasm` into the benchmark watcher. Anything with new inputs, longer context or ensembles needs C++ changes and Python/native/Wasm parity first.
5. Fresh confirmation: after freezing, 192 new independent 60 s flights in untouched scenes (the repo's own stress-set proposal), single scoring. Reserved test split stays untouched.

**Staged schedule (wall time, est.)**
- Day 0 (hours, mostly CPU/1 GPU): Stage-0 diagnostics: (D1) truth velocity through our attitude on Pool-171 and N2 velocity through truth attitude (oracle yaw), extending `decompose.py`/`oracle.py` over the raw-fast zips; (D2) speed-binned velocity bias of N2 on pool flights (needs `odometry_eval.py` on prepared pool shards: prepare 60-100 clean/dev pool flights via a patched `native_campaign.py prepare`); (D3) revisit-fraction and oracle-yaw-snap test; (D4) DPVO ceiling on 20 flights. Decision: H1 or H2.
- Day 0-1: launch T1 (1,000 flights) generation (1.5-2 h) and T0 pilot training as soon as 200 are ready.
- Day 1-3: Lane A/B/C/D/E screens at T1; start T2 generation in the background.
- Day 3-5: promotion runs at T2/T3 with 3 seeds; ensemble/SWA offline; uncertainty head; hand off the best weight-only checkpoint for export; revisit anchor (4a) prototyping in Python on CPU if D3 says go.
- Day 5-7: Pool-171 scoring by the queue watcher; fresh-set confirmation; freeze.

Cumulative compute est.: ~60-120 GPU-h for training and diagnostics (screens ~0.1-0.5 GPU-h each), ~30-60 GPU-h-equivalents of generation wall on shared GPUs, plus ~150-250 engineering hours across items 2a-2e, 3a-3c, 3e (about 60-80 h) and 4a (25-40 h) if pursued.

**Overall expected outcome for the learned family (est.):** 2a+2b+2c+2d+2e+3a-3c compound to roughly 25-40% (not additive) on Pool-171 if H1 holds, i.e. ~2.1-2.6 m, and ~10-20% (2.8-3.2 m) if H2 holds. Neither reaches 0.5 m; reaching it requires the geometric guard/anchor lines of work.

### Gaps
- GPU memory and throughput at 600-frame windows and batch 2-4 on the CNN+correlation volume are unmeasured (est. fits in 80 GB with frame_chunk and bf16, not verified).
- Whether the simulator generation rate scales past 48 workers (GPU render saturation) and the real preparation throughput were not measured.
- GPU0's foreign service could be heavier later; check nvidia-smi before each launch.
