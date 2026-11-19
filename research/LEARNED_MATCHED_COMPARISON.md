# Matched learned comparison, 2026-11-19

The completed learned-attitude A-D0 comparison fails the original dev and ordinary guardrail and worsens proxy validation. Its three-seed dev mean is 1.1440 m versus 1.0950 for B-D0; ordinary is 0.9811 versus 0.9215; proxy30 is 1.3249 versus 1.2765. Campaign30 is 1.3862 versus 1.3534 and full is 1.8204 versus 1.8706. Small full-duration improvement does not qualify it. Reports and source hashes are in `results/eval/provided-comparison/learned-completed-audit.json`.

N2 remains the strongest completed measured accuracy candidate at audit time. It remains unqualified by the unchanged 5% ordinary original-dev guardrail. N2 early-native runs and promoted fast hyperparameter finalists are still training; their incomplete selection scores do not replace completed full-replay comparisons. No decision criteria changed.

The N2 seed217/218/219 weights were exported with the existing C++17 FP32 deployment port unchanged, using its original SIMD4x16 kernel. Build and checkpoint hashes are in `results/eval/provided-comparison/learned-artifacts.json`. These artifacts are comparison artifacts, not approved submissions.

Commands from this worktree's `research/` (Python is `/data/backups/rganapa/Sebastian/venv-teacher/bin/python`):

```bash
DEPLOY=/data/backups/rganapa/Sebastian/eecs116_projects/.worktrees/deploy/research
MAIN=/data/backups/rganapa/Sebastian/eecs116_projects/research
SDK=/data/backups/rganapa/Sebastian/tmp/viobench-toolchain/wasi-sdk
python "$DEPLOY/native_odometry/export.py" "$MAIN/results/loop/N2-ssm-x3-gpu" "$MAIN/data/hub-cache/B-D0-ssm-x3-gpu/manifests/teacher-full.json" results/loop/provided-comparison/n2-217 --wasi-sdk "$SDK"
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' python learned_matched_replay.py results/loop/provided-comparison/n2-217 results/loop/provided-comparison/n2-public-217 --set public --metered --workers 4
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' python learned_matched_replay.py results/loop/provided-comparison/n2-217 results/loop/provided-comparison/n2-campaign-native-217 --set campaign-dev --workers 4
```

Repeat with the corresponding seed218 and219 run names and output directories. Submitted B-D0 control build is `$DEPLOY/results/loop/native-deploy/raw-217`, SHA256 `844f358bc733508f440a36ab30632d997b18ff513b56866c02bd832402dcd56c`; use that build with output names `bd0-public-217` and `bd0-campaign-native-217`.

Public evaluation executes the actual metered guest and its native counterpart on every frame, saves trajectories and per-frame fuel, and measures parity directly. Campaign replays currently execute the native counterpart; their results must be identified as native, with existing public whole-guest measurements shown separately. No fuel is inferred from MACs. Historical prepared campaign results and new raw scores are kept separately because prepared30 uses up to601 inclusive frames whereas raw30 has600 frames. Raw1200/600 prefix scores use the same continuous inference state. Each crop resets the guest and scoring origin. No truth enters inference.

Raw public archives are the exact cached ten flights under `/data/backups/rganapa/Sebastian/tmp/viobench-public-replay`, dataset revision `eecdfdf2502fa50c30bdde17a809d31cc2a9bb6b`. Their single ProcTHOR-Train-1 scene is included in expanded campaign training; public improvement is a development diagnostic. Campaign archive SHA256 values are validated against the dev-only manifest. Reserved tests are not accessed.
