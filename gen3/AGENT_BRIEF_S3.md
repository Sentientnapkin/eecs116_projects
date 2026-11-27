# Stage-3 GSLV upgrade: shared brief for agents (read fully before starting)

## Goal
Improve GSLV-linejac (our best build: server stage-2 0.633 m @ 4.2 M peak fuel; server stage-3 ~1.18 m mean over 24 episodes) on
stage-3 conditions: FoV 75-135 deg, motion blur 0-50 ms, rooms + large warehouse + forest, and (the main weakness) MID-FLIGHT starts,
often moving backwards or sideways relative to the camera. Score = mean unaligned ATE (m) over episodes; also report peak fuel per frame.
NEVER use Sim(3)-aligned ATE as the metric.

## Baseline (unchanged GSLV-linejac on local v3 validation, 148 flights; grows as generation continues)
raw mean 1.683 m, server-weighted 1.489 m, median 1.237, >3 m: 27, peak 5.10 M fuel.
rooms 0.762 | warehouse 2.457 | forest 2.603 ; hover 0.937 | mid-flight 1.857 ; normal heading 1.114 | free-yaw 1.948.
Server per-class for the same build (probe): rooms 0.72, warehouse 1.13, forest 2.22.

## Code
- GSLV-linejac source: /data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/linejac/final/gslv_linejac_arith.c
  (wasm: same dir, gslv_linejac_arith.wasm, sha eb2799cb...). Most behaviour is behind #ifndef/-D switches (startup priors:
  PRIOR_MODE, START_*, MOVE_TILT_STD, MOVE_VEL_STD, SPEED_STD, GATE_*, LV_*, TC_*). Build tooling: see linejac/mkwasm.py and
  research/single_model/run_variant.py (build(src, cmake, defines, name)); CMakeLists in linejac/. Verify that a no-change rebuild
  reproduces the reference wasm sha before trusting your build path.
- The other team's stronger moving-start EKF (read-only reference): /data/backups/rganapa/Sebastian/tmp/goats/submission_stage2/
  (vio.h, vio.cpp, solution.cpp). Key ideas: zero-mean isotropic velocity prior 2 m/s, tilt prior 0.45 rad, gravity along body z,
  per-frame inverse-depth feature updates from frame 1, start-up relinearisation ("seed"), staged bias priors, watchdog restart.
  Do not copy it into any submission without noting it in your NOTES.md.

## Evaluation (shared; CPU only)
- Refresh pools first: `bash /data/backups/rganapa/Sebastian/gen3/refresh_pools.sh` (pools/v3val = v3 validation, pools/v1val = v1 val).
- Run: `cd /data/backups/rganapa/Sebastian/gen3 && ../venv-teacher/bin/python -B evalpool.py NAME WASM pools/v3val WORKERS`
  -> evals/NAME__v3val.json (per-flight results are cached by wasm sha, so re-runs after a pool refresh only do new flights).
- Compare: `python3 score.py evals/gslvlj__v3val.json evals/NAME__v3val.json` (paired on common flights; raw mean, server-weighted
  mean, per class/start, bootstrap CI, >3 m tails, peak fuel). Re-run the baseline name `gslvlj` on the refreshed pool too so the
  comparison set matches.
- Regression check: also run on pools/v1val (normal-heading flights) for any change you recommend.
- CPU budget: AT MOST 20 eval workers per agent (dataset generation shares the machine). Check `cat /proc/loadavg`; if > 170, wait.
- GPU: do NOT use GPUs 0, 1, 2 or 4 (other users). Generation runs on 3, 5, 6, 7. Only the net-training agent may use GPU 5 (shared).
- The v3 TEST split (out/keep/s3v3te*) is reserved: never evaluate on it, never train on it.

## Rules
- Work in your own directory: /data/backups/rganapa/Sebastian/gen3/agents/<your-name>/ . Keep a NOTES.md log there with every result
  (name, flags, flights, raw mean, server-weighted, CI, peak fuel). Don't edit files outside your dir except reading.
- Don't touch the generation/upload pipeline (gen3/g3.py, up.py, run*.sh, out/), don't kill processes you didn't start, never use
  `pkill -f` patterns that could match other processes. No git commits/pushes. No uploads. Never download or probe server episodes.
- Peak fuel matters (score is accuracy vs max fuel per frame): report it; prefer changes that keep peak <= ~5 M.
- Single-run noise is large (chaos per flight): use paired comparisons on the same flights; for a final recommendation run 2-3 replicates
  (e.g. PIXEL_STD=1.515 / 1.485 nudges, as linejac NOTES describe) and report the bootstrap CI.
- Finish with a short summary at the top of NOTES.md: what helped, by how much, with CI, peak fuel, and the exact build to use.
