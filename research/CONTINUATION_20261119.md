# Continuation audit, 2026-11-19

**Latest status: candidate frozen at the user's request.** The subsequent complete input-model C++/Wasm port is documented in [NEWEST_MODEL_WASM.md](/data/backups/rganapa/Sebastian/eecs116_projects/.codex-worktrees/new-model-wasm/research/NEWEST_MODEL_WASM.md). Canonical seed217 file `vio_n2_kfinputs_s217.wasm` has SHA256 `8b05b203adc1f045b67df12399ee6b9e0caf28015b7d31678f5378968e2d60cf`; actual public/campaign means are0.887995/1.005868m, zero filled frames and1,658,013,194peak fuel/frame. Source commit `daa73f809fcd19dc6f5bf16dd0642ca890ae7fd4` on `codex/new-model-wasm`. Packaging includes binaries, hashes, source and canonical packed weights. Strict backend parity remains unresolved. **Further parity work is stopped by explicit user instruction and must not resume without a new request.** The older snapshot below predates this port; its statements about an absent changed-input C++ implementation are historical.

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

The training inventory accounts for all original queued runs: fast HP50/50 (42screen jobs,2smoke jobs,6finalists), older slow HP8/8, N2 early resampling3/3, throughput11/11,72-epoch3/3 and learned-attitude3/3. No unfinished broad sweep remains. Individual run/checkpoint inventories are retained by the training completion report. The only newly resumed training is the bounded, previously declared attitude-input comparison.

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

The separately completed original N2 public metered-Wasm comparison is also preserved under `/data/backups/rganapa/Sebastian/odometry-provided-comparison/research/results/loop/provided-comparison`: seeds217/218/219 score1.678796/1.762447/1.897711m (mean1.779651m). Those are ordinary rolling-attitude N2 guests, not the kf_grid variants. Its raw campaign native counterparts score1.435640/1.361806/1.374386m (mean1.390611m). The campaign N2 numbers in that older comparison are **native**, not actual campaign-Wasm evidence; public uses metered actual guests and corresponding native outputs. This preserves the strongest previously completed learned-model comparison without silently relabeling execution backends or attitude policies.

The adjacent VINS-Mono source was also built in prior work and its ABI check passed, but its provided tests had7 passes and1 failure: noisy hovering-turn translation RPE0.23884 exceeded0.15, despite final drift0.0996 m. No completed matched public/campaign VINS-Mono replays were found. It remains a failed side-baseline check, not a selected candidate.

## Port-correctness findings that supersede historical notes

`KF_GRID_PARITY_REVIEW.md` records an independent source review. Historical C++ passes an empty feature mask into `recoverPose`, while Python supplies the RANSAC inliers. OpenCV uses this mask when choosing pose hypotheses, so this can change attitude and accepted measurements. The historical N2seed218 guest was rebuilt byte-for-byte from that unmasked source. Earlier NOTES claiming the mask was fixed and remaining differences were solely KLT numerics are unsupported and superseded; the historical binary measurements remain valid.

The historical exporter also built ordinary `host.so` without `ODO_KF_GRID` and visual OpenCV flags. That host cannot validate the visual path. The fusion port additionally did not require an accepted rotation update before accepting a direction update, unlike the frozen Python diagnostic. Both changes are now separately named opt-in corrections, declared before their smoke scores; no historical artifacts are overwritten.

The corrected single-seed218 traced public smoke measures1.27988m with corrected kf_grid and1.08677m with corrected direction fusion. It nevertheless fails Python4.12/Wasm4.12 accepted-update parity on all10flights: maximum attitude differences range8.7–27.0degrees. Explicit visual native4.13 differs from Wasm4.12 by0.0511177m maximum position on the first public flight. A completed native4.12 build from the same OpenCV source produces essentially the same discrepancy, so backend version alone does not explain it. These are failed parity evidence, not a qualified deployable improvement. The large650-replay/three-seed expansion was stopped after that failure; only owned new workers were stopped and partials retained. There was no unbounded backend search or untraced corrected candidate advancement after the failed gate.

The separately predeclared staged6r fuel intervention completed120/120campaign crops with zero filling: full mean1.642432605m, peak**1,130,544,377**fuel/frame; exact rebuilt historical kf_grid control full1.642425779m and peak**1,643,004,133**. Public mean1.491599m and peak**987,811,616**, compared with1.491581m/**1,451,941,452**control. It is a31.19% reduction in campaign peak, but still5.19% above the submitted ordinary B-D0's roughly1.075Bpeak. The staged public-only peak is not its whole-roster peak.

Staged guest SHA256 is `238f6901e793b8ad88bfee3fa1c322d920302ec1a474904edae0df16ec9b0c51`. An actual independent600-frame shortened-input guest replay matched every emitted pose and twist exactly against the full replay prefix, with identical timestamps/IMU packets, first camera timestamp0.045s and exact initial identity pose. Native visual reset/prefix also passed26frames. This demonstrates tested causality/first-camera behavior; it does not cure the historical visual-port equivalence failure. Final source flags, artifact hashes and all paired flight regressions are recorded in the fusion completion report. Historical C++ fusion also completed: public1.491581→1.360556m and full campaign1.642426→1.380669m at1,643,036,065peak, but remains unqualified for the same semantic/parity and missing original-raw guardrail reasons.

## Newly completed input-attitude training

All9 predeclared36-epoch runs are complete: one exactly matched existing rolling seed217 control and8 continuation runs. Each policy has seeds217/218/219. Degenerate essential/pose solver inputs in the originally interrupted kf_grid data derivation now reject the unavailable visual measurement instead of aborting; the repaired variant and old failed logs are separately identified. No visual threshold or model family was searched. Regenerated1784 ordered train/dev records preserve original source-shard mapping, parents, crop, scene, domain and sampler order. Explicit source-shard matching retains proxy's69records/68parents, including its known unequal-duration ambiguous parent.

These are **reconstructed-input diagnostics**, not whole-guest replays. Own-attitude scores change both model inputs and the integration path. Common-attitude scores integrate each policy's predicted body velocities through the exact same native-kf_grid reference, isolating changes in the predicted velocities from integration attitude. Three-seed equal-replay mean unaligned ATE:

| Input/training policy | Original dev own | Ordinary original dev own | Proxy30 own | Campaign full own | Campaign full common attitude | Public60 own / common |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Matched compiled N2 rolling control | 0.9157 | 0.9874 | 1.0995 | 1.3751 | 1.1077 | 1.7423 / 1.1844 |
| Static08 | **0.7963** | **0.8163** | **1.1750** | 1.1548 | 0.9919 | 1.2832 / 0.9992 |
| Runtime-repaired kf_grid_native | 0.9217 | 0.9377 | 1.1343 | **0.9724** | **0.9724** | 1.0389 / 1.0389 |

**Both input arms pass their predeclared experimental gate**, which requires at least5% lower common-attitude campaign full mean and no more than5% ordinary/crop-origin regression. Static08 improves primary mean10.46%, ordinary7.49%, nominal14.08% and crop5group7.13%. Repaired kf_grid improves primary12.22%, ordinary8.65%, nominal12.71% and crop5group11.76%. Every paired seed improves in both arms. These are distinct experimental gates, not a change to historical submission qualification.

Static08 nevertheless worsens proxy30 own6.87% and common3.49%. The kf_grid input arm's proxy30 own worsens3.17% (common2.47%). Neither is a submission qualification. Original dev has14records/7parents, proxy69/68, campaign120/60 and public10/10. Their seed-expanded row counts are42/207/360/30; these are not additional independent flights. Each policy's final JSON has639rows.

The current compiled rolling N2 control also improves local original-dev mean over the old N2 score, but ordinary0.9874 remains about7.2% worse than historical B-D00.9215. The unchanged ordinary guardrail still matters. Static08's strong original-dev result does not erase its matched proxy regression.

Actual campaign/public raw kf_grid attitudes are available, but model image histories are regenerated from prepared channel0frames; original-dev/proxy input reconstruction has a documented noncommuting-rate approximation from available gyro/attitude sufficient statistics. Rolling reconstruction and alternate-policy shortened-prefix checks pass bitwise on a real campaign sample. Geometry-degeneracy and roster-identity checks pass. The original odometry suite ultimately passes15/15 in an explicitly available CUDA environment. No truth enters deployed inference; common-attitude references are causal sensor-derived estimates, and truth is used only for training targets/scoring/diagnostic grouping.

No complete C++ static08/kf_grid **input** path already exists: the old visual port changes only integration attitude, while image derotation and direct IMU/bias features retain rolling calibration. The exporter rejects non-rolling policy. Porting these new input policies requires a new causal Inputs/Orientation implementation and full Python/native/Wasm checks, raw public/campaign replay and actual whole-guest fuel. Fuel for the newly trained policies is **unmeasured**. They cannot be described as ready submission artifacts.

## Completion, recommendation and review locations

The executable work from the existing bounded Claude queues is now closed. All continuation-owned training, evaluation and native-build workers exited; unrelated processes and GPUs0/1 were untouched. No paid infrastructure, reserved-test measurements, submissions, remote pushes or main-branch changes occurred. Source repairs and old incomplete/failed logs are preserved rather than overwritten.

**No new submission qualifies yet.** The actual provided OpenVINS guest is unsafe as a replacement on this campaign. Historical kf_grid/fusion and its staged fuel optimization are measured binary experiments, but fail a faithful Python/native/Wasm interpretation and lack original raw guardrails. Newly trained input policies pass their declared experimental gate but have proxy regressions and no complete C++/Wasm input implementation. Preserve their checkpoints for the next discussion rather than treating a reconstructed-input score as a deployable artifact. The compact3.98m/16Mserver submission remains an essential reference; reproducing it is blocked only by the unlocated source/binary, not by its reported quality. Its server score must not be compared directly with local public/campaign scores.

All changes remain isolated; original worktrees and the initial checkout are preserved. Component branches and final commits:

- `codex/session-integration`: this combined handoff, updated historical session notices, compact submission evidence and baseline audit.
- `codex/baseline-finish` at `9750cb5`: [baseline report](BASELINE_FINISH_REPORT.md), [peer parity review](KF_GRID_PARITY_REVIEW.md), trajectory audit and hashes. Those report commits are integrated here.
- `codex/fusion-finish` at `121c385`: [fusion/fuel completion report](/data/backups/rganapa/Sebastian/eecs116_projects/.codex-worktrees/fusion-finish/research/FUSION_COMPLETION.md), preserved deploy sources, named corrections, actual Wasm prefix and failed native/Python parity checks, per-flight/grouped results. Code remains on its component branch.
- `codex/training-finish` at `1907593692d82210fc7ebf8f151017d29b5839a0`: [training completion report](/data/backups/rganapa/Sebastian/eecs116_projects/.codex-worktrees/training-finish/research/TRAINING_COMPLETION.md), source fixes, all nine checkpoint hashes and639-row policy results. Code remains on its component branch. Final verification:15/15 odometry tests,3geometry/fallback-prefix tests, real-input identity/prefix and roster contracts.

`results/eval/completion-components.json` records these review locations. Reproduction commands and exact build flags live in each component report. The staged C++/Wasm artifact exists at `/data/backups/rganapa/Sebastian/eecs116_projects/.codex-worktrees/fusion-finish/research/results/loop/fusion-completion/staged6r-rebuild/odometry.wasm`; its presence and exact SHA256 were independently rechecked by the parent. It is a validated fuel/causality experiment, not an approved next-submission binary.
