# Dataset and error tail: the server-calibrated VIOBench benchmark

All sources are local files (no web sources). Paths are absolute. Numbers I computed myself come from a script at /data/backups/rganapa/Sebastian/tmp/claude-1000/-data-backups-rganapa-Sebastian-eecs116-projects/b6c1eecc-bd43-4dc8-9783-b32fe49af7c1/scratchpad/tail.py. It reads the per-flight scores.json files and the per-flight metadata JSONs listed below. Metric throughout is mean unaligned ATE in metres.

## Which dataset is it, where is it, how big, how was it built?

### Takeaway
The dataset is the "server-calibrated benchmark" from commit a9f29e0 (2026-11-20). It is a pool of 882 simulated VIOBench flights, and 171 of them are the calibrated benchmark selection. Half of the selection starts mid-flight, and the flights are speed-boosted so mean path is about 56-60 m, matching the course server. It is a private Hugging Face draft, `SentientNapkin/viobench-server-calibrated`. It is not a new sensor dataset. It uses the standard VIOBench archive format. There is also a separate untracked 6-flight "mid smoke" test set.

### Cited Findings
- **Commit and files.** Commit a9f29e0 "Server-calibrated benchmark: speed-matched pool, mid-flight starts, two-anchor calibration, failure analysis" added these files — /data/backups/rganapa/Sebastian/eecs116_projects/research/server_benchmark.py, bench_eval.py, failure_analysis.py, bench_pipeline.sh, release_benchmark.py, configs/server_fast_pool.json, configs/server_fast_mid_pool.json, configs/server_observed.json, and results/eval/server-benchmark/{calibration,selection,failure-pool,failure-selected}.{json,txt}.
- **Pool size.** The calibrated pool is 882 flights (441 `fast-*` static-start flights, plus 441 `fastmid-*` mid-flight-start flights). Each is one 60 s, 1200-frame episode. — /data/backups/rganapa/Sebastian/eecs116_projects/research/results/eval/server-benchmark/selection.txt and failure-pool.txt ("882 flights; pool zero-ATE mean 3.226" in the latter), plus configs/server_fast_pool.json and configs/server_fast_mid_pool.json (441 flights each). On disk, /data/backups/rganapa/Sebastian/gen/raw-fast/bench holds 882 json+zip pairs (249 GB for all of gen/raw-fast).
- **Selection.** 300 draws from the pool gave 171 distinct flights. Flights are weighted (`draws`) so the weighted extent (zero-motion ATE) is 4.526 m (server 4.694 m) and the weighted path is 60.2 m (server 59.6 m). Effective sample is about 90. Unweighted, the 171 flights have path mean 56.2 m (range 31.5-78.2, median 56.6) and zero-motion ATE mean 4.12 m. — calibration.txt and my computation.
- **Selection method.** Selection uses only truth statistics (extent and path length), with no guest result involved. Scene-balanced base weights are exponentially tilted on each flight's extent and path length. — /data/backups/rganapa/Sebastian/eecs116_projects/research/release_benchmark.py (README template) and server_benchmark.py docstring.
- **Where the selection lives.** `selected` is a list of 171 ids in calibration.json. Hard links are in /data/backups/rganapa/Sebastian/gen/raw-fast/selected. The packaged release is /data/backups/rganapa/Sebastian/baselines/bench-release (171 episodes, 54 GB, with manifest.json, results.json, README.md and code/). Per-guest scores are in /data/backups/rganapa/Sebastian/baselines/bench-fast/{selected,full}/<guest>-<hash>/scores.json. Only b_d0 and dead_reckoning have `full` scores, so the full 882-flight pool stats are partial (b_d0 n=613 in failure-pool.txt).
- **Server anchors.** Calibrated from the server's 12-episode `private_stage2`, using published scores only. The identity-pose baseline `cpp_minimal` scores 4.694 m, which equals mean RMS distance of truth from start and acts as an extent anchor. Server per-episode path length is 39.5-80.4 m, mean 59.6 m, versus about 18 m for the public set and about 16-17 m for our earlier default-spec pool. — /data/backups/rganapa/Sebastian/eecs116_projects/research/configs/server_observed.json and the memory notes (server-baseline-anchors, server-flight-distribution). Hidden episodes were never downloaded.
- **Generation spec.** Upstream VIOBench defaults (60 s, 48 waypoints, hover, FOV 120 +/- 15 deg, nominal camera, upstream IMU noise), except the planner speed settings. Pool configs use `task_overrides` such as CRUISE_SPEED_MIN/MAX 3.0-4.5 (setting K) or 4.0-6.0 (setting K2), MAX_ACCELERATION 6-8, MAX_JERK 30-40, MAX_YAW_RATE 2.0, ROADMAP_SPACING 1.0, CONNECTION_DISTANCE 6.0. The default planner (0.45-0.8 m/s) cannot exceed about 48 m in 60 s. In the selection, setting K2 has 95 flights and K has 76. — /data/backups/rganapa/Sebastian/eecs116_projects/research/configs/server_fast_pool.json and /data/backups/rganapa/Sebastian/gen/raw-fast/bench/*.json.
- **Mid-flight starts.** In `fastmid-*` flights the flight is generated longer (about 66-82 s) and the first `crop_start_s` seconds are cropped. Offsets in the selection run 3.4-39.5 s, and exactly 50% (86 of 171) of selected flights are mid-flight. Scored length is still 60 s / 1200 frames. Whether the server's flights start mid-route is unknown. Smoke config: /data/backups/rganapa/Sebastian/eecs116_projects/research/configs/server_mid_smoke.json (untracked, 6 flights, data in /data/backups/rganapa/Sebastian/gen/raw-midsmoke, 1.3 GB).
- **Format and streams.** Official VIOBench archive zip (about 280 MB each, 640x480 camera at 20 Hz, 1200 frames) plus a sidecar JSON with scene, seed, sha256 and an `audit` block. `viobench evaluate x.wasm <dir>` runs them directly. Audit fields: travel_m, zero_motion_ate_m, speed_p10/50/90, hover/backward/lateral/vertical/turning/dark/flat fractions, flags. I did not open a zip, so the IMU and ground-truth stream layout is inferred from the format being "official", not verified.
- **Scenes.** Selected groups are seen/procthor 57, seen/hssd-train 44, dev/hssd-val 33, clean/procthor 21, dev/procthor 16. `clean` scenes (ProcTHOR 150-161 and 176-179) are in no training split. Learned-model results on `dev` and `seen` scenes are optimistic. Flags in the selection: 4 `textureless`, 1 `dark`, and 166 unflagged. The 84 reserved campaign-test flights are excluded.
- **Superseded earlier pool.** /data/backups/rganapa/Sebastian/gen/raw-bench (213 GB, 649 episodes, default-spec scenes) and /data/backups/rganapa/Sebastian/baselines/bench-pool (427 flights scored) are the earlier default-speed pool and are older than the fast pool. The release README still says "171 raw episodes (171 of them form the benchmark)".
- **Other directories.** /data/backups/rganapa/Sebastian/eecs116_projects/flights_gpu (1.3 MB) holds only logs and calibration output, and gpu_kit (248 KB) holds generation scripts. Neither is data. research/data (237 GB) is training data (native campaign etc.), not the benchmark.

### Inferences
- The only candidate that matches "just built" is the fast pool plus the 171-flight selection. Alternatives I considered and rejected: gen/raw-bench (older default-speed, README is partly stale), gen/raw-midsmoke (a 6-flight smoke test), and research/data/native-campaign (training campaign).
- Status caveat. The git-tracked commit holds results, but gen/raw-fast has 249 GB and `full` scores exist only for 2 guests. Someone should confirm which directory the team considers the release (probably baselines/bench-release or the HF repo).

### Gaps
- I did not check whether the HF upload has actually happened (the script supports --no-upload). I could not verify the zip's internal stream layout without opening zips.
- The server's actual flight spec is unknown; speed settings are inferred.

## Per-flight ATE tail for N2 (kf-grid / seed217) and for the baselines

### Takeaway
Learned models (N2, B-D0, bd0_*) have a light tail on this dataset: the max is about 10 m, the median is 3.2-3.5 m, and ATE is dominated by flight extent. VIO baselines (OpenVINS, VINS-Mono) have a very heavy tail: medians of 0.58 and 0.62 m but means of 28.5 and 5.5 m, because of rare divergences. Since the official score is the raw mean, a handful of VIO runs dominate it.

### Cited Findings
- **N2 distribution.** `n2_kfinputs_s217` is the frozen seed-217 kfinputs model, and it is the local run for "N2/kf_grid seed217" (artifact vio_n2_kfinputs_s217.wasm in bench_pipeline.sh). On the 171 flights: mean 3.508 m; percentiles 5/25/50/75/90/95/99/max = 1.86 / 2.51 / 3.24 / 3.98 / 5.51 / 6.28 / 9.22 / 10.38 m. 95%-trimmed mean 3.253 m; 5/95 winsorized mean 3.425 m; one flight above 10 m; top 3 flights carry 5% of total error; worst-10% flights carry 19.8% of error. Calibrated (weighted) mean 3.894 m, with a 90% range for a 12-episode draw of 3.18-4.76 m. — scores.json in /data/backups/rganapa/Sebastian/baselines/bench-fast/selected/n2_kfinputs_s217-8b05b203; calibration.json; failure-selected.txt.
- **Other N2 / learned variants.** `n2_kfgrid` has mean 3.633 m (max 10.9) and calibrated mean 3.960 m. B-D0 has mean 3.844 m (max 10.3) and calibrated mean 4.196 m. bd0_velfusion has mean 3.767 m. dead_reckoning has mean 6.698 m, median 6.35, p90 9.56, max 15.5. Learned models have per-flight rank correlation 0.89 with each other and 0.89-0.93 with the zero-motion ATE (the identity pose error).
- **Where N2's worst flights are.** Its worst flights are all large-extent mid-start HSSD flights, with zero-motion ATE 8-12 m and path 54-76 m. Examples: fastmid-106366371_174226743-01 (10.4 m), fastmid-104862501_172226556-01 (9.4), fastmid-107734146_175999971-01 (9.2), fast-106366371_174226743-01 (8.9). This looks like extent-driven drift, not outliers or failures.
- **OpenVINS.** n=171, mean 28.529 m, median 0.584, p90 9.68, p95 60.98, p99 687, max 2168 m. 17 flights exceed 10 m and 12 exceed 30 m. Top 3 flights carry 77% of total error. 95%-trimmed mean 2.495 m; 5/95 winsorized 5.575 m. Initialization: median 1.2 s, p90 6.0 s, never initialized 3.5%. Mean ATE if init within 3 s is 0.982 m versus 168.5 m for later init. — failure-selected.txt.
- **VINS-Mono.** n=171, mean 5.506 m, median 0.621, p90 3.92, p95 12.5, p99 127, max 225.6 m. 10 flights exceed 10 m. Top 3 carry 52%; worst-10% carry 88% of error. Trimmed(95%) mean 1.029 m; winsorized 1.633 m. Init: median 1.9 s, p90 5.4 s, never 0.6%. Mean ATE if init within 3 s is 3.39 m versus 9.84 m for later.
- **Worst VIO flights.** OpenVINS: fast-ProcTHOR-Train-167-01 (2168 m, init 3.6 s, flat_fraction 0.15), fastmid-ProcTHOR-Train-72-02 (1047 m), fastmid-ProcTHOR-Train-151-07 (533 m, init 19.3 s), fast-ProcTHOR-Train-63-02 (252 m, dark 0.17), fastmid-ProcTHOR-Train-167-04 (194 m, init 50.8 s). VINS-Mono: fast-ProcTHOR-Train-63-02 (225.6 m, init 39.5 s), fast-ProcTHOR-Train-64-01 (151.6 m, init 37.3 s), fastmid-ProcTHOR-Train-167-02 (116 m), fastmid-108294897_176710602-00 (98.6 m, "step failed (status -1)"), fastmid-104348361_171513414-02 (44.6 m, "step failed"). — my reading of scores.json plus flight audits.
- **VIO errors by catalog.** For OpenVINS, mean on ProcTHOR is 50.0 m versus 3.1 m on HSSD train and 1.3 m on HSSD val. For VINS-Mono, ProcTHOR 7.1 m versus about 3.4-3.8 m on HSSD. Flights where both exceed 3 m: 7.6%. — failure-selected.txt.
- **Shared failure.** OpenVINS and VINS-Mono ATEs correlate at Spearman 0.64 across the 171 flights, so they fail on partly the same flights. Learned-model errors correlate about 0 with VIO errors (-0.02 to 0.0).

### Inferences
- Because the N2 tail is thin (max about 3x median), no single N2 flight is a "crazy value". Mean and trimmed mean differ by only about 7%. The raw mean is a stable score for learned models.
- The VIO mean is not a robust estimate of typical behaviour. At 28.5 m, OpenVINS's raw mean is about 49x its median.

### Gaps
- Per-flight scores for the full 882-flight pool exist for only 2 guests. No per-flight result CSV exists for the older guests on the final 171 beyond scores.json. The `failure` field is populated only for some VINS runs.
- I did not inspect trajectory plots, so "cause" labels for VIO spikes are from init time, scene catalog and audit fields, not from direct diagnosis of the filter.

## What causes spikes and which flight features correlate with big errors?

### Takeaway
For learned models, error is mostly flight extent: ATE/extent correlation is 0.88-0.93 and path length 0.55-0.60. Higher turning fraction lowers N2's ATE (-0.4), which is likely extent confounding. For VIO, spikes come from late or failed initialization, textureless or dark views (flat_fraction rho 0.59-0.61), and ProcTHOR scenes; they are not driven by speed or extent.

### Cited Findings
- **Learned models.** N2 seed217 on 171 flights, Spearman of ATE against: zero-motion ATE +0.88, travel +0.60, turning fraction -0.41, hover fraction -0.21, flat fraction -0.10, dark about 0, vertical about 0, start offset +0.01. Per-extent tercile means (N2): low 2.35 m, mid 3.17, high 5.01. — my computation; failure-selected.txt.
- **Mid-flight starts.** For N2, static-start flights (n=85) average 3.303 m and mid-flight-start flights (n=86) average 3.710 m. The ATE-vs-offset correlation is about 0 for N2 (0.01) but 0.27 for OpenVINS and 0.42 for VINS-Mono. The release README says learned guests do slightly worse on mid starts. Extent may differ between the two groups, so this is not clean.
- **VIO guests.** Spearman of ATE against flat_fraction: OpenVINS +0.61, VINS-Mono +0.59. Against dark_fraction: +0.35 and +0.48. Against vertical fraction: +0.36 and +0.31. Against start offset: +0.27 and +0.42. Against hover fraction: -0.29 and -0.36. Against path or extent: about +0.1 and about -0.09. Speed is not a driver. The release README attributes failures to "textureless views and runs that initialize late" in ProcTHOR scenes. — scripts above; README in /data/backups/rganapa/Sebastian/baselines/bench-release.
- **Resets, divergence, initialization.** No explicit reset counts exist in the scores. Initialization timing (`initialized_at_s`) and a `failure` string ("step failed (status -1)") are the only recorded failure signals. Failed steps show up in 2 of the top-5 VINS-Mono outliers.

### Inferences
- The VIO tail is an initialization and texture phenomenon, so it is partly a property of this pool's ProcTHOR scenes. The README itself says the server's flights are "probably friendlier to VIO than this pool", because the server's VIO means are 0.553 and 0.475 m, versus a 12-episode-draw 90% range of 0.66-175 m for OpenVINS and 0.56-18.3 m for VINS-Mono here.
- For N2, to lower the mean the main lever is the large-extent mid-start HSSD flights, not outlier handling.

### Gaps
- Yaw rate and aggressive-motion features are not in the audit (only turning/lateral/backward fractions), so yaw rate as a correlate is untested. Low-texture is measured by `flat_fraction`, `dark_fraction` and the `textureless` flag only.

## Excluding "crazy values": thresholds and robust reporting

### Takeaway
Keep the official score as raw mean unaligned ATE. Report alongside it a median, a 95%-trimmed mean, and a 5/95 winsorized mean, plus the count of flights above a fixed cap. A simple justified cap is about 10 m (a flight worse than about 2-3x the zero-motion/identity-pose error). For learned models this removes at most 1 of 171 flights; for VIO it removes 10-17.

### Cited Findings
- **Identity-pose reference.** The zero-motion ATE (identity pose) averages 4.12 m on the 171 flights and 3.23 m on the full pool. Fraction of flights worse than identity: N2 17%, B-D0 22%, OpenVINS 19.3%, VINS-Mono 9.9%, dead_reckoning 94.7%. — failure-selected.txt.
- **Trimmed means from failure_analysis.py.** Existing reports already show 95%-trimmed means: N2 3.253 vs raw 3.508; B-D0 3.581 vs 3.844; OpenVINS 2.495 vs 28.529; VINS-Mono 1.029 vs 5.506.
- **My additional winsorized values.** Winsorized at 5/95: N2 3.425, B-D0 3.779, OpenVINS 5.575, VINS-Mono 1.633.
- **Max values.** The learned-model max is 10-11 m; dead_reckoning max 15.5 m; VINS-Mono 225.6 m; OpenVINS 2168 m. Counts above 10 m: N2 1, B-D0 1, dead_reckoning 14, OpenVINS 17, VINS-Mono 10. Counts above 30 m: OpenVINS 12, VINS-Mono 7, others 0.

### Inferences
- Proposed rule. Flag a flight as an outlier if ATE > max(10 m, 3x the guest's median), or if ATE exceeds the flight's zero-motion ATE by more than 2x. At this threshold a learned model's mean changes by only about 0.2 m (trim) while VIO's changes by 5-28 m. This is for reporting only, since the official score stays raw. A report would list: raw mean (official), median, 95%-trimmed mean, winsorized mean, n > 10 m, and share of error from the worst 10% (a convenient tail summary already produced by failure_analysis.py).
- The 12-episode server score is itself noisy. The 90% range of a 12-draw is about +/-0.8 m for learned models, so differences under about 0.4 m should not be over-read.

### Gaps
- No agreed threshold in the repo. The 10 m cap and the 3x-median rule are my proposal, not an existing project convention.

## How well does local ATE predict server ATE (calibration anchors)?

### Takeaway
Local numbers calibrate acceptably for learned guests and poorly for VIO and dead_reckoning. The one overlapping learned guest, B-D0, lands inside the interval. The VIO server scores sit near the pool medians, not the means, so the server's flights look friendlier to VIO than this pool.

### Cited Findings
- **Anchor table (calibrated pool mean / 12-episode 90% range / server).** B-D0 4.196 / 3.46-5.06 / 4.55 (inside). dead_reckoning 7.035 / 6.02-8.22 / 9.065 (outside, so the benchmark is easier than the server for this guest). OpenVINS 31.155 / 0.66-175.4 / 0.553 (outside). VINS-Mono 4.716 / 0.56-18.3 / 0.475 (outside). N2 seed217 3.894 / 3.18-4.76 / not on the server. n2_kfgrid 3.960 / 3.23-4.81. bd0_kfgrid 4.193. bd0_velfusion 4.142. The calibration used only extent (4.694) and path (59.6 m), so B-D0, dead_reckoning, and VIO results are held-out checks. — calibration.json and calibration.txt.
- **Server per-episode data.** Server B-D0 seed217 ATE ranges 2.77-6.55 m (mean 4.55); `compact_c_v2` ranges 1.79-12.43 (one outlier, e7aa5aee7fb7, 12.43 m, the 74 m path flight); corr(ATE, travel) 0.55-0.63. Local B-D0-vs-travel Spearman is 0.55, consistent. — /data/backups/rganapa/Sebastian/eecs116_projects/research/configs/server_observed.json and memory notes.
- **Other anchors.** B-D0 scored 1.996 m on the public 10-flight set and 4.55 m on the server (a 2.3x gap), which motivated this benchmark. tiny_cnn server 5.825 and cpp_minimal 4.694 are also published anchors. A "compact camera-direction blended-speed" guest scored 3.98 m on the server. — EVALUATION_COVERAGE.md and the memory notes.

### Inferences
- Applying the B-D0 ratio (server 4.55 / calibrated 4.196, about 1.08) to N2 seed217's calibrated 3.894 m would suggest about 4.2 m on the server. This is a single-anchor extrapolation based on one point, so it carries large uncertainty (the 12-draw range is about 3.2-4.8 m, and it assumes a similar ratio). To reach about 0.5 m, a guest would need a very different regime.
- Server VIO means of about 0.5 m versus local VIO medians of about 0.6 m suggest the server's 12 flights contain no VIO divergences. Treat VIO medians, not means, as the comparable local number.

### Gaps
- Only one learned guest (B-D0) overlaps with a server score, plus the compact c_v2 for which no local copy exists. A second learned anchor on the server would be needed to validate the calibration. The server's scene types and any mid-start use remain unknown.
