# Four-lane research checkpoint

All four agents used gpt-6-luna and finite detached scripts. Current submission and holdout untouched. Small local screens are exploratory, not hidden-server gains. Raw ATE and peak fuel are reported; the complete current scoring frontier is unavailable.

## Current MSCKF accuracy
Exact submitted binary, 18-flight scene/start screen: 0.434850 m, peak 4,030,586. AN_DA=.25: .446691 m; AN_DA=.4: .414172 m, peak 3,810,545. The .4 setting failed disjoint 18-flight confirmation: .749926 vs exact baseline .732757 m. Do not promote based on screening alone. Source, manifest, per-episode metrics and resumable script: accuracy/.

## Current-system fuel
12-flight panel, exact current baseline .457110 m / 3,769,529. EDGE_ON_LIVE=30: .473954 m / 3,706,169; 45: .479942 m / 3,706,169. Slight fuel savings cost accuracy; no full-set confirmation scheduled. See fuel/status.jsonl for authoritative unrounded results.

## Cheap frontier
Same 18-flight screen as accuracy: 5 clones/7 observations .515700 m / 3,192,448; 4 clones/6 observations .496994 m / 3,016,986. Both failed the declared per-flight regression gate; no confirmation. Prior independent ultra-cheap and Goats experiments remain negative, not rerun without justification. See extreme/.

## Higher-compute learned/hybrid accuracy
Resumed missing depth quality diagnostics instead of starting large training. The prior sweep had failed for disk space despite a completion marker. New scene/start-stratified 24-flight panel uses OLD A160ft+Ze0, not the submitted small-net baseline. Matched baseline and OR=1/no-intervention control both .592578 m. Independent GT-pose-triangulated pseudo-depth fractional sigma .1: .440050 m; .2: .561590 m. These pseudo-labels fit existing tracks using GT poses and rejection gates, not renderer depths or perfect correspondences. Shared per-episode fractional error .1 with per-landmark marginal sigma .1: .939467 m, illustrating the danger of repeated correlated metric priors under independent measurement covariance. Shared per-episode fractional error .2: 1.401250 m. These rows use positive marginal covariance but assume independence between landmarks, so correlated-error modeling remains a confound. Zero-covariance shared10/shared20 arms are INVALID (division by zero in depth whitening); exclude them. See learned/stratified/INTERPRETATION.md.

## Storage
HF is the source of record for stage-3 data; use streaming or bounded shard/flight downloads. A 600,000,000,000-byte local dataset policy is recorded at gen3/storage_policy.json. Main stage-3 archives/caches ~322 GB before cleanup. Old per-run caches contain ~240 GB of physical shard copies but ~26 GB of distinct named content. Checksum-verified atomic hardlink deduplication is running separately under /tmp/vio_storage_20261127, preserving all unique content and every existing path. This does not assume availability of the older HF repo, which could not be verified. Final conservative inventory: 579,444,137,984 bytes (579.44 GB), under the 600 GB cap. 19,852 checksum-identical files consolidated; 189,619,609,600 bytes of redundant allocation eliminated. Legacy loaders still are not globally intercepted. Persistent audit: gen3/research/storage_20261127/.
