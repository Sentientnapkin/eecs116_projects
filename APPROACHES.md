# Final project: approaches tried so far

Updated 2026-11-19. This is the entry point for the VIOBench visual–inertial odometry work in this repository. Detailed experiment logs and source live under `research/`; older classical code lives under `Final Project/classical_vio/`.

## Current frozen result

The latest candidate is **N2 trained with kf_grid visual-attitude inputs**, compiled to C++/Wasm. Seed 217 measured **0.888 m public / 1.006 m campaign full mean unaligned ATE**, with zero filled frames and **1.658 billion peak fuel/frame**. Only this seed has full public/campaign Wasm measurements. Strict Python/native/Wasm visual-path parity remains unresolved, so this is a frozen experimental artifact, not a newly qualified submission. Further parity work was stopped at the user's request.

[Latest candidate report and artifact paths](research/NEWEST_MODEL_WASM.md) · [Current code map](research/SOLUTIONS.md)

## New structural pipelines prepared for scoring

Four seed217 Wasm guests are now built: unchanged control, Manhattan yaw correction, visual translation-direction correction, and both. Their learned inputs stay fixed; the new modules modify integration only. Geometry, official ABI and synthetic reset/prefix checks pass. Dataset scoring has not started, so no accuracy improvement is claimed. See [pipeline implementation, artifacts and scoring command](research/structural_pipelines/README.md) and the [readiness index](research/results/eval/structural-pipelines/ready.json). The original frozen candidate and its unresolved parity limitations remain intact.

## How to read the results

ATE below means mean unaligned position RMSE in metres. Prepared original dev, proxy validation, raw public, campaign-30, full campaign and server submissions are different evaluations; compare numbers only within their stated set. Unless a row says otherwise, later training comparisons use three seeds. Campaign has 120 overlapping resets from 60 parents, not 120 independent flights. Public is a development diagnostic for expanded-data models because its scene occurs in campaign training. Historical reports contain superseded status statements; the latest candidate report takes precedence for the frozen artifact.

## Experiment catalogue

| Approach we tried | What we learned / disposition | Details |
| --- | --- | --- |
| Classical inertial dead reckoning and older camera-motion/EKF estimators | Established the sensor integration and camera-frame baseline. Older Stage 5 EKF public ATE was 4.662 m. | [Classical implementation](Final%20Project/classical_vio/README.md), [session report](research/SESSION_REPORT.md) |
| Compact camera direction plus blended speed | User-reported server result: 3.98 m, about 16M peak fuel/frame. Exact source/binary was not located during the audit; its server roster is unverified and cannot be compared directly with local scores. | [Continuation audit](research/CONTINUATION_20261119.md) |
| Early visual/temporal learning, EMA, selective SSM and compact student | Built causal visual/IMU prediction, temporal heads and compact deployment. These earlier model families have their own datasets and evaluations. | [Research guide](research/README.md), [robustness report](research/ROBUSTNESS.md) |
| Moving-start robustness, sensor disturbances and recurrent-state changes | Expanded training improved stress performance but regressed nominal accuracy. Reliability features added little; zero initial memory helped reset behavior at a nominal cost. Expanded SSM added no point to the measured nominal accuracy/fuel frontier. | [Robustness experiments](research/ROBUSTNESS.md) |
| Separate frozen CNN versus SEA-RAFT visual-motion screen and native student | Preserved an independent older pipeline, MLP heads and measured diagnostics. Consolidation did not establish a new deployment qualification. | [Visual-motion overview](research/visual_motion/README.md), [experiment guide](research/visual_motion/VISUAL_MOTION.md) |
| Learned body velocity: CNN/correlation + IMU features + GRU/SSM | B-D0 became the learned control: original-dev three-seed mean 1.095 m. Submitted seed217 Wasm: public 1.996 m, campaign full 1.843 m. | [Model guide](research/ODOMETRY.md), [baseline audit](research/BASELINE_FINISH_REPORT.md) |
| More training data: N1, B-D2n and N2 | N2 improved original dev to 0.933 m and campaign full native to 1.391 m, but ordinary original-dev error rose 9.2%, failing the guardrail. N1/B-D2n did not replace the control. | [Data comparison](research/SESSION_REPORT.md), [coverage audit](research/EVALUATION_COVERAGE.md) |
| N2 early-window hard-motion resampling | Regressed original dev 0.9334 → 1.0284 and campaign full 1.3906 → 1.5163. Rejected. | [Training completion](research/TRAINING_COMPLETION.md) |
| Faster training and inference | Compiled recipe reduced warm epoch time 103.02 → 4.83 seconds with comparable three-seed accuracy. Batched replay also improved throughput. Kept as engineering improvements. | [Consolidation](research/CONSOLIDATION.md), [session report](research/SESSION_REPORT.md) |
| Hyperparameter search and longer training | Burn16 finalist improved dev only 1.0905 → 1.0767; higher-LR finalist regressed. 72 epochs improved dev about 5.5% to 1.030, missing the trigger for a 144-epoch follow-up. | [Completion audit](research/CONTINUATION_20261119.md) |
| Learned gyro-bias/attitude correction | A-D0 worsened original dev 1.095 → 1.144. Frozen zero-bias and first-window-freeze policy screens also failed. Closed negative results. | [Training completion](research/TRAINING_COMPLETION.md), [bias ablation](research/FROZEN_BIAS_ABLATION.md) |
| Small visual attitude correction and attitude oracles | Initial causal visual correction improved dev only 0.79%, missing its gate. Truth-only diagnostics identified yaw as a major error source; oracle results are not deployable estimates. | [Session report](research/SESSION_REPORT.md) |
| Fixed EKF over learned velocity | Dev 1.095 → 1.129, worse in every seed. No uncertainty-training follow-up was qualified. | [Completion audit](research/CONTINUATION_20261119.md) |
| Iterative frozen-feature velocity refinement | Dev 1.095 → 1.078, below the required improvement; isolated-kernel fuel did not qualify a whole guest. | [Completion audit](research/CONTINUATION_20261119.md) |
| Our upstream OpenVINS/MSCKF wrapper | Campaign-30 scores around 2.84 m; insufficient initialization excitation, false stationary updates and weak feature support. This is a different implementation from the provided baseline below. | [Wrapper notes](research/openvins_native/README.md), [session report](research/SESSION_REPORT.md) |
| Actual provided OpenVINS consensus smoother | Actual Wasm public 1.108 m, campaign full 32.642 m, peak 4.350B fuel/frame. Strong typical accuracy but catastrophic finite-output divergence and initialization failures made mean accuracy unacceptable. | [Verified baseline report](research/BASELINE_FINISH_REPORT.md), [reproduction](research/provided_baseline/REPRODUCTION.md) |
| OpenVINS/learned trajectory handoff and gating | Predeclared splice arms failed; post hoc per-frame consensus reached 1.376 m campaign. This was offline analysis of saved trajectories, not a qualified fused guest. | [Detailed approach survey](research/APPROACHES.md) |
| Provided VINS-Mono build/check | Built and passed ABI check, but one noisy-hovering-turn test failed. No completed matched public/campaign replay was found; not selected. | [Baseline audit](research/BASELINE_FINISH_REPORT.md) |
| kf_grid visual gyro-bias/attitude correction, integration only | Historical N2 seed218 actual Wasm reached public 1.292 / campaign full 1.146 m. Later audit found mask semantics and backend parity failures, so those measurements do not establish a faithful port. | [Parity review](research/KF_GRID_PARITY_REVIEW.md), [fusion completion](research/FUSION_COMPLETION.md) |
| Visual translation-direction fusion | Historical B-D0/kf_grid Wasm improved public 1.492 → 1.361 and campaign 1.642 → 1.381 m. Semantic/parity failures and missing original raw guards prevented qualification. | [Fusion completion](research/FUSION_COMPLETION.md) |
| C++/Wasm port, SIMD and staged visual work | Original FP32 learned port passed sampled parity; CNN SIMD reduced peak fuel about 19.9%. Staged kf_grid work cut campaign peak 1.643B → 1.131B with nearly unchanged ATE, but retained visual parity limitations. | [Native implementation](research/native_odometry/README.md), [fusion/fuel report](research/FUSION_COMPLETION.md) |
| Retraining with static08 and repaired kf_grid input attitudes | Both passed their declared common-attitude campaign gate across three seeds. kf_grid own-attitude campaign full diagnostic reached 0.9724 m. Proxy regressions and reconstructed-input limitations remained. | [Training completion](research/TRAINING_COMPLETION.md) |
| Complete N2/kf_grid input-model C++/Wasm implementation | Ported attitude into image history, IMU features and integration. Corrected grid-cell border behavior; frozen seed217 achieved the current result above. Strict long parity still fails. | [Newest model report](research/NEWEST_MODEL_WASM.md) |

## Surveyed or proposed, without a completed matched experiment

ROVIO, ORB-SLAM3, DSO/DM-VIO/Basalt, learned velocity factors in the provided smoother, drag-model aiding, learned feature frontends and large learned VO systems were discussed in the [detailed survey](research/APPROACHES.md). A fresh 192-flight stress set and a 64-flight training-only lateral pilot were proposals, not completed generation runs. See the [coverage protocol](research/EVALUATION_COVERAGE.md) and [continuation audit](research/CONTINUATION_20261119.md).

## Where the complete history lives

- [Consolidation and branch-by-branch verdicts](research/CONSOLIDATION.md)
- [Continuation audit and completed workstreams](research/CONTINUATION_20261119.md)
- [Original learned-odometry session report](research/SESSION_REPORT.md)
- [Historical handoff and experiment context](research/HANDOFF.md)
- [Detailed survey, diagnostics and next-experiment proposals](research/APPROACHES.md)
- [Current frozen package, results and failed parity checks](research/NEWEST_MODEL_WASM.md)

This overview summarizes existing evidence. Creating it did not restart training, evaluation, parity work or submission.
