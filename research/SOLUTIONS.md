# Solutions on main

All solution code is maintained on `main`. Earlier branch tips are archived as
`archive/2026-11-19/*` tags; local detached worktrees preserve checkpoints and generated assets.

| Work | Location | Status |
| --- | --- | --- |
| Learned velocity training and inference, including B-D0 and N2 | `odometry_models.py`, `odometry_train.py`, `odometry_eval.py`, `configs/experiments.json` | Completed comparisons retained |
| Causal attitude, startup and bias ablations | `orientation.py`, `input_attitude.py`, `attitude_bias.py` | Individual positive and negative results retained |
| Learned C++/Wasm guest and grid tracking | `native_odometry/` | Newest candidate frozen; strict backend parity remains unresolved |
| Staged fuel deployment | `native_odometry_staged/` | Separate measured variant |
| Actual provided OpenVINS baseline | `provided_baseline/` | Distinct from our upstream wrapper |
| Earlier upstream OpenVINS wrapper | `openvins_native/` | Historical separate experiment |
| Fusion and refinement | `vel_fusion.py`, `refine_c/` | Experimental; prior failed gates still apply |
| Older visual-motion screen and native student prototype | `visual_motion/` | Preserved independently of the newer training pipeline |
| Measured comparisons and failures | `results/eval/` | Includes per-flight reports; mean unaligned ATE remains the decision metric |

The frozen distribution is available locally at
`artifacts/n2-kfinputs-frozen/`; its hashes and relative paths are tracked in
`results/eval/new-model-wasm/current-package.json`. Binary packages, datasets,
checkpoints and feature caches are ignored rather than added to Git.

See [NEWEST_MODEL_WASM.md](NEWEST_MODEL_WASM.md) for the frozen artifact's measurements
and limitations, and [CONSOLIDATION.md](CONSOLIDATION.md) for preservation details.
No new training, replay, parity work, remote push or submission occurred during this cleanup.
