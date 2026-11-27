# Gyro-bias investigation: first diagnostic screen

Date: 2026-11-23. Scope: diagnose the submitted GSLV build; no holdout, fold 4, server episodes, or training.

## Exact build and method

The diagnostic source is a copy of `research/single_model/learnvel/final/gslm_lvnet.c` with logging only. It records each successful EKF update's frame, update phase, row count, gyro-bias correction, and resulting bias. Phases: 1 = learned-velocity re-anchor; 2 = vision; 4 = IMU measurement update. `TC_LOG` and `AUD_STATS` are on for the diagnostic copy. The original submitted source and WASM are unchanged. Submitted WASM SHA256: `5e4d2a0d40333b3f5152d60de84a688abc5d0eec8c1c73fa402dc9907839d196`.

A seven-flight replay used cached `fc_pools/st2bad` and `st2good` episodes (four difficult, three controls), 4 workers. Diagnostic build: all 7 completed, zero filled frames. Debug logging changes fuel, so its peak is diagnostic overhead and is not a fuel result.

## Finding on 100-009

The failure persists in the exact submitted estimator: ATE 3.159 m; mean / p90 / maximum tilt error 10.3 / 12.2 / 14.4 degrees. Truth-derived gyro bias is approximately `[-0.0187, +0.0028, -0.0209]` rad/s.

At frame 71 (3.55 s), an LC learned-velocity update changed estimated gyro bias by approximately `[+0.0098, +0.0116, +0.0004]` rad/s. The end-of-frame monitor reports `att=0`, `gate=0`, `tri=0`, `live=15`, `nanch=3`, `fire=6`: no attempted corner feature update on that frame. `lc_apply()` builds an observation Jacobian on velocity (or the velocity-at-anchor state) only; the bias mean nevertheless moves through the EKF's velocity–gyro-bias cross-covariance. This is the strongest identified mechanism so far.

By 5 s, estimated bias is about `[+0.0068, +0.0210, +0.0016]`, roughly 0.039 rad/s from truth. Net re-anchors contribute materially to this early movement; vision and IMU updates also contribute and later partly correct it. So the current failure is not explained by “vision alone,” and the existing ±0.021 clamp does not prevent transient bias error or accumulated tilt drift.

The other pilot flights show why globally freezing bias during all net updates is unsafe: visual and net updates can help estimate bias on non-failing flights. `142-003` and `64-004`, for example, received substantial visual corrections toward their true biases.

## First candidate screen: rejected

A clean copy of the exact submitted source tested an exact Schmidt/consider-state treatment for every learned-velocity update: suppress the gyro-bias mean correction, leave the bias covariance block unchanged, and update the active/bias cross-covariance normally. One paired screen on the same seven flights worsened mean ATE from 0.783 to 0.924 m. Per-flight changes (candidate minus diagnostic baseline) were: 108294897 +0.169 m; 100-009 +0.554; 142-003 -0.074; 160-009 +0.042; 85-009 -0.004; 64-004 -0.084; 166-007 +0.382. One screen is not a final statistical evaluation, but blanket Schmidt treatment is not a good candidate and will not be promoted.

## Next cheapest useful step

Instrument line-update successes per frame and the current visual row/feature evidence. Then screen a conditional version of the same Schmidt treatment only when a learned-velocity update fires on a frame with no effective visual information (zero accepted corner rows and zero accepted line rows), first on these same seven flights. Do not use `u20`/`tc_used`; prior notes found that counter is stuck at zero. If this narrowly conditioned pilot does not reduce the 100-009 bias impulse without harming controls, stop this branch. Any promising result needs paired multi-replicate confirmation on the difficult and fresh sets before adoption.

## Artifacts

- Instrumented source: `gslv_submitted_diag.c`
- Blanket-Schmidt candidate: `../gbias_trial/gslv_submitted_bg_schmidt.c`
- Diagnostic output: `research/results/single_model/lv_gbfinaldiag/`
- Candidate output: `research/results/single_model/lv_gbfinalsch/`
- Paired screen tables: `research/single_model/learnvel/tables/gbfinaldiag__pool.json`, `gbfinalsch__pool.json`

## Follow-up for high-rate rotation clue

The user reports that the four repeatedly poor hidden MSCKF episodes have aggressive/high-frequency gyro motion. We did not inspect or evaluate those hidden episodes. Instead, we ranked the permitted local st2dev pool by gyro-rate p99 and selected the top 20 public development flights. They have ground-truth angular-rate p99 about 1.66–1.80 rad/s and angular-acceleration p95 about 5.65–6.96 rad/s². The known 100-009 runaway is milder (1.14 rad/s and 4.47 rad/s²), so it is not a good stand-in for that failure mode.

### Bias-jump cap on the actual submitted arithmetic build

Ported the candidate to a copy of `linejac/final/gslv_linejac_arith.c`: on a net re-anchor only, when the current frame has no accepted corner rows and no accepted line rows, if the EKF would move gyro bias by more than 0.005 rad/s, apply the Schmidt/consider-state update instead. On the 7-flight diagnostic/control pilot it changed only 100-009: ATE 3.171 -> 2.661 m; the other six were identical to three decimals. No >3 m flight remained in that 7-flight screen. This is a narrowly targeted tail result, not a full-set result and not yet a submission candidate. On the top-10 high-rotation pool it was bit-identical to baseline.

### Gyro integration screens

- Full midpoint gyro integration (average adjacent gyro samples on every interval) improved the first top-10 single-rep mean slightly, 0.2405 -> 0.2355 m, but created a severe 100-009 regression, 3.171 -> 7.222 m. Rejected.
- Rate-gated midpoint (midpoint only when either adjacent corrected gyro norm exceeds 1.3 rad/s) on the first top-10 was 0.7% better in rep 0, 3.1% better in rep 1, and 0.2% worse in rep 2. Expanded to 20 top-rotation flights, it averaged 0.2739 -> 0.2719 m (-0.7%); 3-rep paired scene bootstrap 95% relative interval [-4.0%, +4.4%], seven scenes. No >3 m failures in this selected pool, but candidate peak was 4.66 M in one rep vs baseline maximum 4.33 M. Not enough evidence to keep.
- Rotating accelerometer readings with the end-of-step attitude follows the public simulator's sampling equation, but a one-rep screen was mixed: top-20 mean 0.282 -> 0.268 m; the separate 7-flight pilot worsened 0.805 -> 0.895 m, including 100-009 3.171 -> 3.593 m. Not a submission candidate.

These screens show that rotation-aware integration is a plausible direction but neither tested discretization tweak is robust enough yet. The current estimator already integrates every 200 Hz sample with an SO(3) exponential; avoid describing it as a coarse frame-rate gyro approximation.

## Other build/submission check

Recent repository records show the current `gslv_linejac_arith.wasm` (SHA256 `eb2799cbdc8dd9fa2711cdeda3062447364b6dfd4b05e72e543edd3ffa1a8e6d`) is already the best-supported submission: holdout 0.380 m vs GSLV 0.379 m (paired interval overlaps zero), with 4.30 M vs 6.02 M peak fuel; the submitted server result recorded 0.633 m and 4.2 M peak. The fuel-budget line-Jacobian variant is rejected for accuracy/tail regressions. The two-back-end ensemble pilot missed its expected gain/fuel gate. OpenVINS is much worse locally and far more expensive. Older HM40/Rsoft and startup-net builds have been superseded by the GSLV accuracy gains. STLONG/student work has no completed, gated final WASM in its notes. Nothing else currently merits replacing the submitted build.

## Current decision after the rotation-stress screens

Do not submit either gyro experiment. The 20-flight rate-midpoint result is a small, unstable gain and misses the 1.05x fuel guard in one replicate. Endpoint-accelerometer rotation is mixed and hurts the seven-flight diagnostic/control pool. The 0.005 rad/s bias-jump cap only improves the known 100-009 tail in one screen; it does not fire on the selected high-rate pool. Keep the official LJARITH build unchanged for now.

The most useful next diagnostic is an offline, truth-aligned comparison of gyro-only attitude integration against ground-truth body orientation on the top-rotation local flights, plus per-frame vision correction/error logs. That separates integration error from bias/cross-covariance and visual-update error before another code arm. The current code uses an SO(3) exponential per IMU row (`propagate` in `gslv_linejac_arith.c`); the rotation-stress work has not found a robust submit-worthy change.

## Follow-up: exact-source ablations of line/Manhattan and soft residual weighting

Date: 2026-11-23. The submitted LJARITH source already has `EDGE=1`, `EDGE_LINE=1`, vertical/horizontal/Manhattan-yaw constraints enabled, and `FC_RMAX_ON=3` (soft residual weighting, threshold 1 px). Rebuilding `linejac/final/gslv_linejac_arith.c` with the documented CMake recipe reproduced the submitted WASM SHA256 `eb2799cbdc8dd9fa2711cdeda3062447364b6dfd4b05e72e543edd3ffa1a8e6d` exactly. This confirms both proposed mechanisms are already in the submission.

To measure their contribution, made isolated source copies in `gbias_trial/` and evaluated each against that exact WASM on the same 20-flight high-rotation pool (7 scenes) and the 7-flight bias/control pool. One replicate per arm; intervals below are scene-bootstrap intervals and do not include replicate-to-replicate uncertainty. No holdout, fold 4, or server episodes were used.

| Ablation / setting | High-rotation mean ATE | Change vs LJARITH [95% scene CI] | 7-flight control mean | Peak fuel |
|---|---:|---:|---:|---:|
| LJARITH (both enabled) | 0.282 m | reference | 0.805 m | 4.05 M |
| Soft weighting off | 0.296 m | +0.014 [-0.045,+0.124] | 1.249 m | 4.02 M |
| All line features off | 0.355 m | +0.073 [+0.055,+0.138] | 0.994 m | 3.73 M |
| Manhattan constraints off, lines retained | 0.316 m | +0.035 [+0.022,+0.110] | 0.811 m | 3.56 M |
| Vertical-only line constraint | 0.315 m | +0.033 [+0.006,+0.102] | 0.771 m | 3.74 M |
| Horizontal lines + Manhattan yaw only | 0.311 m | +0.030 [+0.008,+0.046] | 0.822 m | 3.84 M |
| Horizontal lines, no yaw snapping | 0.325 m | +0.044 [+0.017,+0.092] | 0.869 m | 3.74 M |
| Soft threshold 0.5 px | 0.332 m | +0.051 [-0.017,+0.065] | 1.089 m | 4.10 M |
| Soft threshold 1.5 px | 0.284 m | +0.003 [-0.026,+0.014] | 0.835 m | 4.56 M |

Interpretation: the enabled line/Manhattan block materially helps this local high-rotation pool; disabling all lines costs about 26%, and removing Manhattan constraints costs about 12%. The small control pool does not show a clear control regression from the full configuration. Soft weighting at the submitted 1 px threshold is directionally helpful but uncertain in this one-replicate screen. Threshold changes did not improve on the submitted setting; 1.5 px exceeded the target peak-fuel guard (4.56 M vs 4.29 M baseline). Keep the existing settings; no alternative WASM is supported by this screen. The earlier tests of standalone HM40-derived builds are not used to draw this conclusion because they were not the submitted estimator.

Evaluation tables are `linejac/tables/try_ljarith__pool_highgyro20.json`, `ljarith_no_rsoft_highgyro20__pool_highgyro20.json`, `ljarith_no_lines_highgyro20__pool_highgyro20.json`, `ljarith_lines_no_manhattan_highgyro20__pool_highgyro20.json`, and their `*_controls__pool.json` / threshold-variant counterparts. All ablation sources are under `gbias_trial/gslv_ljarith_*.c`; the submitted source and WASM were not modified.
