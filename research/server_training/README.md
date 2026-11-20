# N3 server-regime pilot

This local pipeline uses 200 already generated raw-fast episodes excluded from selected171, with 100 static and 100 moving starts. Every training scene must occur in the original campaign's train roster; dev/test/clean scenes and selected171 episode IDs are refused. The 70 selected171 clean/dev flights form the final heldout evaluation. Their scenes do not overlap the added training scenes. `data_audit.json` records the realized split check.

Preprocessing reproduces N2's `kf_grid_native` training policy: original rolling input features followed by native 320×240 attitude estimation and `input_attitude.derive` with external attitude/bias. It uses observed camera/IMU only. True velocity and pose enter labels and scoring. Mid-start archives are already cropped into their own camera-0 gauge, so no extra crop is added. All prepared shards are content addressed and raw archive checksums are verified.

Run from `research/` with the teacher environment:

```sh
python -m server_training.prepare --config configs/server_train_pool.json --workers 24
python -m server_training.pilot --config configs/server_train_pool.json --launch
# Once all six runs finish, use separate GPUs for the three seed evaluations:
CUDA_VISIBLE_DEVICES=1 python -m server_training.evaluate --seed 217
CUDA_VISIBLE_DEVICES=2 python -m server_training.evaluate --seed 218
CUDA_VISIBLE_DEVICES=3 python -m server_training.evaluate --seed 219
python -m server_training.evaluate --summarize
```

`run_pilot.py` runs that sequence automatically. All artifacts stay in `data/server-training/`; there are no remote writes. Training uses GPUs 1–6, one process per GPU, and four CPU cores per run. Control and treatment warm-start from each seed's own frozen N2 checkpoint, restart optimizer/EMA, and take the same 244 windows per epoch for 12 epochs. Treatment samples baseline and server domains at 50/50. Control continues with baseline data. The final epoch EMA is fixed before scores; original dev metrics are diagnostics, and clean/dev heldout is evaluated once. This tests a targeted warm-start T0 adaptation rather than claiming a from-scratch architecture comparison.

The pilot gate is >=10% three-seed raw mean ATE improvement over frozen N2, every seed improving, with original-dev regression <=5%. The equal-update control distinguishes server data benefit from merely training longer. Final results are research measurements, not a validated Wasm release. The original frozen N2 artifacts are unchanged. `configs/experiments.json` carries the pilot declaration.

Training adds optional `--init-weights` to `odometry_train.py`; its SHA is part of run identity. Repeat the option with `--resume` to validate identity before checkpoint restore. Optional `training.preload_threads` bounds shard decompression concurrency; the default preserves prior behavior. Baseline paths refer to the preserved training-completion worktree; missing artifacts cause a clear error rather than silently fetching or regenerating a different baseline.
