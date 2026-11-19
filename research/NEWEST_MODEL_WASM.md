# Frozen newest-model C++/Wasm candidate

Completed2026-11-19 on isolated branch `archive/2026-11-19/frozen-candidate`. The newest family is **RA-N2-kfgrid-x3**, the three completed36-epoch N2 runs trained with `kf_grid_native` inputs. Their selected best-EMA checkpoints were compiled without retraining or selecting seeds by public performance. Seed217 is the default;218/219 are also available. No submission, push, reserved-test measurement, paid infrastructure or unrelated-job interruption occurred.

## Package

Directory: `/data/backups/rganapa/Sebastian/eecs116_projects/research/artifacts/n2-kfinputs-frozen/package/`.

| File | Bytes | SHA256 |
| --- | ---: | --- |
| `vio_n2_kfinputs_s217.wasm` |10,614,678|`8b05b203adc1f045b67df12399ee6b9e0caf28015b7d31678f5378968e2d60cf`|
| `vio_n2_kfinputs_s218.wasm` |10,614,678|`e787620f5a5c64eb6655d930d2e0b69d393db870960d3e2df6f8c9ed8784e007`|
| `vio_n2_kfinputs_s219.wasm` |10,614,678|`0938f841b1eb0c14c8811b4a4c758ddac986321f4bde4dbd0cd82679b29c7e3b`|

These are standalone **C++17 native Wasm guests**, with1,286,355 FP32 parameters embedded. Python runs only the evaluator/reference. `manifest.json` and `SHA256SUMS` accompany the files. Canonical checkpoint SHA256: `113606c7b21f4f1b3b726f20036c3f7208d56f5bab5e129cf67fb520702f9bbc`. Full source/checkpoint/compiler identities are in `results/eval/new-model-wasm/artifacts.json`.

**Frozen at the user's request; further parity work stopped. Experimental: strict backend parity remains unresolved.** Seed217 above is the frozen candidate. All three binaries pass ABI checks; only seed217 has the full public/campaign measurements below. No three-seed Wasm accuracy mean is inferred from Python results. The files are usable benchmark artifacts, not automatically qualified submissions. Packaging preserves the existing binaries without rebuilding or changing their outputs.

## Complete input implementation

This goes beyond the old integration-only kf_grid guest. It retains rolling preprocessing as a parallel source of the quantized sufficient statistics used by training, then:

- Computes causal native-resolution grid/KLT rotations and three gyro-bias Kalman states, with the repaired Python essential/pose exception behavior, RANSAC input mask and unchanged acceptance gates.
- Rewrites gyro means, ordered subpacket gyro, bias and activation features while preserving acceleration/std/timing/availability fields.
- Reproduces the separately pooled startup-history reconstruction from `input_attitude.derive`, including its documented stored-increment approximation, and rewarps both historical images/masks using the trained policy's FP32-derived centered intrinsics.
- Runs the existing CNN/correlation/SSM and integrates its body velocities through the new attitude, preserving camera lever arm, first-camera origin and calibrated timestamps. It retains all received IMU rows up to the existing1024-row ABI bound.

The0.8-second startup updates history used by subsequent warps; past emitted poses/predictions are not rewritten. No truth, oracle inputs, scene identifier or future measurement enters inference. A read-only `input_features` export checks the same binary without trace logging. Both native `host.so` and Wasm compile the actual visual input path.

The exporter requires `--input-kf-grid` for the manifest's top-level `input_policy=kf_grid_native`. Its nested `sensor_config.policy` remains `rolling`, so checking only that field could silently export incorrect preprocessing. Old default paths and historical artifacts remain preserved.

## Build investigation and correction

Training used Python OpenCV5.1.0. The initial4.12 port failed long parity, so5.1.0 was pinned at source commit `e4f78fbcf1a773fbed69e14500e8b734963eb585` and built separately for native/Wasm. Installed environments were unchanged. OpenCV5 moved geometry/features APIs; the exporter handles these headers/libraries. The Wasm build initially failed in unused HarfBuzz font shaping because of WASI errno/thread-local declarations. Disabling that unused feature fixed the build; its failed log is retained. No upstream OpenCV algorithm source was patched.

A C++ grid-cell Mat ROI retains parent pixels during border filtering, whereas the Python NumPy slice is wrapped as an independent Mat. This selected different corners. Cloning each grid cell fixes that semantic difference. On the first affected public window, the old correction differs from Python by8.41e-5rad; the corrected value differs by7.37e-18rad. No thresholds were retuned. The exact patch and initial source hash are preserved in `grid-border-fix.patch`.

| Same seed217 actual Wasm variant | Public full ATE | Campaign full ATE | Max measured fuel/frame |
| --- | ---: | ---: | ---: |
| OpenCV5.1 initial parent-ROI grid |1.006927m|1.074409m|1,741,187,448|
| Corrected isolated-cell grid |**0.887995m**|**1.005868m**|**1,658,013,194**|

The4.12 provisional build is retained as a failed parity diagnostic. Earlier variants were not overwritten or silently relabeled.

## Actual official-evaluator results

Evaluator pin: clean VIOBench `9b1b07906aff5a3e6f00155e7aecf967d90aa960`. Metric: equal-flight **mean unaligned position RMSE**, no fitted alignment. Public is the exact10original60-second archives/12,000frames. Campaign dev is120resets from60parents/21scenes/102,000frames. All130replays complete with **zero filled frames**.

| Actual Wasm artifact | Public30/60s | Campaign capped30/full | Eligible60, n=30 | Peak public/campaign fuel |
| --- | ---: | ---: | ---: | ---: |
| Submitted B-D0seed217, prior matched results |0.973/1.996|1.324/1.843|2.768|1.075B/1.075B|
| Historical N2seed218+kf_grid integration |0.687/1.292|0.927/1.146|1.634|1.452B/1.643B|
| **Newest input-model seed217** |**0.621/0.888**|**0.824/1.006**|**1.353**|**1.454B/1.658B**|

The historical seed218 row is an artifact reference, not a matched-seed component ablation. Archive hashes match the submitted seed217 control. All10public flights improve against it;96/120campaign resets improve and24regress. Largest regression: `dev-ProcTHOR-Train-166-00-crop5`,1.425→2.267m. Worst new campaign replay: `dev-106366104_174226329-01`,4.745m. None exceeds5m. Full paired regressions and scene/parent dependence remain visible in `paired-submitted-control.json` and `matched-results.json`.

Capped30 includes shorter25-second remainders. Eligible60 is the continuous first1,200frames on the same30eligible resets for every guest, without resetting at30seconds. It is not a mean over all120records. Raw600-frame prefixes remain separate from older601-inclusive prepared diagnostics.

| Newest guest campaign group | Resets | Capped30/full ATE |
| --- | ---: | ---: |
| ProcTHOR |60|0.871/1.047|
| HSSD |60|0.777/0.965|
| Nominal crop0 |60|0.785/0.991|
| Crop5 |60|0.863/1.021|
| Historical backward/lateral |10|1.134/1.504|
| Historical ordinary |110|0.795/0.961|
| Actual initial speed<=0.05m/s |75|0.779/0.986|
| Actual initial speed>=0.20m/s |31|0.945/1.071|
| Intermediate speed |14|0.793/0.966|

Motion labels retain historical full-crop fractions. Initial speed is a scoring-only camera-speed diagnostic over0.25seconds. The two crops overlap; they are not independent flights. Public has one scene included in expanded campaign training, so it is a development diagnostic. The compact3.98m server result uses a different/unverified roster and is not treated as a matched public comparison.

## Verification and limitations

- All3package binaries pass official five-step ABI checks. The existing Python odometry regression suite passes12/12tests.
- On1,200actual sensor-only frames, streaming Python and the training batch derivation match bitwise for every image, all51IMU features and every rotation.
- On frozen identical inputs, Python/C++ neural velocity separation is at most4.77e-7m/s.
- An independently initialized600-frame actual-Wasm replay exactly matches the full1,200-frame emitted pose/twist prefix (maximum component difference0); first-camera timestamp0.045s and pose identity are preserved. No later measurements reach the shorter guest.
- Static-bias startup/reset and rotating-start/reset contracts pass, including nonzero timestamps and lever arm. The strict synthetic visual-state test **fails** its2e-5 tolerance (first observed mismatch4.44e-5); the failure is retained. An initial reset test accidentally compared native output bit-for-bit to Wasm rather than the same backend; that harness error was corrected and its log preserved.
- **Strict long parity still fails.** On one60-second public replay, corrected Python→native maximum position separation is0.010707m; native→Wasm is0.422255m. Maximum rotation-matrix element differences are0.004726 and0.172402. Matching versions and correcting borders do not prove that every remaining cause is merely rounding; the visual-path discrepancy remains unresolved. Gray conversion matched sampled frames.

The matching seed217 prepared Python scores were0.892560m public and0.997328m campaign, within about1% of the Wasm aggregate means. That similarity does **not** establish per-frame equivalence. Original-dev/proxy raw whole-guest guards remain unavailable, and no new submission is promoted. Measured results, failed checks and implementation hypotheses are kept separate.

## Reproduction

From this worktree's `research/`, with the existing pinned toolchain/venvs:

```bash
export TMPDIR=/dev/shm/sebastian-vio/tmp
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH=/dev/shm/sebastian-vio/viobench
# Only if the isolated source is absent:
git clone --depth 1 --branch 5.1.0 https://github.com/opencv/opencv.git /dev/shm/sebastian-vio/new-model-opencv510-src
python3 build_opencv510.py wasm
python3 build_opencv510.py native
/data/backups/rganapa/Sebastian/venv-teacher/bin/python build_newest.py --out results/loop/my-fresh-build
```

Builds use wasi-sdk34, `--input-kf-grid`, FP32 `simd-8x32-k2` convolution and isolated OpenCV5.1. Exact commands/source hashes are in `artifacts.json`; configure/build/failure logs remain in `results/loop/new-model-wasm/`. Native's original build retained host font support; Wasm disabled it. Those font functions are unused, and the actual native command is retained.

```bash
PY=/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python
$PY -m viobench check results/loop/new-model-wasm/package/vio_n2_kfinputs_s217.wasm
$PY evaluate_newest.py results/loop/new-model-wasm/isolated-grid/seed217-opencv510 --out results/loop/my-fresh-public --set public
$PY evaluate_newest.py results/loop/new-model-wasm/isolated-grid/seed217-opencv510 --out results/loop/my-fresh-campaign --set campaign-dev --workers 32
$PY summarize_newest.py
```

Use fresh output paths for fresh inference. Existing build/replay identities are checked before reuse. `make_sensor_fixture.py`, `new_input_reference.py`, `new_model_parity.py`, `test_new_model_guest.py` and `check_new_model_causality.py` reproduce the checks. Full traces/fixtures stay in ignored `results/loop/`; compact summaries and all per-flight results are under `results/eval/new-model-wasm/`. An inefficient first prefix helper repeatedly decompressed its fixture; only that owned helper was stopped, corrected and rerun. No inference score was changed or excluded.
