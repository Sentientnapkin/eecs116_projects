# Oracle current-anchor port complete

The initial no-go was superseded after a velocity-only harness transplant and successful controls. The portable code and runners are `port.py`, `run_screen.py`, and `run_confirm48.py` in this directory. `SCREEN24.md` summarizes screening results; `confirm48_results.json` contains per-flight ATE/error records and GT measurement counter audits; `confirm48.log` contains runner output.

Required gates all passed:

- OR=0 wasm hash is byte-identical to current SN anchor: `1a169f28916acd813f86a7b526efb8e8b646b3dda73e48cba51b12845c69b1b8`.
- OR=1 with interventions off has exact per-flight ATE and error identity on both 24-flight and 48-flight pools.
- GT lookup hit and measurement attempt/accept counts match on every instrumented flight. On the 48-flight confirmation both perfect and IID arms had 48/48 lookup hits and 120/120 accepted velocity updates per flight. On the 24-flight time-limited arms, counts were 1 per flight for frame-0 only and 21 per flight through frame 20.
- No flight failures occurred in the reported pools.

48-flight confirmation means: current anchor / OR=1 off `0.5684789`; perfect body velocity, assumed sigma 0.02, every 10 frames, actual noise 0: `0.1850488`; IID body velocity sigma 0.1 every 10 frames: `0.3983886`. These are ground-truth diagnostic results only. No current-best/deployed artifact was changed. Do not promote an oracle arm as deployable without an available non-oracle source for the observation and separate validation.
