# Parallel VIO research initiative — shared brief (Phase 0), 2026-11-26
Read fully before starting. Your track spec is in research/tracks/<your-agent>.md. Work ONLY in
/data/backups/rganapa/Sebastian/gen3/research/<your-agent>/ (your isolated experiment dir; copy sources there).

## 1. Frozen baseline (do not modify these files)
- **Current best (local): "A160ft + Ze0"** — wasm `gen3/agents/sweep/builds/a1_Ze0/solution.wasm` sha256 670bc1da…;
  source `gen3/agents/sweep/baseA160.c` (= GSLV-linejac MSCKF + A160ft velocity-net weights), build tool `gen3/agents/sweep/mk.py`
  (`mk.py NAME "FLAGS" SRC` -> builds/NAME; verify a no-change rebuild reproduces 670bc1da before trusting your build path).
  Flags: `PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0`.
  Replicate nudges (chaos control): `PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0` (_r1), `1.485 / 990.0` (_r2).
  Read-only copy for reference: research/baseline/ (frozen copy of the source + wasm).
- **Best SERVER-verified build:** auto_727 net + `PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0` (sha 9a468ce9,
  gen3/agents/net/builds/g_auto_727_sp10/solution.wasm): server mean ATE **0.586 m**, peak fuel **4.1 M**, Sim3 0.29.
  Other server points: F_sp10 0.664 m @ 4.2 M; GSLV-linejac 1.18 m @ 4.4 M. Ze0 not yet submitted.
  Per-episode server results: eecs116_projects/eecs116_vio/results_*.json (match builds by sha). Hidden-episode statistics:
  eecs116_vio/stage3/probe_decoded.json + eecs116_vio/probe/README.md (episodes 1–12 rooms, 13–18 warehouse, 19–24 forest;
  1200 frames = 60 s; paths 27–97 m; start forward speed −1.7…+2.75 m/s; server rooms turn fast: roll/pitch RMS ~1.15 rad/s).
- **Local numbers (dev set v3val, 358 flights, 3-replicate mean):** baseline raw mean ATE 0.665 m, server-weighted 0.641,
  median ~0.60, >3 m: 0, peak fuel 3.77 M (p95 2.82 M). rooms 0.476 / warehouse 0.841 / forest 0.728; hover 0.692 / mid-flight 0.652;
  free-yaw 0.696 vs normal-heading 0.575; FoV <95° 0.72, >115° 0.60; exposure >35 ms 0.71, 15–35 ms 0.61.
  Error is broad drift, not a tail (worst 10% of flights = 23% of total); warehouse is 42% of the total.
  v1val (120 normal-heading flights): 0.556. Local is pessimistic vs server (≈0.85–0.9 local ↔ 0.586 server for auto_727) — rank only.
- Per-flight eval files: gen3/evals/sw_a1_Ze0{,_r1,_r2}__v3val.json, sw_a1_Ze0_v1__v1val.json (fields: ate, peak, setting_class,
  regime, start, start_fwd_speed, fov_deg, exposure_s, motion_style…).

## 2. Score
Server score = log-log area of (max per-frame WASM fuel) vs (mean unaligned ATE over 24 episodes); fuel axis ~1–24e9 (10.4 decades),
ATE axis 0.001–10.6 m (4 decades). Practical estimate vs baseline: **Δscore ≈ 0.4·log2(3.77M/peak) − 2.2·ln(ATE/0.665)**
(halving peak ≈ +0.28…0.4; +10% ATE ≈ −0.21). NEVER use Sim(3)-aligned ATE as the metric. Peak = MAX fuel on any frame of any flight
(measure it; never substitute FLOPs or mean fuel). Report p95/p99 too.

## 3. Evaluation protocol (frozen sets)
- **Dev set (tune here):** gen3/pools/v3val (358 stage-3 val flights, fixed list pools/v3val_keep.txt) + gen3/pools/v1val (120, regression check).
  Run: `cd gen3 && ../venv-teacher/bin/python -B evalpool.py NAME WASM pools/v3val WORKERS` -> evals/NAME__v3val.json (cached by wasm sha).
  Compare: `python3 score.py evals/sw_a1_Ze0__v3val.json evals/NAME__v3val.json` (paired, bootstrap CI, per class, peak);
  `python3 agents/net/tools/pcmp.py BASE.json NEW.json` (paired d + CI). Replicate tooling: agents/sweep/sc.py, agents/startup/rep.py.
  Prefix ALL your eval names with your agent tag (e.g. `r1_`), never reuse another agent's names.
- **Fast subsets:** agents/startup/pools/mid40 (40 mid-flight flights), or make your own stratified subset in your dir.
- **Held-out local set (DO NOT USE):** the v3 TEST split (s3v3te*, 745 flights, on HF viobench-stage3) is reserved for the final
  integration by the orchestrator only. Never download, train on, or evaluate on it.
- **Server-twin set:** another agent is building gen3/pools/twin24 / twin120 (flights matched to the 24 server episodes). Do not
  tune on it unless the orchestrator says so.
- Single runs are chaotic: screen with 1 run, confirm with 3 replicates (paired bootstrap CI) + v1val check.
- No submissions to the competition server. No uploads, no git commits/pushes.

## 4. Data available (privileged GT for offline work only)
- Flights: EuRoC-style zips: mav0/cam0/data/*.png (640x480 RGB native; the host resizes to the width the wasm requests),
  mav0/imu0/data.csv (200 Hz gyro+accel), mav0/state_groundtruth_estimate0/data.csv (GT pose ONLY: timestamp, position, quaternion w,x,y,z of the
  camera0 frame at frame rate — NO velocity and NO biases stored; derive velocity by differentiating/spline-fitting GT positions;
  true biases are not recorded, so bias oracles must be estimated offline from GT + IMU, e.g. least squares), episode.json (intrinsics fx/fy/cx/cy, FoV, exposure_seconds, T_cam_imu, IMU noise/bias
  params, gravity [0,0,-9.81], pose frame "camera0", order xyz_qxyzw, **timestamp convention "mid_exposure"**, meta incl. start type).
  **No depth maps are stored.** Depth would need re-rendering with the simulator (hyperlux, GPU) or proxies (triangulated GT
  landmarks from GT poses + tracks). Ask the orchestrator before any re-rendering.
- Local: 358 v3 val zips (pools/v3val) + 120 v1 val (pools/v1val). Training flights: ~8–10k stage-3 train flights on HF
  `SentientNapkin/viobench-stage3` (train tar shards; gen3/out/up/shards.json maps ids→shards; per-flight metadata gen3/out/up/*.json).
  Download in batches to your dir, delete after use; shared disk — never hold >100 GB.
- Preprocessed net training cache: gen3/agents/net/cache/train/*.npz + train_meta.jsonl (anchors: low-res frame pairs, GT body
  velocity, rotations, FoV; see agents/netv2/tools/lv4.py for the format) and cache/val (v3val).
- Sim facts: IMU noise accel 0.28 m/s², gyro 0.07 rad/s (per sample); accel bias init ≤0.2, gyro ≤0.02, random walks 1e-3 / 6e-4.
  T_cam_imu: camera z = IMU forward axis (see episode.json). Blur: exposure integrated over 5 ms sub-renders in linear light,
  exposure 0–50 ms per episode. **No rotor drag** (accelerometer carries no velocity information). Startup agent finding: the
  velocity targets used by the net are in the camera-local frame — check conventions yourself.

## 5. Existing code to reuse (read-only; copy into your dir)
- GSLV MSCKF (C, single file): agents/sweep/baseA160.c — KLT tracker on a grid, MSCKF with ≤6 clones, Manhattan/vanishing-point
  line constraints (linejac), learned velocity net (2-frame CNN 16,24,32,48 ch, head K = velocity at frame 5, head 0 = at anchor),
  fuel governor GOV_B, startup priors, hover hold, gyro-bias clamp, net re-anchor every LV_PERIOD=10 frames. Most behaviour behind
  -D switches; switch inventory in agents/sweep/NOTES.md. Linejac design notes: eecs116_projects/research/single_model/linejac/NOTES.md.
- Net training: agents/netv2/tools/lv4.py (+ NOTES.md: recipe, capacity results); exporters: agents/net/tools/mkgslv.py (weights→C),
  agents/smallnet/tools/{mksn,mkgsn,mkcheap}.py (int16 SIMD nets, fuel per step), agents/cheap/tools/mknet.py (any shape).
- Startup diagnostics: agents/startup/tools/{early.py (early pos/vel/tilt error vs time), tilt.py, netcal.py, dbgview.py}, startup.patch (V0M).
- Fuel profiling: agents/smallnet/tools/{fuelstats.py, snbench.py, prof.py}.
- Other team's EKF (read-only reference, credit if used): tmp/goats/submission_stage2/.
- Research reports: eecs116_projects/reports/ (e.g. "VIO initialization for moving starts.md", "One million fuel VIO design.md").

## 6. Prior results / known failure modes (don't redo)
- Startup: vision updates before the net's first velocity lock in a wrong scale (0.71→1.36 on mid-flight). Mid-flight tilt error
  6.5° mean (p90 15°) at frame 5, 3° at 1 s, ~1° after 2 s; net lands ≈ frame 13. Net uncertainty is calibrated (z-rms ≈ 1, χ²
  exceedance ≈ nominal) — recalibration/gating gave nothing. Removing early position error post-hoc did NOT lower local mean ATE
  (later drift dominates locally). V0M (net head-0 as 2nd velocity measurement) ≈ −0.02…−0.04 m, n.s.
- Didn't help: tilt prior changes, START_STD, bias freezing, early MSCKF from live tracks, extra early anchors, re-anchor sigma
  changes, filter recalibration; GATE_MODE=1 (hurts warehouse); PIXEL_STD 2.0 (hurts).
- Helped: AB_ZUPT=0 (vision ZUPT was harmful, −0.10…−0.13), INV_LAT/INV_VZ=0, ITER_UPD=1, EDGE=0 (fuel), better net weights.
- Goats-style cheap EKF: 3.3–3.6 m even with oracle velocity — front-end (0–6 features/frame in open scenes) + heading drift limit it.
- Bigger nets (2× fuel) lose in-filter due to later landing; small nets help only at tight budgets (≤3 M). Fuel: full net ≈ 8.7 M per
  run (spread over frames as micro-steps on leftover GOV_B budget); MSCKF rows ≈ 100k fuel each; peak set by vision bursts.
- Running concurrently (don't interfere): anchors agent (gen3/agents/anchors: net re-anchor frequency, long-lived points, warehouse
  heading anchors), twin agent (gen3/twin), autotrain loop + final net round (agents/net), dataset generation (gen3/g3.py, run4.sh,
  up.py, out/ — never touch).

## 7. Resources and rules
- CPU: 192 cores shared with dataset generation and other agents: **≤8 eval workers per agent**, and wait while
  `cut -d. -f1 /proc/loadavg` > 170. RAM: ≤100 GB per agent process.
- GPU: never 0, 1, 2, 4 (other users). GPU 5 is shared (training jobs: OMP_NUM_THREADS=3, small batches, check nvidia-smi memory).
  GPUs 3, 6, 7 only after gen3/out/GEN_DONE exists (generation ends ~22:00 UTC).
- Python: /data/backups/rganapa/Sebastian/venv-teacher/bin/python (torch, numpy). Never `pkill -f`; kill only your own PIDs.
- Submitted estimators: strictly causal, no imports in the wasm, bounded per-frame work; privileged GT only offline.
- Token-light: write scripts, run them in the background, check back rarely (Monitor/until-loops). Keep NOTES.md in your dir with
  every result (name, flags, flights, raw mean, sw, CI, peak).
- Deliverable: SUMMARY at the top of NOTES.md covering the 11 required items (method, literature/code review, derivation,
  prototype path, oracle+ablations, comparison vs baseline with CI, peak fuel, failure modes, generalization risk,
  recommendation integrate/refine/abandon, exact code locations + reproduce commands), then a short final report.

## 8. Work style: scripts do the work, the agent stays idle (added 2026-11-26)
- Put every long step (data prep, training, eval sweeps, replicate runs, scoring) into a detached, resumable pipeline:
  `nohup setsid bash run_<x>.sh > logs/<x>.log 2>&1 &` with a queue file, per-item done markers, and results written to files.
  It must keep running and finish correctly even if you (the agent) are stopped or rate-limited for hours.
- The pipeline should write a machine-readable summary (e.g. results.tsv) and append a line to NOTES.md when stages finish.
- After launching, do NOT poll. Wait with one long Monitor/until-loop on a done-marker (check interval ≥10 min), then analyse.
  Prefer queuing the whole plan (screen → replicates → v1val check) up front, so decisions can be made by the script
  (e.g. auto-run 3 replicates for any variant whose single-run d < −0.02).
- Keep your own reasoning short; read only summaries/tails of logs, never full logs or large files.


## 2026-11-27 storage update (user instruction)

Keep total local VIO dataset storage below 600 GB (600,000,000,000 bytes), including old archives, training caches, and per-experiment data copies. Use SentientNapkin/viobench-stage3 as the remote source of record and stream or fetch bounded batches on demand. Keep only pinned evaluation flights and a bounded compact training cache locally. Reuse a shared cache instead of per-run duplicate downloads. Count shared hardlinks once for physical storage. Do not delete unuploaded/unverified unique data or active inputs. Existing legacy loaders do not all enforce a global budget: check inventory before expanding caches. Policy: ../storage_policy.json. Checksum-verified duplicate consolidation audit: /tmp/vio_storage_20261127/.
