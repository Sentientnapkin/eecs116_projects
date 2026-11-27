# n1 REPORT: learned-velocity-aided INS (IMU + slow velocity net, no vision)
Labels: MEASURED (python sim run here on real IMU+GT), NEW EXPERIMENT, MATH, HYPOTHESIS, UNKNOWN. Files: prep.py, sim.py, grid1.json/res1.jsonl, grid2.json/res2.jsonl.

## Verdict: NO-GO. No wasm built (every simulated configuration is far above break-even).
Break-even (gain 8.23): ATE < ~0.86 m @0.9 M, <1.25 @160k, <1.45 @70k.

## Setup (NEW EXPERIMENT)
- 40 flights (every 9th of pools/v3val), real 200 Hz IMU (60 s, 12000 samples), GT velocity from differentiated GT positions. Python 15-state error-state EKF (attitude, v, p, gyro bias, accel bias; tilt from first accel samples, yaw 0, v prior sd 2 m/s, gyro-bias prior 0.02, accel-bias 0.2), IMU noise 0.07 / 0.28 per sample, bias RW 6e-4/1e-3.
- Measurement: body-frame velocity z = R_true^T v_true + noise, one every P frames (net on frames at k, result arrives P frames later = amortised pipeline, handled by stochastic cloning of (attitude, v)), meas sigma per axis = net error (A160ft 0.30, A2 0.35, C_lo32 0.44; also 0.10 and 0.02 oracle-ish). Noise models: white, AR(1) tau 2 s / 6 s, per-flight scale bias (sd 1.0 x sigma/vb) plus white. Metric: mean unaligned ATE (m) over frames. NOTE sigma was applied per axis (conservative if the quoted 0.30 is a vector RMS); actual net predictions were NOT run (not needed: even near-perfect measurements fail).
- Peak-fuel link (MATH): net cost / P frames per frame, e.g. A160 8.7 M: P=10 -> ~0.9 M, A2 1.43 M: P=9 -> ~160k, P=20 -> ~70k, C_lo32 0.55 M: P=8 -> 70k.

## Results: mean ATE (m), gyro-bias unknown (realistic)
| net (sigma/axis) | P=latency frames | white | AR1 tau 2s | AR1 tau 6s | scale-bias | heading err deg (white) |
|---|---|---|---|---|---|---|
| orc | 5 | 1.76 | 1.33 | 1.28 | 1.30 | 27 |
| orc | 10 | 2.26 | 1.87 | 1.78 | 1.79 | 35 |
| orc | 20 | 3.56 | 3.40 | 3.42 | 3.40 | 42 |
| orc | 40 | 27.77 | 25.09 | 25.48 | 29.21 | 40 |
| s10 | 5 | 2.21 | 3.28 | 3.01 | 1.48 | 34 |
| s10 | 10 | 2.56 | 3.03 | 3.13 | 1.80 | 34 |
| s10 | 20 | 3.57 | 3.52 | 3.71 | 2.80 | 40 |
| s10 | 40 | 6.98 | 7.03 | 7.18 | 6.53 | 43 |
| A160 | 5 | 3.00 | 6.17 | 6.97 | 1.84 | 43 |
| A160 | 10 | 3.53 | 5.86 | 6.79 | 2.31 | 45 |
| A160 | 20 | 4.76 | 6.16 | 7.37 | 3.43 | 43 |
| A160 | 40 | 8.45 | 9.01 | 9.76 | 6.72 | 42 |
| A2 | 5 | 3.17 | 6.82 | 7.94 | 1.92 | 44 |
| A2 | 10 | 3.76 | 6.53 | 7.75 | 2.43 | 47 |
| A2 | 20 | 5.18 | 6.94 | 8.40 | 3.67 | 43 |
| A2 | 40 | 9.14 | 9.85 | 10.78 | 7.07 | 41 |
| C32 | 5 | 3.47 | 8.00 | 9.69 | 2.07 | 45 |
| C32 | 10 | 4.20 | 7.76 | 9.53 | 2.65 | 50 |
| C32 | 20 | 5.96 | 8.35 | 10.24 | 4.09 | 45 |
| C32 | 40 | 10.41 | 11.40 | 12.68 | 7.74 | 40 |

## Same with the TRUE gyro bias given to the filter (oracle; not available in reality)
| net | P | white | scale-bias | hd white |
|---|---|---|---|---|
| orc | 5 | 0.69 | 0.64 | 9 |
| orc | 10 | 0.79 | 0.74 | 8 |
| orc | 20 | 1.47 | 1.44 | 10 |
| A160 | 5 | 1.47 | 0.94 | 8 |
| A160 | 10 | 2.12 | 1.30 | 7 |
| A160 | 20 | 3.19 | 2.03 | 7 |
| C32 | 5 | 2.03 | 1.19 | 8 |
| C32 | 10 | 2.99 | 1.72 | 7 |
| C32 | 20 | 4.42 | 2.65 | 7 |

## Findings
- MEASURED: Even with 0.02 m/s velocity noise (oracle-like) and P=5 the ATE is 1.3-1.8 m; P=20 3.4 m; P=40 diverges (mean 25 m, accel bias/attitude). With net-like noise: 1.8-11 m (A160 P=10: 2.3-6.8). All misses break-even by 2-10x. The tau-correlated errors are worst (a persistent velocity bias integrates directly into position).
- MEASURED: dominant error is HEADING: final heading error 20-65 deg (white, A160 P5: 43 deg). Body-frame velocity measurements carry no yaw information; the yaw-axis gyro bias (up to 0.02 rad/s -> 1.2 rad per 60 s) is essentially unobservable (estimated-bias error 0.013 vs true magnitude 0.018: nearly no bias is learned). Consistent with e1's heading bounds (10 deg -> 1.56 m).
- NEW EXPERIMENT (oracle bias): with gyro bias known the heading error drops to 6-9 deg and ATE to 0.64-0.8 (oracle noise, P5-10), but with real net noise still 0.94 (A160 P5, scale-model) to 2.1 (white); at P=10 (0.9 M) 1.3-2.1 > 0.86. So even a free heading fix would not reach break-even except in the optimistic scale-bias model at P=5 for A160 (0.94, needs ~1.7 M peak: still worse than 0.86@0.9M). Velocity noise alone (0.3 m/s over 60 s, integrated with white noise at P>=10) already costs >1 m.
- Peak fuel claims (MATH only): IMU part cost ~1.5k/frame (e1) is negligible; the net micro-steps set the peak. Nothing measured in wasm.

## Failure modes / unknowns
- UNKNOWN: real net errors might be smaller on straight segments, but calibrated sigma was z-rms~1 (BRIEF), i.e. the sims' sigma is not pessimistic. Vision (feature tracks) is what supplies yaw/bias observability in the baseline; heading-only cheap aids (vanishing-point/Manhattan lines, in baseline) were not tried here (HYPOTHESIS: lines need image processing >=100k fuel/frame and only help in Manhattan scenes).
- Sim ignores GT-vs-IMU timing offsets and the net's frame-5 latency semantics; both would make results worse.

## Recommendation
Abandon n1 (learned-velocity INS without vision). Heading is unobservable without visual/line/mag cues and velocity noise is too large at slow update rates; 1M-4M fuel with vision remains the right region. If revisited: only a cheap yaw/bias source (e.g. few tracked far features or vanishing-point yaw at ~50k fuel) plus net velocity could be tested in this sim first (add an absolute-heading measurement with sd 3-5 deg every 1 s) before any wasm work.
