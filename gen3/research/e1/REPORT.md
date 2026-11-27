# e1 REPORT: ultra-cheap VIO (target ~10k peak fuel)
Labels: MEASURED (run here), NEW EXPERIMENT, MATH, HYPOTHESIS, UNKNOWN. Everything in research/e1/. Dev subsets: s40 = 40 flights (every 9th of pools/v3val; real wasm eval via ev.py), cache20 = 20 of them (native sim, sim.py; no fuel). The full 358-flight v3val was NOT run (all candidates were far from break-even).

## Bottom line
- MATH/MEASURED: break-even vs today (8.23 = 0.586 m @ 4.1 M): at 10k fuel ATE must be < **1.79 m** (not 1.65); at 3k < 2.02; 30k < 1.57; 100k < 1.32; 300k < 1.08; 1M < 0.84 (gain.py, exact server formula).
- NEW EXPERIMENT: the best honest ultra-low-fuel builds reach only **7.4-7.9 m ATE (s40; identity pose = 9.7 m)** at 20-70k fuel, gain 0.00-0.04 (all inside the baseline-dominated region). Nothing near 1.8 m. Verdict: **2 m @ 10k is not achievable with this approach; I judge it infeasible (HYPOTHESIS, backed by the oracle bounds below).** Recommend abandoning Target E; the 1M-4M region is where the score is.

## Q1 measured costs (wasmtime fuel under viobench make_config; mb.c / mb.py)
| item | fuel |
|---|---|
| step with ABI only, identity pose out (build b_m0, full eval peak) | 113 (frame size irrelevant: host resize/copy is NOT charged) |
| reading 64 scattered G pixels | 1,283 (~20 each incl. index math); 1,200 px on a stride-8 grid 6,400 (~5.3/px) |
| 10 IMU samples, double precision, exp-map rotation (sin/cos) | 5,756 |
| 10 IMU samples, float first-order rotation + renorm | 1,564 |
| 10 samples fixed point (Q16, int64 products) | 2,575 (worse than float) |
| frame-averaged IMU (sum 10 rows, one rotation update) | 655 |
| 8x8 SSD over 3x3 search (9 positions) | 6,257 |
| one 7x7 Lucas-Kanade iteration | 2,358 |
| 6-state scalar EKF update | 349; 6x6 covariance propagate (dense) 1,454 |
| rotation->quaternion + frame change | 87 |
| 4x4 box downsample of full frame to 80x60 (G only) | 457,000; 8x8 box to 40x30 402,000 |
- frame_width() accepts only 320 (default) or 640: **no tiny image can be requested**; minimum is 320x240x3 = 230 KB, but unread pixels cost nothing, so reading N pixels costs ~5-20 fuel each. Any dense downsample is impossible at this budget (400k+). (ABI.md, MEASURED)
- Init fuel is free (EXISTING, i1: separate fuel_init budget 2e11), so tables/priors can be built in init(); I did not need it.
- Budget at 10k: IMU (float, averaged ~0.7-1.6k) + ~1-2 LK patch tracks (~4.4k each as built) + a small EKF. Measured full builds: peak = ~2.3k + ~4.4k per tracked 7x7 patch (NF=4: 19.9k, NF=8: 36.4k, NF=16: 69.2k).

## Q2 baselines (real wasm, s40, mean unaligned ATE, 40 flights)
| build | ATE | median | peak fuel | note |
|---|---|---|---|---|
| (a) identity / constant pose (b_m0, sha 4312c2ef) | 9.71 | 9.61 | 113 | rooms 3.0, warehouse 13.9, forest 14.5 |
| (b) IMU dead reckoning, gravity from first accel mean (b_m1) | 1510 | 1379 | 6,708 | accel bias + tilt error, explodes |
| (b') DR + accel-tilt Mahony (b_m1att) | 116 | 110 | 12,981 | |
| (b'') DR + velocity damping 0.5/s (b_m3) | 149 | 125 | 7,880 | |
| (c) gravity-aligned attitude only, position 0 (b_m2) | 9.71 | 9.61 | 5,899 | ATE ignores attitude, so = identity |
- Native sim (cache20, ORACLE attitude, no vision): leaky-velocity IMU integration 9.2-17 m, i.e. no better than identity. IMU alone carries NO usable position information. Attitude: gyro-only drifts ~1 deg/s (bias up to 0.02 rad/s); accel tilt Mahony (K 1.0, Ki 0.05) halves tilt error but yaw is unobservable.
- Local flights are NOT short: GT path mean 74.5 m (not 17 m) over 60 s; identity ATE ~9 m matches the server's (113 fuel, 7.55) baseline scale.

## Q3 oracle bounds (MATH-style, from GT paths; bounds.py, cache20)
| perturbation of the GT path | ATE |
|---|---|
| zero pose | 9.20 |
| scale error x0.7 / x0.8 / x0.9 | 2.76 / 1.84 / 0.92 |
| heading error 2 / 5 / 10 / 20 deg (about vertical) | 0.31 / 0.78 / 1.56 / 3.10 |
| oracle direction + hover flag, constant speed 0.5 / 1.0 / 1.5 m/s | 5.86 / 2.81 / 2.87 |
- Consequence: matching today at 10k needs scale error < ~20% AND heading error < ~11 deg for the whole 60 s, simultaneously. Even PERFECT direction with a constant-speed prior misses (2.8 m). The scale (metric speed) is the missing information; ~10 flow-measured scalars cannot provide it without depth.

## Q3 estimators built (src/ev1.c, src/ev2.c; mk.py builds)
1. ev1: gyro attitude + gyro-predicted persistent LK patches (7x7 @ stride 2, 1 iteration) + 6-state (v, accel bias) EKF with per-feature epipolar velocity-direction constraints, ZUPT, speed prior. NEW EXPERIMENT: **diverges** (hundreds to thousands of m) even with oracle attitude: along-track speed is unobservable from direction-only constraints, accel bias runs away, EKF overconfident (innovations 8-30 deg off). Killed. (Also found+fixed two bugs: GT file orientation is the IMU frame, not camera; template-centre bookkeeping in the tracker.)
2. ev2 (kept): same tracker, but linear least squares of translational flow for velocity-per-unit-depth w (3x3 normal equations, 8 features), metric scale Z from IMU-vs-flow velocity-change energy ratio over 1 s windows (Z clamp 0.8-30 m), v = Z w, position = integral; Mahony tilt correction. NEW EXPERIMENT diagnostics (cache20, ORACLE attitude): velocity direction cosine to GT median 0.96-0.97 (p25 0.89), speed ratio median 0.5-0.7 with a 3x interquartile spread -> ATE 7.1; with real gyro attitude+tilt: 8.1; scale shrink of output 0.6: 7.45.
3. Real-wasm results (s40; flags ZMODE=1 KAP=0.02 NW=20 WLP=0.3 TILTK=1.0 TILTKI=0.05):
| build (wasm, flags beyond the above) | ATE | median | peak fuel | gain() |
|---|---|---|---|---|
| builds/w_nf4/solution.wasm (sha 5e2a0201, NF=4) | 7.78 | 6.74 | 19,910 | 0.00 |
| builds/w_nf8 (43bc46bb, NF=8) | 7.92 | 7.47 | 36,351 | 0.00 |
| builds/w_nf16 (448f3785; NF>8 only repeats seed positions, = nf8 accuracy) | 7.92 | 7.47 | 69,235 | 0.00 |
| builds/w_nf8_s5 (33f381a8, NF=8, output x0.6) | 7.45 | 6.74 | 36,353 | 0.04 |
- Best gain on the ultra-low side that I found: **~0.04** (7.45 m @ 36k). For reference gain(1e5, 5 m)=1.68, gain(1e4, 3 m)=5.15; to be competitive one needs <=1.79 m @ 10k, <=1.32 m @ 100k.
- Not done (UNKNOWN effect): learned speed prior/lookup, hover detector beyond flow-threshold ZUPT, full-v3val/v1val runs, 3 replicates. They cannot close a 7.5 -> 1.8 m gap given the bounds above.

## Failure modes
- Flow > 3 px/frame at 320 px breaks 1-level LK (fast flights, ~10% of frames); features reseed -> v=0.
- Textureless/forest/warehouse: weak-gradient reseeding; scale from depth varies 2-15 m by scene, so a fixed Z prior is off by 3-4x (speed ratio median 0.25 with Z0=3).
- Errors-in-variables bias in the IMU scale regression (w noise) pushes Z low; energy-ratio version better but noisy.
- Gyro bias (<=0.02 rad/s) -> ~60 deg yaw drift over 60 s; without vision-bias estimation heading is the dominant error at 10k.

## Reproduce
`python3 mk.py NAME "DEFS" src/ev2.c`; `venv-teacher/bin/python ev.py e1_NAME builds/NAME/solution.wasm pools/s40 8`; summaries in res/summary.tsv; native loop: `sim.py src/ev2.c "DEFS"` (needs `extract.py pools/s40 cache 2`), oracle bounds `bounds.py`, micro-bench `mb.py`.
