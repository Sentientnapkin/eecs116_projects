# Fresh public VIOBench replay, 2026-11-19

The strongest existing learned Wasm with completed public **and** campaign measurements is N2 seed218 plus historical kf_grid integration attitude. Its prior campaign full mean is1.146m over120resets, distinct from the newer changed-input networks that have no complete Wasm port. Selection here is based on those existing cross-roster measurements, not a claim of final submission qualification.

This fresh replay executes the exact actual guest through the pinned official VIOBench evaluator on all ten public60-second archives, in a new output directory. No server submission or reserved test access occurred. All10flights completed12,000frames with **zero filled frames**.

| Actual guest | Mean unaligned public ATE | Mean first30s ATE | Peak whole-guest fuel/frame |
| --- | ---: | ---: | ---: |
| Submitted B-D0seed217, prior matched public replay | 1.995605m | 0.972853m | 1,074,756,366 |
| N2seed218+kf_grid, fresh public replay | **1.292480m** | **0.687337m** | **1,451,941,733** |

The fresh result is numerically identical to the previous same-guest result; every per-flight peak fuel also matches. Against the submitted B-D0 matched public score, mean error is35.23% lower and peak fuel35.09% higher. The public scene appears in expanded campaign training, so these public measurements are a development diagnostic, not independent generalization evidence.

Guest: `/data/backups/rganapa/Sebastian/baselines/candidates/n2-218-ungated/odometry.wasm`, SHA256 `089559dbb11ccc4ff5b912930497b725ddc39d2344b794521db9d19cfd849915`. Evaluator source is clean at `9b1b07906aff5a3e6f00155e7aecf967d90aa960`. Every archive SHA and every flight score are retained in `results/eval/public-best-fresh-20261119.json`. Ground truth enters scoring only.

Qualification remains limited by the documented historical visual-port Python/native/Wasm parity differences. The corrected traced direction-fusion guest has a lower public-only score1.086775m, but failed parity and lacks the full campaign comparison. New kf_grid-input training reaches1.038871m public /0.972369m campaign full in reconstructed-input diagnostics, but its full preprocessing/inference path is not implemented in C++/Wasm. These are distinct artifacts and evidence types; none is silently substituted for this guest.

Reproduce from this worktree's `research` directory, choosing a new output directory each time:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' \
TMPDIR=/dev/shm/sebastian-vio/tmp \
/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python -B \
  public_best_replay.py --out results/loop/public-best-fresh-new
```

The initial wrapper supplied a relative output path while changing the evaluator's working directory, placing reports in nested folders. The original reports were preserved and linked into the expected layout, then scored without repeating or changing inference. The wrapper now resolves output paths before launching, and `--score-existing` validates guest/evaluator/archive identities before read-only rescoring. No missing report or failed flight was excluded from the mean.
