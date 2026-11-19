# Learned odometry research report

**Continuation notice, 2026-11-19:** The snapshot below is historical. The [completion audit](CONTINUATION_20261119.md) records the latest Git state, all completed Claude workstreams, the actual provided OpenVINS comparison, corrected port-provenance findings, and the additional compact submission. See also the [verified baseline report](BASELINE_FINISH_REPORT.md) and [visual-port parity review](KF_GRID_PARITY_REVIEW.md). The previous upstream OpenVINS wrapper results do not evaluate VIOBench's provided baseline.

**Status at 00:08 UTC on November 19, 2026.** This report covers the work since [the GPU-box handoff](HANDOFF.md). All ATE values are mean **unaligned** trajectory RMSE in metres, averaged across the stated replays. Multi-seed model decisions use seeds **217, 218 and 219**. The original and campaign reserved test splits remain untouched. No submissions or pushes were made through this session.

## What we know

- **N2 is the best measured local accuracy candidate, with a tradeoff.** It reached **0.933 m** on original dev and **1.007 m** on 30-second campaign dev. Ordinary original-dev ATE rose **9.2%**, above the 5% guardrail. A matched targeted-resampling follow-up is training.
- **The submitted binary is the binary we tested.** It achieved **1.996 m** on the ten public 60-second flights and **4.55 m** on the separate 12-episode server set reported by Sebastian. Four longer local raw replays matched PyTorch and C++ to micrometre-scale tolerances. Severe drift appeared in all implementations on the same difficult flight.
- **Compute improved substantially.** The compiled recipe produced a **21.3×** steady single-H100 epoch speedup and cleared three-seed accuracy checks. GPU replay batching gave **2.4–3.9×** speedups on the two measured workloads. The FP32 Wasm port is still expensive even after a **19.87%** SIMD fuel reduction.
- **The attitude hypothesis remains open.** An oracle isolates yaw as the largest attitude error source. The small visual correction missed its gate, so hybrid execution is gated. The learned-attitude training runs are near completion.
- **The current OpenVINS setup fails before and after initialization.** Smooth starts often provide too little excitation and track support to initialize. With stationary aiding, the estimator often takes the stationary path while the vehicle is moving. Suppressing those updates exposes poor visual support and substantial drift.

## Public, server and local evaluation

| Measure | Submitted seed-217 C++ Wasm |
| --- | ---: |
| Public VIOBench mean ATE | **1.996 m** |
| Public range | 1.405–2.937 m |
| Public completion | 10/10 episodes, 12,000 frames, zero filled |
| Public peak fuel per frame | 1,074,756,366 |
| Server mean ATE, supplied by Sebastian | **4.55 m** |
| Server completion | 12/12 episodes, 1,200 frames each, zero filled |
| Server reported peak fuel | 1.1 billion per frame |
| Prepared original dev, same seed | 1.054 m |

The public manifest lists ten 60-second flights in **one** ProcTHOR-Train-1 scene. That scene is absent from B-D0's training manifest and present in the expanded native campaign training roster. The older Stage 5 EKF recorded **4.662 m** on these ten public flights. The identity and motion mix of the server's twelve episodes remain unverified here. [Public replay results](results/eval/public-b-d0-wasm.json) · [Pinned public manifest](https://huggingface.co/datasets/conta-shards/viobench-public/blob/eecdfdf2502fa50c30bdde17a809d31cc2a9bb6b/metadata.json)

The local artifact SHA-256 is `844f358bc733508f440a36ab30632d997b18ff513b56866c02bd832402dcd56c`, exactly matching Sebastian's submission record. Initial raw parity covered two campaign-dev parents and both crop origins, so it did not exercise 1,200 continuous frames. We added four 1,200-frame raw campaign-dev replays using the exact submitted Wasm, the C++ host port and the PyTorch checkpoint.

| Local flight | First 600 frames | First 1,200 frames |
| --- | ---: | ---: |
| HSSD benchmark, 60 s parent | 0.856 | 1.205 |
| ProcTHOR benchmark, 60 s parent | 0.926 | 1.289 |
| HSSD benchmark, 90 s parent | 1.497 | 1.687 |
| ProcTHOR independent yaw, 60 s parent | 5.037 | 7.509 |

All four passed parity, and the largest PyTorch–C++ trajectory separation was **1.12 μm**. The duration and motion sensitivity is measurable locally. The four flights do not establish how much of the server gap each factor explains. No 60-second HSSD independent-yaw parent was available in campaign dev. [Long-horizon parity results](results/eval/long-wasm-parity.json)

## Data and accuracy comparisons

Seven paused runs were resumed at complete checkpoints. The other two B-D2n seeds had already finished. All N1, N2 and B-D2n seeds completed 36 epochs.

| Arm | Original dev | Ordinary dev | Dev static | Dev moving | Proxy 30 s | Campaign 30 s | Campaign full |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B-D0 control | 1.095 | 0.921 | 1.046 | 1.144 | 1.276 | 1.353 | 1.871 |
| N1 native campaign | 1.164 | 1.076 | 1.149 | 1.179 | 1.302 | 1.219 | 1.633 |
| B-D2n expanded proxy/native share | 1.341 | 1.019 | 1.331 | 1.350 | 1.186 | 1.425 | 2.030 |
| N2 expanded proxy plus native campaign | **0.933** | 1.007 | **0.871** | **0.995** | **1.110** | **1.007** | **1.391** |

| Arm | ProcTHOR campaign 30 s / full | HSSD campaign 30 s / full |
| --- | ---: | ---: |
| B-D0 | 1.491 / 2.009 | 1.215 / 1.732 |
| N1 | 1.340 / 1.732 | 1.097 / 1.534 |
| B-D2n | 1.743 / 2.490 | 1.108 / 1.571 |
| N2 | **1.126 / 1.477** | **0.888 / 1.304** |

N1 improved the original-dev backward/lateral subset from **2.136 to 1.690 m** but missed both original-dev gates. N2 cleared the required 10% overall dev improvement and improved both campaign catalogs. Its ordinary-dev regression keeps it from replacing B-D0 under the declared rule. The separate ordinary campaign-dev population improved to **0.938 m** from **1.161 m** at 30 seconds. [N-series replay reports](results/eval/n-series/)

### Evaluation coverage

| Roster | Replays | Independent parents | Scenes | Backward/lateral replays | Backward/lateral parents |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original dev | 14 | 7 | 6 | 2 | 1 |
| Campaign ProcTHOR | 60 | 30 | 6 | 8 | 4 |
| Campaign HSSD | 60 | 30 | 15 | 2 | 1 |
| Proxy validation at 30 s | 69 | 68 | 12 | 31 | 31 |

The nominal and five-second campaign crops share about **25 seconds** of footage. Only **39 of 60** five-second crops begin above 0.1 m/s. Two of the five hard-motion moving crops meet that speed. Start labels in historical reports denote the crop origin. The new protocol would also report actual start speed.

The proposed stress set retains campaign dev for continuity and adds **192 independent 60-second flights**, 12 per catalog × condition × start cell on at least 16 fresh scenes per catalog. The four conditions are ordinary motion, backward/lateral motion, independent yaw and low-texture corridors. A **32-flight feasibility pilot** comes before roster freeze. Each parent supplies one scored reset, with continuous 30-second and 60-second scores and scene-level uncertainty. All 84 reserved campaign test flights remain excluded.

Our existing campaign already generates original trajectories with the native VIOBench simulator. Additional fresh scene assets are required because the installed ProcTHOR Train200 and HSSD Train125/Val43 scenes are already assigned or represented in the ledger. Additional ProcTHOR-10K or HSSD assets require compatible geometry, source provenance and split checks before enrollment. [Coverage audit and full stress protocol](EVALUATION_COVERAGE.md)

### Training coverage and matched follow-up

The separate training-data audit found **592 native training parents**, **256 scenes** and **29,460 configured seconds**. ProcTHOR contributes 394 parents, including 110 independent-yaw parents. HSSD contributes 198, including 45 independent-yaw parents. There are 160 backward-eligible parents and 316 lateral-eligible parents over complete flights. N2 already draws about 82% of backward windows and 87% of lateral windows from the native campaign.

The thin spot is motion immediately after reset. Within the first second of the nominal crop, backward windows are available in **49 ProcTHOR and 23 HSSD scenes**. Lateral windows are available in **two ProcTHOR and zero HSSD scenes**. The five-second crop has substantially more support in both catalogs.

`N2-early-native-x3` keeps the N2 dataset and numerical recipe fixed at 36 epochs, 244 windows per epoch and 4,392 updates. It retargets eligible hard-motion samples earlier in the crop while preserving the motion kind, domain, catalog and crop budgets. All **108** seed/epoch plans passed dry-run coverage checks. The three seeds move **411, 414 and 405** of 8,784 windows, respectively. Compare matched seeds using the ordinary guardrail and catalog/start breakdowns. A separate **64-flight** training-only signed-lateral pilot was proposed for the actual coverage gap, with observed motion requirements before using its data. It has not been generated. Branch `odometry/data-coverage` at `12a6655`.

## Attitude, fusion and OpenVINS

### Learned and visual attitude

With true body velocity, the existing attitude path yields **0.530 / 0.967 m** on campaign dev at 30 seconds / full duration. Ideal yaw correction lowers these values to **0.144 / 0.209 m**. Ideal tilt correction alone gives **0.490 / 0.909 m**. Bypassing rolling gyro calibration gives **0.478 / 0.783 m**, accounting for part of the error. The oracle uses truth only to attribute the error.

The causal visual test freezes the three B-D0 velocity sequences. It uses a small-rotation fit on low-flow pairs and translation-aware essential geometry on higher-flow pairs with cheirality and parallax gates. Its comparison changes only the rotation used to integrate those velocities.

| Set | Overall gyro → visual | Static gyro → visual | Moving gyro → visual |
| --- | ---: | ---: | ---: |
| Original dev | 1.095 → 1.086 | 1.046 → 1.036 | 1.144 → 1.136 |
| Campaign dev 30 s | 1.353 → 1.345 | 1.242 → 1.234 | 1.465 → 1.457 |

The **0.79%** original-dev gain missed the 10% gate. A hybrid that re-anchors at accepted visual intervals using frozen B-D0 velocities is implemented and gated. The three learned gyro-bias correction runs use their own velocities for the separate qualification. They will report static and moving ATE, proxy validation and both campaign catalogs. A compiled-recipe attitude variant is implemented and held. [Frozen-velocity visual replay reports](results/eval/visual-attitude/)

### Native C++ OpenVINS

All arms used the same 120 campaign-dev crops, with causal calibration and IMU delivery. Unavailable poses are counted as zero until initialization, with last estimate held on subsequent missing frames. Earlier uncalibrated scores were discarded after discovering that the wrapper had omitted identity IMU fields normally loaded by the upstream YAML parser. The calibrated on/off measurements reproduced exactly when instrumented.

| Stationary-update mode | Mean ATE | Static | Moving | Initialized static / moving crops |
| --- | ---: | ---: | ---: | ---: |
| Off | 2.843 | 2.726 | 2.960 | 0 / 0 |
| On | 2.837 | 2.709 | 2.964 | 47 / 10 |
| Inertial-only stationary detection | 2.881 | 2.798 | 2.965 | 47 / 10 |
| Still-start initializer only | 9.254 | 13.816 | 4.691 | 47 / 10 |

- Turning stationary updates off also activates OpenVINS's jerk requirement for static initialization. Dynamic initialization reported insufficient rotation on **117 of 120** crops and insufficient feature support on **103**, with overlapping reasons.
- With updates on, **17,548 of 19,490** valid frames above 0.2 m/s received a stationary update. Removing the visual disparity override barely changed this, to **17,474**. Accepted stationary updates skip the ordinary clone and visual-update path.
- Keeping the same initializer and suppressing post-init stationary updates left the same valid frames and exposed drift. MSCKF used a feature on **11,116 of 29,000** update-stage frames, and on **37 of 573** on the worst crop. This bounds what turning off stationary updates alone can accomplish.
- One native OpenCV exception on the same crop was retained in every arm. No arm qualified for Wasm fuel measurement. The original dev raw archives are unavailable on this machine, so this comparison used campaign dev only.

Branch `odometry/openvins` at `4c3381e` contains the C++ harness, diagnostic source and per-crop results. [OpenVINS initialization documentation](https://docs.openvins.com/namespaceov__init.html) · [OpenVINS stationary update documentation](https://docs.openvins.com/update-zerovelocity.html)

### EKF and iterative refinement

The fixed EKF was calibrated on training crops before replay. It scored **1.129 m** versus **1.095 m** on original dev, with a regression in every seed. The ordinary subset worsened from **0.921 to 1.001 m**. The 30-second proxy score improved from **1.276 to 1.253 m**, while both campaign catalogs regressed. Uncertainty training stayed gated. Branch `odometry/ekf` at `f3ae1c8`.

Frozen-feature refinement with three update steps improved dev from **1.095 to 1.078 m**, proxy from **1.276 to 1.269 m**, and campaign dev from **1.353 to 1.351 m**. It missed the 10% dev gate. C99/Wasm parity passed on the isolated refinement kernel. Kernel-only peak fuel was approximately **229k** for one step and **561k** for three, distinct from whole-model fuel. Branch `odometry/refine` at `2f0c5ba`.

## Throughput, architecture and deployment

| Training configuration | Warm epoch | Startup or first epoch |
| --- | ---: | ---: |
| Original single-H100 control, 122 updates | 103.02 s | — |
| Eager prefix scan and preloaded recipe, 122 updates | 7.04 s | 8.44 s first epoch |
| Compiled correlation recipe, 122 updates | **4.83 s** | 75.52 s first epoch with cold compile |

The compiled recipe combines an associative scan, preloaded shards, BF16/TF32, batched dev replay, channels-last CNN, fused AdamW and compiled correlation. Across three 36-epoch seeds it improved dev **1.095 → 1.091 m**, ordinary dev **0.921 → 0.906 m** and proxy 30-second ATE **1.276 → 1.259 m**. It is opt-in on `odometry/throughput`.

| Same global batch and updates | 1 H100 | 2 H100s | 4 H100s |
| --- | ---: | ---: | ---: |
| Warm epoch | 4.20 s | 2.48 s | 1.74 s |
| Speedup | 1.00× | 1.69× | 2.42× |
| GPU-seconds per epoch | 4.20 | 4.96 | 6.94 |

The four-H100 run had about 60.5% strong-scaling efficiency. The distributed benchmarks used NCCL peer-to-peer after disabling NVLS to recover from CUDA error 802. Independent single-GPU seeds and distinct experiments therefore make better use of this workload's available GPUs when throughput across results is the priority. Branch `odometry/throughput` at `78fd8d3`.

The CUDA replay evaluator now loads each checkpoint once and batches independent variable-length flights. On 26 dev replays, it reduced inference from **10.68 s to 4.46 s**, with maximum ATE change **0.035 mm**. The learned-attitude evaluator reduced its 14-replay check from **4.30 s to 1.10 s**, with maximum ATE change **0.0085 mm**. Use `--batch-replays 1` for the original serial numerical path. Metered Wasm evaluation uses CPU processes so it executes the actual guest binary in Wasmtime.

Doubling compiled D0 from 36 to 72 epochs improved dev **1.091 → 1.030 m**, ordinary dev **0.906 → 0.849 m**, proxy 30 seconds **1.259 → 1.219 m**, and campaign full **1.832 → 1.794 m**. Full-duration ProcTHOR rose slightly while HSSD improved. The 5.5% dev improvement did not trigger the predeclared 144-epoch arm. Branch `odometry/long-budget` at `dfc4846`.

The original eight interrupted hyperparameter jobs finished. The queued 21-configuration, two-seed screen transferred to the validated compiled recipe under a distinct tag and with its own matched control. Up to two qualifying finalists advance to 36 epochs across three seeds. The narrow CNN's completed 12-epoch screen was **1.295** versus **1.312** for its paired base using training-time selection scores. Direction differed by seed. This supports finishing the declared comparison before drawing an architecture conclusion.

The B-D0 C++17 FP32 port reproduces prepared and raw inference. The opt-in SIMD pilot reduced matched peak fuel **1,074,754,835 → 861,235,415 per frame**, a **19.87%** reduction with bitwise-equal pose and twist across 12 paired seed/crop replays. The CNN accounts for **99.5%** of counted MACs. The historical small EMA peak is **16.93M fuel** on its separate roster, leaving roughly a **51×** fuel gap even after SIMD. Branch `odometry/deploy` at `abfe47a`.

Integer inference remains unmeasured. A bounded first test would quantize CNN weights and activations to int8 with int32 accumulation, then compare the same replays for ATE, frame completion and peak fuel. A narrower or lower-resolution CNN can reduce arithmetic before quantization. A first quantization pilot is estimated at half a day to a day, and a smaller validated C++/Wasm candidate at another day or two if the model preserves accuracy. These are implementation estimates. The **0.5 m** research target has no established timeline.

## Live work and decisions

| Workstream | Snapshot | Decision when results arrive |
| --- | --- | --- |
| Learned attitude | Seeds 217 and 219 reached epoch 36. Seed 218 reached epoch 35. Batched replays queued and shard cache staged. | Apply dev, ordinary and proxy gates. Measure peak Wasm fuel only for a passing deployable candidate. |
| N2 early-window resampling | Three seeds running on GPUs 1–3, roughly epochs 3–6 of 36. | Compare against original N2 at equal budget. Use the catalog/start results and coverage audit to decide whether to generate the 64-flight pilot. |
| Fast hyperparameter sweep | GPU 4, narrow arm screened, wide and remaining arms in progress. | Promote qualifying paired finalists as declared. |
| OpenVINS, visual attitude, fixed EKF and refinement | Comparisons complete. | Results support investigating initialization/track support if revisiting OpenVINS. Other arms remain gated. |
| Fresh stress set | Design and coverage audit complete. Fresh roster and simulation feasibility pending. | Resolve new scene assets, lock split-safe enrollment and score frozen candidates. |

No child Codex turns were active at the last agent check. The data/throughput owner completed its work, attitude and hyperparameter agent turns hit a Codex usage limit, and the CLI workers for EKF, refinement and deployment completed. Detached training and replay jobs continue independently. The GPU 0 service was left alone.

The main decision is whether to prioritize **robustness at 60 seconds**, **Wasm fuel**, or both in a compact candidate. The evidence supports completing the current learned-attitude and resampling comparisons, establishing coverage on fresh independent flights, and prioritizing a smaller CNN before putting substantial effort into quantizing the full FP32 model. The new stress set and the public long-horizon run provide distinct checks before any reserved test evaluation.
