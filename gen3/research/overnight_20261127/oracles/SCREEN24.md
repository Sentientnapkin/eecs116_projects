# Current SN anchor oracle velocity screen

Date: 2026-11-27 UTC. This is a ground-truth-only diagnostic, not an estimator deployment result.

## Port and controls

- Current anchor source: `agents/anchors/base_sn.c`, exact recorded build flags copied from `agents/anchors/builds/snace6e1/flags.txt`; baseline wasm SHA256 `1a169f28916acd813f86a7b526efb8e8b646b3dda73e48cba51b12845c69b1b8`.
- Velocity-only port generator: `port.py`. It inserts the oracle table/lookup and body-velocity update, plus per-flight ORV lookup/attempt/accept counters.
- The OR=0 compile of the port matches the baseline wasm SHA256 byte-for-byte. OR=1 with all interventions off matched baseline per-flight estimates (ATE and error) on the initial 3-flight pilot and on all 24 screen flights.
- On the pilot, GT lookup matched all 3 flights and perfect-velocity updates were accepted 120/120 each. No orientation or gravity measurement is included.
- GT table `research/i3/data/or_tab.bin`; positive assumed sigma was maintained for every arm. Perfect actual measurement uses `OR_NK=0` while `OR_VEL=0.02`.

## Screen results (24 flights)

Pool: first 24 sorted entries of `research/i3/pools/i3s120`, under `/tmp/vio_overnight/oracles/pool24`. All rows completed, no failures. Control ATE is mean across those 24 flights.

| Arm | Velocity observation | Mean ATE | ORV lookup hits | Attempts/accepted per flight |
|---|---|---:|---:|---:|
| Current anchor | none | 0.7226 | n/a | n/a |
| OR=1 disabled | none | 0.7226 | 24/24 | 0/0 |
| Perfect .02 every 10 frames | assumed sigma .02, actual noise 0 | 0.2343 | 24/24 | 120/120 |
| IID .1 every 10 frames | assumed/actual sigma .1 | 0.4682 | 24/24 | 120/120 |
| Correlated .1, tau 2 s, every 10 frames | assumed/actual sigma .1 | 0.7507 | 24/24 | 120/120 |
| IID .1 at frame 0 only | assumed/actual sigma .1 | 0.6583 | 24/24 | 1/1 |
| IID .1 every frame through 1 s | assumed/actual sigma .1 | 0.6675 | 24/24 | 21/21 |

For each instrumented arm, every per-flight ORV diagnostic showed a GT-table hit and all attempted updates accepted. ORS had 1180 post-start diagnostic samples per flight in the 3-flight mechanism pilot. The 24-flight perfect and IID screens materially improve ATE, while correlated and time-limited cases do not show a comparable benefit. These screen effects remain diagnostic; no current best artifact was modified.

## Confirmation

The strongest two 24-flight arms (perfect .02, IID .1) are being confirmed on the first 48 sorted entries of the same pool. The first-48 confirmation completed with 48/48 rows for each arm. Current anchor mean ATE was 0.568; OR=1-disabled control matched exact per-flight ATE/error. Perfect .02 every 10 frames confirmed at mean ATE 0.185, and IID .1 every 10 frames at 0.398. Per-flight GT lookup and attempt/accept counters passed for both; see `confirm48_results.json` for each value and audit, and `confirm48.log` for the full runner output. No failures occurred. The perfect and IID observations remain diagnostic and were not inserted into the current artifact.
