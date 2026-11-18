# Overnight teacher research loop (started 2026-11-17 23:29)

## What runs unattended

| Process | Job | Log |
| --- | --- | --- |
| `research_loop.py` | Trains queued specs two at a time on MPS, writes `leaderboard.md`, mirrors this folder to `SentientNapkin/viobench-teacher-lab/loop`, replicates the best spec when idle. Stops starting runs at 08:30. | `loop/runner.log`, `results/loop/<name>.log` |
| `teacher_gen.py` | Simulates 60 s flights in about 270 unused scenes (ProcTHOR-Train 0–9, 46–161, 180–199, plus HSSD-Train at about 1 in 4; 15% independent-yaw), 3 passes with new seeds. | `data/gen-spool/gen.log` |
| `teacher_pool.py` | Gates each flight (≥2 m travel, no stall, ≥25% moving, not dark or textureless), prepares 0 s and 5 s crops with the base pipeline, and uploads content-addressed shards plus `manifests/gen-pool-v1.json` to `SentientNapkin/viobench-teacher-data`. | `data/gen-spool/pool.log` |
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
- 09:31 **Paused everything at the user's request** (compute moving elsewhere). Resumable: D0/D1/D2-ssm and ssm-att-nopatience from their last checkpoints via `./teacher_env.sh launch.py D0-ssm D1-ssm D2-ssm` (auto-resume); GRU pair, D1n/D2n, v4 and generation not started.
