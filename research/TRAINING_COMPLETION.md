# Training workstream completion audit

Audit date: 2026-11-19 UTC. This work is isolated on `archive/2026-11-19/training-completion` under `.worktrees/training-completion`. Existing research worktrees, raw archives and checkpoints are preserved. No reserved test was accessed. No submission, push, or unrelated-job interruption was performed.


**Final measured outcome:** both declared input-attitude interventions improve trained velocities through the same common attitude, passing their original experimental gate. Static08 improves reconstructed original-dev own-attitude ATE to **0.7963 m** (ordinary **0.8163 m**); repaired kf_grid input training is best on campaign own-attitude full (**0.9724 m**) and public (**1.0389 m**). Both regress proxy30 against the matched rolling control. Complete changed-input C++/Wasm deployment is not implemented, so these are promising research candidates rather than validated submission artifacts.

## Completed work found during the audit

The session report's running statuses were stale. There were no live matching research trainer/evaluator processes when inspected. GPU 0 retained its existing service and GPU 1 had unrelated allocated memory; this continuation used GPUs 2–4 and 6–7 for training, GPU 5 for evaluation, and the freed GPU 2 for the CUDA regression suite. GPUs 0 and 1 were untouched.

All values below are mean unaligned trajectory RMSE in metres. Training comparisons use paired seeds 217/218/219. Existing gates are retained.

### N2 early native resampling

All three 36-epoch runs and all four evaluations completed in the existing data-coverage worktree. The intervention changes the position of existing training windows, preserving manifest, motion/domain/catalog/crop budgets and optimizer updates. It fails the declared gate.

| Evaluation | N2 matched control | Early resampling |
|---|---:|---:|
| Original dev | 0.9334 | 1.0284 |
| Ordinary original dev | 1.0065 | 1.0409 |
| Dev nominal/static | 0.8714 | 0.9679 |
| Dev 5-second crop | 0.9954 | 1.0888 |
| Proxy validation 30 s | 1.1098 | 1.2070 |
| Campaign dev 30 s | 1.0071 | 1.1388 |
| Campaign full | 1.3906 | 1.5163 |
| ProcTHOR campaign 30 s/full | 1.1261 / 1.4770 | 1.2293 / 1.5893 |
| HSSD campaign 30 s/full | 0.8881 / 1.3042 | 1.0483 / 1.4433 |

Original reports (with per-flight results) are `.worktrees/data-coverage/research/results/eval/data-coverage/training/`. In particular `paired-*.json` retain paired seed arrays and catalog/start/motion groups. Both overlapping crop origins remain in the historical population; they are not independent flights. No further generation is justified by this failed result; the 64-flight early-lateral pilot remains a separate proposal.

### Hyperparameter sweep

The existing bounded 21-configuration, two-seed screen and both selected 36-epoch, three-seed finalists completed. The finalists were `burn16` and `lr1e-3`; selection was already made by the original driver. No new search was started.

| Arm | Original dev | Ordinary original dev | Proxy validation 30 s |
|---|---:|---:|---:|
| Original B-D0 control | 1.0950 | 0.9215 | 1.2765 |
| Matched compiled control | 1.0905 | 0.9061 | 1.2587 |
| Burn-in 16 | 1.0767 | 0.9086 | 1.2528 |
| Learning rate 0.001 | 1.1847 | 1.0260 | 1.3216 |

Burn-in 16 improves dev by only 1.3% against its matched compiled control, missing the 10% gate. Learning rate 0.001 regresses dev and ordinary motion. Neither advances to deployment fuel measurement. Reports are `.worktrees/hparam-fast/research/results/eval/hparam-fast/{dev-best,proxy-val-best-30s}.json`; the completed original driver log is `results/loop/hp-fast-queue.log` in that worktree. A fresh compact audit with source report hashes is `results/eval/training-finish/completed-training-audit.json` here.

### Other completed arms

The original learned-attitude A-D0 comparison fails (dev 1.1440 versus 1.0950 m, ordinary 0.9811 versus 0.9215, proxy 1.3249 versus 1.2765). Its slightly better full campaign score does not override those failures. The 72-epoch compiled D0 comparison is complete (dev 1.030 versus 1.091; ordinary 0.849 versus 0.906; proxy 1.219 versus 1.259; full campaign 1.794 versus 1.832). Its 5.5% dev improvement missed the declared 144-epoch promotion gate; 144 epochs remains unrun. Throughput and strong scaling are completed measurements (4.83 s warm single-H100 epoch vs 103.02 s matched original; fixed global batch 4 strong scaling 4.20/2.48/1.74 s on 1/2/4 H100s). They are not pending trainings.

## Input-attitude retraining continuation

This is the unfinished declared experiment from `odometry/retrain-attitude` at `c35024f`. It asks a distinct question from frozen-velocity attitude replay: does changing causal image derotation and gyro/bias input features improve the trained velocity network? Three policies were already declared: rolling control, static08 input attitude, and kf_grid_native input attitude. Each uses 36 epochs and seeds 217/218/219, balanced N2 data and the compiled recipe. Its primary predeclared metric is campaign full ATE through one common native kf_grid attitude, with at least 5% improvement and at most 5% regression on ordinary motion and either crop-origin group. Own-input attitude, original dev, proxy, campaign prefixes and public are also reported. This experimental gate is separate from qualification under historical submission guards.

At audit only rolling-control seed 217 had completed. static08 derivation had completed. Native kf_grid derivation had aborted near training record 800 in `cv2.findEssentialMat` because OpenCV's polynomial solver rejected a degenerate input. The original log is preserved at `/data/backups/rganapa/Sebastian/retrain-attitude-data/logs/derive-kf_grid_native.log`.

The continuation copies the original source (including the dirty CLI-only `--arms/--root/--records` additions in the old worktree) into this isolated worktree; the old worktree is untouched. **Runtime-repaired kf_grid variant:** `grid_rotation` catches `cv2.error` only around essential-matrix and pose solves and returns an unavailable visual measurement. Causal IMU propagation continues; no threshold, weights, or visual fit is retuned. This extends behavior where the original aborted, so the repaired dataset/model is explicitly distinguished from a completed unmodified original arm. Successful existing evaluation shards remain preserved; the training/dev dataset is regenerated separately under `results/loop/training-finish/kf_grid_native/n2`. Original rolling/static08 datasets are reused without changes.

Three targeted regressions pass: essential solver degeneracy, pose solver degeneracy, and rejected-update causal prefix consistency (full and short prefix are bitwise identical; rejecting every visual update equals static08 propagation). Run:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 /data/backups/rganapa/Sebastian/venv-teacher/bin/python research/test_attitude_degenerate.py
```

All nine declared trainings and all matched replays are complete. Eight missing runs were executed here; original rolling-control seed217 was reused after exact source/data identity checks. Final gates and hashes are below. No candidate is deployment qualified.

## Completed bounded screening results

These are **training-time best-EMA selection scores**, not independent final full-replay scores. They document all completed screen arms; decisions use the separately reported three-seed finalists. All 21 configurations have seeds 217/218 at 12 epochs; two one-epoch smoke runs and six finalist runs bring the fast-worktree completion count to 50. The older slow-worktree eight interrupted screening jobs also completed.

| Screen arm | Seed 217 | Seed 218 | Mean selection score |
|---|---:|---:|---:|
| base | 1.1955 | 1.4276 | 1.3116 |
| burn16 | 1.1461 | 1.2768 | 1.2114 |
| burn48 | 1.3594 | 1.5207 | 1.4401 |
| clip03 | 1.2526 | 1.4454 | 1.3490 |
| clip5 | 1.2534 | 1.5460 | 1.3997 |
| cnn-narrow | 1.3532 | 1.2370 | 1.2951 |
| cnn-wide | 1.1802 | 1.3176 | 1.2489 |
| ema99 | 1.1664 | 1.3935 | 1.2799 |
| ema999 | 1.4818 | 1.6304 | 1.5561 |
| h-long | 1.2777 | 1.4585 | 1.3681 |
| h4 | 1.2509 | 1.4602 | 1.3555 |
| lr1e-3 | 1.1646 | 1.2581 | 1.2113 |
| lr1e-4 | 1.4932 | 1.4874 | 1.4903 |
| lr6e-4 | 1.1804 | 1.2568 | 1.2186 |
| w128 | 1.4767 | 1.4416 | 1.4591 |
| w128-h4 | 1.4779 | 1.4368 | 1.4574 |
| w96 | 1.4049 | 1.4877 | 1.4463 |
| warm0 | 1.3029 | 1.3843 | 1.3436 |
| warm2 | 1.3189 | 1.4254 | 1.3722 |
| wd0 | 1.2047 | 1.4270 | 1.3159 |
| wd1e-1 | 1.2027 | 1.4306 | 1.3166 |

## Verification and limits of the reconstructed inputs

The reused rolling-control seed217 has **exactly the same trainer, model, and data-loader source hashes** as this continuation; its data-manifest identity also matches the new rolling seed218 byte for byte (`a23bde11e6d4364ef2a3a3eb179f81a1f6cc88c63d9ef08d2fb8a41ec8b2799a`). Both alternative N2 datasets preserve all **1,784 ordered records** (1,770 train, 14 dev), their original source-shard mapping, parents, crop origin, scene, frame count, domain and tier, so the seeded sampler visits matched original records. `results/eval/training-finish/matched-input-data-audit.json` retains the check.

An actual campaign crop passed a bitwise identity check for rolling reconstruction of images, IMU features and rotation matrices. Static08 and low-resolution kf_grid regenerated inputs passed shortened-prefix bitwise checks, including image warps and bias features. `results/eval/training-finish/input-identity-prefix-check.json` retains the result. The existing odometry regression suite initially ran 15 tests (14 passed, one CUDA-only test skipped) under a CPU-only invocation; a later invocation on freed physical GPU 2 passed all 15, including the CUDA checkpoint check. The three geometry/fallback regressions and the roster identity contract also passed.

Original-dev and proxy raw archives are unavailable here. Their regenerated inputs reconstruct gyro increments from stored attitudes and gyro/bias sufficient statistics, and perform visual geometry at 128×96 where needed. The reconstruction has the documented noncommuting-rate approximation of order `|omega| |delta_bias| dt²` per step. Native campaign/public kf_grid attitudes use raw-resolution images and raw IMU, but their network image history is still rederived from prepared channel-0 frames. Thus **own-input prepared scores are reconstructed-input diagnostics**, not raw complete-system parity. Common-attitude scores isolate trained velocity differences by integrating each network's predictions through the same reference attitude; they are not complete guest scores either.

Fusion/deployment audit confirms that the existing kf_grid C++ guest changes only the attitude used for integration; `Inputs.in.step` still uses rolling attitude and gyro/bias features. Its exporter rejects a non-rolling sensor policy. There is **no existing complete static08 input deployment** to reuse. A qualifying prepared static08 result would still require implementing static08 in C++ Inputs/Orientation (causal startup and history repropagation, image derotation, direct gyro and subpacket features, bias/activation features and integration), then Python/native/Wasm parity, exact raw public/campaign evaluation and whole-guest peak fuel. No candidate from this retraining comparison can be described as deployment qualified.

The comparison retains all historical proxy records: 69 replay records from 68 parents. One known ambiguous parent has two records with the same parent/crop metadata but different durations (1,801 and 1,701 frames). Matching uses each immutable original **source-shard hash**; neither record is dropped or truncated to make an assertion pass. Parent/scene identifiers remain separate for dependence reporting. An initial evaluator's parent/crop lookup detected the mismatch via a frame/timestamp assertion before accepting a score; logs and partial reports are retained under `results/loop/training-finish`. A metadata-only parent-count correction after changing lookup keys is separately recorded; no inference values are changed. The roster contract checks originaldev14/7, campaign120/60, proxy69/68 and public10/10 records/parents for all three policies.

## Final input-attitude results

All figures are three-seed equal-flight means of unaligned trajectory RMSE. Seeds are paired 217/218/219. Every model's own regenerated images and IMU features are used in both columns of the comparison. **Own attitude** uses that policy's row orientation for integration; **common attitude** replaces only integration orientation with the same ungated native kf_grid reference for every network. The kf_grid policy's own and common columns coincide by construction.

| Policy | Original dev own | Ordinary dev own | Proxy30 own | Campaign30 own | Campaign full own | Campaign60 own, eligible subset | Public60 own |
|---|---:|---:|---:|---:|---:|---:|---:|
| Matched compiled N2 rolling | 0.9157 | 0.9874 | 1.0995 | 0.9911 | 1.3751 | 1.9435 | 1.7423 |
| Static08 input retraining | **0.7963** | **0.8163** | 1.1750 | 0.8786 | 1.1548 | 1.4128 | 1.2832 |
| kf_grid native inputs, runtime repaired | 0.9217 | 0.9377 | 1.1343 | **0.8131** | **0.9724** | **1.2437** | **1.0389** |

| Policy | Campaign30 common | Campaign full common | Campaign60 common, eligible subset | Public60 common |
|---|---:|---:|---:|---:|
| Matched rolling | 0.9407 | 1.1077 | 1.5161 | 1.1844 |
| Static08 inputs | 0.8227 | 0.9919 | **1.2261** | **0.9992** |
| kf_grid native inputs, runtime repaired | **0.8131** | **0.9724** | 1.2437 | 1.0389 |

The campaign full population is 120 records from 60 parents and 21 scenes; the continuously scored 60-second subset contains **30 records from 23 parents and 14 scenes**, not 120 (reported JSON counts of 90 include three training seeds). Campaign30 caps every record, retaining 25-second remainder crops. Prefixes are first-camera continuous time-inclusive `<=30/60 s` masks (601/1201 frames when available), matching the historical prepared evaluator; these should not be silently mixed with exact600/1200-frame raw-guest scores. Public is ten 60-second flights in a single scene represented in N2 training; it is a development diagnostic.

### Declared experimental gates, unchanged

The primary common-attitude campaign full gate requires at least 5% improvement and at most 5% regression on ordinary motion and each crop-origin group. Both interventions pass:

| Common-attitude comparison vs matched rolling | Overall | Ordinary | Nominal crop | 5-second crop |
|---|---:|---:|---:|---:|
| Static08 inputs | **−10.46%** | −7.49% | −14.08% | −7.13% |
| Runtime-repaired kf_grid inputs | **−12.22%** | −8.65% | −12.71% | −11.76% |

Common-attitude campaign full per-seed values (217/218/219): control **1.1024 / 1.1141 / 1.1066**, static08 **0.9400 / 0.9938 / 1.0418**, kf_grid **0.9973 / 0.9942 / 0.9256**. Each intervention improves each seed. The 21-scene paired bootstrap has an equal-scene mean ATE difference of −0.1012 m, 90% [−0.1827, −0.0272] for static08 and −0.1084 m, 90% [−0.2047, −0.0209] for kf_grid. These equal-scene intervals are supplemental; the decision uses equal-flight means, and training variability is separately visible in the per-seed arrays.

Proxy30 is a retained negative result: own-attitude static08 regresses **6.87%** and kf_grid **3.17%** against matched rolling. Common-attitude proxy30 also regresses (1.1456 / 1.1343 versus 1.1069). The experimental gate described proxy as a secondary diagnostic; it was not revised after seeing this regression. The historical original-dev criteria remain unchanged. Static08 and kf_grid meet the historical overall/ordinary criteria on reconstructed prepared-input scores, but those scores cannot qualify a changed-input complete system because raw parity/deployment is absent.

Catalog results are consistent with the primary gain:

| Policy | ProcTHOR common30/full | HSSD common30/full | ProcTHOR own30/full | HSSD own30/full |
|---|---:|---:|---:|---:|
| Matched rolling | 1.0638 / 1.2611 | 0.8176 / 0.9543 | 1.1014 / 1.4530 | 0.8807 / 1.2971 |
| Static08 | 0.9111 / 1.1111 | 0.7344 / 0.8726 | 0.9477 / 1.1978 | 0.8095 / 1.1117 |
| Runtime-repaired kf_grid | 0.9013 / 1.0630 | 0.7250 / 0.8818 | 0.9013 / 1.0630 | 0.7250 / 0.8818 |

Per-flight, seed, scene, parent, catalog, crop, measured start-speed and motion groups are retained in the full JSON reports; `horizon_motion_summary` recomputes the motion classification for each prefix instead of silently using full-flight labels. All **736,407 offline velocity frames per policy** are finite. These offline counts do not establish guest ABI completion, initialization time, filled-frame behavior, or fuel. Those guest measurements remain **unmeasured** for the new input policies.

### Interpretation and remaining deployment work

This materially differs from the previously failed frozen-velocity/no-rolling-calibration and visual-attitude arms: input history warps and gyro/bias features are changed **before training**, then trained velocities improve even when integrated through one identical attitude sequence. It is evidence that input/velocity interaction matters, not proof that orientation correction alone solves the problem. The kf_grid reconstruction also has a repaired unavailable-measurement path and OpenCV-version sensitivity, retained separately.

The strongest completed prepared original-dev result is now static08 (0.7963 m); the strongest completed prepared campaign-full/public result is repaired kf_grid-input retraining (0.9724/1.0389 m). The new rolling control's overall dev 0.9157 improves slightly on original N2, but its ordinary0.9874 remains **7.2% worse** than historical B-D0 ordinary0.9215, so it still fails the historical 5% ordinary guard. There is **no newly qualified deployable learned model** from this training workstream. The supplied camera-direction/blended-speed submission and unchanged provided OpenVINS require their own matched raw-guest comparison, owned by the other workstreams.

### Artifacts, hashes and reproduction

- `results/eval/training-finish/training-artifacts.json`: all nine run paths, best-weight SHA256, run-manifest SHA256, config SHA256, source hashes, full training identities and verified36 epochs/4,392 updates.
- `results/eval/training-finish/rolling.json`: SHA256 `de6a77dd37d829635c0df86de446befb971983d66d3a6ea35f75c7abee29bd9e`.
- `results/eval/training-finish/static08.json`: SHA256 `1f6451adbaf071ec32ad92cfd89b4a1f474dd2a8e0e4fa23ed9c8fea82f8b66d`.
- `results/eval/training-finish/kf_grid_native.json`: SHA256 `645cb7b22f730e8137d759fd74858640cb47dad4083127d3fa5df7fd5c07fd0b`.
- `results/eval/training-finish/decision.json`: unchanged gate application, per-seed values and scene/parent paired summaries.

Commands from this worktree's `research/` (Python: `/data/backups/rganapa/Sebastian/venv-teacher/bin/python`; use `TMPDIR=/data/backups/rganapa/Sebastian/tmp`, `HF_HOME=/data/backups/rganapa/Sebastian/hf`, isolated compiler caches under the same NFS subtree):

```bash
# Runtime-repaired kf_grid training/dev input data, independent of the original failed tree:
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python input_attitude.py derive \
  --policy kf_grid_native --manifest data/hub-cache/N2-ssm-x3-gpu/manifests/n2-campaign-tiers.json \
  --split train development --sources data/hub-cache/N2-ssm-x3-gpu/shards \
  --out results/loop/training-finish/kf_grid_native/n2 --workers 40
python training_finish_prepare.py
# Existing original control217 reused; the remaining controls:
python training_finish_queue.py 2 RA-N2-control-x3:218 RA-N2-control-x3:219
python training_finish_queue.py 3 RA-N2-static08-x3:217 RA-N2-static08-x3:218 RA-N2-static08-x3:219
python training_finish_queue.py 6 RA-N2-kfgrid-x3:217 RA-N2-kfgrid-x3:218 RA-N2-kfgrid-x3:219
# All policies use the same seeds and strict record identity in evaluation:
CUDA_VISIBLE_DEVICES=5 python training_finish_eval.py --policy rolling --output results/eval/training-finish/rolling.json
CUDA_VISIBLE_DEVICES=5 python training_finish_eval.py --policy static08 --output results/eval/training-finish/static08.json
CUDA_VISIBLE_DEVICES=5 python training_finish_eval.py --policy kf_grid_native --output results/eval/training-finish/kf_grid_native.json
python training_finish_verify.py
python training_finish_summary.py
```

The literal commands above describe the same experiments; original concurrent execution split static08 over GPUs3/4 and kf_grid over GPUs4/6/7 to finish the declared arms sooner. Training source/config hashes and all actual outputs are retained. No retraining seeds, thresholds, motion budgets, learning rates, or selection rules were adjusted from observed results. The regenerated kf_grid manifest includes its runtime-repair/source annotations before training; its exact checksum is in the training-artifact receipt. Fuel is not estimated from MACs or inherited kernel measurements.
