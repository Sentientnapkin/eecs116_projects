# Unified evaluation matrix: all candidate builds of the single estimator
Generated 2026-11-20 17:09:28 UTC by `research/single_model/matrix/matrix.py` (re-runnable; per-flight store `matrix/store/<id>.json`). Metric: mean unaligned ATE (m), never Sim(3). Pinned evaluator via run_variant / run_guest_fast.

Replicate noise: the SAME build under 1% parameter nudges moves search means by ~0.2 m and fresh means by ~0.02-0.04 m. Paired differences smaller than 0.2 (search/val) or 0.04 (fresh/holdout) are marked `(noise)`; paired CIs are scene-bootstrap (4000 resamples). Builds are deterministic, so the numbers below are single draws of a chaotic estimator (esp. mid starts).

## 1. Builds, hashes, selection use, preflight, submission
| id | build | wasm SHA-256 | wasm source | sets used for selecting/tuning | preflight | submission |
|--|--|--|--|--|--|--|
| B0 | baseline gp_msckf | `c7413a813edfdc1baf62aaac627e25df9acf7a4f1f37ea107bb3238ae7cc357d` | published: Final Project/classical_vio/gp_msckf/gp_msckf.wasm | originally tuned on its own pool; submitted (server 3.22 m) | n/a (submitted baseline; server completed 12/12) | SUBMITTED, server 3.22 m |
| B1 | f0 (startup prior) | `0d9d923cc0d36b1961e67488a08829b285b0af1eaaa7de8c9d2a2d69cf402464` | published: research/single_model/final/submit/gp_msckf_startup_f0.wasm | 171 selected (search/val); sealed fold 4 read once earlier (1.146 m) at integration, not used for a decision | PASS (check 8 = finding, not blocker) | not submitted (G submitted instead) |
| B2 | G = f0 + vision movement gate (SUBMITTED) | `ac8251454f5cf9564a09b93ae37cf258442f4854b84fffbe2fad20d72582a9b6` | published: research/single_model/final/submit/gp_msckf_startup_gate.wasm | 171 selected (search/val); fresh 711 used as confirmation only; sealed not read for selection | PASS | SUBMITTED 2026-11-19 23:06 PT, server 1.244 m (peak fuel 20.9 M, e7aa5aee 7.70 m regression) |
| B3 | gate + tails merged (REJECTED) | `73c81cedcca4684bec95112a50765b1d50fd9c86cbaa0a3341453a65412d6eb5` | published: research/single_model/final/submit/gp_msckf_startup_gate_tails.wasm | 171 selected (search/val); sealed fold 4 read once earlier (0.981 m); rejected after fresh 711 showed new >10 m tails | PASS (then REJECTED on fresh generalization) | not submitted (rejected) |
| B4 | G + C1 (hover hold + vz/lat priors) | `28ab13673e5a32370af26fad02f128b9589faf56feee7e6756f3ef2585f00214` | published: research/single_model/final/submit/gp_msckf_startup_gate_c1.wasm | search/val of the 171 (ideas screened + 3-replicate means); fresh 711 for adoption (confirmation) | PASS | not submitted |
| B5 | G + C1 + exact fuel rewrite | `dd5fb1c859cf58c865dc7a5ecb5aea3fb8725d3cbbbcc63dfd49599a99a328f0` | published: research/single_model/final/submit/gp_msckf_startup_gate_c1_exact.wasm | same as B4 (bit-identical estimates; only fuel changed) | partial: fuel-agent checks pass (ABI, byte-identical estimate.tum vs B4 on 144/144 visible, ATE identical 711/711, 8/8 fixtures, causality 40/40, reset 5/5); no standalone preflight report yet | not submitted |
| B6 | G + C1 + forward-backward KLT (FB) | `c8dc91deb9a90991d6ba962f22a474a1f33dd5efc5ab5967d3b68d492fdbb25d` | published: research/single_model/fuel/publish/gp_msckf_startup_gate_c1_fbh.wasm | search/val of the 171 (3 replicates) + fresh 711 for adoption (confirmation); fresh partly used for the decision | PASS 9/9 | not submitted |
| B7 | G + C1 + FB + exact fuel | `31137e4fb26f73249d6ededffd71669df307886a3f929ffe2bc5d28204ff0137` | published: research/single_model/fuel/publish/gp_msckf_startup_gate_c1_fbh_exact.wasm | same as B6 (exact port; estimates should be bit-identical to B6) | bit-identical to B6 (144 visible + 711 fresh); fuel agent checks done (fuel/NOTES.md Part 3); no standalone preflight report | not submitted |
| B8 | G + C1 + FB + CMBX (evaluated, not adopted) | `6287ea34612522c47d43f683fcf8b0d0aa447e96c1666a507595ca4f4cc34e2e` | matrix-built: research/results/single_model/mx_B8/solution.wasm | CMBX arm selected on search/val of the 171 and the 582 non-fold-4 fresh flights (edge work) -> fresh is NOT a clean confirmation for B8 | not preflighted (evaluated, not adopted) | not submitted |
| B9 | G + C1 + autoloop vector ba7c9bb8d93e (not adopted) | `cceab11ca1d16182495b3e2f22d577bf76384781b8dfaa4fbf67560d1975df49` | matrix-built: research/results/single_model/mx_B9/solution.wasm | tuned on search (192 vectors, 3-replicate means, fresh-A confirmation); held-out fresh-B (236) showed no gain; NOT adopted | not preflighted (not adopted) | not submitted |
| B10 | learned startup net (learned_c) | `-` | not built / not scored yet | partial port; no wasm | not built (no wasm) | not submitted |

Sealed fold 4 (n=27) numbers below are aggregates from each build's own sealed_aggregate.json, **reported once, not used for selection**. Per-flight sealed rows are never read or stored.

## 2. Headline: mean unaligned ATE (m) per set (paired difference vs B0 and vs B2 in brackets)
| id | search n=119 | val n=25 | fresh n=711 | sealed n=27 (report only) |
|--|--|--|--|--|
| B0 | 2.307 | 2.032 | 1.221 | 1.948 |
| B1 | 1.033 | 0.524 | 0.812 | 1.146 |
| B2 | 1.028 | 0.543 | 0.813 | 1.146 |
| B3 | 0.845 | 0.559 | 0.834 | 0.981 |
| B4 | 1.070 | 0.540 | 0.733 | 0.839 |
| B5 | 1.070 | 0.540 | 0.733 | 0.839 |
| B6 | 0.950 | 0.442 | 0.618 | 0.815 |
| B7 | 0.950 | 0.442 | 0.618 | 0.815 |
| B8 | 0.958 | 0.471 | 0.613 | 0.799 |
| B9 | 0.939 | 0.614 | 0.711 | 0.834 |

Holdout column: **empty** (holdout set not ready when this was generated; re-run `matrix.py --score --holdout` when `holdout/README.md` says it is final).

## 3.1 Set `search` in detail
| id | n | mean | median | p90 | max | >3 | >5 | >10 | static | mid | clean | d vs B0 | d vs B2 | peak fuel (M) | p95 max / mean (M) | median fuel (M) |
|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|
| B0 | 119 | 2.307 | 0.833 | 6.98 | 17.33 | 24 | 17 | 6 | 0.667 | 3.764 | 2.329 | - | +1.279 [+0.709,+2.000] | 22.54 | 15.98 / 14.02 | 8.37 |
| B1 | 119 | 1.033 | 0.536 | 2.11 | 8.50 | 10 | 4 | 0 | 0.678 | 1.348 | 1.261 | -1.274 [-1.997,-0.703] | +0.005 [+0.000,+0.011] (noise) | 22.54 | 15.90 / 14.08 | 8.42 |
| B2 | 119 | 1.028 | 0.519 | 2.11 | 8.50 | 10 | 4 | 0 | 0.678 | 1.339 | 1.261 | -1.279 [-2.000,-0.709] | - | 22.54 | 15.90 / 14.08 | 8.42 |
| B3 | 119 | 0.845 | 0.529 | 1.72 | 5.36 | 6 | 1 | 0 | 0.586 | 1.075 | 1.160 | -1.461 [-2.189,-0.856] | -0.183 [-0.480,+0.031] (noise) | 22.98 | 16.31 / 14.58 | 8.87 |
| B4 | 119 | 1.070 | 0.535 | 3.36 | 7.60 | 13 | 3 | 0 | 0.624 | 1.466 | 1.248 | -1.237 [-1.945,-0.669] | +0.042 [-0.135,+0.194] (noise) | 21.06 | 15.95 / 14.23 | 8.55 |
| B5 | 119 | 1.070 | 0.535 | 3.36 | 7.60 | 13 | 3 | 0 | 0.624 | 1.466 | 1.248 | -1.237 [-1.945,-0.669] | +0.042 [-0.135,+0.194] (noise) | 10.24 | 7.63 / 6.91 | 4.61 |
| B6 | 119 | 0.950 | 0.412 | 2.99 | 7.88 | 12 | 4 | 0 | 0.494 | 1.354 | 1.713 | -1.357 [-2.060,-0.790] | -0.078 [-0.278,+0.097] (noise) | 21.78 | 16.88 / 15.29 | 9.77 |
| B7 | 119 | 0.950 | 0.412 | 2.99 | 7.88 | 12 | 4 | 0 | 0.494 | 1.354 | 1.713 | -1.357 [-2.060,-0.790] | -0.078 [-0.278,+0.097] (noise) | 10.96 | 8.33 / 7.69 | 5.44 |
| B8 | 119 | 0.958 | 0.407 | 2.99 | 9.33 | 12 | 4 | 0 | 0.494 | 1.370 | 1.808 | -1.348 [-2.052,-0.786] | -0.069 [-0.279,+0.128] (noise) | 21.78 | 16.88 / 15.28 | 9.77 |
| B9 | 119 | 0.939 | 0.483 | 2.13 | 7.70 | 10 | 3 | 0 | 0.481 | 1.346 | 1.161 | -1.368 [-2.062,-0.821] | -0.089 [-0.279,+0.072] (noise) | 21.16 | 15.93 / 14.22 | 8.56 |

## 3.2 Set `val` in detail
| id | n | mean | median | p90 | max | >3 | >5 | >10 | static | mid | clean | d vs B0 | d vs B2 | peak fuel (M) | p95 max / mean (M) | median fuel (M) |
|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|
| B0 | 25 | 2.032 | 0.680 | 3.41 | 20.18 | 3 | 2 | 1 | 0.713 | 3.250 | 1.983 | - | +1.488 [+0.329,+3.241] | 20.31 | 15.78 / 14.56 | 8.63 |
| B1 | 25 | 0.524 | 0.485 | 0.80 | 1.18 | 0 | 0 | 0 | 0.607 | 0.447 | 0.481 | -1.508 [-3.254,-0.335] | -0.020 [-0.071,+0.000] (noise) | 20.99 | 15.93 / 14.61 | 8.71 |
| B2 | 25 | 0.543 | 0.485 | 0.97 | 1.18 | 0 | 0 | 0 | 0.607 | 0.485 | 0.481 | -1.488 [-3.241,-0.329] | - | 20.99 | 15.93 / 14.62 | 8.71 |
| B3 | 25 | 0.559 | 0.485 | 1.06 | 1.18 | 0 | 0 | 0 | 0.654 | 0.471 | 0.511 | -1.473 [-3.223,-0.323] | +0.016 [-0.013,+0.041] (noise) | 21.76 | 16.37 / 15.07 | 9.17 |
| B4 | 25 | 0.540 | 0.447 | 1.00 | 1.55 | 0 | 0 | 0 | 0.558 | 0.522 | 0.463 | -1.492 [-3.196,-0.334] | -0.004 [-0.055,+0.072] (noise) | 21.32 | 16.24 / 14.76 | 8.84 |
| B5 | 25 | 0.540 | 0.447 | 1.00 | 1.55 | 0 | 0 | 0 | 0.558 | 0.522 | 0.463 | -1.492 [-3.196,-0.334] | -0.004 [-0.055,+0.072] (noise) | 10.81 | 7.84 / 7.17 | 4.76 |
| B6 | 25 | 0.442 | 0.383 | 0.67 | 1.29 | 0 | 0 | 0 | 0.428 | 0.454 | 0.387 | -1.590 [-3.351,-0.459] | -0.101 [-0.173,-0.042] (noise) | 21.73 | 16.94 / 15.90 | 10.03 |
| B7 | 25 | 0.442 | 0.383 | 0.67 | 1.29 | 0 | 0 | 0 | 0.428 | 0.454 | 0.387 | -1.590 [-3.351,-0.459] | -0.101 [-0.173,-0.042] (noise) | 11.03 | 8.42 / 7.98 | 5.60 |
| B8 | 25 | 0.471 | 0.417 | 0.84 | 1.29 | 0 | 0 | 0 | 0.428 | 0.511 | 0.387 | -1.560 [-3.329,-0.409] | -0.072 [-0.148,-0.013] (noise) | 21.73 | 16.94 / 15.90 | 10.03 |
| B9 | 25 | 0.614 | 0.513 | 1.07 | 1.86 | 0 | 0 | 0 | 0.640 | 0.590 | 0.564 | -1.418 [-3.133,-0.287] | +0.071 [-0.012,+0.167] (noise) | 21.27 | 15.86 / 14.69 | 8.83 |

## 3.3 Set `fresh` in detail
| id | n | mean | median | p90 | max | >3 | >5 | >10 | static | mid | clean | d vs B0 | d vs B2 | peak fuel (M) | p95 max / mean (M) | median fuel (M) |
|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|--|
| B0 | 711 | 1.221 | 0.513 | 2.92 | 22.63 | 67 | 34 | 6 | 0.574 | 1.869 | 0.991 | - | +0.408 [+0.277,+0.561] | 22.76 | 16.06 / 14.42 | 8.55 |
| B1 | 711 | 0.812 | 0.444 | 1.46 | 12.53 | 36 | 16 | 1 | 0.573 | 1.052 | 0.747 | -0.409 [-0.559,-0.281] | -0.001 [-0.019,+0.013] (noise) | 22.76 | 16.10 / 14.45 | 8.57 |
| B2 | 711 | 0.813 | 0.437 | 1.46 | 12.53 | 37 | 17 | 1 | 0.573 | 1.054 | 0.752 | -0.408 [-0.561,-0.277] | - | 22.76 | 16.10 / 14.45 | 8.57 |
| B3 | 711 | 0.834 | 0.434 | 1.44 | 16.00 | 35 | 21 | 3 | 0.570 | 1.100 | 0.757 | -0.386 [-0.545,-0.248] | +0.021 [-0.047,+0.101] (noise) | 23.19 | 16.32 / 14.89 | 9.02 |
| B4 | 711 | 0.733 | 0.419 | 1.43 | 7.99 | 29 | 8 | 0 | 0.471 | 0.995 | 0.642 | -0.488 [-0.640,-0.361] | -0.080 [-0.146,-0.022] | 23.40 | 16.18 / 14.57 | 8.70 |
| B5 | 711 | 0.733 | 0.419 | 1.43 | 7.99 | 29 | 8 | 0 | 0.471 | 0.995 | 0.642 | -0.488 [-0.640,-0.361] | -0.080 [-0.146,-0.022] | 11.50 | 7.67 / 7.06 | 4.67 |
| B6 | 711 | 0.618 | 0.351 | 1.14 | 6.91 | 21 | 8 | 0 | 0.409 | 0.829 | 0.515 | -0.602 [-0.760,-0.469] | -0.195 [-0.275,-0.119] | 24.50 | 17.13 / 15.61 | 9.83 |
| B7 | 711 | 0.618 | 0.351 | 1.14 | 6.91 | 21 | 8 | 0 | 0.409 | 0.829 | 0.515 | -0.602 [-0.760,-0.469] | -0.195 [-0.275,-0.119] | 12.31 | 8.54 / 7.83 | 5.45 |
| B8 | 711 | 0.613 | 0.350 | 1.14 | 7.77 | 20 | 8 | 0 | 0.409 | 0.818 | 0.517 | -0.608 [-0.767,-0.473] | -0.200 [-0.286,-0.122] | 24.50 | 17.13 / 15.61 | 9.83 |
| B9 | 711 | 0.711 | 0.411 | 1.46 | 8.57 | 26 | 7 | 0 | 0.482 | 0.940 | 0.615 | -0.510 [-0.666,-0.373] | -0.102 [-0.188,-0.024] | 22.83 | 16.07 / 14.56 | 8.70 |

## 4. Sealed fold 4 aggregates (n=27, reporting only, not used for selection)
| id | mean | median | p90 | max | >5 | >10 | baseline mean on these 27 |
|--|--|--|--|--|--|--|--|
| B0 | 1.948 | 0.690 | 5.36 | 13.19 | 3 | 1 | 1.948 |
| B1 | 1.146 | 0.616 | 1.26 | 11.60 | 1 | 1 | 1.948 |
| B2 | 1.146 | 0.616 | 1.26 | 11.60 | 1 | 1 | 1.948 |
| B3 | 0.981 | 0.526 | 1.44 | 8.20 | 1 | 0 | 1.948 |
| B4 | 0.839 | 0.491 | 1.12 | 5.56 | 1 | 0 | 1.948 |
| B5 | 0.839 | 0.491 | 1.12 | 5.56 | 1 | 0 | 1.948 |
| B6 | 0.815 | 0.432 | 1.25 | 5.20 | 1 | 0 | 1.948 |
| B7 | 0.815 | 0.432 | 1.25 | 5.20 | 1 | 0 | 1.948 |
| B8 | 0.799 | 0.400 | 1.25 | 5.20 | 1 | 0 | 1.948 |
| B9 | 0.834 | 0.562 | 1.22 | 3.94 | 0 | 0 | 1.948 |

## 5. Per-class tables on `fresh` (mean ATE m; in brackets >3 m / >5 m flight counts)
| class | n | B0 | B1 | B2 | B3 | B4 | B5 | B6 | B7 | B8 | B9 |
|--|--|--|--|--|--|--|--|--|--|--|--|
| all | 711 | 1.22 (67/34) | 0.81 (36/16) | 0.81 (37/17) | 0.83 (35/21) | 0.73 (29/8) | 0.73 (29/8) | 0.62 (21/8) | 0.62 (21/8) | 0.61 (20/8) | 0.71 (26/7) |
| static | 356 | 0.57 (6/4) | 0.57 (6/3) | 0.57 (6/3) | 0.57 (7/4) | 0.47 (3/1) | 0.47 (3/1) | 0.41 (3/1) | 0.41 (3/1) | 0.41 (3/1) | 0.48 (3/0) |
| mid | 355 | 1.87 (61/30) | 1.05 (30/13) | 1.05 (31/14) | 1.10 (28/17) | 0.99 (26/7) | 0.99 (26/7) | 0.83 (18/7) | 0.83 (18/7) | 0.82 (17/7) | 0.94 (23/7) |
| clean scenes | 363 | 0.99 (24/7) | 0.75 (13/8) | 0.75 (14/9) | 0.76 (15/8) | 0.64 (8/3) | 0.64 (8/3) | 0.52 (5/3) | 0.52 (5/3) | 0.52 (5/3) | 0.61 (8/1) |
| flat fraction >0.2 | 6 | 2.29 (1/1) | 1.81 (1/0) | 1.81 (1/0) | 1.14 (0/0) | 2.03 (2/0) | 2.03 (2/0) | 2.47 (2/2) | 2.47 (2/2) | 2.52 (2/2) | 2.41 (2/1) |
| dark fraction >0.2 | 7 | 2.54 (3/2) | 2.59 (2/1) | 2.59 (2/1) | 2.18 (2/1) | 2.07 (2/1) | 2.07 (2/1) | 1.39 (1/0) | 1.39 (1/0) | 1.38 (1/0) | 1.93 (2/0) |
| mid, start-velocity angle 0-45 deg (camera axis) | 182 | 2.00 (35/14) | 0.87 (11/5) | 0.86 (11/5) | 0.93 (10/5) | 0.83 (8/3) | 0.83 (8/3) | 0.68 (5/3) | 0.68 (5/3) | 0.71 (6/4) | 0.91 (11/5) |
| mid, start-velocity angle 45-90 deg (camera axis) | 100 | 1.27 (7/4) | 0.94 (5/3) | 0.98 (6/4) | 0.96 (6/4) | 0.85 (4/2) | 0.85 (4/2) | 0.75 (4/1) | 0.75 (4/1) | 0.80 (4/1) | 0.74 (2/0) |
| mid, start-velocity angle 90-135 deg (camera axis) | 55 | 2.18 (12/7) | 1.58 (9/4) | 1.55 (9/4) | 1.45 (8/6) | 1.50 (9/2) | 1.50 (9/2) | 1.05 (5/1) | 1.05 (5/1) | 1.05 (5/1) | 1.23 (6/2) |
| mid, start-velocity angle 135-180 deg (camera axis) | 18 | 2.95 (7/5) | 1.92 (5/1) | 1.90 (5/1) | 2.51 (4/2) | 1.96 (5/0) | 1.96 (5/0) | 2.04 (4/2) | 2.04 (4/2) | 1.30 (2/1) | 1.47 (4/0) |
| mid, start speed <0.3 m/s | 66 | 1.01 (4/2) | 0.89 (4/1) | 0.87 (5/1) | 0.92 (6/2) | 0.77 (1/1) | 0.77 (1/1) | 0.62 (2/1) | 0.62 (2/1) | 0.68 (3/2) | 0.95 (4/2) |
| mid, start speed 0.3-0.6 m/s | 107 | 1.06 (6/2) | 0.75 (3/1) | 0.77 (3/2) | 0.69 (2/1) | 0.75 (4/0) | 0.75 (4/0) | 0.67 (3/1) | 0.67 (3/1) | 0.67 (3/1) | 0.67 (2/1) |
| mid, start speed 0.6-1.2 m/s | 105 | 1.98 (18/9) | 1.16 (13/7) | 1.16 (13/7) | 1.20 (10/7) | 1.02 (9/3) | 1.02 (9/3) | 0.78 (6/2) | 0.78 (6/2) | 0.77 (5/2) | 0.90 (6/1) |
| mid, start speed 1.2-1.8 m/s | 54 | 2.62 (19/7) | 0.87 (3/1) | 0.87 (3/1) | 0.81 (1/1) | 0.92 (3/0) | 0.92 (3/0) | 0.92 (2/1) | 0.92 (2/1) | 0.78 (1/0) | 0.92 (3/1) |
| mid, start speed >=1.8 m/s | 23 | 5.83 (14/10) | 2.89 (7/3) | 2.89 (7/3) | 3.77 (9/6) | 2.85 (9/3) | 2.85 (9/3) | 2.16 (5/2) | 2.16 (5/2) | 2.22 (5/2) | 2.41 (8/2) |
| regression class (fresh, B2 > B0 + 1.5 m) | 17 | 2.11 (5/2) | 5.39 (12/9) | 5.78 (14/10) | 4.27 (10/6) | 3.52 (8/4) | 3.52 (8/4) | 2.09 (4/2) | 2.09 (4/2) | 2.04 (4/2) | 3.50 (8/4) |

Class notes: angle = angle between the TRUE start velocity and the optical axis (+z of the camera-frame truth velocity; fresh/truth_feats.json, corrected convention) on mid flights with any speed (very slow starts have a poorly defined angle). Speed = true start speed. Flat/dark = sidecar audit fraction >0.2 (edge/audit.json). The regression class is defined by B2 vs B0 on the same flights, i.e. selected on the outcome: other builds regress to the mean there, so read it as a stress list, not an unbiased estimate.

## 6. 12-episode server proxy (edge/NOTES.md method)
Pool = non-fold-4 selected (144) + non-fold-4 fresh (582) = 726 flights; each of the 12 server slots (server path lengths) draws one of the 60 nearest-by-travel pool flights; a draw is mid with probability pm; 30000 draws, identical draws for every build. Reported: mean of the 12-flight mean, 5th/50th/95th percentile, P(any of the 12 > 5 m). Server anchors: B0 3.22, B2 1.244 (G sits at the 59-74th percentile of its own distribution).

### pm = 0.5 (probability a draw is a mid-flight start)
| id | mean | p5 | median | p95 | P(any >5 m) | P(>=2 >5 m) | P(12-mean >= 1.244) |
|--|--|--|--|--|--|--|--|
| B0 | 1.790 | 0.76 | 1.64 | 3.35 | 0.71 | 0.33 | 0.72 |
| B1 | 1.009 | 0.50 | 0.90 | 1.87 | 0.39 | 0.08 | 0.27 |
| B2 | 1.035 | 0.50 | 0.94 | 1.91 | 0.43 | 0.10 | 0.29 |
| B3 | 0.990 | 0.50 | 0.88 | 1.88 | 0.29 | 0.04 | 0.22 |
| B4 | 0.968 | 0.50 | 0.91 | 1.65 | 0.22 | 0.02 | 0.21 |
| B5 | 0.968 | 0.50 | 0.91 | 1.65 | 0.22 | 0.02 | 0.21 |
| B6 | 0.849 | 0.42 | 0.78 | 1.50 | 0.20 | 0.02 | 0.13 |
| B7 | 0.849 | 0.42 | 0.78 | 1.50 | 0.20 | 0.02 | 0.13 |
| B8 | 0.857 | 0.43 | 0.79 | 1.51 | 0.21 | 0.02 | 0.13 |
| B9 | 0.899 | 0.50 | 0.84 | 1.49 | 0.22 | 0.02 | 0.14 |

### pm = 0.0 (probability a draw is a mid-flight start)
| id | mean | p5 | median | p95 | P(any >5 m) | P(>=2 >5 m) | P(12-mean >= 1.244) |
|--|--|--|--|--|--|--|--|
| B0 | 0.831 | 0.45 | 0.70 | 1.54 | 0.35 | 0.06 | 0.13 |
| B1 | 0.835 | 0.43 | 0.66 | 1.65 | 0.30 | 0.05 | 0.17 |
| B2 | 0.836 | 0.43 | 0.66 | 1.65 | 0.30 | 0.05 | 0.17 |
| B3 | 0.700 | 0.44 | 0.64 | 1.17 | 0.09 | 0.00 | 0.03 |
| B4 | 0.707 | 0.41 | 0.65 | 1.19 | 0.13 | 0.01 | 0.04 |
| B5 | 0.707 | 0.41 | 0.65 | 1.19 | 0.13 | 0.01 | 0.04 |
| B6 | 0.631 | 0.36 | 0.58 | 1.08 | 0.06 | 0.00 | 0.02 |
| B7 | 0.631 | 0.36 | 0.58 | 1.08 | 0.06 | 0.00 | 0.02 |
| B8 | 0.631 | 0.36 | 0.58 | 1.08 | 0.06 | 0.00 | 0.02 |
| B9 | 0.692 | 0.43 | 0.65 | 1.09 | 0.00 | 0.00 | 0.02 |

### pm = 1.0 (probability a draw is a mid-flight start)
| id | mean | p5 | median | p95 | P(any >5 m) | P(>=2 >5 m) | P(12-mean >= 1.244) |
|--|--|--|--|--|--|--|--|
| B0 | 2.757 | 1.35 | 2.62 | 4.60 | 0.88 | 0.60 | 0.97 |
| B1 | 1.188 | 0.59 | 1.11 | 2.06 | 0.46 | 0.12 | 0.40 |
| B2 | 1.242 | 0.59 | 1.17 | 2.15 | 0.54 | 0.17 | 0.44 |
| B3 | 1.286 | 0.60 | 1.15 | 2.37 | 0.45 | 0.11 | 0.43 |
| B4 | 1.235 | 0.62 | 1.19 | 2.04 | 0.30 | 0.05 | 0.45 |
| B5 | 1.235 | 0.62 | 1.19 | 2.04 | 0.30 | 0.05 | 0.45 |
| B6 | 1.068 | 0.51 | 1.01 | 1.83 | 0.32 | 0.05 | 0.30 |
| B7 | 1.068 | 0.51 | 1.01 | 1.83 | 0.32 | 0.05 | 0.30 |
| B8 | 1.083 | 0.52 | 1.02 | 1.86 | 0.34 | 0.06 | 0.31 |
| B9 | 1.113 | 0.60 | 1.06 | 1.83 | 0.40 | 0.08 | 0.33 |

## 7. Preflight / submission status
* B0: preflight n/a (submitted baseline; server completed 12/12); evidence server run 2026-11-19 19:05 PT; submission SUBMITTED, server 3.22 m
* B1: preflight PASS (check 8 = finding, not blocker); evidence final/preflight/REPORT.md; submission not submitted (G submitted instead)
* B2: preflight PASS; evidence final/preflight_gate/ (report_a.txt, cmp_gate.txt, abi_check.txt); server result final/SERVER_RESULT.md; submission SUBMITTED 2026-11-19 23:06 PT, server 1.244 m (peak fuel 20.9 M, e7aa5aee 7.70 m regression)
* B3: preflight PASS (then REJECTED on fresh generalization); evidence final/preflight_fgt/REPORT.md; submission not submitted (rejected)
* B4: preflight PASS; evidence final/preflight_c1/REPORT.md; submission not submitted
* B5: preflight partial: fuel-agent checks pass (ABI, byte-identical estimate.tum vs B4 on 144/144 visible, ATE identical 711/711, 8/8 fixtures, causality 40/40, reset 5/5); no standalone preflight report yet; evidence fuel/NOTES.md; submission not submitted
* B6: preflight PASS 9/9; evidence final/preflight_c1_fbh/REPORT.md; wasm staged at fuel/publish/ (not in final/submit); submission not submitted
* B7: preflight bit-identical to B6 (144 visible + 711 fresh); fuel agent checks done (fuel/NOTES.md Part 3); no standalone preflight report; evidence fuel/NOTES.md Part 3; fuel/publish/; submission not submitted
* B8: preflight not preflighted (evaluated, not adopted); evidence cmbx/NOTES.md; submission not submitted
* B9: preflight not preflighted (not adopted); evidence -; submission not submitted
* B10: preflight not built (no wasm); evidence learned_c/NOTES.md: in-filter prototype on B6 (net lcF injected at frame 5) search 0.816 / val 0.442 vs B6 0.931 / 0.441 (3-rep means), peak fuel ~26 M; no plain-C wasm, no fresh/holdout scores; submission not submitted

## 8. Ranked recommendation
1. **B7 (G+C1+FB+exact fuel)**: fresh 0.618 (best, tied with B6/B8 within noise, paired vs B2 -0.195 [-0.275,-0.119], >10 m: 0, max 6.9 m), static 0.409, 12-draw proxy median 0.78 / P(any >5 m) 0.20 (B2: 0.94 / 0.43), peak fuel 12.3 M (B6/B8 24.5 M, B2 22.8 M). Estimates bit-identical to B6, which is fully preflighted 9/9; B7's own checks are by the fuel agent (no standalone preflight report yet) -> run the standard preflight on the exact wasm before submitting. Holdout: pending.
2. **B6 (G+C1+FB)**: same accuracy as B7, preflight 9/9 PASS, but 2x the peak fuel. Safe fallback if B7's preflight is not finished.
3. **B8 (CMBX on B6)**: statistical tie on fresh (0.613 vs 0.618), search/val slightly worse, no proxy improvement, fresh was partly used to select CMBX; not adopted.
4. **B5 (G+C1+exact)**: fresh 0.733, 11.5 M, strictly dominated by B7 on accuracy; B4 same accuracy at 2x fuel.
5. **B9 (tuned vector)**: search/val of B9 is within the 0.2 noise of B4; fresh 0.711 vs B4 0.733 is inside the 0.04 noise band plus held-out fresh-B showed no gain: not adopted.
6. **B2 (submitted G)**, B1, B3: B3 has no generalization (fresh worse than B2 despite search gain; more >10 m tails); B2 is the current server build at 1.244.
Common weak spots for all builds: reverse starts (135-180 deg, n=18), start speed >=1.8 m/s (23 flights, 2.2-2.9 m), flat/dark scenes (n=6/7, 1.4-2.6 m) and the B2-regression class (n=17, B6/B7 2.09 vs B2 5.78; this class is selected on B2's outcome so it flatters later builds). Sealed fold 4 numbers (reported once, not used for selection): B7/B6 0.815 vs B2 1.146 vs B0 1.948.

Automatic ranking by fresh mean (holdout mean where present), tails and peak fuel:
| rank | id | fresh mean | fresh >5 / >10 | holdout mean | peak fuel (M) | preflight |
|--|--|--|--|--|--|--|
| 1 | B8 | 0.613 | 8/0 | (empty) | 24.5 | not preflighted (evaluated, not adopted) |
| 2 | B6 | 0.618 | 8/0 | (empty) | 24.5 | PASS 9/9 |
| 3 | B7 | 0.618 | 8/0 | (empty) | 12.3 | bit-identical to B6 (144 visible + 711 fresh); fuel agent checks done (fuel/NOTES.md Part 3); no standalone preflight report |
| 4 | B9 | 0.711 | 7/0 | (empty) | 22.8 | not preflighted (not adopted) |
| 5 | B4 | 0.733 | 8/0 | (empty) | 23.4 | PASS |
| 6 | B5 | 0.733 | 8/0 | (empty) | 11.5 | partial: fuel-agent checks pass (ABI, byte-identical estimate.tum vs B4 on 144/144 visible, ATE identical 711/711, 8/8 fixtures, causality 40/40, reset 5/5); no standalone preflight report yet |
| 7 | B1 | 0.812 | 16/1 | (empty) | 22.8 | PASS (check 8 = finding, not blocker) |
| 8 | B2 | 0.813 | 17/1 | (empty) | 22.8 | PASS |
| 9 | B3 | 0.834 | 21/3 | (empty) | 23.2 | PASS (then REJECTED on fresh generalization) |
| 10 | B0 | 1.221 | 34/6 | (empty) | 22.8 | n/a (submitted baseline; server completed 12/12) |
