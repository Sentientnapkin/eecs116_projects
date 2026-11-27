# Server twin (stage-3) — NOTES

(summary tables go here at the end)

## Log
    n=30  probe vs python: median |rel err|, p90 |rel err|, corr ; probe vs metadata likewise
    hfov        n=30 py:  0.000  0.000 r=1.000      meta:  0.000  0.000 r=1.000
    start_fwd   n=30 py:  0.000  0.001 r=1.000      meta:  0.003  0.019 r=1.000
    start_gyro  n=30 py:  0.026  0.051 r=0.999      meta: -
    start_acc   n=30 py:  0.058  0.103 r=0.990      meta: -
    distance    n=30 py:  0.000  0.000 r=1.000      meta:  0.000  0.001 r=1.000
    mean_speed  n=30 py:  0.000  0.000 r=1.000      meta:  0.000  0.000 r=1.000
    rms_dist    n=30 py:  0.000  0.000 r=1.000      meta:  0.000  0.000 r=1.000
    spread      n=30 py:  0.000  0.000 r=1.000      meta:  0.000  0.000 r=1.000
    rms1s       n=30 py:  0.000  0.000 r=1.000      meta: -
    gyro_rms    n=30 py:  0.018  0.035 r=0.999      meta:  0.033  0.064 r=0.999
    yaw_rms     n=30 py:  0.022  0.048 r=0.998      meta:  0.035  0.119 r=0.998
    jerk        n=30 py:  0.030  0.051 r=0.991      meta:  0.741  0.817 r=0.991
    accxy       n=30 py:  0.017  0.038 r=0.995      meta: -
    Y           n=30 py:  0.013  0.020 r=1.000      meta:  0.014  0.038 r=0.999
    chroma_g    n=30 py:  0.002  0.011 r=0.995      meta: -
    chroma_b    n=30 py:  0.006  0.014 r=0.993      meta: -
    grad2       n=30 py:  0.033  0.063 r=0.999      meta: -
    Ytop        n=30 py:  0.043  0.089 r=0.993      meta: -
    Ybot        n=30 py:  0.043  0.086 r=0.990      meta: -
    blurx0      n=30 py:  0.013  0.023 r=0.983      meta: -
    blurx1      n=18 py:  0.010  0.049 r=0.993      meta: -
    blury0      n=30 py:  0.008  0.019 r=0.997      meta: -
    blury1      n=19 py:  0.015  0.063 r=0.975      meta: -
- 2026-11-26T22:56Z stage feat1 done: 1748 featurized
- 2026-11-26T22:57Z stage feat2 done (re-indexed after generation): 1748 featurized rows; candidates 9729 shortlist 1718 local 478 remote 1240
- 2026-11-26T22:57Z stage match done: twin24.txt twin120.txt coverage.txt (mean d: twin24 0.885  twin120 1.168)
- 2026-11-26T23:33Z stage pools done: twin24 24 twin120 120 v3val120 120 ; zips 46G
- 2026-11-26T23:35Z eval tw_gslvlj twin120: tw_gslvlj twin120 n 120 / 120 mean ATE 1.469 median 1.050 >3m 17
- 2026-11-26T23:36Z eval tw_gslvlj twin24: tw_gslvlj twin24 n 24 / 24 mean ATE 1.433 median 1.107 >3m 3
- 2026-11-26T23:36Z eval tw_gslvlj v3val120: tw_gslvlj v3val120 n 120 / 120 mean ATE 1.774 median 1.401 >3m 21
- 2026-11-26T23:38Z eval tw_F_sp10 twin120: tw_F_sp10 twin120 n 120 / 120 mean ATE 0.918 median 0.687 >3m 4
- 2026-11-26T23:39Z eval tw_F_sp10 twin24: tw_F_sp10 twin24 n 24 / 24 mean ATE 0.726 median 0.602 >3m 0
- 2026-11-26T23:40Z eval tw_F_sp10 v3val120: tw_F_sp10 v3val120 n 120 / 120 mean ATE 0.968 median 0.799 >3m 3
- 2026-11-26T23:42Z eval tw_auto727 twin120: tw_auto727 twin120 n 120 / 120 mean ATE 0.927 median 0.658 >3m 5
- 2026-11-26T23:42Z eval tw_auto727 twin24: tw_auto727 twin24 n 24 / 24 mean ATE 0.830 median 0.634 >3m 0
- 2026-11-26T23:43Z eval tw_auto727 v3val120: tw_auto727 v3val120 n 120 / 120 mean ATE 0.916 median 0.755 >3m 3
- 2026-11-26T23:45Z eval tw_b16 twin120: tw_b16 twin120 n 120 / 120 mean ATE 1.584 median 1.081 >3m 14
- 2026-11-26T23:45Z eval tw_b16 twin24: tw_b16 twin24 n 24 / 24 mean ATE 1.616 median 1.177 >3m 3
- 2026-11-26T23:47Z eval tw_b16 v3val120: tw_b16 v3val120 n 120 / 120 mean ATE 1.922 median 1.342 >3m 24
- 2026-11-26T23:49Z eval tw_m7 twin120: tw_m7 twin120 n 120 / 120 mean ATE 1.897 median 1.484 >3m 25
- 2026-11-26T23:49Z eval tw_m7 twin24: tw_m7 twin24 n 24 / 24 mean ATE 1.790 median 1.510 >3m 5
- 2026-11-26T23:51Z eval tw_m7 v3val120: tw_m7 v3val120 n 120 / 120 mean ATE 2.509 median 1.896 >3m 35
- 2026-11-26T23:53Z eval tw_gate twin120: tw_gate twin120 n 120 / 120 mean ATE 2.084 median 1.151 >3m 24
- 2026-11-26T23:53Z eval tw_gate twin24: tw_gate twin24 n 24 / 24 mean ATE 1.849 median 1.282 >3m 4
- 2026-11-26T23:55Z eval tw_gate v3val120: tw_gate v3val120 n 120 / 120 mean ATE 2.165 median 1.394 >3m 20
- 2026-11-26T23:57Z eval tw_v4d twin120: tw_v4d twin120 n 120 / 120 mean ATE 5.628 median 4.618 >3m 89
- 2026-11-26T23:57Z eval tw_v4d twin24: tw_v4d twin24 n 24 / 24 mean ATE 5.597 median 4.976 >3m 17
- 2026-11-26T23:58Z eval tw_v4d v3val120: tw_v4d v3val120 n 120 / 120 mean ATE 7.592 median 7.028 >3m 87
- 2026-11-27T00:00Z eval tw_cv2 twin120: tw_cv2 twin120 n 120 / 120 mean ATE 6.292 median 5.308 >3m 107
- 2026-11-27T00:00Z eval tw_cv2 twin24: tw_cv2 twin24 n 24 / 24 mean ATE 6.454 median 6.297 >3m 21
- 2026-11-27T00:02Z eval tw_cv2 v3val120: tw_cv2 v3val120 n 120 / 120 mean ATE 8.321 median 7.330 >3m 106
- 2026-11-27T00:02Z stage calib done: see calib.txt, reweight.txt

## SUMMARY (final, 9 calibration builds incl. snace6e1 0.444 m)
- Sets: pools/twin24 (unique Hungarian, 1 flight/episode), pools/twin120 (5 nearest/episode); eval: twin/eval.sh NAME WASM; details calib.txt, reweight.txt, coverage.txt.
- Mean level: local/server ratio twin24 1.01-1.42 (geo ~1.2), twin120 1.10-1.58 (geo ~1.3 -> server ~= twin120 x 0.76), v3val120 1.18-1.66. Local runs pessimistic everywhere.
- Ranking across 9 builds: Spearman 0.967 for all sets; r(log) 0.993-0.997. LOO new-build error after offset: twin24 x1.13, twin120 x1.14, v3val120 class-weighted x1.10 (best), raw x1.12. Twin sets are NOT better than v3val at predicting build MEANS.
- Close builds: twin24 (F_sp10 0.73 < auto727 0.83) and twin120 (0.918 vs 0.927, tie) mis-rank F_sp10 vs auto727 (server 0.664 vs 0.586); v3val120 ranks them correctly (0.968/0.873 vs 0.916/0.826). Differences <0.1 m are not resolvable.
- Per-episode (gslvlj, snace6e1): correlation weak (log Pearson 0.24-0.64, Spearman 0.16-0.71); twin120 > twin24 for gslvlj; for snace6e1 twin24 pearson 0.49, twin120 0.24. Per-episode matching has little predictive power (chaotic per-flight ATE); episode-level twinning does not beat class-weighted v3val.
- Verdict: use twin120 (or v3val class-weighted 0.5/0.25/0.25) as ~x1.3 pessimistic predictor with ~13% error on new builds; do not trust sub-0.1 m or per-episode differences.
