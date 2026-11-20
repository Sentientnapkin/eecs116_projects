# Guarded hybrid fusion of geometric VIO (VINS-Mono, OpenVINS consensus, our OpenVINS wrapper) with learned N2/kf_grid: design and implementation path

Scope: internal, repo-based. All sources are local paths under `/data/backups/rganapa/Sebastian/` (repo root `R = /data/backups/rganapa/Sebastian/eecs116_projects`, baselines root `BL = /data/backups/rganapa/Sebastian/baselines`). Metric everywhere: mean (over flights) unaligned ATE RMSE in metres, `ate_full`/`evaluate_trajectory(...).ate_rmse`; never Sim(3). No private server episode was read; "server" numbers below are the course-leaderboard anchors already recorded in `R/research/server_benchmark.py`.

Scratch scripts and outputs I produced (diagnostic, thresholds NOT predeclared): `/data/backups/rganapa/Sebastian/tmp/claude-1000/-data-backups-rganapa-Sebastian-eecs116-projects/b6c1eecc-bd43-4dc8-9783-b32fe49af7c1/scratchpad/{o.py,g.py,g2.py,g3.py,guards*.json}`.

---

## 1. Do the needed saved per-flight trajectories and scores exist? (and what do they give)

### Takeaway
Yes. For all 171 server-calibrated flights, every guest needed (VINS-Mono, provided OpenVINS consensus smoother, N2 kf-input seeds 217/218/219, plus 9 others) has a saved camera-frame pose trajectory (`estimate.tum`), twist (`twist.txt`), fuel and stdout/stderr logs; the truth is in the episode zips. The Stage-0 oracle bound and any offline guard can be computed today with no new runs. What does NOT exist is any per-frame VIO internal health signal (chi2, feature count, covariance), and no trajectory from our own OpenVINS wrapper on this pool.

### Cited findings
- Selected-pool per-guest outputs: `BL/bench-fast/selected/<guest>-<hash>/<episode>/report/logs/<run-hash>/{estimate.tum,twist.txt,fuel.npy,stdout.txt,stderr.txt,trajectory.mp4}` plus `.../report/report.json`, and a per-guest `scores.json` with 171 rows. Verified counts: 171 `estimate.tum` and 171 `twist.txt` for each of 13 guests: b_d0, bd0_kfgrid, bd0_velfusion, dead_reckoning, n2_kfgrid, n2_kfinputs_s217/s218/s219, openvins (`openvins-c6cd96bc`), sp5_combined, sp5_direction, sp5_manhattan, vins_mono (`vins_mono-f368cf2c`).
- `scores.json` row fields: `episode, frames, completed, failure, peak_fuel_per_frame, median/p95_fuel_per_frame, scene, duration_s, ate_30s, ate_60s, ate_full, filled_*, initialized_at_s, full_vio_at_s, ate_reported_full`. `initialized_at_s` is parsed from the guest's own stdout (`... initialized at t=`).
- `estimate.tum` format: `# t x y z qx qy qz qw (camera k in camera 0 frame)`, 1200 rows at 20 Hz; `twist.txt`: `# t vx vy vz wx wy wz` (camera-frame velocity and angular velocity).
- Truth episodes: `/data/backups/rganapa/Sebastian/gen/raw-fast/selected/<episode>.zip` (read with `viobench.tools.datasets.storage.read_episode(path, frames="none")`; `ground_truth_state()`, `frame_times`). The `matrix.json` in `bench-fast/selected` lists the guest hashes and the pool; `BL/bench-fast/full` has b_d0 and dead_reckoning only (882-pool).
- Frame/gauge: every guest outputs `T_c0_ck` (pose of the current camera in the first camera frame); ABI says so in `viobench-provided-openvins/docs/ABI.md`. The per-guest `estimate.tum` therefore share a position origin at frame 0, but each guest's yaw/tilt gauge is only as good as its own attitude (N2: gyro+kf_grid; VIO: after init, anchored by back-integrating IMU, which is the main source of the OpenVINS late-init anchor error per `R/research/approach_splice.py` docstring).
- Existing splice harness: `R/research/approach_splice.py` already builds causal spliced trajectories from two guests' saved `estimate.tum` (`splice`, `to_states`, `handoff`, `handoff_guard`, `late_skip`, `diag_gate_X`, `oracle_min`) and scores them with the pinned `evaluate_trajectory`. It reads `guest.json` from `wasm_eval.py run` output dirs, so it must be pointed at a dir built from `bench-fast/selected` (or generalised, see section 5).
- Our own OpenVINS wrapper (`R/research/openvins_native/replay.cpp`, native-only, host executable; not wasm) has results only on campaign-dev crops (`R/research/results/eval/openvins/campaign-dev-30s.json`: 2.843 m, no init on 117/120 crops due to the 45 degree dynamic-init rotation threshold). It has NOT been run on the 171 selected flights. The provided OpenVINS consensus guest has (scores above).
- Which of VIO's per-frame diagnostics are logged now: VINS prints `initialized at t=...`, gyro-bias calibration, and `still initializing after 5.0 s; metric translation unavailable` to stdout/stderr; OpenVINS prints `[init-d] only N valid features of required M` etc. (observed in `openvins-c6cd96bc/fast-102344193-01/.../stdout.txt`). Nothing else per frame. (Source: provided example `solution.cpp` files, `grep` for fprintf/stderr only found init messages.)

### Measured numbers from saved scores (171 flights, my computation from `scores.json`, `ate_full`)
| Source | Mean | Median | Max | Flights >5 m (from trajectories, scored by me) |
|---|---:|---:|---:|---:|
| VINS-Mono | 5.506 | 0.621 | 225.6 | 16 |
| OpenVINS (provided consensus) | 28.529 | 0.584 | 2168 | 21 |
| N2 kf-input s217 | 3.508 | 3.239 | 10.4 | 25 |
| **Oracle min(VINS, OV, N2) per flight** | **0.759** | 0.464 | 5.0 | 1 |
| oracle min(VINS, N2) | 0.995 | | | |
| oracle min(OV, N2) | 1.146 | | | |
| oracle min(VINS, OV) (no N2) | 2.769 | | | |

Best source per flight: VINS 88, OV 71, N2 only 12 flights. N2 is "best" mainly where BOTH VIOs fail (6 flights have all three >3 m; 13 flights both VIOs >3 m). Sorted worst VIO-min flights: `fast-ProcTHOR-Train-63-02` (VIO-min 225.6, N2 2.14), `fastmid-ProcTHOR-Train-0-01` (59.5, 2.55), `fastmid-ProcTHOR-Train-167-02` (48.5, 3.28), `fastmid-104348361_171513414-02` (9.7, 3.6), `fastmid-103997643_171030747-01` (8.6, 2.2). A guard that only needs to rescue about 6 flights captures nearly the whole gap: the bound is 0.76 m, below the 1.5 m kill threshold stated in `R/reports/Drone VIO ATE approaches.md` (Stage 0), so rank 1 is not ruled out by the bound.
- Init status as a hard rule (diagnostic): VINS if initialized within T s else N2 gives 3.31 (T=3), 3.09 (T=5), 2.80 (T=8); OpenVINS if init<=3 s else N2 gives 1.449 (T=3, 137 flights) but 21.6 at T=5 (some flight with init in 3-5 s that is catastrophic); cascade (VINS if init<=3 else OV if init<=3 else N2) gives 2.90. Init-time alone is therefore not enough.

### Inferences
- The best caused-by-existing-data path is: offline guard on saved trajectories first (section 5), then and only if a guard clears the predeclared bar, build a composite wasm guest.
- Since saved `twist.txt` exists for every guest, VIO-vs-N2 and VINS-vs-OV velocity disagreement can be computed causally from saved data without re-running anything.

### Gaps
- No saved per-frame internal VIO health (chi2/innovation, tracked feature counts, covariance/consensus spread, sliding-window state). Producing it requires instrumented guests (section 4).
- Our OpenVINS wrapper has no pool trajectories; unclear it is useful (117/120 init failures on campaign crops), so probably skip it as a fusion source and use the provided OpenVINS consensus guest.
- N2 s217 is the only seed with a detailed table I read; s218/s219 `ate_full` are in `matrix.json` and `scores.json` and can be used for seed-robustness.
- Whether the server flights start mid-route is unknown; the pool has 86 `fastmid` flights.

---

## 2. One guest versus separate guests

### Takeaway
Evaluate with separate guests combined offline first (already feasible, zero new runs), because the three guests cannot be trivially linked into one wasm: N2/kf_grid needs OpenCV 5.1.0 while both VIO examples link the runtime's OpenCV 4.12. A composite single guest is the end state only if offline guard clears the bar, and the preferred composite design is a thin selector that re-implements the winning offline rule inside one module, built in stages (VINS+N2 first).

### Cited findings
- Current wasm artifact sizes and fuel: VINS wasm 6.71 MB (`bench-fast/.../vins_mono-f368cf2c/.../report.json: solution_bytes 6714426`), peak fuel/frame about 3.96 B on one flight (`report.json`), median wall 94 ms/frame; OpenVINS peak about 4.0 B (server anchor `max_fuel 3955863154` in `R/research/server_benchmark.py`); N2 kf-input peak about 1.74 B (`R/research/NEWEST_MODEL_WASM.md`). Hard limits (report.json): 2e10 fuel per step, 2e11 init fuel, 60 s wall per step, 2 GiB memory, 1,048,576 table elements.
- The sum of peaks (about 9.7 B) is under the 2e10 cap but the three estimators' heavy steps are not known to be uncorrelated; VINS and OV solve Ceres problems on keyframes.
- OpenCV mismatch: `R/research/NEWEST_MODEL_WASM.md` line 34: N2 training used Python OpenCV 5.1.0, "the initial 4.12 port failed long parity, so 5.1.0 was pinned ... and built separately"; `R/research/KF_GRID_PARITY_REVIEW.md`/`FUSION_COMPLETION.md` document further kf_grid wasm-vs-Python parity failures (empty mask to `recoverPose`, 0.051 m native-vs-wasm position difference). VINS and OpenVINS examples bundle with the workspace's wasm OpenCV 4.12 recipe (`viobench-provided-openvins/viobench/solution/examples/native/{vins_mono,openvins}/README.md`).
- The provided OpenVINS example is already a composite: two `VioManager` frontends, three smoother hypotheses, and `consensus_output.h` (geometric median of 3 positions and velocities, rotation mean, causal position correction). VINS-Mono example is a single synchronous estimator (no loop closure/pose graph).
- The wasm ABI (`viobench-provided-openvins/docs/ABI.md`): `abi_version, alloc, frame_width, init(json,size), step(t, frame, imu, imu_count, out[13])` with `out = [x y z qx qy qz qw vx vy vz wx wy wz]` (pose T_c0_ck, twist in camera frame). 320x240 or 640x480 RGB, imu 10 rows `[t, ax, ay, az, gx, gy, gz]` at 200 Hz, 20 Hz frames. Any non-finite value, all-zero quaternion or non-zero status ends the episode and scores the rest at origin; a combined guest must therefore wrap each sub-estimator in try/catch (VINS and OV examples already catch and return -1; OV `std::exit` traps).
- N2 guest entry: `R/research/native_odometry/guest.cpp` (`init` parses width/height/fx/fy/cx/cy/T_cam_imu, `step` writes via `Estimator::step`, position from `0.5*dt*(v+last_v)` trapezoid integration at `odometry.hpp:719`, quaternion at line 756).
- Prior parity discipline: `R/research/native_odometry/replay.py`, `test_guest.py`; structural guests built by `R/research/structural_pipelines/build.py` patch an isolated copy of `native_odometry/` (pattern to copy for a composite build).

### Inferences
- Three options:
  A. Separate guests, offline combination (recommended first; no runtime risk, uses saved outputs). Limitation: no access to internal VIO states, and cannot test closed-loop actions (VIO re-initialisation from N2 state, resetting VIO), because the VIO never receives N2 information.
  B. Two-process composition is impossible in the ABI (one wasm module per episode); the only runtime-combined form is one module that links all code.
  C. One composite guest. Cleanest sequencing: (C1) VINS + N2 where N2 is run at 1.7 B peak but needs OpenCV 5.1 (kf_grid) while VINS needs 4.12. Pragmatic escape: N2 variant without kf_grid visual input (gyro-only, `native_odometry` default, no OpenCV; but that is the older B-D0-type inputs, weaker, about 3.8-4.5 m), or build VINS against OpenCV 5.1 (unverified, large port risk), or namespace-isolate the two OpenCV builds in separate static libs (symbol clashes likely). Treat this as the main engineering risk of option C and do it only after offline evidence.
- Closed-loop interventions (re-init VIO from N2 state) are only possible in C (or by patching the VIO guest alone with a deterministic hint signal, not available from N2).

### Gaps
- Not tested: whether VINS 4.12 + N2 kf_grid 5.1 can coexist in one wasm. Not tested: whether N2 without OpenCV 5.1 (non-kf_grid) is an adequate fallback in the guard (the 171-pool table suggests kf_grid helps, `n2_kfgrid-089559db` and `bd0_kfgrid` are saved on the pool so it can be quantified offline for free).

---

## 3. Causal gating and selection signals

### Takeaway
Available now causally from saved data: VIO init time/status, VIO-reported pose/twist, VINS-vs-OV disagreement, VIO-vs-N2 displacement and velocity disagreement, speed sanity, and tracked-feature/initialisation log lines. NOT saved: chi2/innovation, feature counts, covariance. My first measurements show N2 is a weak referee (its own error is about 3.2 m median, growing with speed), whereas VINS-vs-OpenVINS agreement is a strong signal.

### Cited findings (signal inventory)
| Signal | Where it comes from | Saved today? | Causal? |
|---|---|---|---|
| VIO initialised flag and time | stdout line `initialized at t=` (regex `INIT` in `approach_splice.py`), `initialized_at_s` in `scores.json` | yes | yes (a combined guest knows it at that frame) |
| Pre-init status (VINS "metric translation unavailable", OV "init-d only N valid features") | stderr/stdout | yes (text) | yes |
| VIO pose and twist per frame | `estimate.tum`, `twist.txt` | yes | yes |
| Speed sanity (|v| vs plausible maximum; pool cruise 3-6 m/s; OV takeover transients up to 25 m/s per `R/research/APPROACHES.md`/`approach_splice.py` docstring) | derived from `twist.txt` | yes | yes |
| N2 vs VIO velocity/displacement disagreement | `twist.txt` and `estimate.tum` of both | yes | yes |
| VINS vs OV agreement | both saved | yes | yes |
| N2 attitude drift or kf_grid accepted-window counts | internal to N2 (`kf_grid.hpp`) | no | yes (needs instrumentation) |
| Per-frame optimizer cost / chi2 / innovation | Ceres cost in VINS `Estimator` and `fixed_lag_vio.h` | no | yes |
| Tracked feature count and spatial coverage | VINS `feature_tracker.h`, OV `VioManager` | no | yes |
| Covariance (OV MSCKF state cov; consensus spread of 3 hypotheses via `consensus_output.h`) | internal | no | yes |
| Visual flat fraction (Spearman +0.59..+0.61 with VIO error per project notes) | image statistics, computable in a guest | no (not logged) | yes |

### My measurements on the 171 pool (diagnostic, thresholds swept on the same data, so optimistic; NOT predeclared)
Increment-level gating (take VIO per-frame relative motion if its per-frame velocity is within X m/s of N2's, else N2's):
| Guard | mean ATE (m) |
|---|---:|
| N2 alone | 3.508 |
| cascade VINS->OV->N2, X=0.5 / 1.0 / 2.0 | 3.559 / 3.443 / 2.406 |
| VINS->N2, X=0.5 / 1.0 / 2.0 | 3.561 / 3.453 / 2.466 |
Windowed (2 s) displacement disagreement with N2, sticky trip with ordering (a + b*|d| threshold): VINS->N2 (3.0,0.5) 2.53; VINS->OV->N2 2.36; OV->VINS->N2 2.29; tighter thresholds are worse (3.2-3.5).
VINS-vs-OV agreement guard (2 s window, use VINS when |d_v - d_o| <= a + b*max|d|; otherwise pick the source whose window displacement is closer to N2 if within `big*(1+|d|)`, else N2; re-evaluated every frame, no hysteresis): (a,b)=(0.5,0.1) 1.865; (1.0,0.2) 1.851; (2.0,0.3) **1.741** (median 0.893, 7 flights >5 m, max 29.9). Oracle is 0.759.
Pure init-time hard switches: 2.8-3.3 (see section 1).

### Inferences
- N2 is not a good per-frame referee: at 3-6 m/s cruise a 10-15% velocity-scale error is 0.3-0.9 m/s, similar to VIO transient errors. Tight N2 gates throw away good VIO and lose almost everything (3.4-3.6). So the main discrimination must come from VIO-internal quality and VINS-vs-OV agreement; N2's role is (i) tie-breaker, (ii) bounded fallback when both VIOs fail, (iii) coarse magnitude sanity.
- The VINS/OV consensus guard already moves the pool mean from 5.5/28.5 to about 1.7-1.9 with no tuning discipline; honest expectation after predeclared thresholds and cross-validation is 1.8-2.5. To approach the 0.76 bound, the remaining 7 flights >5 m need to be inspected (are they both-VIO-agree-wrong, or switch lag/transient at takeover?). Switching at increment granularity also splices rotation across sources with different yaw gauge: a switch should compose the new source's relative motion, as `approach_splice.splice()` does, and a rotation-gauge step should be smoothed (section 4, algorithm F).
- Interaction with server: VINS 0.475 and OV 0.553 on the server, i.e. VIO medians; the guard should not cost the friendly case. On the pool, guard medians (0.89-1.05) are above VIO medians (0.58-0.62), so there is a measurable tax from false trips; reduce it with covariance/health signals.

### Gaps
- Whether chi2/feature-count signals separate failures better than the VINS/OV consensus is unknown; needs instrumented guests.
- Statistical power: effective sample is about 90 flights (`results/eval/server-benchmark/selection.txt`); the six all-fail flights and a few catastrophic VIO flights dominate means, so rank guards by paired differences and bootstrap by scene, not by point estimates.

---

## 4. Candidate guard/fusion algorithms (6 concrete + 1 control)

All operate causally on frames 1..k, all consume (a) a VIO pose/twist stream for VINS (V) and OpenVINS (O), (b) N2's stream (N). Pose composition rule for any switch at frame j: `T_out(k) = T_out(j) * T_src(j)^-1 * T_src(k)` for k >= j (as `approach_splice.splice`), so the unaffected relative motion is preserved.

- **Control: fixed single guest** (N2, VINS, OV) for reproduction of the table above.
- **A. Hard init-status switch (baseline).** Use V if initialised and healthy; else O; else N. Implementation: a state machine over `initialized_at_s`, speed sanity (reject |v| > ~12 m/s which is above any pool speed), and a permanent trip to the next source on violation. Measured: 2.8-3.3 as pure init rule; expected 2-3 with a speed trip. Cheap and robust; sets the minimum bar.
- **B. Per-frame consensus (geometric-median style).** Treat three velocity/displacement estimates; use `consensus_output.h`'s geometric median of positions/velocities (equal weight, three points) over a 1-2 s window, selecting the source closest to the median; reject when the three disagree strongly and fall to N. This reuses an already-parity-tested primitive, and is the generalisation of the VINS/OV agreement guard measured at 1.74-1.87. Hysteresis: require 1 s of agreement to return; hold the last source otherwise.
- **C. Covariance- (or health-) weighted blending.** Blend relative translation increments with weights w_i proportional to 1/sigma_i^2 where sigma_V from feature count/Ceres cost, sigma_O from consensus spread/MSCKF covariance, sigma_N = a speed-proportional term (0.10-0.15 of |v|, fit offline from truth on dev scenes). Rotation from V/O after init, from N before. Requires instrumentation (section 4.1) because no covariance is saved. Expect gains mostly in transients rather than catastrophic tails.
- **D. EKF: N2 velocity as pseudo-measurement, VIO pose as measurement.** State: position, camera-frame velocity, scale/bias of N2 velocity (3-vector b with random walk), VIO-to-N2 gauge offset (yaw drift correction). Prediction: N2 body velocity integrated (as `odometry.hpp:719`); update with VIO window displacements (gated by chi2 on the innovation, Mahalanobis threshold about 11.3 for 3 dof, 99%) so a catastrophic VIO window is rejected by statistics rather than a threshold. This is the "right" fusion because VIO's drift-free-ish scale corrects N2's yaw/scale drift while N2 bounds VIO failures. The repo's own fixed-EKF-over-learned-velocity regressed (dev 1.095 to 1.129), but that EKF had no geometric measurement; this one does. Expected best median, risk: tuning; `R/research/ekf_experiment.py` is the reusable scaffold.
- **E. Re-initialisation / restart of VIO from N2 state.** On trip, restart VIO (fresh VINS/OV instance) with a seed velocity and attitude/gravity from N2, and splice back when the new instance passes init + N-agreement; this addresses the identified failure mode (init tails, late-init takeover transient up to 25 m/s). Only implementable in the composite guest (or with a patched VIO guest taking a hint). In offline form it can be emulated by running the VIO guest on crops starting at trip times (`wasm_eval.py crop/run`, which is how the campaign crops work) and splicing, which gives an upper bound on what restart can achieve.
- **F. Takeover transient smoothing.** At any switch, remove the position/velocity step: blend the new source's relative motion with the old for a ramp (0.5-1.0 s) or apply an exponentially decaying offset to the output position (as the structural guests do for direction correction: 0.5 s decay, 1 s expiry, past positions never rewritten). Reduces switching cost in all of A-E; check in section 5 as a modifier (on/off), since a position step of a few metres at 60 m paths is costly under mean ATE.
- **G. (Optional) majority/voting with N2 as tie-break only.** If V and O agree use them; if they disagree, choose the one nearer N2 (what I implemented; 1.74-1.87), else N2. This is B in its simplest form and is the recommended first implementation to port.

### 4.1 Instrumentation to add (small patches, no behaviour change; separate wasm builds, parity-tested to be bit-identical in `out`)
- VINS (`viobench/solution/examples/native/vins_mono/solution.cpp`): write to stderr every N frames or per frame: `solver_flag` (INITIAL/NON_LINEAR), tracked feature count, number of features in window, last Ceres cost/iterations, failure-detection trip status if present (I did not verify that the patched solution exposes `failureDetection`; unknown).
- OpenVINS (`.../openvins/solution.cpp`, `consensus_output.h`, `fixed_lag_vio.h`): per frame: number of MSCKF update features used, per hypothesis position/velocity (so consensus spread can be recomputed), smoother cost, initialised flag per frontend.
- N2 (`R/research/native_odometry/odometry.hpp`/`kf_grid.hpp`): per-frame speed, accepted kf_grid window count, gyro-bias estimate norm.
Compact format: one stderr line per frame `TEL f=k <fields>`; the `Sandbox` already stores `stderr.txt` per run in `report/logs/<hash>/`, so no ABI change.

### Gaps
- None of C, D, E is measurable on saved data alone; they need 4.1 instrumentation (C, D) or the composite/crop re-run (E).
- Design D noise parameters have no data yet; derive from truth on the dev scenes (clean scene groups excluded from tuning).

---

## 5. Implementation plan: files, interfaces, offline protocol

### 5.1 Files to create (read-only repo for this task; this is the plan)
- `R/research/guard_fusion/__init__.py`
- `R/research/guard_fusion/traj.py`: loader of one guest's saved estimates for an episode: `load_guest(selected_dir, guest_key, episode) -> dict(t, T (N,4,4), pose13 (N,13), twist (N,6), init_s, stdout, stderr)` using `viobench.tools.runner.score.load_estimates` and the regex `INIT` from `approach_splice.py`; truth loader via `read_episode(zip, frames="none")`.
- `R/research/guard_fusion/guards.py`: guard classes with a single causal interface `Guard.step(k, obs) -> (source_id, T_k)` where `obs` contains only frames <= k (enforce by slicing; unit test truncating the future and asserting the identical past output, like `R/research/test_causal.py`). Algorithms A, B/G, C, D, F as modules; D reuses `ekf_experiment.py`.
- `R/research/guard_fusion/evaluate.py`: runs all guards on the 171 flights, writes `R/research/results/eval/guard-fusion/{per_flight.json,summary.json}` with mean unaligned ATE through `evaluate_trajectory(...).ate_rmse`; reuses the reporting statistics already in `R/research/failure_analysis.py` (median, 95%-trimmed, winsorised, count >10 m, worst-10% share, bootstrap 12-draw range).
- `R/research/guard_fusion/oracle.py`: oracle bound and ablations (oracle3, oracle pairs, best-source histogram, "all fail" list).
- `R/research/guard_fusion/README.md` (predeclaration record: thresholds, rule, kill criteria).
- Later (only after offline bar is met): `R/research/guard_fusion/composite/` with `guest.cpp` (ABI exports as in `native_odometry/guest.cpp`), `build.py` modelled on `R/research/structural_pipelines/build.py` + `package.py` + `validate.py`, `score.py` modelled on `R/research/structural_pipelines/score.py`.
- Instrumented VIO builds: patches kept under `R/research/guard_fusion/telemetry/{vins_mono.patch,openvins.patch}`, built with `BL/vins-mono-9b1b079/build.sh`-style scripts into new output dirs (never overwrite `BL/vins-mono-9b1b079/vins_mono.wasm` or `BL/openvins-9b1b079/openvins.wasm`).
- Modify: nothing in existing modules required; `approach_splice.py` and `wasm_eval.py` are reused, not edited. If run-dir compatibility is wanted, write a one-time `guest.json` per selected guest dir from `scores.json` (`archives` field already lists the zips) instead of changing `approach_splice.py`.

### 5.2 Interfaces
- Offline stream per source: `T_c0_ck` (N,4,4), t (N,), camera-frame twist (N,6), `init_s`. Output of a guard: (N,13) states in the same format as `estimate.tum` so the evaluator treats it as a guest.
- Composite guest ABI: exactly the viobench ABI v1 above. `step(t, frame, imu, 10, out)` calls each sub-estimator in turn with copies of `frame`/`imu` (buffers are overwritten each step), collects (pose, twist, health), runs the selector, writes `out[13]`. Initial state until any source is ready: identity and zero twist. Sub-estimator exceptions must be caught and mark that source dead permanently. Total per-step fuel must stay below 2e10; the sum of observed peaks is about 9.7 B.
- State each guest exposes (current ABI): only the 13-vector. With instrumentation: TEL lines in stderr (offline) or direct C++ accessors (composite).

### 5.3 Offline evaluation protocol (predeclare before running)
1. Inputs: the 171 flights, guests {vins_mono-f368cf2c, openvins-c6cd96bc, n2_kfinputs_s217-8b05b203}, repeated with s218/s219 as the N source for seed robustness. Truth from `gen/raw-fast/selected/*.zip`. No server episodes.
2. Reproduce the three singles' `ate_full` from trajectories; assert equality to `scores.json` within 1e-6 (my run reproduced 5.506/28.529/3.508).
3. Compute oracle bound: mean of per-flight min over {V,O,N} (my value 0.759) plus pairwise oracles, best-source histogram, and the list of flights with all three >3 m. Kill/continue: if oracle3 > 1.5, stop rank 1 (it is 0.759, so continue).
4. Evaluate every guard (A-G) with thresholds fixed in a predeclaration file before scoring. Use cross-validation grouped by scene (e.g. leave-one-scene-group-out over clean/dev/seen and by house) to choose any threshold; report held-out guard means. Do not tune on all 171 flights and report them as results (my numbers in section 3 were swept on all flights and are only an indication).
5. Report: mean unaligned ATE (the official), median, 95%-trimmed, winsorised, count >10 m and >5 m, worst-10% share, paired differences vs best single (VINS) and vs N2 with bootstrap (resample scenes, then flights) and 12-flight bootstrap range to mimic the server draw; also split static (`fast-*`) vs mid-start (`fastmid-*`) and ProcTHOR vs HSSD.
6. Decision rules (proposed, to declare first): guard must beat min of the three singles' means, must lose to VINS on at most a stated fraction of flights, and its median must stay within 25% of VINS's median (to protect the friendly server world where VIO medians of 0.5-0.6 m are the score); transitions must cost less than X m per switch (measure the ATE with and without smoothing F).
7. Then, if the bar is met: add telemetry runs (below), evaluate C and D, then E via crops, then the composite guest, then official `viobench evaluate` through `server_benchmark`/`release_benchmark`-style evaluation on the same 171 archives and, finally, a three-way table with the structural/N2 guests.

### 5.4 What to run (only if telemetry/new data is required; none for step 5.3.1-5.3.5)
- Telemetry rebuilds: build instrumented VINS and OpenVINS with the toolchain in `/dev/shm/sebastian-vio/viobench` (clone pattern in `BL/vins-mono-9b1b079/build.sh`; env-only workarounds in `R/research/provided_baseline/REPRODUCTION.md`), then replay on the 171 selected archives with the same evaluator path that produced `bench-fast/selected` (`R/research/wasm_eval.py run --wasm <instrumented.wasm> --archives gen/raw-fast/selected/*.zip --out <dir>`, or `bench_pipeline.sh` for pool scoring). VINS is about 94 ms/frame median (about 2 min/flight); OpenVINS comparable; 171 flights with 32 workers about 10-20 min wall each, as indicated by the per-flight `elapsed_s` of 178 s for VINS.
- Verify instrumented wasm gives identical `estimate.tum` (bitwise) to the saved run before using telemetry.
- Our OpenVINS wrapper on the pool is not recommended (no wasm, 117/120 init failures); if wanted, `R/research/openvins_native/replay.cpp` via `openvins_eval.py --raw-dev ...` on `gen/raw-fast/selected`, but it is not on the ABI path.
- For E (re-init emulation): `wasm_eval.py crop --start <trip_time>` then `run` of VINS and OV on those crops, then splice (gauge anchored by N2 attitude at trip).

### Inferences
- Priority order by value/effort: (1) oracle plus VINS/OV agreement guard (G/B) with CV thresholds and smoothing F, offline, hours; (2) instrumented telemetry and C/D, a day; (3) composite wasm guest, days, with the OpenCV 4.12/5.1 conflict as the dominant risk; (4) E in composite form.
- Because server VIO medians (0.58, 0.62) equal the pool VIO medians, a guard with median close to 0.9 would cost about 0.3 m on a friendly server draw; the goal 0.5 m is only reachable if false-trip cost is reduced, so smoothing F and health signals matter, and hysteresis should bias toward staying with VINS when VINS and OV agree.

### Gaps
- Telemetry-based algorithms (C, D, E) unmeasured.
- The 7 remaining flights >5 m in the consensus guard (max 29.9 m) have not been examined individually; first diagnostic step is to list them and classify (both VIOs agree but wrong; switch transient; N2 itself bad).
- Parity of the composite versus offline emulation is untested.
- The 3.98 m server submission has no located source (per `R/reports/Drone VIO ATE approaches.md`), so no server calibration of N2-family guests exists; any server expectation is extrapolated.
