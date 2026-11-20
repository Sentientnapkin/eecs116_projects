# autoloop: unattended parameter optimisation of the plain-C wasm estimator

Base = `research/single_model/inventive/adopted.c` = gate build G + C1 (INV_HOLD hover-hold, INV_VZ 0.3, INV_LAT 0.5); r0 search 1.070 / val 0.540 (rebased 2026-11-20; the first run used final/submit/gate.c, archived in `ledger_G_base.jsonl` + `archive_G_base/`).
The tails patch is NOT in the base (it did not generalise on the fresh pool). Only `#define NAME value` numbers are rewritten; code never changes.
Default vector is checked at INIT against `results/single_model/inv_adopted` (all 144 visible per-flight ATEs must be identical; wasm sha warns) and `inventive/fresh_table_c1.json` on fresh-A
(checked at INIT, loop aborts otherwise). No LLM runs while it is going: everything is deterministic python, decisions come from `ledger.jsonl` + `state.json`.

## Run / stop / resume
* Running as one process group (setsid nohup): `python -B -m research.single_model.autoloop.loop --budget-h 5` (teacher python, PYTHONPATH = repo root). `loop.out` is its log, `loop.lock` prevents a second copy.
* Status: `cd <repo>; PYTHONPATH=. /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.autoloop.status`
* Graceful stop: `touch research/single_model/autoloop/STOP` (or `kill -TERM <pid>`): in-flight evaluations finish, summary is written, process exits (state 'stopped').
  Hard stop: `kill -TERM -<PGID>` (whole group; in-flight evaluation is redone on resume). Process group id = pid of the loop (see `loop.pid`).
* Resume: `rm -f STOP; setsid nohup env PYTHONPATH=<repo> <teacher python> -B -m research.single_model.autoloop.loop > loop.out 2>&1 < /dev/null &`.
  Extend the budget with `--budget-h N` (spent time is accumulated in state.json). Finished vectors are skipped (ledger dedupe by vector hash).
* Budget: 5 h wall clock (spent clock, not counting downtime), last 25 min reserved for the final stage (held-out fresh-B for top-3 + SUMMARY.md + best/*.c).

## Files
`params.py` registry (44 parameters, incl. HOLD_T/T0/GN/TAU, INV_VZ, INV_LAT, ranges, generator, hash) | `cats.py` -> `categories.json` (truth labels, analysis only) | `evalvec.py` one-vector evaluation subprocess |
`scoring.py` metrics, constraints, promotion tests | `loop.py` orchestration | `status.py` | `ledger.jsonl` (one row per evaluation: params, metrics, timestamp,
wall time, src/wasm SHA) | `results/<hash>.<stage>.json` per-flight ATE/fuel for VISIBLE flights (folds 0-3) or fresh splits | `state.json` | `LOG.md` (promotions, phase changes) |
`logs/` | `best/` and `SUMMARY.md` (at the end) | `pools/freshA|freshB` symlink pools. Trajectories of all but the best 20 vectors are deleted
(research/results/single_model/loop_<hash>_r0; replicates r1/r2 and fresh outputs are always deleted). Fold 4 rows are dropped inside evalvec before anything is stored;
`run_variant.report()` (sealed_aggregate.json) is never called.

## Evaluation
Per vector: build once per replicate and score the 171 selected flights with the shared fast runner (24 workers, PNG cache). R=3 replicates: r0 = the vector, r1/r2 = PIXEL_STD and
DETECT_MIN_SCORE nudged by +1%/-1% (chaos replicates, as tails/rep.sh; the nudge is applied on top of the vector's own values). Metrics use VISIBLE flights only: search = folds 0-2 (n=119),
val = fold 3 (n=25), replicate-mean per flight. Recorded: per-replicate search/val means, replicate means, static/mid, counts >3/5/10, per-category mean + worst flight, peak/p95/median fuel, wasm size.
Edge-case categories (visible, from truth, camera optical axis = +z of the camera-frame truth velocity; the fresh/truth_feats.json angle uses body +x on a camera-frame velocity and is not comparable):
wrong-direction start (>90 deg), fast start (>1.5 m/s), slow start (<0.3), static start, textureless/dark (audit flat or dark fraction >0.05), long path (>58 m), high yaw rate (top 25%), clean-scene group,
mid-start angle bins 0-45/45-90/90-135/135-180. Fresh-A/B also report the same angle bins (recomputed with the correct axis).

## Objective and promotion
Minimise replicate-mean SEARCH mean unaligned ATE subject to (vs the current reference): static mean not worse by >0.05 m; no new >10 m flights (replicate-mean); no category mean worse than
max(0.15 m, 15%); peak fuel <= ref +5%. Rank: feasible first, then search mean, then count >3 m, then peak fuel. A separate Pareto front (search ATE, peak fuel) is reported by status.
PROMOTION (candidate becomes the reference): (a) search improvement >= 0.03 m (replicate means), (b) val replicate-mean not worse by >0.15 m (paired scene bootstrap logged), (c) constraints, and then
(d) one fresh-A run (475 unselected flights, scene-hash folds 0-2 of the fresh tags; ~4 min) with mean <= ref + 0.02 m and the >5 m and >10 m counts not increased.
Fresh-B (folds 3-4, 236 flights) is only touched for the final top-3 (+ default) at the end.

## Phases
INIT reproduction check + fresh-A reference; A one-at-a-time sweeps (skipping `flat_params.json`: parameters measured flat on the G-based run) 0.8x/1.25x then 0.5x/2x (capped at 40% of budget) -> rank parameters; B coordinate descent on the top 12 with step halving (0.30 -> 0.07,
capped at 70% of budget) plus combos of individually helpful moves; C (4,6) evolution strategy (log-normal mutation of 2-5 of the top-20 parameters, uniform crossover) until the budget ends; FINAL fresh-B + SUMMARY.md.
Concurrency: 2 evaluations x 24 workers; before every launch the loop waits while the 1-minute load average is above 140.
