# disp_teacher: learned 1 s displacement measurement for B16 (teacher -> student)

Started 2026-11-21 ~00:15 (laptop: RTX 3050 Ti 4 GB, i9-11900H 16 threads; no lab box access).
Nothing below is a result unless a table says so.

## Idea
B16's remaining error is slow horizontal drift (bulk/NOTES.md). Add a learned *relative displacement* measurement
between the newest clone and the clone 5 back (exactly 20 frames = 1 s): z = R_b^T (p_b - p_a), with a learned
per-axis Laplace uncertainty, as an EKF update (whitened, chi2(3) gate) inside B16.

Network inputs (all at 128x96, camera frame at t):
* frames t, t-10, t-20 (gray, OpenCV RGB2GRAY + INTER_AREA), the two past frames warped into frame t's orientation
  with the filter's relative rotation (rotation-only homography, inverse bilinear warp, zero padding) + validity masks;
* gravity direction in the camera frame, fx/width (FOV varies per flight);
* acceleration-only displacement a = R_c(t)^T (p(t) - p(t-L) - v(t-L) tau) over the far and mid windows (IMU
  preintegration with the filter's rotation/biases). With three views the images fix the ratio of the two baselines and
  a fixes the metric scale (classic VIO observability). First version without `a` (vision + gravity only) plateaued at
  ~0.7 relative error after 4000 steps: a monocular pair cannot observe metric scale. Restarted with `a`.
Time-scaling augmentation: the cached flights are slow (mean 0.33 m/s vs ~1 m/s server), so the lag L is drawn from
20..72 frames; the images are time-free and `a` = d - v0 tau is exactly invariant under time compression, so a 3 s
window of a slow flight is a valid sample of a 1 s window at 3x speed. Windows rotating > 45 deg are re-drawn.
Noise on the inputs mimics deployment: derotation 0.4 deg, tilt 0.5-2 deg, gravity leak + accel bias + white noise on `a`.

## Data (no flight generation possible here)
viobench-teacher-data shards (HF), one longest crop per parent flight, scenes of the 240-flight clean holdout and of
the 171 server-calibrated flights excluded: 617 flights, 155 scenes, 699 k frames (work/train_records.json).
Validation = scene hash % 12 == 0 (39 flights, never trained on). Cache: work/cache (build_cache.py).

## Evaluation (Windows-native; evalrun.py)
wasi-sdk 34 (Windows) + viobench 9b1b079 (= upstream HEAD) in C:/Users/alexa/vio_eval. Rebuilding tc_b16.c reproduces
the published B16 wasm's code and data sections byte for byte (only the producers string differs).
B16 on the 144 visible server-calibrated flights here: search 0.595 / val 0.374 (lab: 0.595 / 0.370), so local
scoring matches the lab. Sealed fold 4 is never scored.

## Checks done
* derotation direction: photometric error on rotation-only windows 0.023 (ours) vs 0.118 (inverted) vs 0.091 (none).
* target: integrating true body velocity through estimated relative rotations matches truth camera displacement to 0.02 %.
* C vs PyTorch parity (warp + forward, 24 val samples): warp 1e-5, outputs 1e-6.
* DT_ON=0 build == B16 (ATE identical on 8 flights).
* guest preintegration `a` vs truth on fast-102344193-01 frames 220/620: agree to 1-6 cm (expected tilt/bias error).

## Results so far (teacher t2 = IMU-aware v1 architecture)
Teacher validation (39 scene-held-out cached flights, lags 1-3.6 s, noisy inputs; zero predictor 0.603 m):
step 2000 0.452 | 4000 0.363 | 6000 0.334 | 8000 0.324 | 10000 0.320 m mean error (rel 1-2 m bin 0.61 -> 0.39).
Linear regression on the non-image inputs alone: 0.468 m, so the image pathway only kicked in after ~3000 steps.

DOMAIN CHECK on 40 server-calibrated flights (domain_check.py, step-8000 teacher, 1 s windows at every clone):
teacher 0.513 m mean error vs B16's own 1 s displacement 0.110 m (B16 5x better on every |d| bin); teacher
Laplace z 1.4-1.9 (overconfident on server-speed flights). The teacher is NOT a better short-horizon motion
estimate than the MSCKF; its value is as an independent anchor when B16 has diverged.

IN-FILTER, step-4000 teacher, 144 visible flights (search 119 + val 25), paired vs B16 (0.557):
| variant | mean | median | >3 m | static | mid | val | d vs B16 [95% CI] |
|---|---|---|---|---|---|---|---|
| B16 | 0.557 | 0.345 | 6 | 0.407 | 0.690 | 0.374 | |
| every 5th clone, infl 1 | 0.576 | 0.398 | 3 | 0.456 | 0.684 | 0.437 | +0.020 [-0.025,+0.061] |
| every 5th clone, infl 2 | 0.512 | 0.348 | 2 | 0.385 | 0.626 | 0.420 | -0.044 [-0.114,+0.016] |
Reading: the teacher fixes B16's tails (7 of 9 flights > 1.5 m improve at infl 1, e.g. 5.07 -> 3.58, 4.45 -> 2.88,
2.25 -> 0.89) and costs accuracy on typical flights; inflation 2 keeps most of the tail gain. Next: disagreement
trigger (apply only when the update's NIS says B16 disagrees), latest checkpoint.
Fuel: a teacher call (~400 M MAC, f32 im2col SIMD GEMM) makes its frame ~1.27 G fuel (B16 ~18 M); OpenVINS 2-4 G.

## Domain fine-tuning (the step that made it work)
The teacher-data flights are 3x slower than the server and no flights can be generated on Windows (hyperdrone
imports fcntl). So the server-calibrated flights were split BY FOLD: folds 0-1 (88 flights) -> fine-tuning data
(true 1 s windows, truth attitude + the same input noise), folds 2-3 (56 flights) -> in-filter evaluation only,
fold 4 sealed. From here on, only folds 2-3 numbers are honest for fine-tuned models.
Fine-tune: from t2 final, lr 4e-4, 50 % server windows / 50 % teacher-data, 0.6 h (runs/t3ft, final = last.pt).

Offline 1 s displacement error on folds 2-3 (domain_check.py; B16's own: 0.164 m mean / 0.083 median):
| model | mean | median | Laplace z (1 = calibrated) |
|---|---|---|---|
| teacher t2 (before fine-tune) | 0.480 | 0.360 | 2.09 / 1.42 / 1.68 |
| student s1 (distilled from t2) | 0.495 | 0.369 | 1.95 / 1.29 / 1.67 |
| teacher fine-tune step 1500 | 0.339 | 0.254 | 0.91 / 1.01 / 0.98 |
| teacher fine-tune final | 0.293 | 0.228 | 0.93 / 1.02 / 0.99 |

In-filter, folds 2-3 (56 flights; B16 mean 0.629, median 0.283, 3 flights > 3 m):
| build | mean | median | > 3 m | d vs B16 [95% CI] | peak fuel |
|---|---|---|---|---|---|
| teacher t2, 1/s, infl 2 | 0.585 | 0.317 | 3 | -0.043 [-0.193,+0.065] | 1.27 G |
| teacher t2, every clone, infl 4.5 | 0.578 | 0.308 | 3 | -0.050 [-0.200,+0.053] | 1.27 G |
| student s1, 1/s, infl 2 | 0.582 | 0.325 | 3 | -0.047 [-0.182,+0.038] | 0.42 G |
| student s1, every clone, infl 4.5 | 0.589 | 0.343 | 2 | -0.040 [-0.210,+0.078] | 0.42 G |
| ft teacher (step 1500), 1/s, infl 1 | 0.554 | 0.288 | 2 | -0.074 [-0.269,+0.071] | 1.27 G |
| ft teacher (step 1500), every clone, infl 2.24 | 0.521 | 0.278 | 1 | -0.108 [-0.366,+0.052] | 1.27 G |
| ft teacher final, 1/s, infl 1.0 | 0.563 | 0.302 | 2 | -0.066 [-0.267,+0.084] | 1.27 G |
| ft teacher final, 1/s, infl 1.5 | 0.516 | 0.289 | 1 | -0.113 [-0.295,+0.002] | 1.27 G |
| ft teacher final, every clone, infl 2.24 | 0.509 | 0.283 | 1 | -0.120 [-0.405,+0.057] | 1.27 G |
| ft teacher final, every clone, infl 3.0 | 0.486 | 0.276 | 1 | -0.143 [-0.389,+0.011] | 1.27 G |
| student s2, 1/s, infl 1.5 | 0.514 | 0.270 | 1 | -0.115 [-0.339,+0.027] | 0.42 G |
| student s2, every clone, infl 2.24 | 0.478 | 0.248 | 1 | -0.151 [-0.426,+0.017] | 0.42 G |
| student s2, every clone, infl 3.0 | 0.480 | 0.278 | 1 | -0.149 [-0.392,-0.002] | 0.42 G |
| student s3, every clone, infl 2.24 | 0.484 | 0.273 | 1 | -0.144 [-0.431,+0.034] | 0.42 G |
| **student s3, every clone, infl 3.0 = B17** | **0.456** | **0.261** | **1** | **-0.173 [-0.448,-0.013]** | **0.42 G** |
B17 by start type: static 0.358 (n=26), mid 0.541 (n=30); p90 0.88; max 3.29 m.

Student (s2/s3): model.student(), half the teacher's channel widths, ~100 M MAC (teacher ~400 M), distilled from the
fine-tuned teacher (Laplace NLL vs truth + 0.5 * |mu_s - mu_t| / b_t + 0.1 * feature hint), 50 % (s2) / 70 % (s3)
server windows from folds 0-1. Offline 1 s error on folds 2-3: s2 0.266, s3 0.254 m (teacher 0.293): the student is
better than its teacher in the server domain (it was trained on more server windows and on the teacher's targets).

## B17 = B16 + student displacement measurement (final/)
final/gp_msckf_b17_dtstudent.wasm sha256 e4d23d80d1ba143632ecd44d51077c66a360f38da1a9a2688a4a1055f7fd06a6 (2.4 MB),
source final/b17_solution.c (= tailcap/tc_b16.c + dt_weights.h(s3) + dt_core.h; DT_ON=1 DT_EVERY=1 DT_INFL=3.0).
Reduced preflight (preflight.py): viobench check ok, zero imports, byte-identical estimate.tum across two runs.
Peak fuel 418 M/frame (a student call every 4th frame); median frame 9.4 M (B16: peak 18 M).

## Caveats (read before submitting)
* B17 was picked as the best of ~10 in-filter variants on the same 56 fold-2/3 flights: its -0.173 is optimistic
  (selection bias). The CI excludes zero only barely. Neighbouring variants give -0.14..-0.15, a fairer estimate.
* Folds 0-1 are now training data for the fine-tuned models; fold 4 (sealed) was never scored here.
* The clean 240-flight holdout lives on the lab box; B17 has not been scored there. That one-shot is the decisive check.
* Not done here: the lab's causality/prefix-poison and reset/re-init replay checks (needs the lab tooling).
* Fuel: 418 M is ~23x B16; still ~5-10x below OpenVINS/VINS-Mono (2-4 G). Spreading the student over the 4 frames
  between clones (encoder of one image per frame) should bring the peak to ~110-150 M; not done.

## Reproduce
  python -I build_cache.py                                   # teacher-data shards -> work/cache (617 flights)
  vio_env/Scripts/python train.py --out runs/t2 --hours 2.2 --workers 8          # teacher
  vio_eval/Scripts/python dump_eps.py --ids <folds 0-3 ids>; python -I server_cache.py --folds 0 1
  vio_env/Scripts/python train.py --out runs/t3ft --resume runs/t2/best.pt --lr 4e-4 --hours 0.6 --extra work/server_records_f01.json --extra_frac 0.5
  vio_env/Scripts/python distill.py --teacher runs/t2/best.pt --out runs/s1 --hours 0.5
  vio_env/Scripts/python distill.py --teacher runs/t3ft/last.pt --out runs/s2 --init runs/s1/best.pt --lr 8e-4 --hours 0.5 --extra ... --extra_frac 0.5
  vio_env/Scripts/python distill.py --teacher runs/t3ft/last.pt --out runs/s3 --init runs/s2/last.pt --lr 5e-4 --hours 0.5 --extra ... --extra_frac 0.7
  export_c.py --ckpt runs/s3/last.pt --out out/b17/dt_weights.h; bash build.sh b17 out/b17/dt_weights.h DT_ON=1 DT_EVERY=1 DT_INFL=3.0
  python -I evalrun.py --wasm out/b17/solution.wasm --name b17 --ref b16 --slice f23
Training is not bit-reproducible (cuDNN, worker timing seeds); expect +-0.02-0.05 m in-filter between retrains.

## Server outcome (2026-11-21)
B17 scored 0.992 m @ 419 M on the server (B16 0.782 m @ 17 M): worse, despite -0.173 on HF folds 2-3. Diagnosis in
../proxy/NOTES.md: the server's bad episodes are startup offsets made in the first ~1 s by the learned startup net,
which the displacement student (active from 1.2 s) cannot undo, and the HF folds contain almost no such episodes.
