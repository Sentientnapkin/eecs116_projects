# Causal three-source guard

The saved-trajectory implementation uses VINS-Mono, provided OpenVINS, and N2
seed217/218/219. It reads the existing 171 selected flights and the pinned evaluator;
there are no evaluator changes, private server episodes or reserved test flights.
The metric is **unaligned position ATE RMSE**, averaged over flights. Failed rows
remain in evaluation and receive the evaluator's origin filling.

The measured median-focused policy reaches **0.993 / 1.012 / 0.973 m mean** and
**0.475 / 0.479 / 0.479 m median** on five scene-disjoint held-out folds, for N2
seeds 217/218/219 respectively. This is offline evidence, not a deployable guest or
a server score. The current strict G1 gate fails its oracle-frequency condition.

## Why absolute consensus helps the median

The three guests already report camera poses in the initial camera frame. When
healthy VINS and OpenVINS positions agree, their translations can be averaged in
that common gauge. When they disagree, N2 breaks the tie or supplies the bounded
fallback. Unlike increment splicing, absolute consensus does not permanently
retain the learned estimator's initial translation error or compose successive
sources' attitude drift into the rest of the flight.

A source is eligible only after its initialization timestamp, with a valid current
row and finite-difference speed/acceleration below 12 m/s and 100 m/s². These are
causal physical checks, not learned health estimates. The agreement threshold is
`a + b * max(norm(p_vins), norm(p_openvins))`. The selected median candidate uses
`a=2m, b=.3`, equal VIO translation weights, and N2 position as tie-breaker. A VIO
farther than `6m + norm(p_n2)` from N2 is rejected when the VIOs disagree.

At a source-weight change, a 0.5 s exponentially decaying offset avoids a pose
step. The safe version starts from the previous emitted position plus the new
healthy source's current increment. It never uses a rejected source's current
position to construct that offset. A synthetic million-metre VINS jump produces
no output step above 0.1 m in the fault test. Rotation follows the largest-weight
source; a production attitude handoff still needs runtime validation.

## Protocols and honest selection

`protocol.json` declares 75 candidate rules before the first new guard scores:
54 absolute-consensus candidates, 18 smoothing variants and 3 incremental
baselines. Training folds select minimum mean among candidates with training
median at most 0.6 m. All flights of a scene stay together; folds are assigned by
SHA256(catalog:scene) modulo five. Ground truth is available only in evaluation;
`guards.py` accepts source streams, never truth or scene tags.

`protocol-v2-safe.json` declares the fault-containment correction after v1 was
observed. It retains the original candidate grid and uses the safe transition
formula. Its reports explicitly label the family as a post-hoc followup.

`protocol-v3-median.json` declares the user's stronger median objective after v2
was observed. Among candidates within 0.02 m of the best training mean, it selects
the lowest training median (after the same 0.6 m eligibility filter). The original
mean-focused results are preserved. This objective changes selection only; it
reuses the exact v2 inference candidates and their cached scores.

| Policy | Seed | Held-out mean, m | Held-out median, m |
|---|---:|---:|---:|
| v1 initial absolute consensus | 217 | 0.989638 | 0.503441 |
| v2 safe, mean-focused | 217 | 0.989518 | 0.503431 |
| v2 safe, mean-focused | 218 | 1.006842 | 0.474852 |
| v2 safe, mean-focused | 219 | 0.974797 | 0.478567 |
| v3 safe, median-focused | 217 | 0.993445 | 0.474747 |
| v3 safe, median-focused | 218 | 1.011637 | 0.478560 |
| v3 safe, median-focused | 219 | 0.972605 | 0.478567 |

The three-seed mean of v3's held-out means is 0.992562 m; the corresponding mean
of medians is 0.477291 m. `selected_config_median.json` freezes an exploratory
full-data three-seed refit, rather than pretending that one fixed guest produced
the fold-selected predictions. `selected_config_safe.json` preserves the original
mean-focused seed217 refit, and `selected_config.json` preserves its v1 predecessor.

All three singles reproduce their saved pinned-evaluator ATE within 1e-6 on every
flight. The per-flight three-source oracle is 0.758592 m mean / 0.464135 m median;
it is a hindsight bound, never a guest. The timestamp-window incremental control
is an adaptation of the old report's fixed-40-frame guard, with failed-row masks;
it scores 1.790 m rather than the historical 1.741 m and is not claimed as an exact
reproduction of that threshold experiment.

G1 is reported literally: mean <=2.2 m and median <=1.5×VINS pass, but no worse
than the best single source on at least 70% of flights fails (about 50%). No release
promotion is claimed. The v1 scene-bootstrap 90% paired mean difference versus
VINS is [-7.87,-1.84] m and versus N2 is [-2.84,-2.22] m. These intervals describe
this selected sample and do not certify a private server score.

The non-clean-selected v2 rule on the 21 clean flights scores 1.373 m mean /
0.858 m median, substantially weaker than the overall result. Seven v2 held-out
flights remain above 5 m. Four have both VIOs bad; three select the wrong VIO;
five also have a bad learned fallback. The dominant remaining issue is sustained
source selection, not switch smoothing. See `v2-safe/failure-classification.json`.
Fresh flights/scenes and runtime telemetry are required before a stronger claim.

## Reproduce

From the repository root, using the existing teacher environment:

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/data/backups/rganapa/Sebastian/venv-teacher/bin/python
$PY -m research.guard_fusion.evaluate --workers 48 --seed 217
$PY -m research.guard_fusion.evaluate --workers 48 --seed 218
$PY -m research.guard_fusion.evaluate --workers 48 --seed 219
$PY -m research.guard_fusion.evaluate --workers 48 --seed 217 \
  --protocol-version v2-safe --out research/results/eval/guard-fusion/v2-safe
# Repeat the preceding command for seeds 218 and 219.
$PY -m research.guard_fusion.median_objective
$PY -m research.guard_fusion.oracle
$PY -m research.guard_fusion.classify_failures
$PY -m research.guard_fusion.test_guards
```

A 48-process pass loads each flight once and evaluates every declared arm in
memory, with BLAS threads limited to one. The initial full selected171 scoring
pass took roughly 3.2 s on the available machine; bootstrap reports add several
seconds. Scores are cached with a protocol digest and checked for the requested
episode set. Summary JSON includes tails, 12-flight bootstrap ranges, scene
bootstrap paired differences, split tables, per-fold selections, gates, and
per-flight rows. No GPU is useful for this saved-trajectory stage.

Four tests check every candidate's poisoned-future and truncated-prefix equality,
batch versus streaming equivalence, safe containment of a rejected-source jump,
and exact 600/1200-frame prefixes on real static, moving-start, and catastrophic
VIO flights. `OnlineGuard` is a reference streaming interface; it retains observed
history for clarity. The C++ implementation should keep a fixed-size ring buffer.
