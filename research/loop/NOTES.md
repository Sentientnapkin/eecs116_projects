# Overnight teacher research loop (started 2026-11-17 23:29)

## What runs unattended

| Process | Job | Log |
| --- | --- | --- |
| `research_loop.py` | Trains queued specs two at a time on MPS, writes `leaderboard.md`, mirrors this folder to `SentientNapkin/viobench-teacher-lab/loop`, replicates the best spec when idle. Stops starting runs at 08:30. | `loop/runner.log`, `results/loop/<name>.log` |
| `odometry_gen.py` | Simulates 60 s flights in about 270 unused scenes (ProcTHOR-Train 0–9, 46–161, 180–199, plus HSSD-Train at about 1 in 4; 15% independent-yaw), 3 passes with new seeds. | `data/gen-spool/gen.log` |
| `odometry_pool.py` | Gates each flight (≥2 m travel, no stall, finite truth; until 2026-11-18 also ≥25% moving, not dark or textureless), prepares 0 s and 5 s crops with the base pipeline, and uploads content-addressed shards plus `manifests/gen-pool-v1.json` to `SentientNapkin/viobench-teacher-data`. | `data/gen-spool/pool.log` |
| `data_scheduler.py` | At 100/200/280 generated shards, freezes `teacher-v2/v3/v4` snapshots (base + pool, same development set) and queues the best spec on each ahead of other work. | `loop/data_scheduler.log` |

Add work with `python3 loop/enqueue.py '<spec json>'`.

## Lessons this plan builds on

From our own runs:
- v1 teachers (no weight averaging, constant learning rate) swing ±0.3 m between epochs. GRU v1 peaked at 1.48 (epoch 4) and ended at 1.91. SSM v1 reached 1.36 at epoch 7. Selection on noisy epochs needs weight EMA plus a decaying learning rate.
- The earlier robustness work found the SSM's first-memory initialization hurts reset/moving starts, and that longer windows (140–280 frames) were used for the best robust runs.

From the other teams' Stage-1 slides:
- Speed is the largest error source. Team 11's oracle: true speed cuts ATE 30%, true rotation 19%. Drift dominates over noise (Team 1). This motivates long displacement horizons (1–6 s), which Teams 1 and 7 also used as measurements.
- Best server accuracy came from a CNN giving 1 s relative pose plus uncertainty into an EKF (Team 7, 0.207 m), and from our own derotated triple-frame network (0.237 m). Uncertainty outputs matter for later fusion.
- More, varied data helped consistently (Team 2: 80 to 398 episodes; Team 3: 788 flights in 70 scenes). Generated data needs gates: stalled flights and zero-motion flights poison training (Teams 4, 6).
- Attention and velocity feedback did not help (Teams 7, 10). Larger models alone did not help speed from flow (Team 11).

From recent literature:
- AirIO (RA-L 2025): body-frame IMU features plus explicit attitude encoding improve learned drone odometry; attitude encoding alone was worth about 24%. Our inputs were already body-frame; attitude input is now a queued experiment.
- Velocity networks with uncertainty feeding a filter (ICD-Net 2025, EVC-Mamba 2026, learned bias prediction 2025) are the current pattern for drift correction.
- SkyJEPA (2026): physics-structured latent dynamics dampen error growth over long rollouts. This is a candidate next step: residual-on-IMU-preintegration head.

## Queue rationale

1. `gru-recipe`, `ssm-recipe`: v1 models plus EMA, cosine LR, 12 epochs, patience 5 (direct comparison to v1).
2. `gru-w160*`: longer context; then a 6 s horizon; capacity; AirIO attitude input; combinations.
3. `data-teacher-v*`: best spec on 2×, 3×, 4× training data as the pool grows.

## Selection metric

Mean of nominal and 5 s moving-start unaligned ATE on the fixed 7-flight development set (lower is better). Sim(3) ATE (course alignment) is logged alongside.

## Findings during the night

- 01:38 `gru-recipe` 1.446 (best at last epoch, Sim(3) 0.481). Stable, unlike v1.
- 02:01 `ssm-recipe` 1.292 (best at last epoch, Sim(3) 0.503, 1.29M params). New leader, so the remaining architecture experiments moved to SSM.
- The independent-yaw development flight (scene 166) has 0% backward-sign accuracy in both models (2.6–2.8 m ATE). The base training data has one yaw flight; the generated pool is about 15% yaw.
- Velocity RMSE is about 0.2 m/s at 0.25–0.5 m/s speeds. Speed is the weak point, as Team 11's oracle predicted.
- 02:58 `gru-blind` (images blanked): 1.594 vs 1.446 with images, but Sim(3) 0.472 vs 0.481. Vision currently improves global speed scale, which Sim(3) alignment removes, and does not yet improve path shape.
- 03:05 rotation floor (`loop/rotation_floor.py`): true body velocity integrated with our estimated attitude scores 0.41 m unaligned and **0.17 m Sim(3)**. Our models are at 1.29–1.45 and 0.47–0.50. **Attitude error explains only about a third of the Sim(3) error; about 0.3 m is velocity error**, so better velocity (data, context, horizons) remains the main lever.
- Follow-ups (not run tonight): (1) make vision improve velocity *shape*, not just scale: per-step speed supervision weighted by speed change, or selecting on Sim(3); (2) a rotation or gyro-bias output trained against truth (Team 1's vision gyro-bias correction cut rotation error 55° to 17°) to approach the 0.17 m floor.
- 03:20 v3 snapshot queued (322 train shards) at 6 epochs; v4 snapshot dropped so every queued run finishes by morning. The pool keeps growing for later runs.
- 04:00 a broken HSSD scene (mesh with no faces) crashed the native renderer and stopped generation. `gen_supervisor.sh` now restarts the generator and marks any crashing scene as failed; about 10 minutes lost.
- 04:51 `ssm-w160-h6` was level with plain SSM at epoch 7 (1.499), so the last slot tests attitude input on the plain leader (`ssm-att`, 10 epochs) instead of on the long-context variant.
- 05:47 `ssm-w160-h6` 1.435 (nominal 1.40, moving 1.47, Sim(3) 0.503) vs plain SSM 1.292: longer windows + 6 s horizon at equal compute hurt nominal accuracy. Confounded by half as many windows per epoch.
- 07:08 `ssm-att` early-stopped at epoch 7 (best epoch 2, 1.517, Sim(3) 0.471): **patience 5 is wrong with a cosine schedule**, since gains arrive as the learning rate decays (the plain SSM improved through epoch 12). Rerun without early stopping queued as `ssm-att-nopatience`. Future recipes should drop patience or measure it from the decay phase.
- 07:32 **`data-teacher-v3-ssm-recipe` 1.260 (nominal 1.15, moving 1.37, Sim(3) 0.478): new leader; data scaling is the clearest win of the night.** Queued `data-teacher-v4-ssm-recipe` on all ~400 generated shards (finishes about 12:30).
- 07:40 New directive (D0/D1/D2 data experiment first). Generator paused (resumable: `./gen_supervisor.sh --seconds 60 --passes 3`). **Leakage note:** gen-pool-v1 used ProcTHOR 150–161, which are proxy-validation scenes; v2–v4 snapshots trained on them, so proxy val is not a clean holdout for those models. Native dev (166–171), final test (162–165, 172–175) and confirmation (176–179) scenes were excluded.
- 08:02 **My error:** evicted generated-pool cache shards (verified on the Hub) while the v4 run was still reading them; v4 crashed in its first epoch with no checkpoint (~30 min lost). It was about to be paused for the D-series anyway; spec kept in loop/paused.json for a fresh restart later. Lesson: never evict shards referenced by any running manifest.
- 08:30 Full-replay reference (`results/eval/reference/dev-best.json`, equal-flight mean unaligned ATE on 14 dev replays / 6 scenes): zero 2.591; ssm-recipe 1.292; gru-recipe 1.446; v3-data SSM 1.260; **deployed EMA 1.291 (ordinary flights 1.055, best of all)**; deployed SSM 1.395. The larger teachers do not yet beat the submitted EMA. v3's gain is entirely on the yaw flight (backward-sign 0.90 vs 0.44); scene-paired vs ssm-recipe −0.003 m, 90% [−0.12, +0.11]: no evidence of overall improvement. Six dev scenes give wide intervals, so the 12-scene proxy-validation holdout (clean for the D-series, contaminated for pool-trained v2–v4) is used as a second evaluation set.
- 08:26 D-series epoch ≈25 min with 4 jobs; GRU D0/D2 pair deferred until the SSM D-series finishes (expected ≈12:50) so the priority comparison completes first.
- 09:40 Confound found: native shards are 21.3% of D0 training records but 4.4% of D1/D2 (same native parents, diluted). D1 at epoch 4 is worse on native dev (1.730 vs D0 1.537). Declared follow-up D1n/D2n (native share pinned at 21.3%) before seeing final D results. Published the ledger and labeled manifests (teacher-full-labeled, d1-expanded-tiers-labeled); the original compose step mislabeled native records as proxy (labels only; shards and splits unaffected).
- 09:31 **Paused everything at the user's request** (compute moving elsewhere). Resumable: D0/D1/D2-ssm and ssm-att-nopatience from their last checkpoints via `./odometry_env.sh launch.py D0-ssm D1-ssm D2-ssm` (auto-resume); GRU pair, D1n/D2n, v4 and generation not started.

## 2026-11-18 afternoon: GPU box (wnckcaina01)

- Restarted the D-series fresh on GPUs 1–5 (`--tag gpu`; GPU 0 hosts another service). **First launch crashed all five runs in under a minute: they shared `data/hub-cache` and one process unlinked shards another was still writing** (the same class of error as the 08:02 eviction). Fixed in `launch.py`: one cache directory per run. Nothing had trained; the run folders were deleted and relaunched.
- Reproducibility across hardware: D0-ssm-gpu epoch 1 scores 1.508, identical to the Mac's D0-ssm epoch 1. The CUDA evaluator reproduces every Mac reference number exactly (ssm-recipe 1.292, gru-recipe 1.446, v3 1.260; rotation floor 0.407).
- D1n/D2n were started early on the idle GPUs 6–7 **as speculative compute only**; they are interpreted only if the predeclared domain-follow-up condition holds.
- **Proxy-validation records recovered** without the Mac: shard names from the four `proxy-proxy_validation` upload commits, crop-0 shards matched to ledger parents by (travel, backward frames, lateral frames), crop-5 shards matched to their crop-0 sibling by exact velocity overlap. 136 records, 68 parents, 12 scenes; published as `manifests/proxy-validation-records.json` (data repo commit 2d16465). Proxy-validation flights are **90 s** (1,801 frames), not 60 s.
- **Ledger near-duplicate:** `agile-ProcTHOR-Train-155-s00906-00` and `-01` have identical truth (same scene and seed, different renders/files), which the sha-based duplicate check cannot see. Both are proxy-validation in scene 155, so scene-level results are unaffected; the records are flagged `ambiguous_parent`.
- Generation gates now reject only simulator failures (non-finite truth, <2 m travel, stall). `moving<25%`, `dark` and `textureless` remain audit fields.
- **Proxy-validation reference (crop 0, 68 replays, 12 scenes, unaligned ATE):** zero 2.129; true velocity with our attitude 1.042 (Sim(3) 0.512); ssm-recipe 2.345; gru-recipe 2.170; v3-data SSM 2.239 (contaminated: its pool used these scenes). **No reference teacher beats zero output on the 90 s holdout.** They are much better early (0–10 s: 0.69 vs zero 1.13) and on Sim(3) (1.10–1.12 vs 1.54), but under-estimate speed (bias −0.16 to −0.18 m/s) and drift: final error 2.7–3.1 m vs zero 1.98. Agile flights are worst (2.5–2.7 vs zero 1.97). On this set the GRU beats the SSM (scene-paired −0.173 m, 90% [−0.25, −0.10]), the reverse of the native dev ranking. The 6-scene dev set alone would have missed both.
- **D0 finished (12 epochs, best at epoch 12 for both).** Dev: D0-ssm-gpu **1.152** (ordinary 1.020, backward/lateral 1.943, Sim(3) 0.455, backward sign 0.84); D0-gru-gpu 1.415. D0-ssm-gpu vs ssm-recipe (same data and recipe apart from the sampler path and patience): −0.132 m, 90% [−0.18, −0.09]. **First teacher to beat the deployed EMA on dev (1.291 overall, 1.055 ordinary).** The gap to ssm-recipe may be seed or sampler noise, so seeds 218/219 of D0-ssm started on GPUs 1 and 4.
- **Proxy-validation criterion declared before any D1/D2 result:** score the first 30 s of each replay (benchmark length; new `--max-seconds`). The 90 s score is a diagnostic only, because even true velocity through our attitude scores 1.04 m over 90 s. At 30 s: zero 2.041, true velocity 0.348, ssm-recipe 1.375, gru-recipe 1.359, D0-ssm-gpu **1.303**, D0-gru-gpu 1.353. Over 90 s: D0-ssm-gpu 2.188 and D0-gru-gpu 2.136, both still no better than zero (2.129).
- **D-series decision (single seed 217, best-EMA checkpoints, control D0-ssm-gpu, scene-paired 90% intervals):**

  | Run | Dev mean | Dev ordinary | Dev bk/lat | Dev Sim(3) | vs D0 (dev) | Proxy-val 30 s | vs D0 (30 s) | Proxy-val 90 s |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | D0-ssm | **1.152** | **1.020** | **1.943** | 0.455 | – | **1.303** | – | 2.188 |
  | D1-ssm | 1.611 | 1.312 | 3.406 | 0.495 | +35% [+0.14, +0.62] | 1.357 | +4.5% [−0.00, +0.12] | 2.190 |
  | D2-ssm | 1.458 | 1.108 | 3.557 | **0.444** | +18% [−0.08, +0.50] | 1.348 | +3.1% [−0.02, +0.11] | 2.193 |
  | D1n-ssm (exploratory) | 1.556 | 1.214 | 3.606 | 0.465 | +27% [+0.03, +0.58] | 1.383 | +5.7% [−0.05, +0.20] | 2.579 |
  | D2n-ssm (exploratory) | 1.520 | 1.196 | 3.462 | 0.497 | +26% [+0.01, +0.56] | 1.321 | +1.3% [−0.04, +0.08] | **2.025** |
  | D0-gru | 1.415 | 1.250 | 2.400 | 0.540 | – (GRU control) | 1.353 | – | 2.136 |
  | D2-gru | 1.450 | 1.198 | 2.962 | 0.563 | +1.8% vs D0-gru [−0.14, +0.12] | 1.455 | worse | – |

  - D1 and D2 fail the screen and the ordinary-motion guardrail. They do not improve the declared 30 s holdout either, so **the domain follow-up condition is not met**. D1n/D2n (run early on idle GPUs) are exploratory and change no decision; they are also worse on dev.
  - Backward motion: D2 learns backward sign on proxy flights (0.82 on proxy-val vs D0 0.13) but **not on the native yaw dev flight (0.00 vs D0 0.84)**. Backward competence from proxy data does not transfer to the native domain; D0 gets it from the one native yaw training parent at its 21% native share.
  - **Caveat that keeps the question open:** at the fixed 1,464 updates, D0 revisits each of its 61 parents about 5× more often than D1/D2 revisit theirs, and D0 was still falling steeply at epoch 12 (1.40 → 1.15 over epochs 8–12) while D2 had the best Sim(3). Declared before running: B-D0-ssm-x3 vs B-D2-ssm-x3 (36 epochs each), same gates.
  - Expanded proxy data is not adopted. The T-series (architecture) runs on D0 data.
- ~18:10 **Hub rate limit stalled every run for ~1 h.** Seven concurrent runs each committing to the lab repo every ~5 min hit the HF commit limit (HTTP 429), and the per-epoch sync blocked training inside huggingface_hub's hour-long retry. I noticed only at 19:10. Checkpoints are written before the sync, so the runs were killed and resumed exactly from their last complete epoch. The sync now runs in a background thread (`odometry_hub.BackgroundSync`): busy epochs are skipped, failures warn, and the final epoch is always pushed. The code change does not affect training numerics.
- **Seed noise is large and the D0 control seed was an outlier.** D0-ssm seeds 217/218/219: dev 1.152 / 1.439 / 1.420 (mean 1.337); ordinary flights 1.020 / 1.312 / 1.298; backward sign 0.84 / 0.34 / 0.55; 30 s proxy-val 1.303 / 1.406 / 1.368. Seed-to-seed paired differences on dev are +0.27 to +0.29 m with intervals that exclude zero: **the scene-paired bootstrap captures flight sampling, not training randomness, so single-seed intervals overstate certainty.** Revised D-series reading: D2-ssm (1.458 dev, 1.348 proxy-val 30 s) is within the D0 seed range on the holdout and only slightly outside it on dev. The decision stands (no candidate shows a ≥10% gain, so expanded proxy data is not adopted), but "+18% worse" is not evidence of harm. D2-ssm seeds 218/219 are queued so the comparison becomes 3 seeds vs 3. Seed 217's 1.152 also explains the earlier "D0 beats ssm-recipe and the deployed EMA": that was one seed's luck, not a recipe gain.
- **GRU checkpoints on CUDA were incomplete.** accelerate's safetensors `save_state` deduplicated cuDNN's flat GRU weight views and silently dropped 7 of 49 tensors per checkpoint (checked: D0-gru epoch 12 has 43 of 50 keys). The `best.safetensors` files are CPU copies and complete, so every reported GRU evaluation stands, but no GRU run on CUDA could resume. T-grures2/T-grures4/T-grussm (epochs 7/7/5) restarted fresh as `-gpu2`; the broken folders are kept locally as `*.broken-checkpoints`. Checkpoints are now pickled (`safe_serialization=False`), with a CUDA regression test.
- T-ssm-w240 first crashed: the original sampler draws startup/uniform pairs, so 65 windows planned 64 items. It now uses 66 windows (scored frames +1.4% over the budget) and the planner rejects odd counts.
- 19:13 a queue launched B-D0-ssm-x3, B-D2-ssm-x3, P-imu-blind and T-ssm-w240 into GPUs I had just freed to restart runs, so a few GPUs briefly held two runs. No result is affected beyond wall time.
- **T-series and IMU probe (seed 217 each, D0 data and recipe, best-EMA checkpoints).** Dev mean / 30 s proxy-val: D0-ssm seeds 1.152–1.439 / 1.303–1.406 (seed means 1.337 / 1.359); T-ssm4 1.227 / 1.338; T-ssm2e148 (parameter-matched 2-layer) 1.349 / 1.343; T-grures2 1.276 / 1.323; T-grures4 1.374 / 1.333; T-grussm 1.335 / 1.312; T-ssm-w240 1.480 / **1.511**; P-imu-blind 1.429 / **1.426**; plain GRU (D0-gru) 1.415 / 1.353.
  - No head passes the ≥10% screen against the control. On the 30 s holdout every 2- and 4-layer SSM, residual GRU and hybrid lands at 1.31–1.34, inside the control's three-seed range, so **depth and head type are not the bottleneck at this data size.** 4 vs 2 layers at matched parameters: 1.338 vs 1.343 (no difference).
  - **12 s context at matched scored frames hurts** (holdout 1.51, outside the seed range): it gets 792 optimizer updates instead of 1,464, and the backward sign collapses on the yaw flight.
  - **IMU features matter only modestly** beyond derotation and attitude: zeroing them costs about +5% on both sets, just outside the seed range.
  - Residual GRU is much better than the plain stacked GRU (dev 1.276 vs 1.415, holdout 1.323 vs 1.353).
- **Native campaign restarted on the GPU box (user request; the Mac session's uncommitted code is not used).** The course simulator (`viobench[sim]==0.0.1`, `hyperdrone`/`hyperlux` 0.1.10, the instructor's packages, verified by metadata before install) runs here in `venv-sim` with the OptiX renderer. `native_campaign.py` + `configs/native_campaign.json`: 600 train / 60 dev / 88 reserved-test flights, no scene in two splits (test enforced). Train: ProcTHOR 0–9, 46–149, 180–199 + HSSD Train125. Dev: new flights in ProcTHOR 166–171 + 15 HSSD Val43 houses. Test: ProcTHOR 162–165, 172–175 + the other 28 HSSD Val43 houses. ProcTHOR 150–161 and 176–179 unused. Flights vary length 30/60/90 s, autopilot (25% independent yaw), hover 0.2/1/3 s and route density. Raw 640×480 archives are kept; only simulator failures are rejected. Pilot (8 flights): all pass, truth-integration RMS 0.2 mm, 10–280 MB each; independent-yaw flights give 15–25% backward frames. 16 workers (two per GPU) started at ~20:10.
- **D-series with three seeds per arm (217/218/219):** dev mean D0 1.337 (1.152/1.439/1.420) vs D2 1.509 (1.458/1.613/1.457); dev ordinary flights D0 1.210 vs D2 **1.201**; dev backward/lateral (the single native yaw flight) D0 2.098 vs D2 3.357, with D2's backward sign 0.00 in every seed; 30 s proxy-val D0 1.359 vs D2 **1.347** (spread 1.346–1.348 vs 1.303–1.406). **Expanded proxy tiers tie the control on ordinary native flights and on the holdout. The whole dev deficit is one flight: backward motion learned from proxy data does not transfer to native rendering, while D0 learns it from its single native yaw parent.** That points at native backward/lateral training data, which the native campaign provides (25% independent-yaw flights). Decision unchanged: not adopted (no ≥10% gain).
- Generation fixes: per-worker private build caches avoided the NFS failure but recompiled every simulator configuration in every worker (~4 min each); a copied build tree fails (CMake pins absolute paths). Final setup: one shared JIT cache on local tmpfs (`/dev/shm`), where hyperlux's flock works. ~110 flights were marked failed by the broken attempts; they have no archive and are retried.
- B-series at 36 epochs: B-D0-ssm-x3 1.060 at epoch 29 (vs 1.152 at 12 epochs, same seed); B-D2-ssm-x3 1.174 at epoch 25 and still falling. Seeds 218/219 of both arms queued.
- **Metric rule (from Sebastian):** everything is scored on mean unaligned ATE (m, log scale) only. Sim(3) ATE is removed from `odometry_train.py` logs, `odometry_eval.py` summaries and plots (now log-scale mean-ATE axes), and the guide. Sim(3) numbers earlier in these notes are historical and do not inform any decision; no gate or selection ever used them.
- **Native campaign complete (train/dev).** 592/600 train flights (8 lost to scenes that always crash the simulator: ProcTHOR-Train-121 and -124, flights crash; HSSD 103997940_171031257, native abort) and 60/60 dev. A native abort (core dump) killed one worker's remaining list; leftovers were rerun one process per flight (`--ids`). Published to the data repo: 1,184 train shards + `manifests/native-campaign-train-records-1184.json`, 120 dev shards + `manifests/native-campaign-dev-records-120.json`, and the composed **`manifests/n1-campaign.json` (teacher-full-labeled + 592 campaign parents; 1,306 train records; dev roster unchanged) at data revision `508d93ffd230e5c6dfb543312e768b678339382b`**. The reserved test split is still generating; it is archived only. N1-ssm-x3 seeds 217/218/219 started 21:25.
- **B-series (3× budget, 36 epochs, three seeds each), mean unaligned ATE:**

  | Arm | Dev mean | Dev ordinary | Dev yaw flight | Proxy-val 30 s |
  | --- | --- | --- | --- | --- |
  | B-D0 (teacher-full) | **1.095** (1.054/1.120/1.111) | **0.921** | 2.136 | 1.276 (1.256/1.274/1.299) |
  | B-D2 (expanded tiers, balanced) | 1.250 (1.150/1.271/1.329) | 0.952 | 3.038 | **1.128** (1.096/1.110/1.177) |

  - **Training 3× longer is the clearest win so far:** D0 dev improves 1.337 → 1.095 (−18%) and holdout 1.359 → 1.276. **B-D0 is the first teacher that beats the submitted EMA in every seed** (dev 1.05–1.12 vs 1.291; ordinary 0.92 vs 1.055).
  - **With enough updates, expanded proxy data generalizes better to unseen scenes**: −11.6% on the 30 s holdout with non-overlapping seed ranges, ordinary native flights within the 5% guardrail (+3%), but the native yaw flight is still lost (backward sign ≤ 0.13). This meets the predeclared domain-follow-up condition, so **B-D2n-ssm-x3** (balanced mixture, 21.3% native share, 3× budget, three seeds) started 21:37.
- **Campaign-dev reference (60 new native flights × 2 crops; 30 s / full duration), three-seed means:** zero 2.843 / 3.122; true velocity with our attitude 0.530 / 0.967. B-D0 1.353 / 1.870 (ProcTHOR 1.491 / 2.009, HSSD 1.215 / 1.732, backward/lateral 3.47 / 4.40); B-D2 1.402 / 1.963 (ProcTHOR 1.670 / 2.364, HSSD **1.133 / 1.563**, ordinary **1.085 / 1.498** vs 1.161 / 1.640, backward/lateral **4.89 / 7.08**). The 15 native independent-yaw dev flights confirm on many flights what the single old yaw flight showed: **proxy-only backward training does not transfer to native**, while expanded proxy data helps ordinary motion and unseen house styles.
- **Campaign holdout frozen:** reserved test split final at 84/88 flights (HSSD house 104862384_172226319 aborts natively). Roster plus all 736 per-flight audits (with archive SHA-256) published to the private `SentientNapkin/viobench-native-campaign` (metadata only; revision `596b40b`). Raw archives stay on the GPU box (`/data/backups/rganapa/Sebastian/gen/raw`, ~100 GB). The test split has not been prepared or scored.
- N2-ssm-x3 (expanded tiers + campaign, balanced sampler, 3× budget, three seeds) declared and started 21:55 on `n2-campaign-tiers` (1,770 train records).
- `git push` from the GPU box fails (no GitHub credentials); the branch is committed locally only.
- **Renamed (Sebastian's request):** this is learned odometry, not teacher–student distillation. Branch `research/learned-odometry` (was `claude/teacher-model-training-60911a`); `teacher_*.py` → `odometry_*.py`, `test_teacher.py` → `test_odometry.py`, `TEACHERS.md` → `ODOMETRY.md`, `configs/teachers.json` → `configs/odometry.json`, class `Teacher` → `OdometryNet`, `TEACHER_GUEST_DIR` → `GUEST_DIR`. The unused `--teacher` distillation option is removed (its identity field and `distillation_weight` stay as inert legacy keys so existing checkpoints resume). Hub repos, manifests and run names keep their names; earlier entries in these notes use the old names.

## Campaign restart and initial dev replays

- Resumed seven interrupted campaign runs from the last complete checkpoints on GPUs 1–3. The other two B-D2n seeds were already at epoch 36. N1 and B-D2n finished all three seeds, and N2 continues at the same 36-epoch budget.
- Three-seed mean unaligned ATE on dev (overall / ordinary / backward-lateral): B-D0 1.095 / 0.922 / 2.136 m, N1 1.164 / 1.076 / 1.690 m, and B-D2n 1.341 / 1.019 / 3.273 m. N1 improved backward/lateral ATE by 20.9%, alongside a 16.8% ordinary-flight regression. N1 and B-D2n both missed the overall dev screen and ordinary-flight guardrail. Initial replays are in `results/loop/campaign-early-dev/`. The combined evaluation in `results/eval/n-series/` is queued behind the final N2 checkpoints.
- Independent 30 s replays (three-seed mean unaligned ATE). Proxy validation: B-D0 1.276 m, N1 1.302 m, B-D2n 1.186 m. Campaign dev overall / ProcTHOR / HSSD: B-D0 1.353 / 1.491 / 1.215 m, N1 1.219 / 1.340 / 1.097 m, B-D2n 1.425 / 1.743 / 1.108 m. N1 improved campaign backward/lateral ATE from 3.473 m to 2.696 m and ordinary ATE from 1.161 m to 1.084 m. Neither candidate clears the predeclared dev screen.
- Parallel workstreams: the compiled-correlation throughput pilot reached 4.83 s per warm epoch versus 103.02 s for the matched one-H100 control (21.3×, 122 updates in both). Accuracy validation and 1/2/4-GPU scaling continue on `odometry/throughput`. The campaign attitude oracle identified yaw as the main source of attitude error (with true velocity, 0.967 → 0.209 m full campaign ATE under ideal yaw correction). The learned correction is training on `odometry/attitude`.
- The fixed EKF scored 1.129 m versus 1.095 m on dev, with a regression in each seed. The best refinement arm scored 1.078 m with a 1.52% reduction, short of its 10% adoption screen. The two approaches remain opt-in on `odometry/ekf` and `odometry/refine`.
- The B-D0 C++ FP32 reference passed parity on all three seeds. Peak measured fuel was 1.075 billion per raw replay frame on the sampled clips. The CNN accounted for 99.5% of the counted MACs and is the focus of a matched SIMD fuel pilot on `odometry/deploy`.
- The compiled recipe cleared the three-seed full-replay throughput gate (B-D0 → compiled, dev 1.0950 → 1.0905 m, ordinary dev 0.9215 → 0.9061 m, proxy validation at 30 s 1.2765 → 1.2587 m). The remaining hyperparameter sweep will use this recipe with a separate paired control after the original eight runs drain and smoke tests pass.
- At fixed global batch four, the two-H100 timing pilot reached 2.48 s per warm epoch versus 4.20 s on one H100, with both completing 183 updates over three epochs. Cost rose from 4.20 to 4.96 GPU-s per warm epoch. NCCL required NVLS to be disabled for this benchmark. The four-H100 benchmark waits for N2 to release GPUs 2 and 3.
- The opt-in Wasm SIMD convolution preserved every pose and twist output bit-for-bit across all four matched raw crops and three seeds, reducing peak fuel by 19.87% (1,074,754,835 → 861,235,415 per frame).

## Parallax-aware visual attitude, frozen B-D0 velocity

- Reused the existing small-rotation fit after a low-flow gate and used a cheirality- and parallax-gated essential matrix for higher-flow pairs. Replayed the same frozen velocity vector sequence through gyro-only and corrected rotations for each of B-D0 seeds 217/218/219. Focal lengths matched the stored sensor features. The synthetic pure-rotation direction and causal prefix checks passed.
- Three-seed mean unaligned ATE in metres (gyro-only → visual): dev overall 1.0950 → 1.0863, nominal/static 1.0456 → 1.0362, moving 1.1443 → 1.1364. Campaign-dev 30 s overall 1.3534 → 1.3454, nominal/static 1.2419 → 1.2342, moving 1.4648 → 1.4565. Campaign ProcTHOR 1.4914 → 1.4849, HSSD 1.2153 → 1.2059. The 0.79% dev gain missed the 10% advancement gate. Hybrid and peak-fuel evaluation stayed gated. Per-replay results and checkpoint hashes are in `results/eval/visual-attitude/`.
- Native OpenVINS ZUPT on/off completed on all 120 30 s campaign-dev crops after setting identity calibration for the fields normally filled by the YAML loader. Off scored 2.843 m overall (2.726 static / 2.960 moving) and emitted no estimate. On scored 2.837 m (2.709 / 2.964), with an estimate on 57 crops and one native tracking exception retained in each arm. Neither cleared the dev gate. Results are on `odometry/openvins` at `76e44d3`.
- Added the [development coverage and stress-set design](../EVALUATION_COVERAGE.md). The training audit on `odometry/data-coverage` found adequate general backward/lateral coverage and thin uncropped lateral coverage, with eligible windows in two ProcTHOR scenes and zero HSSD scenes within the first second. The matched N2 resampling queue changes approximately 410 of 8,784 windows per seed. A separate 64-flight training-only lateral pilot is proposed for the coverage resampling cannot supply.
- CUDA replay reuses each loaded checkpoint and batches eight independent flights sorted by length. On one H100, 26 original and campaign development replays took 10.68 s sequentially and 4.46 s batched with a 32-frame image chunk. Maximum per-replay ATE shift was 0.035 mm and maximum trajectory separation was 0.109 mm. With the original eight-frame image chunk the batched path took 8.46 s and the largest ATE shift was 0.073 μm. Use `--batch-replays 1` for the original serial numerical path.
- The exact submitted seed-217 Wasm scored 1.996 m unaligned ATE on all ten 60-second public VIOBench episodes, with zero filled frames and 1.075 billion peak fuel per frame. The public episodes all use the same ProcTHOR scene.
- Final N-series replays finished. Three-seed N2 unaligned ATE was 0.933 m on original dev, 1.110 m on proxy validation at 30 s, and 1.007 / 1.391 m on campaign dev at 30 s / full duration (ProcTHOR 1.126 / 1.477 m, HSSD 0.888 / 1.304 m). N2 cleared the overall dev screen and exceeded the ordinary-flight guardrail (1.007 m vs 0.921 m). Three matched resampling seeds are running on GPUs 1–3.
- Extending compiled D0 from 36 to 72 epochs improved three-seed dev ATE from 1.091 to 1.030 m and 30 s proxy ATE from 1.259 to 1.219 m. Campaign dev improved from 1.332 to 1.279 m at 30 s and from 1.832 to 1.794 m at full duration. The 5.5% original-dev improvement missed the 10% promotion gate for 144 epochs. See the report on `odometry/long-budget`.
## Training throughput, 2026-11-18

- Predeclared matched D0 timing pilots, a global-batch-matched H100 strong-scaling pilot, and three-seed 36-epoch validation in `configs/experiments.json`. Timing uses steady-state train plus development replay and records startup separately.
- The unoptimized GPU-5 control took **103.02 s per epoch** (median of epochs 2–3). Training waited **44.13 s per epoch** on the host for input batches. Matched pilots use the same D0 manifest and private local read-only data views.
- The branch preserves the original model/trainer defaults. Opt-in paths add chunked matrix and affine-prefix scans, preloaded rows, batched causal development replay, channels-last convolutions, BF16/TF32, fused AdamW, deferred loss checks, and a compiled-correlation probe. CPU regressions cover the scan's output/state/gradient parity and uneven-length batched replay. CUDA GRU checkpoint regression passed before the new replay test.
- GPU 5 is running the timing pilots. A detached supervisor in `results/loop/throughput-local/supervisor.py` runs the fastest eligible pilot's 36-epoch recipe at seeds 217/218/219. Full replay evaluation and multi-GPU scaling remain pending.
- The matched matrix-scan pilot took **12.935 s/epoch (7.96×)**. The matched prefix-scan pilot took **7.04 s/epoch (14.63×)** and held the same 244 windows and 122 optimizer updates per epoch. Prefix startup was 7.87 s, and peak PyTorch GPU allocation was 2.13 GiB. Steady-state figures are medians of epochs 2–3 on one H100. These are timing pilots. Their one-seed checkpoint scores do not decide accuracy.
- Dev and 30 s proxy-validation replays are queued after all three 36-epoch checkpoints, using `odometry_eval.py --cache-dir` to isolate the evaluation cache on this shared machine.
- Compiled correlation reached **4.83 s/epoch (21.33×)** with the same 122 updates and 244 windows. Its cold epoch took 75.52 s, including compilation in training and replay. The cache-reusing 36-epoch run's first epoch took 8.26 s. The uncompiled batch-4 pilot took 4.91 s/epoch with 61 updates and 244 windows, so the predeclared timing rule advanced `B-speed-compiled-x3`.

### Strong scaling

- `P-speed-ddp` holds the batch at four globally and uses the same 244 windows and 61 optimizer updates at every H100 count. The reported distributed phase times use the slowest rank, with per-rank timing and peak allocation recorded in metrics.
- The 1-H100 GPU 7 reference finished its three epochs. Trainer startup was 6.08 s, first epoch 5.06 s, and steady-state epoch 4.20 s (3.78 s training and 0.42 s replay). The loader accounted for 0.26 s of the training phase. GPU 5 and GPU 7 share the same NUMA node and a direct NVLink path.
- The 2-H100 test is queued behind GPU 5's three-seed validation and replay jobs. All 14 regressions passed on GPU 7.

### Three-seed throughput validation

The compiled recipe and B-D0 control each finished 36 epochs at 244 windows and 122 optimizer updates per epoch. Full replays on the best checkpoint use mean unaligned ATE in metres.

| Replay | B-D0 mean | Compiled mean | Relative change |
| --- | ---: | ---: | ---: |
| Dev | 1.09497 | 1.09053 | −0.40% |
| Dev ordinary motion | 0.92147 | 0.90610 | −1.67% |
| Proxy validation, first 30 s | 1.27647 | 1.25870 | −1.39% |

Both predeclared dev tolerances passed and the independent proxy check also improved. Compiled dev scores for seeds 217/218/219 were 1.0900/1.0609/1.1207 m. Ordinary-motion scores were 0.8997/0.8531/0.9655 m. Proxy 30 s scores were 1.2692/1.2264/1.2805 m. Backward/lateral dev was 2.1973 m versus 2.1359 m for the control (+2.88%).

The initial 2-GPU launch failed before training with CUDA error 802 during NCCL NVLink SHARP multicast initialization. The retry and the queued 4-GPU run disable NVLS through `NCCL_NVLS_ENABLE=0` for the benchmark processes.

The two-H100 retry completed using NCCL point-to-point communication. Median epoch time fell from 4.20 to 2.48 s (1.69×, 84.7% scaling efficiency); training fell from 3.78 to 2.27 s and replay from 0.42 to 0.21 s. Warm input wait fell from 0.26 to 0.17 s. Trainer startup rose from 6.08 to 9.91 s, while first-epoch time fell from 5.06 to 3.28 s. The two-GPU run uses 4.96 GPU-seconds per warm epoch versus 4.20 on one GPU. Both runs scored the same 14 dev replays and preserved all 183 planned updates over the three epochs, with one-seed timing-pilot scores of 1.459265 and 1.458970 m.

A separate eight-step GPU-resident profile of the eager batch-four SSM identified kernel dispatch and tensor copies alongside convolution backward. CUDA launches consumed 19.5% of attributed CPU self time across 26,848 calls. Copies and convolution backward accounted for 20.5% and 13.5% of attributed CUDA self time. Multiple ranks repeat setup, data preparation and optimizer operations, then synchronize on each step. The timing does not attribute the scaling gap to an individual distributed operation.

For every seed in the full compiled validation, the control and candidate had matching data-manifest digests, exposure accounting at every epoch, and all 4,392 planned optimizer updates.

The four-H100 retry setup completed on GPUs 2, 3, 5 and 7 after the campaign jobs finished. All three hardware counts used the same window exposure, 183 optimizer steps and 14 development replays per epoch. Timing pilots used seed 217 only.

| H100s | Startup (s) | First epoch (s) | Warm train (s) | Warm replay (s) | Warm epoch (s) | Speedup | GPU-s per warm epoch |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 6.08 | 5.06 | 3.78 | 0.42 | 4.20 | 1.00× | 4.20 |
| 2 | 9.91 | 3.28 | 2.27 | 0.21 | 2.48 | 1.69× | 4.96 |
| 4 | 12.53 | 2.64 | 1.585 | 0.15 | 1.735 | 2.42× | 6.94 |

Four ranks reached 60.5% scaling efficiency and consumed 65.2% more GPU-seconds per warm epoch than one rank. Four ranks use 1.10 GiB of peak PyTorch allocation per H100 versus 4.21 GiB on one H100. Warm loader wait was 0.11 s at four ranks, with 1.585 s of total warm training. Best selection scores were 1.459265, 1.458970 and 1.459903 m at 1, 2 and 4 ranks. Full accuracy conclusions use the 36-epoch three-seed comparison above. Both distributed runs used NCCL P2P with NVLS disabled.
### 2026-11-18 — Hyperparameter sweep restart

- Resumed the eight `hp1` LR-screen runs from their complete epoch-1/2 checkpoints. The scheduler uses four concurrent slots on H100 GPU 4. All eight retain their original run directories and per-run caches.
- Declared the 12-epoch paired screen and 36-epoch three-seed promotion rule in `configs/experiments.json`. Replaced the inactive 6 s horizons in two 64-frame probes before launching them. The 128-frame probe retains 6 s.
- Queued the remaining screen, promotion, and full dev and 30 s proxy-validation replays. See `results/loop/hp-scheduler-rung0.log` and `results/loop/hp-sweep-resume.log` in this worktree for status.
### 2026-11-18 — Fast hyperparameter sweep transfer

- The three-seed compiled recipe cleared the throughput gate in full replays. Mean unaligned ATE was 1.0905 m vs 1.0950 m on dev, 0.9061 m vs 0.9215 m on ordinary dev flights, and 1.2587 m vs 1.2765 m on 30 s proxy validation. GPU 5 measured 4.83 s per warm epoch for the compiled recipe.
- The eight original `hp1` jobs finish on GPU 4. A separate worktree, tag `hpfast`, and paired fast base isolate all screening, promotion, and evaluation. Each fast run has its own read-only local shard view and local compiler caches. The optimizer applies weight decay and gradient-clip trial overrides while preserving the fast baseline defaults.
- GPU 4 will check the base and longest-window probe for one epoch before starting the full fast sweep. If either smoke test fails, the original slow sweep takes over. Final 36-epoch replays compare qualifiers to both three-seed controls, compiled and original B-D0.
## EKF fusion (2026-11-18)

- **Fixed-covariance B-D0 screen failed the development gate.** Used the frozen best checkpoints for seeds 217/218/219. CPU-only tuning compared 16 settings on 32 crops from 16 native campaign training parents, balanced across catalog and motion regime. The nine-state filter estimates position, velocity and gravity using gyro attitude. Training selected acceleration sigma 0.20 m/s², zero gravity walk and velocity sigmas [0.200, 0.142, 0.121] m/s. Train mean unaligned ATE was 1.8391 m direct and 1.8033 m fused.
- Three-seed mean unaligned ATE for the frozen setting:

  | Evaluation | Direct (m) | EKF (m) | Change |
  | --- | ---: | ---: | ---: |
  | Development | 1.0950 | 1.1294 | +3.15% |
  | Development ordinary | 0.9215 | 1.0006 | +8.59% |
  | Development yaw flight (two crops) | 2.1359 | 1.9020 | −10.95% |
  | Proxy validation, 30 s (69 replays) | 1.2765 | 1.2534 | −1.81% |
  | Campaign development, 30 s (120 replays) | 1.3534 | 1.3758 | +1.66% |
  | Campaign ProcTHOR, 30 s | 1.4914 | 1.4967 | +0.35% |
  | Campaign HSSD, 30 s | 1.2153 | 1.2550 | +3.27% |

- Dev ATE regressed in all three seeds. The improvement on the single dev yaw parent did not repeat on the campaign backward/lateral subset (3.4732 → 3.5102 m). Both dev gates failed, so uncertainty training and GPU allocation were deferred. Reserved test and confirmation stayed unopened.
- The CPU direct controls match the stored B-series results within 0.00023 m on every evaluated replay and seed. The proxy run used the same 69 replay files as that reference. The [summary](../results/eval/ekf-fixed/summary.json) records the full grid, frozen checkpoint fingerprints, per-seed summaries and scene-paired differences. Per-replay results are in the ignored `results/loop/ekf-fixed-v1/` directory. CPU regression suite had 15 passes and one CUDA-only skip, including the new causal prefix check.
## 2026-11-18 — Causal iterative refinement

- Screened one and three shared inertial updates (K=1 and K=3) on frozen B-D0-ssm-x3 heads, paired on seeds 217/218/219. Fitted on teacher-full train only and selected among eight epochs on dev. Refiner initialization, sampled windows and optimizer were matched across both arms. K=0 replays reproduced archived B-D0 results to their 4-decimal reporting precision. The proxy manifest supplies 69 nominal replays, matching the archived evaluator.
- Mean unaligned ATE (m), averaged over the three seeds

  | Replay | K=0 | K=1 | K=3 |
  | --- | ---: | ---: | ---: |
  | Dev | 1.0950 | 1.0816 | 1.0783 |
  | Dev ordinary | 0.9215 | 0.9056 | 0.9006 |
  | Proxy-val 30 s | 1.2765 | 1.2711 | 1.2694 |
  | Campaign-dev 30 s | 1.3534 | 1.3511 | 1.3512 |
  | Campaign-dev 30 s, ProcTHOR | 1.4914 | 1.4911 | 1.4924 |
  | Campaign-dev 30 s, HSSD | 1.2153 | 1.2109 | 1.2100 |

- K=3 improved dev by 1.52%, below the predeclared 10% threshold, and ordinary dev by 2.26%. The extra iterations gained 0.0032 m over K=1 on dev, and the campaign-dev means were within 0.0002 m of each other. Keep refinement opt-in. Reserved and confirmation test splits stayed unscored. Per-seed results are in `results/eval/refinement/summary.json`.
- The inertial C99 kernel matched PyTorch within 2.98e-8 m/s on a 600-frame seed-217 dev replay for both iteration counts, on the host and after compilation to WASI. Peak Wasmtime fuel for the isolated refinement step was 229,423 for K=1 and 561,403 for K=3. The refiner has 14,947 parameters in both arms. The normal CUDA checkpoint replay matched the cached-head replay on the checked flight within 5e-8 m ATE. The complete CPU head differed by about 2e-5 m ATE on that flight for all three arms, including the control.
- All 17 tests passed, and a one-epoch CUDA smoke with both the inertial and correlation residuals completed. Disabled inference was bit-identical to the base branch for all five heads on the CPU fixture. Correlation coverage is limited to lookup, causality and training smoke checks. The pilot setup needed a pre-fit restart to cast float64 shard rotations for the training loss. The parity harness needed the generated-header include path and explicit library unload for NFS cleanup.
## 2026-11-18 attitude correction
- Declared A-D0-ssm-x3 versus the three B-D0-ssm-x3 seeds before attitude results. A causal, zero-initialized head estimates residual body-axis gyro bias, bounded to ±0.12 rad/s per axis. It corrects the attitude used for vehicle velocity and camera lever-arm integration. The existing gyro-warped inputs and body velocity targets are preserved. The head learns through the camera displacement loss.
- GPU regression suite passed (14 tests), including cancellation of synthetic yaw drift, chunk-boundary parity, and finite nonzero gradients from the displacement loss. Seeds 217/218/219 launched on GPU 6 at the 36-epoch budget. Native-campaign dev oracle analysis started on CPU.
- Campaign-dev attitude oracle (120 replays) used truth body velocity and raw archive rotations. At 30 s/full duration, ATE was 0.530/0.967 m with the current gyro attitude, 0.490/0.909 m with tilt corrected, and 0.144/0.209 m with yaw corrected. True attitude reduced the floor to 0.0001 m. Mean absolute yaw drift was 20.27° by 30 s on the 60 static starts, versus 5.65° for tilt.
- A separately declared calibration diagnostic held true velocity fixed and compared the prepared rolling-calibration attitude with raw gyro integration. Raw gyro reduced 30 s/full ATE to 0.478/0.783 m (about 10%/19% lower). Rolling calibration accounts for part of the drift. The remaining error is larger than that of the yaw-corrected oracle. The diagnostics used campaign-dev only.
- Prepared the conditional hybrid comparison. It uses the exact same frozen B-D0 velocities for the raw, visual, learned, and hybrid attitude arms. An accepted visual interval supplies the endpoint correction once, with the hybrid trajectory's previous anchor as the reference. The evaluator requires the visual dev pass and all three learned epoch-36 checkpoints. It consumes dev and 30 s campaign-dev artifacts only. CPU coverage verified the re-anchor's causal behavior.

## Native training-data coverage, 2026-11-18

The 592 successful native train parents match both prepared crops and the N2 roster exactly by audited flight ID, scene, catalog, regime and parent SHA. They cover 256 scenes and 29,460 configured seconds. ProcTHOR contributes 394 parents, including 110 independent-yaw flights. HSSD Train125 contributes 198, including 45 independent-yaw flights. Five audits flag darkness and five flag low texture. All coverage calculations use training data.

A usable backward or lateral window has at least seven corresponding labels over the 64 scored frames after 32 burn-in frames. The uncropped native bank has 160 backward-eligible parents with 54,876 candidate starts and 316 lateral-eligible parents with 98,929 candidate starts. Candidate starts overlap within flights. All 155 independent-yaw parents contain usable windows of both kinds. In the exact N2 plans across 36 epochs and seeds 217/218/219, native campaign records supply 81.74% of backward draws and 87.37% of lateral draws. The seeds cover 304/307/308 distinct native hard-motion parents respectively.

| Early support within 1 s | ProcTHOR scenes | HSSD Train125 scenes |
| --- | ---: | ---: |
| Backward, uncropped start | 49 | 23 |
| Lateral, uncropped start | 2 | 0 |
| Backward, 5 s moving crop | 79 | 37 |
| Lateral, 5 s moving crop | 71 | 39 |

At the exact uncropped start, only 15 parents have an eligible backward window and none have an eligible lateral window. Broad conversion of hard proxy draws or broad new generation would address a bank that already has extensive mid-flight native coverage.

The predeclared `N2-early-native-x3` changes the placement of existing native hard draws. At least 25% of draws in each supported kind, catalog and crop stratum start within the first second of that crop. Supported strata have at least 12 eligible training scenes. Each seed and epoch preserves the original draw order, kind, domain, catalog and crop at every slot and preserves all untargeted windows. The six supported strata met their quota for all 108 CPU-replayed epoch plans. Retargeting replaced 411/414/405 of the 8,784 draws for seeds 217/218/219 using 144/143/139 distinct replacement parents. The resulting early windows included 148/148/147 distinct native parents. Near-crop native backward draws increased from 229 to 992 across all seeds, and near-crop lateral draws increased from 45 to 512 using the moving crop.

The comparison uses the original N2 numerical recipe and control checkpoints, the identical manifest, 36 epochs, 244 windows per epoch and 4,392 optimizer updates. The primary gate is at least 10% lower dev mean unaligned ATE across the three paired seeds, with no more than 5% regression on ordinary dev or on either dev start group. Report 30 s proxy-val and both 30 s and full campaign dev, including separate ProcTHOR/HSSD, static/moving and backward/lateral rows. The reserved test stays sealed.

For the remaining raw-lateral gap, a targeted train-only generation pilot would use 16 already validated training scenes in each catalog, two opposite lateral yaw offsets per scene, 30 s durations and 0.2 s initial holds. Freeze IDs, seeds, directions and generator settings before rendering. Require label-only support in at least 12 distinct scenes per catalog within 1 s of the uncropped start after burn-in, with both lateral directions represented and the existing finite-truth and integration checks. Existing 30 s archive sizes imply about 7.6 GiB for the 64 pilot flights, before prepared shards. A successful bank would fill only the absent raw-lateral training slots in a separately declared matched-budget arm, with the feasible resample arm as the reference. The generation pilot remains a proposal.

The local queue stages hardlinks to the 1,770 training and 14 development records in the frozen N2 manifest. The three training commands were dry-run checked, and the queue checks device occupancy before starting. Source shard storage is approximately 21 GiB and the three checkpoint trees should add about 2.9 GiB. Recent control epochs took 113–118 s by median across seeds, implying about 68–71 minutes per 36-epoch seed or 3.4–3.6 GPU-hours total before evaluation. The queue awaits released GPU slots.

## 2026-11-19 — Provided OpenVINS baseline and visual gyro-bias attitude (branch odometry/provided-openvins)

**Measured.** All guests run by the pinned upstream evaluator (jonas-eschmann/viobench @ 9b1b079, `wasm_eval.py`),
mean unaligned ATE; public = 10 x 60 s ProcTHOR-Train-1 flights (conta-shards/viobench-public@eecdfdf); campaign dev =
60 flights x crops 0/5 s (fresh-recording crops, 5 s crop files made by `wasm_eval.py crop`). Missing estimates count as
the origin (harness rule); zero filled frames everywhere. The pinned evaluator reproduces the submitted result exactly
(1.996 m, peak 1,074,756,366). Scores in results/eval/provided-comparison/.

| Guest (sha256 prefix) | Public | Campaign 30 s / full | Campaign median | >5 m | Peak fuel |
| --- | ---: | ---: | ---: | ---: | ---: |
| Submitted B-D0 s217 (844f358b) | 1.996 | 1.324 / 1.843 | 1.321 | 6 | 1.075e9 |
| Provided OpenVINS, unchanged (c6cd96bc) | **1.108** (median 0.923) | 6.714 / 32.642 | 1.112 | 27 | 4.350e9 |
| B-D0 s217 + kf_grid (8 in candidates/bd0-217-kfgrid) | 1.492 | 1.276 / 1.642 | 1.281 | 4 | 1.643e9 |
| **N2 s218 + kf_grid (089559db)** | 1.292 | **0.927 / 1.146** | **0.888** | 3 | 1.643e9 |
| N2 s218 + kf_grid gated (cc3ae8f3) | 1.369 | 0.940 / 1.170 | 0.992 | 2 | 1.643e9 |

- OpenVINS build: unchanged source; two environment-only fixes were needed (the wasm runtime recipe inherited the
  cross-compiler CC when invoked from the example's CMake, so it is run first on its own; NFS-dated venv files made
  ninja loop "still dirty", fixed by building on /dev/shm and backdating). Its own 7 tests pass. Initializes at
  0.95-3.75 s on public. On campaign it has excellent medians (HSSD 0.62 m) but late moving-start initialization and
  divergences (worst 2232 m), so its mean is unusable there. Not comparable to its README's 0.849 m median on eight
  120 s recordings (median vs mean, different roster).
- PyTorch public replay (prepared path, parity with the submitted wasm exact at 1.996): B-D0 3 seeds mean 2.092, N2 3 seeds
  1.780; true velocity through our deployed attitude 1.512 (vs 0.407 on original dev) — attitude was the binding error.
- Frozen-velocity attitude ablation (attitude_bias.py; arms fixed in its docstring before running; 6 models x flights):
  public 1.936 -> 1.383 (kf_grid) vs oracle bias 1.289; campaign full 1.631 -> 1.355 vs oracle 1.332; no subset regresses;
  backward/lateral unchanged (velocity-limited). The earlier visual correction (attitude nudges, no bias state) and the
  original strict-gate measurement (kf: 10-18 of 119 windows accepted) do little; grid support (100-112 accepted) is what
  matters. static08 alone gives ~-15% on public. A first static08 version was non-causal (applied the 0.8 s window bias
  from frame 1); fixed to re-integrate history at the decision frame; effect tiny.
- C++/Wasm port (odometry/deploy-kfgrid, export.py --kf-grid-opencv, wasm OpenCV 4.12 from the pinned runtime). One
  porting bug found and fixed (RANSAC mask passed into recoverPose). Remaining Python/Wasm differences come from KLT
  floating point (wasm SIMD vs x86) flipping accept/reject gates (traced window by window); a 3-sigma innovation gate
  restores parity (public 1.369 vs Python 1.385) but costs accuracy, so the ungated build is the candidate.
- Mean ATE decisions only; the public set shares one scene that is in N2's (and campaign) training, so campaign dev is
  the stronger evidence. Proxy-validation raw archives are unavailable here, so the attitude path was not checked there.
## 2026-11-18 deploy workstream

- Completed the opt-in C++17/VIOBench WASM port of the existing B-D0 SSM. Predeclared the protocol in `a4f13f9`. The separate visual-motion checkout retains its compact EMA work.
- Seeds 217/218/219 reproduced **1.0535 / 1.1202 / 1.1112 m** mean unaligned ATE on the 14 prepared dev replays per seed. C++ agreed with PyTorch to 0.626 µm/s per velocity component and 0.418 µm in trajectory position.
- Raw replay used two campaign-dev parents and both crop origins per parent because the original dev archives were unavailable here. Across all seeds it returned 6,600 complete frames, 0.6587 m mean unaligned WASM ATE and a 0.122 µm maximum host–WASM position separation. Pixels and IMU matched Python exactly. Peak was **1,074,754,835 fuel/frame**, 63.5× the historical EMA on its separate roster. FP32 B-D0 is a deployment parity reference. Its CNN accounts for 354.34 M of 356.20 M counted MACs/frame.
- CPU verification passed. The reserved splits were preserved. [Reproduction](../native_odometry/README.md) · [Per-replay results](../results/eval/native-deploy/b-d0-cpp-fp32.json)

### Convolution SIMD fuel pilot

- Predeclared and screened the original 4×16 tile and two 8×32 SIMD128 variants on seed 217. The tile with two sequential K iterations per loop won the synthetic screen at 861,235,039 peak fuel and advanced to raw replay. The exporter retains the default 4×16 and explicit scalar builds.
- The three-seed matched raw replay reproduced all 12 archived control peaks. The selected kernel reduced peak fuel from **1,074,754,835 to 861,235,415 (19.87%)**. Pose and twist were bitwise identical across all 6,600 frames. Mean unaligned ATE was 0.658690 m in both arms. No failed or filled frames. Init fuel matched on every replay.
- Reserved test data was preserved. [Pilot results](../results/eval/native-deploy/b-d0-cpp-fp32-convolution-pilot.json)

## 2026-11-19 approach survey and OpenVINS/learned splice (branch `odometry/approaches`)

- Survey and ranked shortlist: [APPROACHES.md](../APPROACHES.md). Offline splice of saved guest outputs, arms predeclared in `approach_splice.py` (commit `9e688fc`) before scoring; results `results/eval/approaches/splice.json`.
- Predeclared arms fail: re-anchoring OpenVINS on learned odometry at init 32.64 → 32.48 m campaign (the IMU back-integration anchor is not the cause); permanent divergence switch 3.05 m (rule required < 1.2).
- Failure anatomy: late static init at a hover is followed 1-1.5 s later (smoother takeover) by a 6-25 m/s velocity transient, after which OpenVINS tracks again; early-init ProcTHOR 168-03/169-04 are linear runaways (411 m, 2232 m).
- Post hoc (decides nothing): per-frame increment gate (OpenVINS increment if within 0.3 m/s of B-D0, else B-D0) scores 1.376 m campaign (median 0.854; B-D0 1.843, OpenVINS 32.64, oracle-min 1.258), public 1.077 with B-D0 and 0.964 with N2-s218-gated (OpenVINS 1.108). Gates 0.5/1.0 m/s: 1.424/1.473.
- OpenVINS peak fuel is the 5 Hz keyframe solve (~2.6e9 every 4th frame vs 2-3e8 otherwise); amortizing the three smoother solves is the cheapest peak cut.
## Research completion: visual fusion and fuel, 2026-11-19

Completed historical B-D0 visual-direction guest scoring (public1.491581→1.360556m; campaignfull1.642426→1.380669m,120/120 andzero filling). Staged6r+SIMDk2 measured120 campaign resets at1.642433m/1.130544B peakfuel, public1.491599m/987.812M. Source snapshot rebuilt byte-identically; actual independently shortened600-frame guest matches full emitted pose/twist prefix exactly. Found two historical C++/Python semantic mismatches (recoverPose input mask; direction acceptance) and historical host.so excludes visual macros. Separately named corrected traced N2s218 public smoke improves1.279878→1.086775m but fails Python/Wasm attitude parity(8.7–27deg); explicit nativeOpenCV4.12/Wasm delta0.051118m. No three-seed promotion or submission qualification; originaldev/proxy raw guards unavailable. Preserve all old measured results; FUSION_COMPLETION.md and results/eval/fusion-completion contain hashes, exact rosters, negatives, groups and reproducible commands.

## Newest trained input model C++/Wasm, 2026-11-19

Built all3 RA-N2-kfgrid-x3 best-EMA checkpoints with the complete changed-input path: gyro/bias/subpacket features, causal startup-history reconstruction, rewarped images/masks and integration. Canonical seed217 SHA8b05b203 scores actual official-Wasm public0.887995m and full campaign1.005868m, all130replays114000frames zero filled; peak1,658,013,194. Matching public improves10/10; campaign improves96/120 against submitted B-D0, retains24regressions. Corrected C++ ROI corner borders to match independent Python slices; OpenCV5.1 isolated to match training version. All3ABI checks and12Python regressions pass; sensor-only Python stream/batch inputs match bitwise over1200frames;600-frame actual guest prefix matches exactly. Strict visual-state and long native/Wasm parity still fail (0.422m max position on one60-second sample), so package is experimental and no submission is promoted. Earlier variants/logs preserved, no threshold tuning/test scoring/push/submission. See NEWEST_MODEL_WASM.md and results/eval/new-model-wasm.

## 2026-11-19 — Finish training queues and input-attitude comparison

All prior bounded queues are accounted for: fast HP50/50, original slow HP8/8, early-native3/3, throughput11/11, 72-epoch3/3, and original learned-attitude3/3 completed. Early resampling fails (dev0.9334→1.0284; campaignfull1.3906→1.5163). HPburn16 improves dev only1.3% versus its compiled control; HPlr0.001 regresses. No fresh sweep was started.

Finished the eight missing predeclared RA input-attitude trainings, reusing the original rolling seed217 after exact trainer/model/data-source and manifest identity checks. All9 runs completed36 epochs/4,392updates. The native-kfgrid data derivation's original OpenCV polynomial-solver crash is preserved; a separately named runtime-repaired path rejects degenerate essential/pose solves as unavailable visual measurements. No thresholds or budgets changed.

Three-seed common-attitude campaignfull: rolling1.1077, static08-input0.9919 (−10.46%), runtime-repaired kfgrid-input0.9724 (−12.22%). Both pass the original experimental gate and improve each seed, ordinary motion and both crop groups. Own-attitude dev/ordinary: rolling0.9157/0.9874, static08 0.7963/0.8163, kfgrid0.9217/0.9377. Own campaign30/full: rolling0.9911/1.3751, static08 0.8786/1.1548, kfgrid0.8131/0.9724. Own public60:1.7423/1.2832/1.0389, respectively. Proxy30 regresses versus matched rolling (1.0995→1.1750/1.1343), retained as negative evidence. Campaign60 subset has30 records/23parents/14scenes; it is not the120-record variable-duration population.

These are reconstructed prepared-input diagnostics; original-dev/proxy raw archives are unavailable, and the complete changed-input C++/Wasm path does not exist. Existing kf_grid deployment changes integration only, retaining rolling network inputs. No new deployment qualified; peak guest fuel, ABI initialization/completion/filling and raw parity remain unmeasured for these input policies. Existing15 odometry tests passed including CUDA checkpoint; three degenerate-geometry/causal-prefix regressions, actual rolling input identity/derived prefix checks, and the all-policy roster contract passed. All736,407 offline frames per policy are finite. Reports, per-flight/seed/parent/scene breakdowns, gate decisions and artifact hashes: `TRAINING_COMPLETION.md` and `results/eval/training-finish/`. No reserved split, push or submission. GPUs0/1 and unrelated processes untouched.

## 2026-11-19 — Research completion audit of provided baseline

Recovered completed actual pinned OpenVINS Wasm results from odometry/provided-openvins023198d, verified source9b1b079clean, artifactc6cd96bc, saved7passed checks, and reran five-step ABIcheck successfully. Recomputed saved trajectory means and SHA-verified all60campaign-dev parents; no new inference or reserved-test access. Public1.108m; campaign capped30/full6.714/32.642m; eligible60n30=84.191m; peak4.350Bfuel. All120campaign resets completed102000frames with zero filling,114initialized. Full per-flight/start/motion/catalog/scene/parent audit and diagnostic evidence are in BASELINE_FINISH_REPORT.md and results/eval/baseline-finish-audit.json. Single-seedN2+kfgrid promising but remains unqualified; original-dev/proxy raw unavailable. VINS-Mono side build had7passed/1failed checks and no matched roster replay; recorded as gated. All historical gates preserved.

## 2026-11-19 — Bounded research continuation completed

Pulled origin/main: already up to date; main unchanged. All original training queues accounted for and all nine declared input-attitude training runs complete. Static08/common-kf_grid input arms pass their predeclared shared-attitude campaign gates (1.1077→0.9919/0.9724m), but proxy30 regresses and complete changed-input C++ deployment does not exist. Historical visual-port parity claims are superseded: recoverPose mask and accepted-rotation semantics differ, historical host.so lacked visual flags, and separately corrected Python/native/Wasm parity still fails even at native/Wasm OpenCV4.12. Staged6r actual whole guest completed120campaign resets with zero filled, mean1.642433m and1,130,544,377peak fuel; actual600-frame causal emitted pose/twist prefix matches exactly. No candidate qualifies for submission. New user-supplied compact submission67b8a4d97b9f161b reports3.98m/16Mpeak/zero filled; source/binary not found in main or local scans. All continuation-owned workers exited. Full commands, hashes, regressions and component branches are in CONTINUATION_20261119.md; old reports preserved, no reserved tests, submission or push.
