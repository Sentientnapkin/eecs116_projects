# Frozen visual motion screen

This track holds data and temporal architecture fixed while the D-series data experiments varies data coverage and sampling. The isolated branch is `research/visual-motion` based on `a4b4d86`. The GPU host is `wnckcaina01`. Run outputs and feature data stay in this worktree on NFS.

## Frozen protocol

- Use the D0 `teacher-full` roster, manifest SHA-256 `a48e89a07ce127ccf3fce7873f7f020e5f54cdf684b65fb21a3e911edcf40428`, from the shared D0 cache and verified directly against Hub dataset revision `3ff76b2eace12233a23cac10cbda2b37b6d4ad65`. All 136 copied shards passed SHA-256 checks. Training has 61 parents across 36 scenes and development has 7 parents across 6 scenes, with disjoint parent and scene sets. No sealed holdout was read.
- V0 caches CNN spatial features and matching maps from the legacy SSM recipe checkpoint. That checkpoint was selected on this development roster, which favors V0 in this development screen. V2 caches pretrained SEA-RAFT-S vectors and valid support for both gyro-warped histories. Both consume the same 128×96 image pixels and 0.25 s / 1 s causal histories with calibrated warps. SEA-RAFT additionally uses replicate padding to support the four-level correlation pyramid. The source shard checksum binds the exact prewarped histories, masks, IMU and current timestamps. The raw calibration and individual history timestamps live upstream. V2 flow stays in pixel units and the head learns metric velocity from supervision and IMU.
- Fixed two-block SSM and output MLP, with a learned input projection specific to each feature dimension. V0 has 5,232 cached features and V2 has 72, so projection capacity differs. Both train from seed 217 for 488 optimizer updates on 976 windows and 62,464 scored frames. Supervision is metric body velocity and the existing multihorizon displacement loss.
- Select the best EMA checkpoint under the original nominal/5 s crop development score, then report equal-episode unaligned ATE and the legacy ordinary-motion subset. Advance when improvement is at least 10% over V0 with at most 5% ordinary-motion regression. Use scene-paired results and run additional seeds before making a transfer claim. Observed initial speed labels use median truth body speed in the first 0.25 s with threshold 0.2 m/s. Crop-based checkpoint selection is unchanged. Last-checkpoint replay uses the last completed EMA state.
- V1 and WAFT are deferred until V2 answers whether pretrained motion improves the replay. A framewise MLP on the same flow cache provides a temporal control. Fine-tuning and student work require a replay improvement.

## Benchmark contract and control

The published `viobench==0.0.1` leaderboard plots median 1 s translation RPE against maximum frame fuel. Its table also reports **median** per-episode unaligned ATE. [Published package](https://pypi.org/project/viobench/0.0.1/) Our repository's archived public course table is labeled mean Sim(3) ATE. The current private course server contract could not be independently inspected. This screen retains equal-episode mean unaligned ATE, with aligned ATE and fitted scale as diagnostics.

The original SSM checkpoint replay on CUDA reproduced 1.292 m overall, 1.141 m ordinary motion, and 0.503 m aligned ATE. A CPU replay after refactoring changed per-episode ATE by at most 0.000073 m. A 96-frame spot check of the float16 CNN cache changed predicted velocity by at most 0.000013 m/s when the downstream weights were copied from the legacy checkpoint. The true-body-velocity probe using estimated attitude scored 0.407 m. Oracle speed with predicted direction gave 1.078 m overall and 0.823 m on ordinary flights. Oracle direction with predicted speed gave 1.063 m overall and 0.950 m on ordinary flights. Both interventions matter overall. Speed accounted for more ordinary-flight error in this comparison. Interpret the interventions as separate replays. The GPU ledger resolves none of the seven raw development archives and has no exported EMA bundle, so 1.291 m remains the historical EMA reference. A fresh guest replay and complete truth-attitude integration check require the raw files.

## Reproduction

To restore the local D0 input, download `manifests/teacher-full.json` and every `shards/<file>` listed in its training and development rosters from the pinned data snapshot. Place the manifest at `data/visual-motion/d0/manifest.json` and the shard files directly alongside it. Check each SHA-256 against the manifest before training. The archive and SHA-256 paths are content-addressed.

Run from `research/`. Set `CUDA_VISIBLE_DEVICES` to an available device and put `HF_HOME`, `TMPDIR` and pip cache on NFS. Supply the prepared D0 directory named below and the legacy checkpoint directory. Use SciPy 1.17.1 with the existing teacher environment. Clone SEA-RAFT into the ignored data directory and check out `9137517ba24e628442aec097d3afe71d03503b75`. The extractor verifies the source checkout and downloads released `MemorySlices/Tartan-C-T-TSKH-spring540x960-S` revision `31b9b4b711bd2d0d0d38cb99d93ba144beb2dc92`, checkpoint SHA-256 `d6a75e47f2630ba6c354ce84a322e24c3d9def668a6956f340a054b9a3211908`. The V0 checkpoint SHA-256 is `f27acd6b1a5d5ec02daa1b37468b88c17209a7dceaa4cfcbc50d153fca638a2b`. [SEA-RAFT implementation](https://github.com/princeton-vl/SEA-RAFT)

```bash
python visual_motion_cache.py --data data/visual-motion/d0 --cnn-run "$SSM_RECIPE_RUN" --output data/visual-motion/v0
python visual_motion_cache.py --data data/visual-motion/d0 --sea-source data/visual-motion/SEA-RAFT --output data/visual-motion/v2
python teacher_train.py --config configs/visual-motion-screen.json --data data/visual-motion/v0 --set model.cached_visual_size=5232 --output results/visual-motion/v0-s217
python teacher_train.py --config configs/visual-motion-screen.json --data data/visual-motion/v2 --set model.cached_visual_size=72 --output results/visual-motion/v2-s217
python teacher_eval.py --data data/visual-motion/v0 --ledger "$LEDGER" --runs results/visual-motion/v0-s217 --output results/visual-motion/v0-replay
python teacher_eval.py --data data/visual-motion/v2 --ledger "$LEDGER" --runs results/visual-motion/v2-s217 --output results/visual-motion/v2-replay
```

Evaluate each arm on its own feature cache and pair rows by the common prepared shard filename. The caches preserve the original record order and fields used by the deterministic sampler. The generated manifests record feature and source shard hashes.

The same-representation control uses the V2 training command with `--set 'model.head="mlp"'` and a distinct output directory. To apply the frozen gates:

```bash
python visual_motion_compare.py \
  --control results/visual-motion/v0-replay/dev-best.json --control-model v0-s217 \
  --candidate results/visual-motion/v2-replay/dev-best.json --candidate-model v2-s217
```

Focused checks passed for flow direction and units, crop/padding and masks, cached SSM causality and chunking, isolated exported module loading, last-complete EMA restoration, and a synthetic camera lever-arm integration. The ten existing teacher tests also passed.

## Exploratory temporal control

The first complete V2 replay favored the framewise MLP over the SSM. The MLP receives the same two causal histories and IMU summary but carries no learned recurrent state. To distinguish head choice from representation, run the corresponding V0 MLP and compare both MLPs at seeds 217, 218 and 219. This follow-up was added after seeing the first V2 result. Use the same 10% overall / 5% ordinary-motion thresholds for interpretation and report all three pairs.

## Independent proxy validation protocol

Evaluate the development-selected checkpoints out of sample on the audited proxy-validation scenes 150–161. This roster is scene- and parent-disjoint from both D0 training and native development. The recovered index had 69 zero-crop rows for 68 parents. Select the longest zero-crop record per parent and break ties by ascending shard hash, before scoring any proxy flight. Replay all three MLP seeds and the original SSM pair, with no proxy selection or retuning. This is a proxy-domain transfer check. The sealed native holdout remains untouched.

The frozen proxy manifest SHA-256 is `30811894a83fbc45b3ff1ad71b926071ee0084c49cbd45a31114ae96e334f884`. Repeat the two cache commands using `data/visual-motion/proxy` as input and `proxy-v0` / `proxy-v2` as output. Pass each proxy cache to `teacher_eval.py --data` with the trained arm's checkpoints. The local manifest stores the proxy roster in the evaluator's `development` slot so the output remains `dev-best.json` under the distinct proxy result directories. The proxy data is used only by extraction and evaluation.

The screen uses Python 3.12, PyTorch 2.15.0+cu132, NumPy 2.5.5, Accelerate 1.16.0, safetensors 0.8.0, Hugging Face Hub 2.4.0, OpenCV 5.1.0 and H100 GPUs. Each training run snapshots the full source and per-epoch logs. V2 cached 131,696 frames. The complete epoch-4 V2 SSM EMA tensors were bitwise identical to its saved best checkpoint. V0 extraction first started on CPU and was restarted on a GPU once one became available. Both reported training comparisons use H100s.

## Native development results

All scores are meters, means of 14 full replays. The stress group in this roster comes from a single yaw parent.

| Arm | Overall | Ordinary | Stress | Worst replay | Sim(3) | Downstream trainable parameters |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Historical deployed EMA | 1.291 | 1.055 | 2.706 | — | — | — |
| Reproduced legacy end-to-end SSM | 1.292 | 1.141 | 2.196 | 2.323 | 0.503 | 1,286,355 |
| V0 frozen CNN + SSM, seed 217 | 1.564 | 1.392 | 2.596 | 2.708 | 0.594 | 848,131 |
| V2 frozen SEA-RAFT + SSM, seed 217 | 1.144 | 1.111 | 1.343 | 1.889 | 0.355 | 187,651 |
| V2 frozen SEA-RAFT + MLP, seed 217 | 0.998 | 0.990 | 1.046 | 1.975 | 0.351 | 42,435 |

In the predeclared SSM comparison V2 improved overall ATE by **26.8%** and ordinary ATE by **20.2%**. The mean paired scene delta was **−0.337 m**, with a 90% bootstrap interval of [−0.624, −0.051] m across six scenes. Scene 167 regressed by 0.329 m. Every leave-one-scene-out mean favored V2. V2 vs V0 improved speed RMSE from 0.207 to 0.142 m/s, mean speed bias from −0.116 to −0.070 m/s, and the mean of replay median direction errors from 33.7° to 18.5°. V0 / V2 mean ATE by elapsed interval was 0.821 / 0.576 m in the first 10 seconds, 1.753 / 1.313 m from 10–20 seconds, and 1.799 / 1.382 m from 20–30 seconds. Final error averaged 2.132 / 1.533 m.

At seed 217 the SEA-RAFT MLP improved mean scene ATE by 0.147 m over the SEA-RAFT SSM with a 90% interval for the signed delta of [−0.238, −0.046] m. It had higher worst-flight ATE (1.975 vs 1.889 m). Carrying more learned temporal state gave no mean gain for this representation and budget. The result includes the existing causal image histories and IMU summary in both variants.

The V0 extraction took 1m56s on H100 plus local storage IO. Seed 217 SSM training took 3m22s for V0 and about 2m10s for V2. The V2 MLP took about 13s. These are wall-clock pilot measurements under shared-host load. The frozen encoder's parameters and runtime are excluded from the downstream parameter column. The differences in feature cache size and input projection also affect those timings.

Raw results and paired scene deltas are under `results/visual-motion/`, including `v0-replay/dev-best.json`, `v2-replay/dev-best.json` and `dev-ssm-comparison.json`.

### Framewise MLP across paired seeds

| Seed | V0 overall | V2 overall | V0 ordinary | V2 ordinary | Mean paired scene delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| 217 | 1.565 | 0.998 | 1.389 | 0.990 | −0.480 |
| 218 | 1.535 | 1.056 | 1.361 | 1.016 | −0.432 |
| 219 | 1.533 | 1.153 | 1.346 | 1.147 | −0.305 |

All three exploratory pairs cleared both development thresholds. The V2 MLP's ordinary-motion ATE was below the historical EMA for two of three seeds. The single-seed advantage over the historical EMA varies with training initialization and merits a fresh guest comparison. V0 MLP training took 82–84 seconds per seed and V2 MLP training about 13 seconds per seed.

The feature cache manifest SHA-256 values are `1de28969ef282066a768446f1afb71cde9c4cd001d16fce1388ef3f97d739671` (V0) and `7289545ddc6ae3a3e9f4a8b2487d461aafad69423f2caf1e426acbc80b4e9253` (V2). All eight trainers completed 488 optimizer updates. See `dev-mlp-paired-seeds.json` for full paired scene results and both `*-mlp-seeds/dev-best.json` files for individual full-replay metrics.

## Proxy transfer diagnostics

The zero-motion baseline is 2.122 m overall and the truth-velocity probe with estimated attitude is 1.034 m. The legacy SSM scored 2.334 m on these same shard IDs in the other workspace's replay. The V2 checkpoints improved early proxy replay segments and accumulated larger errors over time. For example, the seed-217 MLP scored 0.549 m in 0–10 s, 1.359 m in 20–30 s, 2.152 m in 30–60 s and 3.302 m final error. Its native and proxy speed biases were −0.062 and −0.134 m/s. The proxy fitted Sim(3) scale averaged 0.659, consistent with trajectory shape and integration effects also mattering.

The seed-217 V2 MLP scored 2.303 m on proxy. The oracle-direction intervention improved it to 1.706 m. Oracle speed alone worsened it to 2.716 m. A correction targeting only speed magnitude is insufficient for this shift. The 1.034 m truth-velocity floor also warrants checking the proxy attitude and integration path on the raw flights.

SHA-256 hashes for all eight trained checkpoints are in `results/visual-motion/checkpoint-sha256.txt`. Proxy extraction and evaluation logs are in the same results directory.

| Arm | CNN overall | SEA-RAFT overall | CNN ordinary | SEA-RAFT ordinary | Mean paired scene delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| SSM, seed 217 | 2.238 | 2.253 | 2.271 | 2.451 | +0.026 |
| MLP, seed 217 | 2.206 | 2.303 | 2.244 | 2.332 | +0.077 |
| MLP, seed 218 | 2.267 | 2.252 | 2.276 | 2.256 | −0.019 |
| MLP, seed 219 | 2.313 | 2.261 | 2.271 | 2.216 | −0.037 |

The 12-scene paired intervals all span zero. SEA-RAFT SSM worsened ordinary proxy ATE by 7.9%, while reducing speed RMSE from 0.308 to 0.246 m/s and the mean replay direction error from 27.3° to 18.7°. Better instantaneous motion did not translate to better long-horizon unaligned ATE here. Both representations and all tested heads scored above the zero-motion baseline. Complete results are in `proxy-v0/dev-best.json`, `proxy-v2/dev-best.json`, `proxy-comparison.json` and `paired-scenes.png`.

## Decision

The controlled comparison supports keeping **frozen SEA-RAFT with the framewise MLP** as the candidate for independent **native** validation. The proxy transfer result blocks promotion to a general teacher. Use the same frozen checkpoints and compare against a fresh exported EMA replay on a newly frozen native roster with disjoint scenes. Include the raw-truth integration sanity check and an attitude probe. If long-flight transfer still fails, test a matched broader training roster and inspect signed direction drift and attitude before adding recurrent depth or fine-tuning the visual backbone. V1 and WAFT, visual fine-tuning, and distillation were deferred. A student and WebAssembly fuel were not measured. Raw native archives and the exported EMA bundle are required for the remaining replay and deployment checks.

## Follow-up using the campaign's 30 s proxy protocol

Replayed the same frozen checkpoints on the same 68 parent-disjoint proxy flights through 30 s inclusive, matching the current data stream's benchmark-length convention. The earlier transfer verdict applies to full-duration proxy trajectories. At 30 s, the visual comparison favors SEA-RAFT in every pair.

| Arm | CNN overall | SEA-RAFT overall | CNN ordinary | SEA-RAFT ordinary |
| --- | ---: | ---: | ---: | ---: |
| SSM, seed 217 | 1.482 | 1.090 | 1.448 | 1.049 |
| MLP, seed 217 | 1.482 | 1.122 | 1.448 | 1.085 |
| MLP, seed 218 | 1.478 | 1.133 | 1.438 | 1.060 |
| MLP, seed 219 | 1.480 | 1.193 | 1.395 | 1.158 |

The zero-motion baseline is 2.027 m and truth velocity through estimated attitude is 0.343 m at 30 s. The current result supports benchmark-length proxy transfer, with long-horizon drift and independent native transfer remaining open. The paired scene results are in `results/visual-motion/proxy-comparison-30s.json`. The comparison uses a single representative zero crop per parent, giving 68 episodes. The shared index also contains one additional crop-zero variant, so direct comparisons with other published proxy numbers require matching the exact roster.

Evaluate both the frozen SEA-RAFT MLP and SSM on the published campaign development roster once it is frozen. Keep new flights in familiar ProcTHOR scenes and new HSSD houses visible as separate results. Carry their full-duration drift alongside the benchmark-length scores.

## N1 flow and native deployment kickoff

The first cache pass consumes 230 verified campaign shards from 115 finished parents, including 202,100 frame records. It reads shared staging and writes feature files to this worktree. The full screen waits for the pinned N1 and campaign development manifests. Its input assembler verifies materialized shard checksums and reuses matching offline caches. The matched screen uses seed 217, 36 epochs and 4,392 updates per arm, with a two-block SSM and the same metric supervision in both arms. Campaign validation reports the full trajectory and the first 30 seconds separately. The framewise MLP remains the native development candidate from the prior screen.

The nominal campaign has 600 train parents with about 1.13 million cropped frame records and 60 campaign validation parents with about 102,000 frames. The legacy train/development roster contributes another 131,696 frame records. Expected feature storage is about 1 GB for SEA-RAFT and 15–20 GB for the cached CNN, before incomplete cache artifacts. For expected first-result timing, budget roughly 40–60 minutes for flow extraction and 20–35 minutes for the first 36-epoch SSM on one shared H100, excluding roster preparation and publication.

The deployment target is C++ for the complete guest. The first host-tested components are the CNN/EMA prediction kernels and the calibrated camera-position integrator. See `native_student/README.md` for scope and verification still required.
