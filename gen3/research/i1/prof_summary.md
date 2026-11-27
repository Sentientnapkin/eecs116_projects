# Baseline fuel breakdown (A160+Ze0, instrumented build i1_prof) — 358 flights, 429600 frames

Per-frame fuel: max 3,738,591, p99 3,251,310, p95 2,817,972, median 2,271,962, mean 2,104,686; init frame excluded below unless named.

Per-flight peaks: median 3,468,314, p90 3,631,981; peak frame index median 708 (0 = init frame); peak frame is the init frame in 0% of flights.

Global peak: flight s3v3va-ro-9300071 frame 474 fuel 3,738,591.

| component | share of all fuel % | mean/frame | own p95 | own max | mean on per-flight peak frames | share on peak frames % | mean on frames >= p95 | share >= p95 % | on global-peak frame |
|---|---|---|---|---|---|---|---|---|---|
| host entry | 0.0 | 10 | 10 | 10 | 10 | 0.0 | 10 | 0.0 | 10 |
| IMU input filter (hz_filter) | 0.4 | 8,365 | 9,076 | 10,431 | 8,397 | 0.2 | 8,359 | 0.3 | 8,405 |
| init frame (pyramid+detect+net begin) | 0.1 | 1,519 | 0 | 2,022,533 | 0 | 0.0 | 0 | 0.0 | 0 |
| pre-propagation setup | 0.0 | 106 | 106 | 106 | 106 | 0.0 | 106 | 0.0 | 106 |
| IMU mean propagation | 0.4 | 7,372 | 7,378 | 7,378 | 7,378 | 0.2 | 7,378 | 0.2 | 7,378 |
| covariance propagation | 0.9 | 19,766 | 19,877 | 19,877 | 19,681 | 0.6 | 19,728 | 0.6 | 19,877 |
| IMU measurements (gravity/zupt/priors) | 5.8 | 122,896 | 123,474 | 253,535 | 124,872 | 3.6 | 122,781 | 4.0 | 123,474 |
| net re-anchor/startup (lc_begin/lc_step, incl. tc_prior) | 1.0 | 21,385 | 235,303 | 238,931 | 27 | 0.0 | 804 | 0.0 | 27 |
| image->gray + pyramid | 10.0 | 210,939 | 211,115 | 211,115 | 211,115 | 6.1 | 211,115 | 6.9 | 211,115 |
| KLT tracking | 15.7 | 331,165 | 465,483 | 560,875 | 325,894 | 9.4 | 254,009 | 8.2 | 437,670 |
| clone + record obs + vision zupt | 0.4 | 8,348 | 45,941 | 67,032 | 24,304 | 0.7 | 13,735 | 0.4 | 45 |
| MSCKF batching/governor selection | 0.1 | 1,819 | 3,816 | 17,436 | 63 | 0.0 | 787 | 0.0 | 0 |
| triangulation + Jacobians + nullspace (build_rows) | 13.0 | 272,904 | 523,770 | 638,216 | 1,734 | 0.0 | 76,518 | 2.5 | 0 |
| EKF visual update (update) | 28.5 | 600,704 | 1,171,785 | 1,455,759 | 4,321 | 0.1 | 161,051 | 5.2 | 0 |
| clone marginalization/bookkeeping | 0.5 | 9,903 | 42,331 | 47,633 | 29,387 | 0.8 | 17,499 | 0.6 | 848 |
| feature detection | 5.1 | 107,691 | 280,386 | 1,189,134 | 150,010 | 4.3 | 156,066 | 5.1 | 401,520 |
| map relocalize | 1.1 | 22,750 | 216,989 | 342,392 | 120,358 | 3.5 | 53,250 | 1.7 | 222,546 |
| net governor loop + monitor | 0.0 | 641 | 1,246 | 1,395 | 1,227 | 0.0 | 1,099 | 0.0 | 1,150 |
| health watch (hz_watch) | 0.1 | 2,602 | 2,616 | 2,616 | 2,590 | 0.1 | 2,598 | 0.1 | 2,616 |
| write_state + output guard | 0.1 | 1,119 | 1,209 | 1,209 | 1,120 | 0.0 | 1,119 | 0.0 | 1,097 |
| after last mark | 0.0 | 5 | 5 | 6 | 5 | 0.0 | 5 | 0.0 | 5 |
| net: gray conversion (k<16) | 1.6 | 32,907 | 281,994 | 751,984 | 0 | 0.0 | 7 | 0.0 | 0 |
| net: k16-31 | 1.6 | 32,731 | 282,054 | 752,144 | 0 | 0.0 | 11 | 0.0 | 0 |
| net: k32-55 | 2.6 | 54,204 | 467,394 | 1,112,877 | 0 | 0.0 | 39 | 0.0 | 0 |
| net: k56-61 | 1.4 | 28,832 | 198,931 | 666,224 | 0 | 0.0 | 2,495 | 0.1 | 0 |
| net: k62-73 | 2.5 | 52,180 | 493,767 | 1,207,074 | 17,648 | 0.5 | 232,678 | 7.6 | 0 |
| net: k74-85 | 3.8 | 80,660 | 640,728 | 1,869,788 | 1,424,242 | 40.9 | 1,195,209 | 38.8 | 1,762,002 |
| net: k86-91 | 1.7 | 35,850 | 293,528 | 832,228 | 714,836 | 20.5 | 370,387 | 12.0 | 538,700 |
| net: k92-94 | 0.7 | 15,122 | 88,104 | 351,336 | 140,721 | 4.0 | 91,348 | 3.0 | 0 |
| net: head k95+ | 1.0 | 20,193 | 0 | 470,120 | 153,681 | 4.4 | 80,694 | 2.6 | 0 |

Instrumented/uninstrumented per-flight peak ratio (vs evals/sw_a1_Ze0__v3val.json): median 1.0001, min 1.0001, max 1.0001 (n=358).
Uninstrumented peak over these flights: 3,738,239.
- frames >= 1,000,000: 92.23%
- frames >= 2,000,000: 68.48%
- frames >= 3,000,000: 3.06%
- frames >= 3,600,000: 0.02%

## Peak if one component cost zero (max over all frames of frame total minus that component)

- host entry: 3,738,581
- IMU input filter (hz_filter): 3,730,186
- init frame (pyramid+detect+net begin): 3,738,591
- pre-propagation setup: 3,738,485
- IMU mean propagation: 3,731,213
- covariance propagation: 3,718,714
- IMU measurements (gravity/zupt/priors): 3,615,117
- net re-anchor/startup (lc_begin/lc_step, incl. tc_prior): 3,738,564
- image->gray + pyramid: 3,527,476
- KLT tracking: 3,613,727
- clone + record obs + vision zupt: 3,738,546
- MSCKF batching/governor selection: 3,738,591
- triangulation + Jacobians + nullspace (build_rows): 3,738,591
- EKF visual update (update): 3,738,591
- clone marginalization/bookkeeping: 3,737,743
- feature detection: 3,669,011
- map relocalize: 3,597,482
- net governor loop + monitor: 3,737,441
- health watch (hz_watch): 3,735,975
- write_state + output guard: 3,737,494
- after last mark: 3,738,586
- net: gray conversion (k<16): 3,738,591
- net: k16-31: 3,738,591
- net: k32-55: 3,738,591
- net: k56-61: 3,738,591
- net: k62-73: 3,738,591
- net: k74-85: 3,282,503
- net: k86-91: 3,573,441
- net: k92-94: 3,738,591
- net: head k95+: 3,738,591

## Frame-type breakdown (mean fuel per component)

- frames with MSCKF update: 77% of frames, mean total 2,234,102, p95 2,730,156
- frames without update: 23% of frames, mean total 1,662,241, p95 3,218,075
- frames running net micro-steps: 54% of frames, mean total 1,937,577, p95 3,040,480
