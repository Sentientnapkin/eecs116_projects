# Provided OpenVINS reproduction and controlled adaptations

Work started 2026-11-19 UTC. This report supersedes the interpretation of the earlier upstream OpenVINS wrapper, not its measured results. Work is in isolated worktrees; no submission, remote push, reserved-test scoring, or unrelated-job interruption is authorized.

## Source identity and verified implementation

Provided source: https://github.com/jonas-eschmann/viobench/tree/9b1b07906aff5a3e6f00155e7aecf967d90aa960/viobench/solution/examples/native/openvins

Isolated checkout: `/data/backups/rganapa/Sebastian/viobench-provided-openvins`.
The prior `odometry/openvins` experiment used upstream OpenVINS through our own wrapper. It did **not** evaluate this provided solution. Its failures cannot establish the quality of this baseline.

Source inspection confirms in `solution.cpp`: 0.8 s static initializer, 5 degree dynamic excitation threshold, per-sample white-noise conversion by sqrt(200), continuous-time bias random walks, static accelerometer prior sigma 0.2/sqrt(3), two frontend instances and three smoother hypotheses. The README documents rotation-aware startup, gyro-compensated forward/backward KLT, direct keyframe matching, and a 2.4 s fixed-lag smoother. `fixed_lag_vio.h` sets 0.2 s keyframe interval and six solve iterations. These are source facts, not reproduced accuracy claims.

The pinned README reports median unaligned ATE 0.849 m across eight 120 s recordings, with no held frames; this differs from our ten-flight 60 s public roster. It reports 224 M median frame fuel and 2.648 B p95 (medians of episode statistics), **not peak fuel**. Those figures must not be compared directly with our mean ATE or maximum frame fuel. The arithmetic mean of the eight rounded ATE entries is 1.047 m; this is a calculation from the README table, not a local reproduction.

## Pre-result comparison policy

Keep historical selection gates unchanged: three matched learned seeds 217/218/219, at least 10% lower mean original-dev unaligned ATE and at most 5% ordinary original-dev regression, then proxy and campaign catalog checks. A deterministic baseline requires one reproduction, not seed repetition. Public is a development diagnostic sharing one scene with expanded campaign training. An exploratory attitude replay cannot qualify a complete deployment by itself.

For each raw comparison use identical archive bytes, camera/IMU calibration and timestamp delivery, reset/crop origin, frame counts and truth convention. Prefix scores come from continuous trajectories, without resetting at 30 s. Explicitly distinguish first 600 frames from a time-inclusive <=30 s mask (which can contain 601 frames). Use identical masks within each comparison. Report available-duration caps separately from complete 60 s populations. Never compare differently sized populations as matched results.

Report equal-flight mean of per-flight sqrt(mean squared position distance), with no fitted alignment. Retain failures: zero position before available output, hold last position for subsequent missing frames, and report filled/completed frames separately. A finite zero translation returned by a guest during startup is a guest output, not evaluator filling; measure initialization separately from ABI completion. Report maximum **whole-guest step fuel**, alongside initialization fuel when available. Group by ProcTHOR/HSSD, historical crop group, measured initial-speed bin, motion, scene and parent. Overlapping crops are not independent trials.

## Live audit and current evidence

At initial audit GPUs 1–3 retained three N2 early-window training jobs; GPU 4 retained four promoted hyperparameter jobs; learned-attitude training processes also persisted. GPU 0 hosted its existing service. None were stopped. Root disk is full; new checkouts/builds/results use the Sebastian NFS subtree or local tmpfs.

New completed learned-attitude comparison (agent audit): three-seed original dev 1.1440 vs B-D0 1.0950 m, ordinary 0.9811 vs 0.9215 m, proxy30 1.3249 vs 1.2765 m, campaign30 1.3862 vs 1.3534 m, full 1.8204 vs 1.8706 m. It fails original gates. N2 remains the strongest completed measured accuracy candidate at initial audit and remains disqualified under its ordinary-dev guardrail. New jobs must be checked again before final selection.

## Pending measurements

Unchanged provided build/checks and exact guest public/campaign replays are in progress. Two separately predeclared frozen-velocity bias-policy ablations are owned by the adaptation worktree. No new candidate is qualified by this preliminary report.

## Build investigation

The first unchanged `viobench bundle` failed during automatic OpenCV runtime preparation, before compiling the estimator. The runtime recipe configured its host CPython with inherited WASI clang; `config.log` records `./conftest: cannot execute binary file: Exec format error` (exit 77). The corrective action is to run the unchanged runtime recipe directly with host `CC=/usr/bin/gcc CXX=/usr/bin/g++`, then rerun unchanged bundling to reuse its OpenCV libraries. The original failed log is preserved as `build-initial-failed.log`. This is an environmental build repair; no estimator source change is authorized as an unchanged reproduction.
