# Extreme low-fuel lane status

State: COMPLETE; bounded queue exited cleanly. The accuracy lane supplied the exact paired baseline measurement (same current-best wasm, same stratified 18-flight panel), so no duplicate control evaluation is run here.

Experiment: structural geometry pruning by shortening the active clone window while preserving the same small-net and adaptive clone policy. Queue: `MAX_CLONES=5 MAX_OBS=7`, then `MAX_CLONES=4 MAX_OBS=6`. Source `gen3/agents/anchors/base_sn.c`; baseline flags from the verified `snace6e1` build in anchors NOTES. This tests the covariance/feature-window cost directly, independent of the fuel lane's edge-work gating and governor-budget sweep.

Screen: 18 stratified v3val flights (3 each per scene/start bucket), paired with `snace6e1`. Confirm only settings with >=20% lower peak fuel, <=0.10m mean paired ATE penalty, and no >0.45m per-flight regression; confirmation uses a disjoint 18-flight panel. 4 evaluator workers, 60-minute wall cap, `/dev/shm` cap 8GB. No test/hidden set, uploads, or GPU. Full dev358/v1val120 is gated for the coordinator after this screen.

Current paired baseline from accuracy lane: n=18, raw ATE 0.434850m, peak 4,030,586 fuel; wasm SHA256 `1a169f28916acd813f86a7b526efb8e8b646b3dda73e48cba51b12845c69b1b8`.

## Current screen row

`mc5` finished on screen18: raw ATE 0.515700m (baseline 0.434850m, paired difference +0.080850m), peak 3,192,448 fuel (baseline 4,030,586, −20.8%). It clears the mean ATE and peak thresholds, but failed the predeclared per-flight tail gate, so it did not get disjoint confirmation.


## Screen complete

`mc4` finished: raw ATE 0.496994m (+0.062143m paired), peak 3,016,986 fuel (−25.1%); max paired per-flight regression +0.681m. `mc5` finished: raw ATE 0.515700m (+0.080849m paired), peak 3,192,448 fuel (−20.8%); max paired regression +0.555m. Neither passed the predeclared tail gate (max regression <=0.45m), so no disjoint confirmation was run. Full dev358/v1val120 remains ungated; these are screen-only candidates, not score claims. The executable queue completed and exited.
