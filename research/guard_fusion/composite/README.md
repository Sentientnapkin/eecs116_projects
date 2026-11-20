# Experimental composite guest

The composite links VINS-Mono, provided OpenVINS, and the N2 C++ input model into
one Wasm binary against OpenCV 4.12. Each estimator has isolated ABI symbols and
RNG state; estimator failures are contained before source selection. This is a
new N2 backend, distinct from the frozen OpenCV 5.1 guest. Its measured runtime
scores must be reported independently of the saved-trajectory experiments.

The safe selector has matched the Python implementation across all 171 saved
source streams to floating-point precision. That checks selector arithmetic,
not the complete composite's estimator trajectories. Root `README.md` documents
scene-disjoint guard selection and the still-failed strict G1 gate.

From the repository root, with the existing teacher Python:

```bash
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
$PY -m research.guard_fusion.composite.build \
  --config research/guard_fusion/selected_config_median.json \
  --out research/artifacts/guard-composite-median-v3
$PY -m research.guard_fusion.composite.validate \
  --config research/guard_fusion/selected_config_median.json \
  --output research/results/eval/guard-fusion/selector-median-parity.json
```

Build outputs are isolated and existing output directories are rejected. Build
records capture compile commands, source hashes and dependency hashes. The
original upstream guests and frozen N2 artifacts are preserved.

`score.py` supports running the pinned evaluator or consolidating saved results.
The runner compiles each distinct binary once into a shared local Wasmtime cache,
forwards the upstream compilation lock unchanged, uses one BLAS/OpenMP thread per
process, and caps concurrency at 64. Cached `report.json` files are reused. Each
flight has a lock to prevent duplicate writers, and progress `scores.json` is
atomically replaced. No evaluator source is changed by this runner.

```bash
$PY -m research.guard_fusion.composite.score \
  --wasm /absolute/path/composite.wasm \
  --episodes /data/backups/rganapa/Sebastian/gen/raw-fast/selected \
  --name guard_median --out research/results/loop/composite-median \
  --workers 64
# Consolidate an existing scores.json without running any guest:
$PY -m research.guard_fusion.composite.score --scores /path/scores.json \
  --offline research/results/eval/guard-fusion/v2-safe/summary-s217.json \
  --config research/guard_fusion/selected_config_median.json \
  --out /path/summary.json
```

Every declared flight is retained. A missing or non-finite runtime score receives
the origin-output ATE computed over that complete flight and is flagged as an
origin substitution. ATE, medians, tails, completed/filled counts and measured fuel
are reported. An optional offline comparison checks the same rule and flight set,
while explicitly recording the changed N2 backend.

`package.py` packages an already-built guest, source code, weights, configuration,
build records and copied JSON evidence. It verifies the recorded source and binary
hashes and refuses to overwrite an output directory. Source archives have fixed
metadata; an optional ZIP is likewise deterministic for a fixed package snapshot.
External static libraries and toolchain are recorded by hash rather than bundled.

```bash
$PY -m research.guard_fusion.composite.package \
  --build research/artifacts/guard-composite-median-v3 \
  --out research/results/loop/composite-package \
  --evidence selected171_scores=/path/raw-scores.json \
  --evidence selector_parity=/path/selector-median-parity.json \
  --evidence future_poison=/path/future-poison.json \
  --zip /path/composite-experimental.zip
# Older v2 builds require --config .../selected_config_safe.json explicitly.
```

Evidence is not upgraded into a claim: the manifest remains experimental, marks
G1 as failed and states that the user controls uploads. No code submits a guest.
The packaging command performs a static smoke audit and records the release
preflight's actual incomplete state. It does not run a new evaluation sweep.

`research/preflight.sh PACKAGE` runs twelve release checks in the plan's order,
stopping at the first failure or unavailable proof. Remaining checks are
`not_checked`, and unknown evidence never passes. `--smoke` is a separate artifact
audit; it cannot produce `release_pass=true`. `--run-abi` additionally runs the
official five-step checker on the exact packaged binary and records its SHA.

```bash
research/preflight.sh /path/package --smoke --run-abi
research/preflight.sh /path/package
```

Release evidence must bind its `wasm_sha256` (or the raw score guest's `sha256`)
to the packaged binary. Supported evidence names are `provenance_freeze`,
`official_abi`, `future_poison`, `reset_reinit`, `mid_start`, `selected171_scores`,
`full_backend_parity`, and `standard_report_and_gates`. Selector-only parity is
kept as evidence but does not satisfy full-backend parity. The current dirty
checkout, absent reproducible rebuild, incomplete standard reports and failed G1
are represented as incomplete requirements; a package is not release-qualified.
