# Continuation audit, 2026-11-19

The user requested finishing outstanding Claude work with Codex agents before discussing new research directions. Work is isolated under `.codex-worktrees/`; existing branches and artifacts are preserved. No reserved-test scoring, submission, push, paid infrastructure, or interruption of unrelated jobs is authorized.

## Git and submission provenance

`git fetch origin --prune` succeeded. Remote main is `8f3f644ec591b747a396f53565d18fbf3e6e81ce`, already an ancestor of local research HEAD `70ea60a`. Remote heads contain main and `claude/teacher-model-training-60911a`; no remote `research/learned-odometry` ref exists. A fast-forward pull naming that absent ref failed without modifying the checkout. The subsequent explicit `git pull --ff-only origin main` succeeded with **Already up to date**. Main retains the older Python classical estimators; its README's historical aligned results are not decision metrics for this work.

New reference submission: **camera direction + blended speed**, ID `67b8a4d97b9f161b`, `vio_c_v2.wasm`, SHA256 `17612d2a1dff9ef50c185dbeed08a8778f10dc19a8475c0dc55a3fdacef072f2`. The user's server summary reports mean unaligned ATE **3.98 m**, peak fuel **16.0M/frame**, all twelve 1,200-frame episodes complete with zero filled frames. The exact rounded episode values are retained in `results/eval/submissions/camera-direction-blended-speed-67b8a4d97b9f161b.json`. This is server evidence supplied by the user, not a local reproduction. Source and artifact location are pending; no checked-in filename/hash match was found in fetched main. The user clarified it might not have been uploaded. A local walk found no matching filename, and a targeted 40–90 KiB Wasm scan of project/artifact directories found no compact binaries to hash. Do not claim a matched server comparison to B-D0 until roster identity is established.

## Corrections to the initial status explanation

The main session report and `/data/backups/rganapa/Sebastian/odometry-provided-comparison` report are stale relative to Claude branch `odometry/provided-openvins` at `023198d`. That newer branch contains completed actual Wasm baseline replays. Its notes report provided OpenVINS public **1.108 m**, campaign30/full **6.714/32.642 m**, peak **4.350B/frame**, with zero filled frames. They also report N2 seed218 + `kf_grid` public **1.292 m**, campaign30/full **0.927/1.146 m**, peak **1.643B/frame**. These are existing measurements under validation, not newly produced measurements and not three-seed deployment qualification.

Frozen visual-fusion controls differ from original N2 raw replay because they use `kf_grid` attitude; this is not by itself evidence of an evaluator bug. Their full causality, input, duration and native/Wasm correspondence still require audit.

HP finalist training and N2 early-window resampling already finished. Attitude-input retraining remains incomplete after a degenerate visual fit during preprocessing. The two frozen gyro-bias policy screens completed and failed their exploratory gates; these are diagnostic-only, unqualified and have no measured deploy fuel.

## Assigned completion work

- Baseline agent: verify newest pinned OpenVINS source, tests, raw artifacts, all matched baseline metrics, failures and hashes.
- Training agent: audit finished HP/resampling/attitude results and finish the bounded predeclared attitude-input comparison, preserving historical gates and matched seeds.
- Fusion agent: reconcile frozen attitude controls and finish existing fusion/fuel deployment comparisons with whole-guest measurements and parity.
- Parent: Git/source provenance, new compact submission evidence, integration and final recommendation.

Initial process checks found no matching existing odometry training/replay jobs. GPU0's service and unrelated GPU1 occupancy are left alone. Root filesystem remains full; work and caches use NFS or tmpfs.

## Closed prior workstreams

These values are audits of previously completed work, not new training results. All ATE values are mean unaligned metres. Training comparisons use seeds 217/218/219.

| Workstream | Matched outcome | Disposition |
| --- | --- | --- |
| N2 early-window resampling | N2 control → resample: original dev 0.9334 → 1.0284; proxy30 1.1098 → 1.2070; campaign30 1.0071 → 1.1388; full 1.3906 → 1.5163 | Rejected; both campaign catalogs and both crop-start groups regress. |
| HP burn16 finalist | Compiled control → finalist: dev 1.0905 → 1.0767; ordinary 0.9061 → 0.9086; proxy30 1.2587 → 1.2528 | Misses declared 10% dev improvement gate. |
| HP lr1e-3 finalist | Dev 1.1847; ordinary 1.0260 | Rejected; worse than matched compiled control. |
| Learned gyro-bias head A-D0 | B-D0 dev 1.0950 → 1.1440; ordinary 0.9215 → 0.9811; proxy30 1.2765 → 1.3249 | Rejected under unchanged gates. |
| Frozen gyro bias policies | Campaign30 control 1.35336; zero-bias propagation 1.36846; first-window bias freeze 1.36420 | Both exploratory gates fail; input/model velocities frozen, fuel unmeasured. |
| Original visual attitude correction | Original dev 1.0950 → 1.0863 | Prior 0.79% gain misses 10% gate; distinct from newer `kf_grid` and direction-fusion experiments. |
| Fixed EKF | Dev 1.095 → 1.129, every seed worse | Closed negative result; no uncertainty-training follow-up. |
| Frozen-feature refinement | Dev 1.095 → 1.078; proxy30 1.276 → 1.269 | Misses 10% gate; isolated kernel fuel does not qualify deployment. |
| Throughput | 103.02 → 4.83 seconds/warm epoch; three-seed dev 1.0950 → 1.0905 | Fast numerical recipe validated; no architecture claim. |
| Longer D0 budget | Compiled36 →72 epochs: dev 1.091 → 1.030 | 5.5% improvement misses predeclared 144-epoch trigger; no new144 arm. |
| Existing CNN SIMD pilot | Whole-guest peak 1,074,754,835 → 861,235,415; outputs bit-identical in matched sample | Validated optimization, distinct from newer expensive visual attitude guest. |

Fresh192-flight stress generation and the training-only64-flight lateral pilot were proposals, not interrupted jobs. No new scene enrollment or broad generation is being launched as part of closing declared existing comparisons. Reserved test data remain untouched.

## Verified matched raw Wasm baseline audit

The baseline audit re-read actual saved guest trajectories and reports, recomputed direct position RMSE, checked all60 campaign-dev nominal-parent archive hashes against the dev manifest, and recorded public/cropped archive hashes. The successful clean source/build checkout is `/dev/shm/sebastian-vio/viobench` at the pinned commit; the earlier failed NFS build logs do not describe the completed artifact. Provided OpenVINS guest SHA256 is `c6cd96bcbadef6c098fc285a293bc8f3045032245d232b10be84d6423789da8e` (8,462,133 bytes). Its saved check log records seven tests passing.

| Actual Wasm guest | Public60,10 flights | Campaign capped30,120 crops | Campaign full,120 crops | Continuous60-eligible,30 crops | Max step fuel, all measured sets |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unchanged provided OpenVINS | 1.108 | 6.714 | 32.642 | 84.191 | 4,349,914,268 |
| Submitted B-D0 seed217 | 1.996 | 1.324 | 1.843 | 2.768 | 1,074,758,773 |
| N2 seed218 + historical `kf_grid` | 1.292 | 0.927 | 1.146 | 1.634 | 1,643,004,075 |
| B-D0 seed217 + historical `kf_grid` | 1.492 | 1.276 | 1.642 | 2.480 | 1,643,004,112 |

All table guests completed every requested frame with zero evaluator filling. Campaign contains102,000 frames per guest; public12,000. For OpenVINS, finite startup outputs are counted as guest outputs: all10 public flights initialized (0.9–3.7 s), but only114/120 campaign crops initialized. Six crops returning finite startup poses never initialized. The very poor campaign mean includes severe finite-output tracking divergence; completion is not tracking success. Full campaign replays have mixed parent durations, and capped30 includes25-second remainders. The eligible60 column uses the same30 crop population for every guest and is not a mean across all120 records. Historical motion labels and actual initial-speed groups are both reported in the detailed audit.

The N2/kf rows are single-seed historical deployment evidence, not a three-seed passing replacement. Original-dev14 raw archives remain unavailable. These raw600-frame prefix metrics are separate from older prepared601-inclusive-frame metrics. Full artifacts, per-flight failures, catalogs/scenes/parents, initialization and commands are supplied by the baseline-finish report and JSON.

The adjacent VINS-Mono source was also built in prior work and its ABI check passed, but its provided tests had7 passes and1 failure: noisy hovering-turn translation RPE0.23884 exceeded0.15, despite final drift0.0996 m. No completed matched public/campaign VINS-Mono replays were found. It remains a failed side-baseline check, not a selected candidate.
