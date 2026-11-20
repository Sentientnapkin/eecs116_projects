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
