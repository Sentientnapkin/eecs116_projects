# Movement gate for the startup prior of f0  (WORK IN PROGRESS, updated as I go)
Source: gate/g.c = f0.c + a switchable GATE_* define block (GATE_MODE 0 = bit-identical to f0). Search slice = folds 0-2 (n=119), val = fold 3 (3 finalists only), fold 4 never read.

## KEY CORRECTION to the preflight finding (verified in the guest itself)
The preflight REPORT claims the f0 motion detector is a constant (|mean f| ~9.8 > 8.8 always). That is measured on `imu_window(1)`, but the harness
gives frame 0 an IMU window too (viobench/tools/datasets/episode.py `imu_window`: "frame 0 gets one frame interval as well"), so the guest's initialize()
sees window 0 (10 samples, t=0..0.045 s), where the motors have not spun up yet. I built f0 with a debug output of the detector inputs (gate_dbg3, search n=119):
  static (56): |mean f| 8.13 / 8.37 / 8.69 (min/med/max), |mean gyro| 0.00 / 0.06 / 0.11      -> detector says NOT moving, 56/56
  mid    (63): |mean f| 8.81 / 9.90 / 11.35,                |mean gyro| 0.04 / 0.62 / 1.33      -> detector says moving, 63/63
So in f0 as measured, hover starts ARE untouched (search static 0.678 is the baseline-rebuild number, 56/56 bit-identical between f0 and every gate arm).
The detector is correct but with thin margins: static max |f| 8.69 vs threshold 8.8 (0.11 m/s^2); 8 of 63 mid starts are detected by force alone (gyro <= 0.2),
the closest has |f| 8.81. The user's numbers (static gyro 0.16-0.24, f ~9.6) are window 1 statistics (spin-up), not what the guest sees at init.
Consequence: on this pool the vision gate cannot improve static starts (already baseline); its role is (a) protection if the IMU detector false-triggers
(thin margin, drift of hover thrust, other vehicles) and (b) releasing the prior on genuinely slow mid starts.

## Vision statistic (calibration, search slice only, n=119; gate_dbg build = f0 dynamics, GATE_MODE 0)
d_k = median de-rotated disparity (px) between consecutive clones (vision_zupt's statistic), pair k at t = 0.045 + 0.2k s (first measurable pair ~0.25 s;
needs >= 10 matched features, else no value). Percentiles 0/10/50/90/100 over flights:
| pair (t) | static d | mid d |
|---|---|---|
| 1 (0.25 s) | 0.21 0.41 0.80 1.19 1.73 | 1.09 2.43 6.93 12.1 19.9 |
| 2 (0.45 s) | 0.29 0.49 0.80 1.21 1.59 | 0.64 2.88 6.42 13.4 19.9 |
| 3 (0.65 s) | 0.35 0.46 0.78 1.22 1.41 | 0.78 2.51 6.18 14.6 22.1 |
| 5 (1.05 s) | 0.21 0.34 0.70 1.32 1.70 | 0.85 1.97 6.38 12.8 26.0 |
Static median d is 0.8 px, ABOVE the existing ZUPT threshold 0.4 (de-rotation with gyro-bias error, KLT noise): the existing vision ZUPT rarely fires on hover starts,
so the gate threshold must sit well above 0.4. Static pairs 1-5 (hover, n=275): mean 0.80, sd 0.31, max 1.73; threshold 2.0 is 3.8 sd out.
Mid d is ~7 px per m/s of speed (corr(d, true speed) 0.68). Truth check: start speed = norm of the truth twist velocity (camera axes, invariant norm),
mean over t<=0.45 s; static flights all 0.04 m/s; mid p10 / median / p90 = 0.31 / 0.94 / 1.9 m/s (a few are ~0).

## The gate as built (GATE_MODE 1, defaults GATE_DISP 2.0, GATE_PAIRS 2, GATE_PAIRS_MAX 5)
Inside vision_zupt() (only data up to the current clone): for each clone pair with >= 10 matches keep max d. If max d >= GATE_DISP the prior stays for good (latched).
If >= GATE_PAIRS valid pairs (t ~0.45 s) have all been below GATE_DISP (and the decision is within the first GATE_PAIRS_MAX pairs, 1 s) the prior is RELEASED:
imu_measurements() stops applying the heading prior (falls back to the original zero-mean speed prior), and a ZUPT update (sigma 0.02 m/s, r = -v) is forced
once, which pulls the 0.9 m/s prior-mean velocity (and its correlated states) to zero with a proper update instead of a state overwrite. Pairs with <10 matches do
not count; "undecided" keeps the prior (conservative default, the cheap error). The IMU startup branch (initial tilt 0.15, prior initial velocity) is unchanged,
the gate only acts when the IMU detector said moving. GATE_MODE 2 = soft form: prior mean scaled by w = clamp(mean d / GATE_SOFT_D, 0, 1), sigmas by 0.3 + 0.7 w.
Test-only switches: GATE_STRESS (detector sees window 0 with 2x noise, 2x bias range), GATE_STRESS_OFF, GATE_DEBUG (writes d into estimate.tum position columns).

## Confusion of the gate decision (rule: release iff max over clone pairs so far < 2.0 px), search slice, per flight

decision after pair 1 (t~0.25 s); REL=release prior, hold=keep, undec=<10 matched features so far (prior stays)
| group | n | REL | hold | undec |
|---|---|---|---|---|
| static label | 56 | 55 | 0 | 1 |
| mid label | 63 | 5 | 49 | 9 |
| mid, true |v| 0-0.2 m/s | 3 | 1 | 0 | 2 |
| mid, true |v| 0.2-0.5 m/s | 12 | 3 | 7 | 2 |
| mid, true |v| 0.5-1.0 m/s | 23 | 1 | 20 | 2 |
| mid, true |v| 1.0-9 m/s | 25 | 0 | 22 | 3 |

decision after pair 2 (t~0.45 s); REL=release prior, hold=keep, undec=<10 matched features so far (prior stays)
| group | n | REL | hold | undec |
|---|---|---|---|---|
| static label | 56 | 55 | 0 | 1 |
| mid label | 63 | 3 | 51 | 9 |
| mid, true |v| 0-0.2 m/s | 3 | 1 | 0 | 2 |
| mid, true |v| 0.2-0.5 m/s | 12 | 2 | 8 | 2 |
| mid, true |v| 0.5-1.0 m/s | 23 | 0 | 21 | 2 |
| mid, true |v| 1.0-9 m/s | 25 | 0 | 22 | 3 |

decision after pair 3 (t~0.65 s); REL=release prior, hold=keep, undec=<10 matched features so far (prior stays)
| group | n | REL | hold | undec |
|---|---|---|---|---|
| static label | 56 | 55 | 0 | 1 |
| mid label | 63 | 2 | 54 | 7 |
| mid, true |v| 0-0.2 m/s | 3 | 1 | 0 | 2 |
| mid, true |v| 0.2-0.5 m/s | 12 | 1 | 10 | 1 |
| mid, true |v| 0.5-1.0 m/s | 23 | 0 | 22 | 1 |
| mid, true |v| 1.0-9 m/s | 25 | 0 | 22 | 3 |

decision after pair 5 (t~1.05 s); REL=release prior, hold=keep, undec=<10 matched features so far (prior stays)
| group | n | REL | hold | undec |
|---|---|---|---|---|
| static label | 56 | 55 | 0 | 1 |
| mid label | 63 | 2 | 56 | 5 |
| mid, true |v| 0-0.2 m/s | 3 | 1 | 0 | 2 |
| mid, true |v| 0.2-0.5 m/s | 12 | 1 | 11 | 0 |
| mid, true |v| 0.5-1.0 m/s | 23 | 0 | 22 | 1 |
| mid, true |v| 1.0-9 m/s | 25 | 0 | 23 | 2 |

start speed = mean |v| over t<=0.45 s from truth (twist rows, camera axes, norm is frame invariant); static label: all 0.04 m/s
mid start-speed percentiles 0/10/50/90/100: [0.04 0.31 0.94 1.9  2.26]

released mid flights (decision at pair 2): start speed, d1,d2
  fastmid-107734254_176000121-00 speed 0.50 d [1.65, 1.54, 3.12]
  fastmid-ProcTHOR-Train-107-00 speed 0.04 d [1.09, 0.64, 1.46]
  fastmid-ProcTHOR-Train-5-02 speed 0.20 d [1.77, 1.08, 1.29]

mid: corr(d pair2, speed) 0.68 ; median d/speed ratio 7.2 px per m/s
static pairs 1-5 (hover) n=275 mean 0.80 sd 0.31 max 1.73; (thr-mean)/sd = 3.8

row-level change a_h20 vs f0 (flights where ATE differs):
  fastmid-107734176_176000019-00 mid f0 0.572 gate 1.066 speed nan fold 3
  fastmid-107734254_176000121-00 mid f0 0.493 gate 0.331 speed 0.50 fold 1
  fastmid-ProcTHOR-Train-107-00 mid f0 0.654 gate 0.519 speed 0.04 fold 0
  fastmid-ProcTHOR-Train-5-02 mid f0 0.680 gate 0.380 speed 0.20 fold 0


## Arms (search = folds 0-2 n=119, 56 static / 63 mid; val = fold 3, 3 finalists only: a, b, c; all deltas vs f0 = final_f0 unless noted)
| arm (results/single_model/gate_*) | change | search mean / med | static | mid | >5 / >10 m | paired d vs f0 [95%] | val mean (mid) | verdict |
|---|---|---|---|---|---|---|---|---|
| f0 | reference | 1.033 / 0.54 | 0.678 | 1.348 | 4 / 0 | = | 0.524 (0.447) | |
| k0_off | g.c, GATE_MODE=0 | 1.033 / 0.54 | 0.678 | 1.348 | 4 / 0 | 0.000, 119/119 bit-identical | | switch is inert |
| a_h20 | hard release, thr 2.0 px, 2 pairs | 1.028 / 0.52 | 0.678 | 1.339 | 4 / 0 | -0.005 [-0.012,+0.000] (3 flights differ) | 0.543 (0.485) | neutral; ADOPTED build |
| b_h15 | hard, thr 1.5 | 1.032 / 0.52 | 0.678 | 1.346 | 4 / 0 | -0.001 [-0.004,0.000] (1 flight differs) | 0.524 (0.447) | neutral |
| c_soft3 | soft, D=3 px | 1.048 / 0.54 | 0.678 | 1.378 | 4 / 0 | +0.016 [-0.060,+0.088] (13 differ) | 0.512 (0.424) | neutral, noisier, not preferred |
| adopted | a_h20 as adopted.c defaults | = a_h20 bit-identical 119/119 | | | | | | |
Static flights are bit-identical to f0 in every arm: the detector already leaves them alone, and the gate only acts on flights that the IMU detector called moving.
The 3 search flights that a_h20 changes are the slow mid starts it releases (start speed 0.50, 0.04, 0.20 m/s): ATE 0.493->0.331, 0.654->0.519, 0.680->0.380
(all improve, i.e. releasing the prior on slow starts is harmless or mildly helpful; sample of 3). On val one mid flight goes 0.572 -> 1.066 (+0.49, a_h20 releases it;
b_h15 does not) which is the only visible cost; n=1, within the run-to-run noise but it shows the release is not free for borderline-speed starts.

## Robustness (the point of the gate: protect hover starts if the IMU detector fails). Search slice, vs f0 (=baseline-like static 0.678)
| scenario | static | mid | note |
|---|---|---|---|
| s3 f0, detector forced always-moving (DET_FORCE 7.5; the preflight's "constant detector" world, also what a step-0-without-IMU fixture gives) | 0.872 (+0.19 [+0.06,+0.38] vs f0) | 1.348 | prior wrongly on for all hover starts |
| s4 gate a_h20, same forced detector | 0.659 (-0.018 [-0.105,+0.069]) | 1.339 | gate undoes the damage: hover starts back at baseline level |
| s1 f0, 2x noise + 2x bias range on the detector's first window | 0.673 (54/56 identical) | 1.419 (+0.07 [0,+0.22]; 1 mid flight) | few detector flips (|f| margin 0.11, rarely crossed) |
| s2 gate a_h20, same stress | 0.673 | 1.410 | same; 2x IMU noise does not flip the vision gate (it does not use IMU) |
So the vision gate is insensitive to IMU noise/bias; the IMU detector is the fragile part (static max |f| 8.69 vs 8.8 threshold; 8/63 mid starts are detected by force alone).
Long hover: the decision is latched at ~0.45 s, so a hover of any length keeps the prior released; if the vehicle later accelerates, the filter behaves like the original
baseline (and f0's prior would have expired at 2 s anyway). What I could NOT test: the pool's hover starts last only 1 s (pairs 1-5), the static d statistic has been
checked for 1 s only; a hover of minutes can raise d through gyro-bias drift (de-rotation error), scene texture loss (<10 matches -> undecided -> prior stays, i.e. f0 behaviour),
or vibration; the 3.8 sd margin makes a false hold unlikely at the decision time (0.45 s) but later-decision variants are untested. Also untestable: IMU stress on the filter
itself (only the detector input was perturbed), real start-from-rest flights with different hover thrust (a different |f| shifts the IMU detector, not the vision gate).

## Causality
check_future_poison.py on gate_a_h20 wasm, 3 sensor-only 300-frame fixtures (1 static, 2 mid incl. the released ones) x prefixes 2, 41, 120, 299: 12/12 pass
(repeat, prefix equality, future-sensor poisoning; results/single_model/gate_causal/poison.log). The fixtures deliver NO IMU at step 0 (make_sensor_fixture.py),
so there the detector sees window 1 (constant detector): the gate release path is exercised too and still causal. The gate uses only quantities that exist at
the current clone (disparity of the last two clones).

## Another discrepancy worth knowing
make_sensor_fixture.py (used by all causality/preflight fixtures) gives step 0 an empty IMU window, while the real `viobench evaluate` delivers the 10-sample window 0
(guest debug count = 10 at initialize). So the preflight's constant-detector finding holds for the fixture/server-style delivery IF the real server also withholds window 0,
and does not hold for our local evaluations. I cannot tell which the sealed/server harness does (viobench's own Episode.imu_window docstring says frame 0 gets a window);
this is exactly why the vision gate is a useful backstop: s3/s4 above show f0 static 0.872 vs gated 0.659 in the constant-detector world, and no loss in the working-detector world.

## Recommendation
Adopt gate/adopted.c (diff: gate/adopted.patch, 109 lines, GATE_MODE 1, thr 2.0 px) ONLY as a safety net, not as a score improvement: end-to-end search change is -0.005
(3 of 119 flights differ; static identical; no >10 m flights; causality holds). Benefit: it makes hover-start behaviour independent of the IMU detector
(+0.19 -> -0.02 in the constant-detector scenario). Cost: one borderline slow mid start in val got worse (+0.49), so use thr 2.0 only if the detector may fail; if you are sure
the harness delivers window 0 and want zero risk to mid starts, thr 1.5 (b_h15) is the more conservative choice (changes 1 flight). Soft form not recommended.
Files: gate/g.c (arms), gate/adopted.c, gate/adopted.patch, gate/calib.py, confusion.py, tables.py, pair2.py, series_search.json, tables.txt, logs.
