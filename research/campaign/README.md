# Campaign harness

Run from the repository root using the teacher virtual environment:

```sh
python -m research.campaign.perflight --scores /data/backups/rganapa/Sebastian/baselines/bench-fast/selected --metadata /data/backups/rganapa/Sebastian/gen/raw-fast/bench --selection research/results/eval/server-benchmark/selection.json --output research/campaign/perflight.jsonl
python -m research.campaign.report --table research/campaign/perflight.jsonl --parent vins_mono --output research/campaign/baseline_report.json
python -m research.campaign.test_campaign
```

`perflight.jsonl` includes all 13 saved guests × 171 flights, including filled and failed episodes. Missing scores cause an error requiring pinned evaluator rescoring; audit approximations never substitute for ATE. Tags come from generator sidecars. Draw weights are the 300 selection multiplicities, not uniform weights over the 171 distinct flights.

`baseline_report.json` contains overall and group/catalog/start-type summaries, a clean plus dev-HSSD slice, raw mean/median, trimmed and winsorized means, tails, weighted mean, filled/failed counts, fuel, 12-flight weighted sampling interval, and paired scene bootstrap against VINS. The JSON contains more detail than the Markdown table. These historical scores are reference rows, excluded from final ranking until preflight and provenance exist.

`ledger.write_spec(root, spec)` validates mandatory sections, raw metric, timestamp and 160-worker cap, then creates an immutable content-addressed spec using exclusive creation. Guest build output should be recorded separately by experiment ID, rather than mutating the declaration. `Claim(root, key)` uses atomic mkdir acquisition and token-checked release; call `.heartbeat()` at least once a minute for long tasks. An abandoned claim is identified after 15 minutes. Stale claims are **never automatically stolen** because a paused worker can still be alive: inspect its owner host/PID, archive the stale directory, and resume. There are no concurrent shared-file appends.

`leaderboard.render(rows, output)` rejects duplicate SHA/seed entries and mixed slices. Only final preflight-passing rows with declarations preceding scores rank; learned rows also require three seeds and verified training split exclusion. Eligibility consumes provenance fields supplied by the build/training pipeline; it does not independently inspect model weights or training manifests. Oracles are always unranked bounds. Historical baseline references have no fabricated declarations.

All statistics use raw unaligned ATE; no Sim(3). Bootstrap intervals capture sampling uncertainty, not training randomness or server distribution shift. The scene bootstrap resamples complete scenes and retains every flight in each sampled scene. Synthetic unit tests cover failure retention, draw weights, scene pairing, missing-score rejection, claim exclusion, immutable specs, split tags and ranking eligibility.
