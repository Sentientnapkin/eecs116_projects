# Instructions: train a better periodic velocity net for GSLV

For a fresh Claude Code session. Paste this to start:

> Read `reports/Instructions periodic velocity net training.md` and carry it out exactly, in `research/single_model/stlong/`. Keep `stlong/NOTES.md` current. Report the final table and sha256 when done.

Repo root: `/data/backups/rganapa/Sebastian/eecs116_projects` (paths below are relative to it).

---

## 1. Goal

Train a better learned velocity net for the **periodic re-anchor** in our best build, **GSLV**, and prove it helps **inside the filter**:

- **Base build:** `research/single_model/learnvel/final/gslm_lvnet.c` → `gslm_lvnet.wasm`, sha256 `5e4d2a0d40333b3f5152d60de84a688abc5d0eec8c1c73fa402dc9907839d196`. Holdout 0.379 m, peak fuel ~6–7.4 M.
- **The net it uses:** `learnvel/runs/v700b` (weights `v700b_w.h` / `v700b_w.npz`). Architecture lcJ, int16 C path, gray 128×96 frame pairs + IMU → body-frame velocity + sigma, ~1.7 M MACs. Trained with beta-NLL on the old data plus 700 fast flights.
- **How GSLV uses it:** `LV_NET=1 LV_PERIOD=10 LV_PSCALE=3.0 TC_GAP=9 TC_MAXANCH=400 LV_BGC=1 LV_BGMAX=0.021`, i.e. every 10 frames, with sigma ×3.

**Success** = a new net (same C cost class, peak fuel not above GSLV's) that beats GSLV by **≥ 5%** pooled on st2dev + st3, with the CI excluding 0, and is not worse than +2% on st2conf, fresh fold 3, fresh folds 0–2 and st1.

## 2. What is already known (read before starting)

Read these first:
- `research/single_model/learnvel/NOTES.md` (most important)
- `research/single_model/learned_c/NOTES.md` (the original net pipeline)
- `research/single_model/STUDENT_TEACHER.md`, `proxy/NOTES.md` and `proxy/lc_local.py` (teammate's teacher → student recipe)
- the last ~10 entries of `research/single_model/LOOP_LOG.md`

**What the net does well and badly:**
- **Where it helps:** it is worse than the filter on average (0.255 vs 0.147 m/s velocity error on st2dev), but about 2× better exactly where the filter has failed (0.42 vs 0.82 m/s when filter error > 0.5).
- **Why periodic updates work:** its errors decorrelate within ~1 s.
- **Main error:** speed under-estimation at high speed (speed scale 0.81 for v700b, 0.74 for older nets; error > 2 m/s is 0.55 m/s). Direction is good (perpendicular error ~0.13 m/s).

**What has been tried:**
- **v700b vs b2 direct error:** 0.240 vs 0.258 on st2dev.
- **Ensembles:** −7% direct error, but need C changes.
- **More input frames, longer frame gap, width 2:** at most −7% direct error. Width 2 also needs C changes, because the int16 conv only supports ≤ 48 output channels.
- **The new net alone with the old (sparse) schedule does nothing:** it only pays off with periodic re-anchoring.
- **Teammate's startup students** (S2 distilled from lcJ; S1 from a bigger teacher T1): direct error 0.74 → 0.64 m/s on fast starts, but a tie in-filter.

**Lesson:** direct-error gains do not always transfer; **always judge in-filter on GSLV.**

**What failed in-filter:** chi2-gating net updates (+6%), and a learned gravity-direction net (worse than the filter's tilt).

## 3. Data

- **Already cached:** `/data/backups/rganapa/Sebastian/tmp/lv_cache_train`, built with `learnvel/lv_prep.py`. It holds the old train sets (raw-fast folds 0–2 non-holdout, raw-speed) plus learnvel's roster_a (600 fast, texture-weighted flights).
- **Generated but never trained on:** a second batch, "roster b" (~600 flights, with gravity labels in `tmp/lv_grav`). Check `learnvel/NOTES.md` for its exact location and whether its cache is complete.
- **Generator:** `learnvel/gen/driver.py` with a roster JSON (see `learnvel/gen/roster_a.json`; variants K/P1/P4/P5/K1 = fast planner specs). It runs `research/native_campaign.py generate`, writes raw zips, prepares the cache and deletes the zips.
- **Partial roster from an earlier aborted session:** `stlong/gen/sl_roster.py`, `stlong/gen/roster_c.json`, `stlong/gen/driver.py`. Inspect them and reuse them if sound; nothing was generated from them.
- **Generate more:** target **≥ 3000 training flights** in total. Use new seeds. Use only eligible scenes: folds 0–2, non-holdout, not st2conf, not st2dev/st3 (st2dev/st3 are the tuning set, so keep their scenes out of training). Weight towards untextured ProcTHOR scenes (`learnvel/tables/scenetex.json`) and fast planners. Run generation on CPU in the background with `nohup` while training on what exists.

**Forbidden data** (check every roster against these before generating):
- holdout scenes and flights (`gen/raw-holdout/final`, `research/single_model/holdout/`)
- fold 4 / sealed
- st2conf scenes
- private server episodes

## 4. Training plan

1. **Baseline repro:** retrain the v700b recipe (`learnvel/lv_train.py`) on the current cache, to confirm the pipeline and its direct-error numbers on st2dev/st3 anchors (`learnvel/lv_eval.py`). Report direct error by speed bin (< 1, 1–2, > 2 m/s), speed scale, and sigma calibration (error/sigma rms).
2. **Teacher:** a large net, unconstrained by fuel. Try:
   - more width and depth
   - more input frames (3–5) and a longer baseline
   - 128×96 or full-resolution input
   - rotation-compensated IMU integrals as extra inputs
   - beta-NLL with a calibrated sigma
   - mirror augmentation
   - speed- and texture-bin-balanced sampling

   Train long (many epochs) on up to 4 GPUs (check `nvidia-smi`; GPUs 1 and 2 were idle; share with others). Pick on st2dev/st3 direct error, high-speed bins first.
3. **Student:** same architecture as lcJ/v700b, so it drops into the existing C (`learnvel/mknet.py` exports weights to a C header, and `patchlv.py` / LV_NET selects the net). Distil from the teacher: soft velocity and sigma targets plus truth loss. Use 3+ seeds.

   **Optional:** a 2-net ensemble or width 1.5. Only do this if you also implement the C changes (wider int16 accumulators, governor micro-step costs) and keep peak fuel ≤ GSLV's.
4. **Speed bias fix:** check whether a learned or calibrated speed rescale (net/true scale vs predicted speed) on the student's output further reduces in-filter error. Keep it inside the net or as a small calibration in C.

## 5. In-filter evaluation (the only thing that decides)

- **Build:** GSLV source with the new student weights (`LV_NET` variant); all other defines identical. With the new switch off, the build must be **byte-identical to GSLV** (`5e4d2a0d…`).
- **Pools:**
  - `/data/backups/rganapa/Sebastian/tmp/st_pools/{st2dev,st2conf,st1dev,st1conf}`
  - st3 (234 flights in st2-dev scenes, `/data/backups/rganapa/Sebastian/gen/raw-learnvel-st3/`; pool dir in `learnvel/NOTES.md`)
  - `/data/backups/rganapa/Sebastian/tmp/lv_pools/{fdev,fconf}` (fresh folds 0–2 / fold 3, fold 4 excluded)
- **Tools:**
  - building and running: `learnvel/bp.sh`, `learnvel/runpool.py`, `learnvel/reps.sh`
  - comparing: `learnvel/cmp.py`, `learnvel/pooled.py`
- **Replicates:** 3 reps (rep 1/2 add `PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0` / `PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0`). Report:
  - mean over reps and paired scene-bootstrap CI vs GSLV
  - tails > 3/5/10 m summed over reps
  - peak and p99 fuel
- **Process:** tune on st2dev + st3 pooled. Confirm on st2conf and fresh fold 3. Check for regressions on fresh folds 0–2 and st1. Screen candidates with 1 rep and only run 3 reps for finalists.

## 6. Deliverable

In `stlong/final/`:
- the recommended `.c` (GSLV + new weights + defines), `.wasm` and `SHA256SUMS`
- teacher and student checkpoints, plus the C weight header
- preflight output: copy `learnvel/final/preflight.sh`. It must pass:
  - zero imports and the ABI check
  - poison/prefix/repeat on 18 fixtures × 41 prefixes, including the periodic-fire frames 20, 24, 29–31, 40, 41, 60–66, 70, 80, 99–105
  - reset 8/8
  - a byte-identical rebuild
  - 0 filled frames

At the top of `stlong/NOTES.md` add a final summary:
- data size (number of training flights and scenes)
- teacher and student direct error by speed bin
- the in-filter table vs GSLV on every set
- the recommended sha256
- what failed

Then tell the user. The coordinator session scores the build once on the holdout.

## 7. Hard rules

- **Holdout:** never score on the clean 240-flight holdout (coordinator only).
- **Fold 4 / sealed:** never read or evaluate them.
- **Training data:** never train on holdout, st2conf, st2dev or st3 scenes.
- **Server episodes:** never download or probe them.
- **Metric:** never use Sim(3) ATE (mean unaligned ATE only).
- **Git and files:** no git commit/push, no uploads, don't write outside `stlong/` (plus generated data under `/data/backups/rganapa/Sebastian/gen/` and `/data/backups/rganapa/Sebastian/tmp/`).
- **Resources:** ≤ 48 CPU eval workers, ≤ 4 GPUs. `TMPDIR=/data/backups/rganapa/Sebastian/tmp` (root `/` is full).
- **Usage limits:** run all training and generation with `nohup`. Keep `NOTES.md` updated after every milestone so an interrupted session can resume. On resume, check `ps` and `nvidia-smi` for your own jobs before relaunching. Never `pkill -f`/`pgrep -f` a pattern that also appears in your own command line (it kills your shell).
- **Background processes:** the user wants to save usage, so when you finish or stop, leave nothing running.
