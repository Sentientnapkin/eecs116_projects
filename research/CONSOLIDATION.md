# Consolidation of all odometry branches into main (2026-11-19)

## Final organization

`main` is now the only local branch. The 17 former branch tips are preserved as
descriptive `archive/2026-11-19/*` tags, and their checkouts are detached archives.
Local internal checkouts live under ignored `.worktrees/` with descriptive names.
Ignored compatibility symlinks retain old absolute paths used by historical commands.
No remote branch was renamed or deleted and nothing was pushed.

All previously committed solution branches were already ancestors of main.
The remaining uncommitted visual-motion implementation and its measured JSON reports
are now preserved under `visual_motion/` and `results/eval/visual-motion/`.
Its older training modules are isolated to avoid overwriting the current pipeline.
See [the experiment README](visual_motion/README.md).

The frozen C++/Wasm distribution is available from this main checkout at
`research/artifacts/n2-kfinputs-frozen/` (ignored binary assets). Its tracked index is
`results/eval/new-model-wasm/current-package.json`; all source remains in Git.
The seed-217 Wasm SHA-256 is unchanged:
`8b05b203adc1f045b67df12399ee6b9e0caf28015b7d31678f5378968e2d60cf`.
The original frozen ZIP and its internal provenance remain byte-identical.
Further parity work remains stopped and prior qualification limitations still apply.

A pre-cleanup Git bundle and the original uncommitted visual-motion source are backed up
outside the repository at `../archive/main-consolidation-20261119/`.
Checkpoints, caches, raw data, untracked attitude dumps and original local changes were
preserved. Historical commit messages and immutable result identifiers were not rewritten.
The earlier sections below describe the prior merge and its verification, not new runs.

Every odometry and completion branch, plus the uncommitted work left in their worktrees, was merged
into one history. No result was changed. Mean unaligned ATE remains the only metric. No push, no
reserved-test scoring, no submission.

## What each line of work concluded

| Branch(es) | Solution | Verdict (3-seed unless noted) | Opt-in in code |
| --- | --- | --- | --- |
| `throughput`, `long-budget`, `hparam`, `hparam-fast` | Compiled training recipe, 72-epoch budget, hyperparameter search | 21.3x faster epochs, dev 1.095 -> 1.091; 72 epochs 1.030 (5.5%, misses the 10% trigger); HP finalists miss gate | recipe `B-speed-compiled-x3` |
| `data-coverage`, N1/N2 (`campaign`) | Native campaign data; early-window resampling | N2 0.933 dev / 1.007 campaign-30 s, ordinary-flight +9.2% (fails guardrail); resampling rejected | `n2-campaign-tiers` |
| `ekf` | Fixed EKF and uncertainty head | 1.095 -> 1.129, worse in every seed; rejected | `--ekf`, `model.uncertainty` |
| `refine` | Iterative refinement | 1.095 -> 1.078 (misses 10%); rejected | `model.refine_iters` |
| `attitude`, `attitude-fast`, `attitude-hybrid`, `retrain-attitude`, `bias-ablation` | Learned gyro-bias, hybrid, input-attitude retraining | learned bias 1.144 (worse); static08/kf_grid input arms pass campaign gate, regress proxy-30 s | `model.gyro_bias_correction`, `input_attitude.py` |
| `openvins`, `openvins-provided-diag`, `provided-openvins`, `provided-comparison` | Native/provided OpenVINS baselines | public 1.108, campaign mean 32.6 (median 1.1): unusable mean | `provided_baseline/`, `openvins_native/` |
| `approaches` | Survey and OpenVINS/learned splice | predeclared arms fail; post hoc gate 1.376 campaign (decides nothing) | `APPROACHES.md` |
| `vel-fusion`, `fuel`, `deploy*`, `codex/new-model-*`, `archive/2026-11-19/public-best-replay` | C++/Wasm deployment, SIMD, kf_grid visual attitude, direction fusion, staged fuel | FP32 port parity; SIMD -19.9% fuel; kf_grid N2 s218 public 1.292 / campaign 1.146 but **not parity-qualified** | `native_odometry/`, `native_odometry_staged/` |
| `codex/session-integration`, `baseline-finish`, `training-finish` | Audits and closure reports | see `CONTINUATION_20261119.md` | - |

## Conflict decisions (where branches touched the same code)

- `odometry_models.py` carries all of: compiled correlation, `refine_iters`, `uncertainty` and
  `gyro_bias_correction`. Combinations of refinement, uncertainty and gyro-bias raise explicitly.
- `odometry_train.py`: `make_optimizer` (with `fused_adamw`), `loss_fn(..., nll_weight, rotations)`
  (**attitude rotations must be passed by keyword**), batched `replay(..., return_attitude)`.
- `odometry_eval.py`: batched GPU replay kept; attitude-aware replay and `--ekf` added on top.
- `hp_search.py`: `command(..., overrides=None, recipe=..., local_source=...)`.
- `native_odometry/kf_grid.hpp`: the parity-audited version from `archive/2026-11-19/frozen-candidate`. The staged-fuel
  variant is preserved verbatim in `native_odometry_staged/` (identical to the `fuel` branch file).
- `attitude_bias.py`: the newest version (arms, `--root`) plus the degenerate-solve guard.
- `configs/experiments.json` is valid JSON (a text union had broken it); `RA-N2-kfgrid-x3.data` points
  at `retrain-attitude-data/`, not a worktree.
- Not committed: 130 per-flight attitude `.npz` dumps (37 MB, `results/eval/attitude-bias/*/attitudes/`).
  They stay in the `provided-openvins` worktree.

## Verification run on the merged tree

- `test_odometry.py` 32/32, `test_causal.py` 16/16, `test_attitude_degenerate.py` 3/3,
  `test_training_rosters.py` 1/1 (needs `data/` and `results/loop/training-finish`), `compileall` clean.
- Re-ran the merged `odometry_eval.py --set dev` on one H100 for six checkpoints: B-D0 1.054/1.120/1.111
  (mean **1.095**, ordinary 0.921), N2 1.028/0.791/0.981 (mean **0.933**, ordinary 1.007). Identical to
  the recorded values.
- Recomputed from saved JSON: N1 1.164, B-D2n 1.341, campaign-30 s B-D0 1.353 / N2 1.007; public Wasm
  1.9956 m over 10 flights; EKF ordinary +8.6%; long-budget 5.5%.
- Merged C++ FP32 host vs PyTorch, B-D0 seed 217 only (14 prepared dev replays; seeds 218/219 not re-run):
  ATE 1.0535247814 vs 1.0535247924, `passed: true`.
- **Not re-run:** Wasm builds (no wasi-sdk used), the kf_grid Python/C++/Wasm parity (documented failing in
  `KF_GRID_PARITY_REVIEW.md`), the pinned-evaluator public and campaign Wasm replays, OpenVINS.
