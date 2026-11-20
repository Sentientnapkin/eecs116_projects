# Isolated VIO recovery and physical-guard experiments

These are exploratory source interventions. **Neither source fix is promoted.**
The original VIO guests and frozen learned guest are untouched. Use the causal
selector for the next deployable candidate; recovery alone does not repair a
bad estimate already published before a VINS reset.

`prepare.py` copies the pinned upstream examples into a new `/dev/shm` directory.
It writes full source patches here and instrumentation-only patches in
`../telemetry/`. `build.py` builds separate C++/Wasm artifacts with provenance:

```sh
python research/guard_fusion/vio/build.py --guest vins_mono --out research/artifacts/guard-fusion/vins-recovery.wasm
python research/guard_fusion/vio/build.py --guest vins_mono --fault-reset 20 --out research/artifacts/guard-fusion/vins-reset20.wasm
python research/guard_fusion/vio/build.py --guest openvins --guard --out research/artifacts/guard-fusion/openvins-guard.wasm
python research/guard_fusion/vio/build.py --guest openvins --telemetry-only --out research/artifacts/guard-fusion/openvins-telemetry.wasm
```

The runtime is the existing pinned OpenCV 4.12/WASI runtime. Downloaded source
caches can be reused; CMake build trees are freshly configured, never relocated.
Defaults use 24 compilation jobs. Artifacts produced during development are
under the ignored `artifacts/` directory alongside this document.

The VINS variant keeps a persistent first-camera gauge across an upstream
estimator reboot. It starts a new bounded IMU history at the reboot exposure,
reports gyro rotation plus expiring previous metric velocity while initializing,
and anchors the newly initialized current camera to the predicted output. A
new initializer with speed above 6 m/s cannot immediately take over. `init()`
fully resets all estimator, tracker, history and recovery state. The optional
compile-time reset injection calls the actual estimator's `clearState()` and
`setParameter()` once at 20 s. This exercises the real recovery path.

The OpenVINS variant rejects an implausible smoother output (speed above 6 m/s,
world velocity acceleration above 12 m/s², or over 1 s without visual factors)
and uses that frontend's live EKF output instead. Its independent conservative
graph uses a speed guard. The modification does not feed posterior states or
outputs back into a smoother. Telemetry records initialization, factor counts,
Ceres costs, consensus spread and guard activation. Mixing EKF and smoother
rotations can still make the consensus rotation solver reject the candidates;
this occurred in two bad probes and is another reason to reject this arm.

## Measured replay evidence

`replay.py` evaluates fixed thresholds from the plan on all 171 saved flights,
using the pinned unaligned ATE evaluator and current/past source observations.
Version 1 had an implementation error: acceleration was compared against the
last *accepted* velocity, creating sticky rejection. The corrected version 2
compares consecutive raw source velocities. No threshold was changed or swept.
Results are in `research/results/eval/guard-fusion/vio-replay-v2/replay.json`.

| Saved-trajectory arm | Mean ATE (m) | Median ATE (m) |
|---|---:|---:|
| OpenVINS original | 28.5290 | 0.5843 |
| Physical guard, expiring previous velocity | 2.2803 | 0.5833 |
| Physical guard, N2 relative-motion fallback | 2.1822 | 0.5455 |
| Same with N2 origin at initialization | 2.2401 | 0.6440 |
| VINS original | 5.5064 | 0.6214 |
| VINS physical guard | 2.0141 | 1.6671 |
| VINS physical guard with N2 origin/fallback | 1.6159 | 1.2343 |

These are fixed-rule exploratory replay results, **not** scene-held-out
selection results or deployable-guest scores. The OV/N2 replay needs both
estimators inside one module. On the 17 original OV flights over 10 m, even the
physical/N2 replay mean is 11.75 m, so it does not meet gate G3's 5 m bar. All
119 original OV flights below 1 m worsen by at most 0.2394 m for this arm.

## Source-fix probes and rejection evidence

The OpenVINS source guard was run on all 17 original >10 m flights plus six
clean flights. Tail mean falls from 276.761 to 177.724 m, far above G3's 5 m
bar; two episodes now terminate when the consensus rejects mixed candidates.
The six clean flights worsen by at most 0.000037 m. This is an initialization
origin/estimator-health failure, not a clipping problem that EKF fallback fixes.

The first two VINS recovery prototypes complete both originally terminating
episodes but worsen their already-corrupted trajectory. Six clean no-reset
runs are byte-identical in both pose and twist to their original baseline.
The first prototype raises the two-tail mean from 71.610 to 285.355 m; the
second raises it to 317.989 m. They are rejected. The third corrects the
recovery attitude's IMU-to-camera transformation and is scored separately;
it still raises the two-tail mean to 317.993 m. Its forced-reset tests finish
both episodes but score 3.805 m mean, compared with N2 at 2.643 m on those
same two flights. It reinitializes within 1.4–1.75 s after the forced reset,
but one flight reboots again. The full recovery acceptance gate therefore fails.
Consult `vio-source-summary.json` for per-flight measurements and fault times.
Do not treat completion alone as an accuracy improvement.

The instrumentation-only OV build also fails bytewise parity with the
previously saved baseline: the catastrophic static probe changes from
2168.274 to 2168.708 m. This is about 0.02%, but violates the strict telemetry
control criterion. The cause has not been isolated; do not infer behavior
equivalence from the instrumentation-only source diff. Use a matching rebuilt
control before drawing conclusions from its health telemetry.

Reproduction/checks:

```sh
OPENBLAS_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python research/guard_fusion/vio/test_replay.py
OPENBLAS_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python research/guard_fusion/vio/replay.py --out research/results/eval/guard-fusion/new-replay --workers 24
/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python research/guard_fusion/vio/summarize.py
```

The four replay tests cover identity on healthy inputs, a +20 m/s velocity and
position transient, prefix equality, and poisoning of all later poses/twists.
They pass. Source probes use fresh evaluator processes; `wasm_eval.py` scores
all declared episodes, including failures. `summarize.py` compares every probe
to its matching baseline episode and records byte equality, telemetry and
fault/reinitialization times. These probes deliberately inspect known tails;
they are diagnostics and cannot establish generalization.
