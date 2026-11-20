# Holdout set (gen/raw-holdout) -- ONE-SHOT final-decision set

RULE: final candidates are scored here at most once each. Nothing in this set may be used to tune or select
anything. Candidates scored so far: see "Scores" (filled in at the end). Progress log: PROGRESS.md.

## Why
Estimator candidates were selected many times on the 171 'selected' flights (gen/raw-fast/selected) and partly on
the 711 'fresh' flights (the rest of the raw pool). This set contains flights whose seeds appear nowhere in any
existing sidecar/roster, in scenes mostly absent from gen/raw-fast.

## Construction (same as the raw-fast pool: configs/server_fast_pool.json / server_fast_mid_pool.json)
- Static 'fast-<scene>-NN': 60 s, hold 1.0 s, 0.8 waypoints/s, regime benchmark, planner task_overrides K
  (cruise 3.0-4.5, accel 6, jerk 30, yaw 2, roadmap 1.0, connection 6.0) or K2 (cruise 4.0-6.0, accel 8, jerk 40), 50/50.
- Mid 'fastmid-<scene>-NN': simulated for 60+crop s (hold 0.2 s), then cropped by native_campaign.crop_episode so the
  scored recording is 1200 frames starting crop s into the flight; crop ~ U(3,40) s on a 0.05 s grid (pool: 3.1-39.9).
- Generated with native_campaign.py generate (unmodified), same audit + failure-only gates (stalled, truth-integration
  RMS > 0.05 m, non-finite, flags), sidecar json per episode beside the zip in gen/raw-holdout/bench/.
- Seeds: 970000+ (static) / 980000+ (mid); checked disjoint from every seed in gen/raw*/ sidecars and configs/*.json
  (and from the native campaign roster).
- Scene choice and truth-statistic-only calibration selection: see make_roster.py and select_final.py here
  (details and numbers are appended below as the run progresses).

## Realized set (final selection, 240 flights in gen/raw-holdout/final -> symlinks to bench/)
- Candidates generated: 620 (256 stage-1 static: one per eligible scene; 364 stage-2: extra static + mid in scenes with stage-1 extent >= 2.8 m;
  0 generation failures). Stage-2 allocation and the final selection (select_final.py: 120+120 without replacement, <=3 per scene per start type,
  seeded local search to match mean extent 4.694 / path 59.6 as closely as possible) use truth statistics only; no estimator result anywhere.
- Scenes: all catalog scenes already appear in some roster/manifest, so NONE is entirely new. 110 scenes used: 101 absent from gen/raw-fast
  (58 ProcTHOR + 43 HSSD-train), 9 HSSD-Val43 dev houses reused (new seeds). Reserved test scenes excluded. 0 seed / (scene,seed) collisions.
- Audit vs selected171/fresh711: AUDIT.md (audit_dist.py). Gates: verify_zips.py (240/240 load, 1200 frames, finite, not stalled, truth integration <= 0.0011 m).
- Caveat: hitting the extent anchor requires big houses, so the mix is HSSD-train heavy (112 hssd-train, 99 procthor, 29 hssd-val) vs selected (44/94/33).
- Rejected candidate zips (380) were kept under gen/raw-holdout/bench (not in final/); do not score them.

## Scoring
`holdout/score_build.sh <wasm> <name>` (copy of fresh/run_fresh.py on final/ via run_holdout.py; refuses a second run of a name; logs SCORED.log).
Tables: table_<name>.json/csv; summary RESULTS.md (analyze.py). Scored once: base (gp_msckf.wasm), gate (G), gatec1 (G+C1).
