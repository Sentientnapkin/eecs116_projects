# Instructions: a long, GPU-heavy teacher → student training run (the student-teacher track)

For a fresh Claude Code session. Paste this to start:

> Read `reports/Instructions long student teacher training run.md` and carry it out exactly in `research/single_model/stlearn/`. Keep `stlearn/NOTES.md` current. Report the final tables when done.

Repo root: `/data/backups/rganapa/Sebastian/eecs116_projects`. This is the **learned student-teacher track**, the teammate's line of work, scaled up on this GPU machine. It is **not** about tuning our classical GP + MSCKF filter. The filter only appears at the end, as the place where a student's output is used and judged.

---

## 0. Another run is already going: share, don't collide

A separate session is already running the **GSLV periodic-velocity-net run** in `research/single_model/stlong/`. Before starting, read `stlong/NOTES.md` and check `ps` / `nvidia-smi`. Here is what it is doing:

- **Generating fast flights** into `/data/backups/rganapa/Sebastian/gen/raw-stlong/`: `generated.jsonl`, roster `stlong/gen/roster_c400.json`, logs in `stlong/logs/generation_multi.log`. That is 400 flights in batches of 72, using CPU simulation with OptiX GPU rendering on about 4 GPUs (1, 3, 4, …).
- **Caching:** about 2,800 eligible flights are already cached for training.
- **Width-1.5 velocity students:** it is training and screening these (`stlong/wide_screen.py`, up to 48 eval workers).

Rules for this run:
- **Never touch `stlong/`** or its processes, caches or output dirs. You may **read** its generated flights and caches. Reuse them instead of regenerating the same flights, and record which ones you used.
- **Use different seeds:** give new rosters a seed range that cannot collide with stlong's or learnvel's (check their rosters), and write flights to your own raw dir, e.g. `/data/backups/rganapa/Sebastian/gen/raw-stlearn/`.
- **Use other GPUs:** pick ones stlong isn't using (the machine has 8). Use at most 4, and fewer if the free ones are busy. Don't start more generation workers than the CPU can take alongside stlong: check `uptime` and keep the load below ~150.
- **CPU evaluation:** up to 48 workers, but only while stlong isn't also evaluating. Otherwise use 24.

## 1. What exists (read first, all on local `main`, merged from `origin/student-teacher-proxy`)

- **`research/single_model/STUDENT_TEACHER.md`:** an index of the teammate's work.
- **`research/single_model/disp_teacher/`:** the main experiment (`README.md`, `NOTES.md`, `model.py`, `train.py`, `distill.py`, `build_cache.py`, `server_cache.py`, `domain_check.py`, `export_c.py`, `dt_core.h`, `parity.py`, `evalrun.py`, `sweep.sh`).
  - **What the teacher predicts:** the drone's **1 s relative displacement**, with a per-axis Laplace uncertainty.
  - **Its inputs:** 3 gyro-derotated 128×96 frames, gravity, focal length, and the IMU acceleration-only preintegration (which fixes metric scale).
  - **How it is used:** fused as an EKF update every clone.
  - **Sizes:** teacher ~400 M MAC; student = half width, ~100 M MAC (distilled with Laplace NLL + KD + feature hint).
  - **Result:** "B17-dt" (their B17; not our lateinit B17) = B16 + student s3 was −0.17 m better locally, but **0.992 m @ 419 M fuel on the server** (B16 0.782 @ 17 M).
- **`research/single_model/proxy/`:** startup-velocity teacher T1 → students S0/S1/S2 (`lc_local.py`, `prep_lc_local.py`). T1 overfit its 102 flights; S2 (self-distilled lcJ) improved fast starts 0.74 → 0.64 m/s but tied in-filter. Also `server_results.json` (per-episode server scores for every submission) and a 26-flight proxy set.
- **`eecs116_vio/gpu_kit/`:** the teammate's flight-style overrides (`styles.txt`: per-flight top speed 0.3–4 m/s; styles `wide_gentle`, `wide_agile`, `wide_long`, `agile2`, `jerky`). Also `eecs116_vio/videos/` (failure styles such as "knee" and jerky turns).

## 2. Why the teammate's run fell short, and what this run fixes

| Limitation on the laptop (from their NOTES) | What to do here |
|---|---|
| RTX 3050 4 GB; short runs (teacher 10 k steps, fine-tune 0.6 h) | Train for days on up to 4 large GPUs: bigger batches, many more steps, EMA, proper LR schedule |
| Only **617 slow flights** (mean 0.33 m/s vs ~1 m/s server); couldn't generate flights on Windows; time-scaling augmentation as a substitute | **Generate thousands of real fast flights here** with the server-matched generator and the 0.3–4 m/s styles |
| Teacher worse than the filter on server-speed flights (1 s error 0.513 m vs B16's 0.110 m) and **overconfident** (Laplace z 1.4–1.9) | Train in-domain at speed; calibrate the uncertainty (z ≈ 1) on held-out fast flights |
| **Fuel:** a student call costs ~0.42 G per frame → server peak 419 M | Distil a ladder of much smaller students (target ≤ ~20 M fuel per frame after time-slicing the forward pass across frames) |
| Server failures happen at **startup (< 1 s)**, before a 1 s displacement window exists | Also train a short-window / startup variant (0.25–1 s windows from frame 0), or a joint velocity + displacement head |
| Test sets didn't predict the server | Judge on the server-like sets listed in §6, not only the 171 server-calibrated flights |

## 3. Data (the biggest lever): ≥ 5,000 flights

1. **Generator:** `research/native_campaign.py generate` with roster JSONs. Copy the pattern of `research/single_model/learnvel/gen/driver.py` (generate → cache → delete zips).
2. **Port `eecs116_vio/gpu_kit/styles.txt` into roster `task_overrides`.** Check `gpu_kit/viobench_local.patch` for whether the autopilot needs patching. Mix:
   - `wide_gentle`, `wide_agile`, `wide_long`, `agile2`, `jerky` styles
   - half hover starts, half mid-flight starts
   - all scene types, with extra weight on untextured ProcTHOR (`learnvel/tables/scenetex.json`)
3. **Sanity check** speed ranges on a sample (the `gpu_kit/calibrate.sh` logic); drop crashed flights.
4. **Also reuse:** the teammate's teacher-data cache recipe (`disp_teacher/build_cache.py`; HF dataset `SentientNapkin/viobench-teacher-data`), our caches in `/data/backups/rganapa/Sebastian/tmp/lv_cache_train`, and learnvel's untrained roster b (~600 flights).
5. **Build displacement-training caches** in the `disp_teacher` format: windows at several lags, plus derotation and IMU-preintegration inputs computed with **realistic noise**. Their NOTES list the noise model: derotation 0.4°, tilt 0.5–2°, gravity leak, bias, white noise.
6. **Splits by scene:** train, plus a held-out validation of ~5% of scenes, never trained on.
7. **Forbidden for training or selection:**
   - our 240-flight holdout scenes and flights (`research/single_model/holdout/`, `gen/raw-holdout/final`)
   - fold 4 / sealed data
   - st2conf scenes
   - the private server episodes (never download or probe them)
8. Run generation with `nohup` in the background, concurrently with training. Delete zips after caching; watch disk space.

## 4. Teacher

1. **Reproduce first:** retrain their t2 recipe on their cache and check the validation numbers in their NOTES (step 10 k ≈ 0.320 m mean 1 s error).
2. **Scale up:**
   - wider/deeper trunk (or a light transformer over frame features)
   - 3–5 frames
   - optionally 160×120 input
   - multi-lag heads (0.25, 0.5, 1, 2 s)
   - a **velocity head** alongside displacement
   - calibrated per-axis Laplace (or Gaussian beta-NLL) uncertainty
3. **Augmentation:** brightness, contrast and dark frames; blur; mirror with consistent sign flips. Keep time-scaling as an extra.
4. **Training:** long, multi-GPU (DDP), with EMA weights, cosine schedule and checkpoints every N steps.
5. **Selection metrics,** on the held-out fast flights and on the server-calibrated folds the teammate used for selection, by speed bin:
   - mean 1 s displacement error
   - velocity error
   - z-score calibration
   - error vs the filter's own 1 s displacement (their `domain_check.py`): the teacher is useful where it is **independent of and better than the filter when the filter has diverged**

## 5. Students (fuel ladder)

1. **Distil** with their `distill.py` recipe: NLL vs truth + KD on mean and scale + feature hint, using the long-trained teacher and the big data.
2. **Make a ladder:**

   | Student | MAC per call | Notes |
   |---|---|---|
   | S100 | ~100 M | their size, for comparison |
   | S25 | ~25 M | |
   | S6 | ~6 M | |
   | S2 | ~2 M | the size of our existing lcJ velocity net |

3. **Fuel per call:** for each student, estimate it with their `dt_core.h` C path (fuel ≈ a few × MAC with the SIMD GEMM). Also say how many frames its forward pass must be split across to keep peak fuel ≤ ~20 M.
4. **Check C parity** for each exported student: `export_c.py` + `parity.py`, target 1e-5.

## 6. Evaluation

**Offline (always):** for every teacher and student, by speed bin (0–1, 1–2, 2–3, 3–4 m/s), start type, and textured vs untextured:
- 1 s displacement error
- velocity error
- z calibration

**In-filter (for the best 2–3 students):**

1. **Their pipeline:** B16 + DT (`disp_teacher/make_dt.py`, `build.sh`, `evalrun.py`). Score on the server-calibrated slices they used (search/val/f23/f34; **never the sealed fold 4**) and on the 26-flight proxy set if it can be regenerated locally.
2. **Server-like sets** in `/data/backups/rganapa/Sebastian/tmp/st_pools/`:
   - `st2dev` + `st2conf`: fast flights in untextured rooms
   - `st1dev` + `st1conf`: long fast flights
   - fresh folds 0–2 / fold 3 in `/data/backups/rganapa/Sebastian/tmp/lv_pools/{fdev,fconf}`

   Runners and 3-replicate protocol: see `reports/Instructions periodic velocity net training.md` §5.
3. **Optional:** plug the best student's velocity or displacement output into our current best filter GSLV (`research/single_model/learnvel/final/gslm_lvnet.c`) as an extra measurement, and compare.

Report: mean unaligned ATE, tails > 3/5/10 m, peak fuel. Use 3 replicates for anything recommended.

## 7. Deliverables (`stlearn/final/`)

- teacher and student checkpoints
- exported C headers and parity reports
- a results table: offline metrics per model, plus in-filter ATE and peak fuel per student size
- for any build recommended for submission: `.c`, `.wasm` and `SHA256SUMS`, plus a preflight. Copy `research/single_model/learnvel/final/preflight.sh`; it must pass:
  - ABI check and zero imports
  - poison/prefix/repeat 18 × 41
  - reset 8/8
  - byte-identical rebuild
  - 0 filled frames

At the top of `NOTES.md`, a final summary: data mix, teacher curves, the student ladder, what failed.

## 8. Rules (hard)

- **Holdout:** never score on our 240-flight holdout. The coordinator session does that once per final build.
- **Fold 4 / sealed:** never read or evaluate them.
- **Training:** never train on holdout or st2conf scenes, and don't select on anything you trained on.
- **Server episodes:** never download or probe them.
- **Metric:** never use Sim(3) as the metric.
- **Git and uploads:** no git commit/push, no uploads.
- **Resources:** ≤ 4 GPUs (check `nvidia-smi`, share). ≤ 48 CPU workers for evaluation (generation may use more while nothing else runs). `TMPDIR=/data/backups/rganapa/Sebastian/tmp` (root `/` is full).
- **Interruptions:** run all long jobs with `nohup`. Update `NOTES.md` after every milestone (data counts, each training run, each eval), so an interrupted session can resume. On resume, check `ps` / `nvidia-smi` for your own jobs before relaunching. Never `pkill -f`/`pgrep -f` a pattern that is also in your own command line.
- **When finished or stopped:** leave no background processes running. The user is saving usage.
