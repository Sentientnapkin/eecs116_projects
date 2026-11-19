# Provided VIOBench baseline: completed-work audit, 2026-11-19

This report recovers the completed baseline work at `odometry/provided-openvins` (`023198d`) and `odometry/openvins-provided-diag` (`b059d44`). The older session report and initial NFS build logs were stale. No new estimator, threshold search, training, submission, remote push, or reserved-test access was performed in this audit.

## Source, build and checks

The **actual provided** OpenVINS example is pinned to upstream commit `9b1b07906aff5a3e6f00155e7aecf967d90aa960`. The successful isolated build checkout is `/dev/shm/sebastian-vio/viobench`; `git status --short` is empty. The earlier `/data/backups/rganapa/Sebastian/viobench-provided-openvins` checkout contains preserved unsuccessful environment builds and should not be mistaken for the latest outcome.

Measured unchanged artifact: `/data/backups/rganapa/Sebastian/baselines/openvins-9b1b079/openvins.wasm`, **8,462,133 bytes**, SHA-256 **`c6cd96bcbadef6c098fc285a293bc8f3045032245d232b10be84d6423789da8e`**. The pinned runtime uses OpenCV 4.12.0 and wasi-sdk 34. Earlier environment failures were repaired by building runtime dependencies outside inherited WASI compiler variables and using local tmpfs to avoid NFS future timestamps. The saved final bundle log ends with a successful output artifact. No tracked estimator source changes are present.

Saved integration/math test log reports **7 passed in 60.88 s**. This audit reran `viobench check` on the exact artifact: **5 steps, check ok**, exit 0. The saved check log also contains a benign NFS temporary-directory cleanup warning after completion; no estimator failure occurred. Source confirms rotation-aware startup, gyro-compensated forward/backward tracking, direct keyframe tracking, a 2.4 s fixed-lag graph, three correlated hypotheses, and simulator-noise conversion. The README's 0.849 m median across eight 120 s recordings is an upstream claim on a different roster; its fuel median/p95 does not establish peak fuel.

## Independently checked matched results

`audit_provided_baseline.py` reads the saved *actual metered Wasm* reports and trajectories, recalculates direct first-camera position RMSE, verifies artifact hashes, verifies all 60 **campaign-dev** nominal-parent archive SHA-256 values against the dev manifest, and records all public/crop archive SHA-256 values. Every compared saved full score agreed with the pinned evaluator within1e-5 m. There were **no inference reruns** because the complete saved inference evidence exists.

Public is the same ten 60 s flights and 12,000 frames as the submitted B-D0 comparison; its only scene is ProcTHOR-Train-1, which appears in N2 training. Campaign dev is the same 120 resets (60 parents, 21 scenes: 6 ProcTHOR and 15 HSSD),102,000 frames. Each five-second crop resets both scoring origin and guest. The evaluator supplies the same calibrated IMU windows and first-camera conventions to every guest. All comparisons use equal-flight mean **unaligned** RMSE; no fitted alignment enters decisions. Missing output would be filled at origin by the pinned evaluator, but **all these runs completed every frame with zero filled frames**, so hold-last versus origin-fill has no numerical effect. Finite zero startup output is counted as output and is separately distinguished from filter initialization.

| Actual Wasm guest | Public30/60s mean(m) | Campaign capped30/full mean(m) | Campaign eligible60 mean(m),n=30 | Peak public/campaign fuel per frame |
|---|---:|---:|---:|---:|
| Submitted B-D0seed 217 |0.973/1.996|1.324/1.843|2.768|1,074,756,366/1,074,758,773|
| Provided OpenVINS unchanged |0.666/1.108|6.714/32.642|84.191|3,548,774,401/4,349,914,268|
| B-D0seed 217+kf_grid |0.911/1.492|1.276/1.642|2.480|1,451,941,431/1,643,004,112|
| N2seed 218+kf_grid |0.687/1.292|0.927/1.146|1.634|1,451,941,733/1,643,004,075|
| N2seed 218+kf_grid+innovation gate |0.702/1.369|0.940/1.170|1.635|1,452,891,385/1,643,393,244|

Capped30 uses the first 600 frames or the complete shorter crop, preserving historical inclusion of 25 s crops. Full uses each crop's entire available duration. Eligible60 uses exactly first1,200frames only on 30 resets with that much footage; it must not be compared to the120-reset full mean as a horizon change on identical populations. The audit additionally reports eligible30 on 83 resets. Historical displayed campaign30 values already match capped30-all 120; this audit adds explicit population counts rather than revising historical values. Every prefix uses the continuous full-run state with no reset at 30 s. Initialization ABI fuel for unchanged OpenVINS peaks at89,916,083 public / 89,916,023 campaign.

The B-D0 comparison hash is `844f358bc733508f440a36ab30632d997b18ff513b56866c02bd832402dcd56c`. All other exact hashes and per-flight values are in `results/eval/baseline-finish-audit.json`; repeated source data retain artifact and archive paths. The N2+kf rows are **single-seed completed deployment comparisons**, not qualified replacements. Three-seed qualification and original-dev/proxy guardrails remain required. The parent agent owns completion of matched remaining seeds and adaptations.

## OpenVINS robustness, initialization and dependence

| Campaign group | Resets | Capped30/full mean(m) | Initialized | Full ATE>5m |
|---|---:|---:|---:|---:|
| ProcTHOR |60|8.499/59.379|56|16|
| HSSD |60|4.929/5.904|58|11|
| Nominal crop0 |60|5.005/45.419|58|4|
| Crop5 |60|8.423/19.864|56|23|
| Manifest backward/lateral |10|3.757/4.601|9|2|
| Manifest ordinary |110|6.983/35.191|105|25|
| Measured initial speed<=0.05m/s |75|4.180/36.548|72|4|
| Measured initial speed>=0.20m/s |31|11.575/17.301|29|13|
| Intermediate initial speed |14|9.524/45.684|13|10|

Measured initial speed here is mean camera linear speed during the first 0.25 s, diagnostic ground truth used only after inference. Motion groups retain manifest full-crop backward >5% or lateral >10% labels; they are explicitly historical labels rather than horizon-specific recomputation. The JSON includes each scene and parent separately. The two crops share footage and parents; counts are not independent evidence, and six ProcTHOR scenes are a small scene population.

Public initialized 10/10, at 0.90–3.70 s **after first camera**, corresponding to printed absolute timestamps 0.945–3.745 s. Campaign initialized 114/120, at 0.90–24.55 s after first camera. No initialization log on six crops does not mean ABI failure: they still returned finite startup states. In learned-guest JSON, initialization counts are **null / not applicable**, because those guests do not emit OpenVINS initialization strings.

The mean is driven by actual divergence, not missing frames: worst unchanged flight `dev-ProcTHOR-Train-169-04` has 2,231.714 m full unaligned RMSE and estimated speed above 300 m/s while true speed remains below 0.404 m/s. Other failures arise later (`dev-ProcTHOR-Train-168-03`, 411.484 m full; its crop5, 488.852 m) or during delayed moving initialization. Their early prefixes and speed timeline are retained in the existing `baselines/runs/ovdiag/baseline_timeline.json`. Small medians cannot override those means.

The already-completed **separately named instrumented** `openvins_diag.wasm` gives 1.110 m public / 32.576 m campaign, close but **not bitwise identical** to unchanged 1.108 / 32.642 m. Instrumentation modifies numerical execution enough that its values must remain diagnostic. Its full patch and selected initialization/hypothesis logs are preserved here as `baseline-diagnostic-variant.patch` and `baseline-diagnostic-evidence.json`.

In that diagnostic worst-flight replay, both frontends initialize with gyro bias [-0.0823,-0.0193,0.0208] rad/s and later all three smoother hypotheses acquire large velocities, with zero active visual factors near the end. The EKF's velocity is then around 0.236 m/s while smoothers diverge. This supports investigation of initialization and visual-factor survival, **not a proven isolated cause** or a baseline modification. On delayed moving initialization `dev-106878858_174886965-00-crop5`, the diagnostic records 19.65 s delay and 107.192 m backward-integrated origin displacement, while later estimated speeds recover near realistic values. This demonstrates why good tracking after initialization cannot recover a wrong reset origin by itself. No threshold has been tuned against these flights.

## Other existing side baseline

VINS-Mono was built unchanged at the same pin in clean `/dev/shm/sebastian-vio/viobench-vins`. Artifact `baselines/vins-mono-9b1b079/vins_mono.wasm`, 6,714,426 bytes, SHA-256 `f368cf2c7301a15d6aaa6dab7b52ff6424711ecfe2e2e013ff97489dae30762f`. ABI check passed. Tests: **7 passed, 1 failed**; `test_noisy_tracking_after_hovering_turn[mild_settling]` gives translation RPE 0.23884 m versus 0.15 m bound (final drift 0.0996 m). No matched public/campaign replay output exists. It is a gated side experiment, not a completed accuracy baseline; no broad new evaluation was launched.

## Reproduction

From this worktree's `research` directory, use the isolated pinned venv and source:

```bash
export VIOBENCH_SRC=/dev/shm/sebastian-vio/viobench
export PYTHONPATH="$VIOBENCH_SRC"
export TMPDIR=/data/backups/rganapa/Sebastian/tmp
PY=/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python
# Original successful build recipes are preserved; they change environment, not estimator source.
bash /data/backups/rganapa/Sebastian/baselines/openvins-9b1b079/build_runtime.sh
bash /data/backups/rganapa/Sebastian/baselines/openvins-9b1b079/build.sh
# Original provided checks (existing seven-pass log retained):
cd "$VIOBENCH_SRC"
VIOBENCH_OPENVINS=/data/backups/rganapa/Sebastian/baselines/openvins-9b1b079/openvins.wasm "$PY" -m pytest tests/test_openvins.py tests/test_openvins_math.py
# Actual guest ABI check:
"$PY" -m viobench check /data/backups/rganapa/Sebastian/baselines/openvins-9b1b079/openvins.wasm
```

Original replay code lives in branch `odometry/openvins-provided-diag`, `research/wasm_eval.py`. It supports `crop`, `run`, `score`; exact archive lists and artifact paths are preserved in each `baselines/runs/{public,campaign}-openvins/guest.json`. For a new output directory, pass the unchanged artifact and that exact archive list to `wasm_eval.py run`, then `score`; do not overwrite old run directories. This audit is reproduced with:

```bash
cd /data/backups/rganapa/Sebastian/eecs116_projects/.codex-worktrees/baseline-finish/research
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "$PY" -B audit_provided_baseline.py
```

Original-dev 14 raw archives and raw proxy validation remain unavailable; no new path can be declared qualified from campaign/public alone. The compact `vio_c_v2.wasm` server result supplied by the user is a separate artifact/evidence stream, owned by the parent audit. Neither its hash nor server roster is substituted for these matched local measurements.
