# Finding stand-ins for the 24 hidden stage-3 episodes

The goal: for each hidden episode, find the flight in the
[viobench-stage3](https://huggingface.co/datasets/SentientNapkin/viobench-stage3) dataset (10,667 flights) that is
most like it. Similarity has three parts:
- **(A) motion and geometry:** FoV, path length, RMS distance from start, spread, start forward speed, tilt rate, yaw
  rate and jerk;
- **(B) appearance:** brightness, colour, texture and blur;
- **(C) our submissions' errors:** each submission's ATE, Sim(3) ATE and rotation error on the candidate flight, against
  the same submission's server error on the hidden episode.

The hidden-episode side of (A) and (B) comes from the probe (`../README.md`, `../../stage3/probe_decoded.json`).

## Status (2026-11-26)

| step | state |
|---|---|
| Stage A (manifest only) | done: `../../stage3/match_stage_a.json`, top 40 per episode |
| probe ↔ manifest calibration | done (24 flights): FoV to 0.002°, path / distance / spread to 0.03 %, tilt / yaw / jerk to 3 %. The mapping in `stage_a.py` is right, so the remaining differences are real |
| downloads for stage B | the top 10 per episode = 236 unique flights (74 GB), list in `../../stage3/ids_stage_b.txt` |
| submission runs | **775 of 3,068 done** (13 wasm × 236 flights), in `../../stage3/match_runs/<server id>/<flight id>.json` |
| stage B selection + validation | not run yet (needs the complete runs) |

**Main finding so far:** no dataset flight is a near-twin of any hidden episode. None falls within the tolerance on
all 8 motion features at once. The features are nearly independent, so the expected number of twins in the whole
dataset is about 0.01. Episodes 1, 14 and 22 also sit at the edge of what the dataset covers: episode 1 is slow,
short and barely rotates.

## How to finish it (Linux machine with a viobench venv; about 16 s per run per core)

```bash
. ~/viobench/.venv/bin/activate                       # any venv with viobench installed (gpu_kit/setup.sh makes one)
cd eecs116_projects/eecs116_vio/probe/match
python3 fetch.py ../../stage3/manifest.csv ../../stage3/ids_stage_b.txt 6     # 236 flights -> ~/data/s3match (74 GB, sha256-checked)
bash run_subs.sh                                      # 13 wasm x 236 flights; skips the 775 done; ~2,300 runs left
                                                      #   = about 10 h on 1 core, ~40 min on 16 cores
pip install pandas scipy                              # for the analysis only
python3 stage_b.py                                    # picks the 24 proxies, prints the validation, writes ../../stage3/proxy24.json
```

Then commit `../../stage3/match_runs/` and `../../stage3/proxy24.json` (small JSON files, about 12 MB in all). Do not
commit the flights.

`wasm/` holds the 13 submissions, each named by its server submission id; every sha256 matches the server's. The probe
is `6b316c1f9da012f7`. The three slowest are `9cf6355f…` (418 M fuel per frame, about 30 s per flight),
`59022b14…` and `5674e74f…`.

### What `stage_b.py` prints and how to read it

- **Leave-one-submission-out table.** For each submission S, the proxies are chosen *without* S's errors, and then
  S's ATE on those proxies is compared with S's server ATE (per-episode RMS log error, correlation, mean). Two
  columns:
  - (A+B only): motion and appearance;
  - (+ other subs): also matching on the other submissions' errors.

  If the second column is not clearly better, matching on submission errors only fits noise, and the A+B proxies are
  the honest choice.
- **The final 24** proxies with their three cost parts, and the per-submission mean ATE, server vs proxies. The final
  pick uses every submission, so this comparison is in-sample; the leave-one-out table is the honest number.

## Targeted generation (next step, GPU)

Generating flights aimed at each hidden episode should get much closer than searching the existing dataset. How it
would work:
- **Set directly:** FoV (`fov_range=0`, `fov=<episode value>`), the scene type, and hover vs in-flight start. For the
  warehouse and forest episodes the server almost certainly used the official `Warehouse` / `Forest` scenes, so those
  12 can be near-twins. Exposure and brightness can be fitted to the probe's blur ratios and luminance.
- **Search:** the motion features, over autopilot style × seed × crop window. One 120 s flight contains hundreds of
  60 s windows, each with its own start speed, path, spread and rates, scored from ground truth alone. If the
  simulator can run with rendering off (or rare) and still produce an identical trajectory, test that first, so the
  search costs almost nothing.
- **Render:** only the 10–20 best windows per episode. Then run `../run_local.sh`, `run_subs.sh` and `stage_b.py` on
  them.

Rough cost is about 24 × 15 ≈ 360 renders: hours on an RTX 5080, about 17 min per flight on a laptop CPU. Pilot it on
2–3 episodes first, including one warehouse episode.

Room episodes stay neighbours, not twins, because we don't know which room the server used. Picking the best of many
candidates by our submissions' errors also risks fitting noise; the leave-one-out table measures how much.
