# Front-end tracking tricks: arms, results, adopted patch

Source: `fe.c` = fgt.c + switchable blocks (first screening, old base), `fe2.c` = research/single_model/inventive/adopted.c (G+C1) + the same blocks
(generator `mk_fe2.py`; all blocks `#ifndef`, default 0, base wasm bit-identical to the unmodified source). Scripts: `run2.sh`, `rep2.sh` (3 chaos replicates,
same nudges as inventive/rep.sh), `cmprep2.py` (replicate-mean paired scene bootstrap vs inv_c1_r0..2), `fresh_cmp.py` (711 fresh flights vs inventive/fresh_table_c1.json).
Functions touched: `build_pyramid` (FE_NORM), `track_all` (FE_FB), `detect` (FE_CELLFALL, FE_RMAX), `feature_rows` (FE_RADW), new `ransac_filter` + call at clone frames (FE_RS).

## Screening on the OLD base (fgt_merged, search 0.845 / val 0.559; single run, noise ~0.2)
| arm | search | static | mid | d vs ref [CI] | val | peak fuel |
|---|---|---|---|---|---|---|
| fb (0.5 px) | 0.858 | 0.428 | 1.241 | +0.013 [-0.17,+0.28] | 0.445 | 25.1 M |
| rs (gyro 2-pt RANSAC) | 0.901 | 0.589 | 1.179 | +0.056 [-0.05,+0.19] | 0.598 | 22.1 M |
| norm (contrast normalise) | 0.943 | 0.641 | 1.211 | +0.098 | 0.567 | 28.4 M |
| grid 16x8 | 1.133 | 0.583 | 1.623 | +0.288 [+0.06,+0.57] worse | 0.537 | 37.7 M |
| grid 10x8 | 1.014 | 0.506 | 1.465 | +0.168 | 0.508 | 27.0 M |
| radw 0.5 (1/(1+kr^2) obs weight) | 1.106 | 0.674 | 1.490 | +0.261 [+0.06,+0.52] worse | 0.594 | 23.1 M |
| rmax 1.4 (no detection >54 deg) | 0.960 | 0.586 | 1.292 | +0.114 | 0.596 | 21.1 M |
| cellfall (weak corners if <25 tracks) | 0.838 | 0.542 | 1.101 | -0.007 | 0.589 | 23.0 M |
| KLT_R=5 | 1.075 | 0.777 | 1.341 | +0.230 [+0.08,+0.40] worse | 0.453 | 24.2 M |
| LEVELS=3 | 1.143 | 0.598 | 1.597 | +0.298 worse | 0.563 | 23.8 M |

## Rebased on adopted.c (G+C1), 3 replicates, search n=119 (ref inv_c1 replicate mean 1.079, static 0.595, mid 1.510; val 0.537)
| arm | search mean (reps) | d [95% CI] | static | mid | >5 / >10 per rep | val | peak / max-p95 fuel |
|---|---|---|---|---|---|---|---|
| cellfall | 1.025 (1.018/1.003/1.055) | -0.054 [-0.18,+0.06] | 0.638 (+0.043) | 1.370 | 3,3,5 / 0 | 0.598 (+0.061) | 22.1 / 16.2 M |
| **fb** (every frame) | 0.978 (0.969/0.998/0.968) | -0.101 [-0.30,+0.12] | **0.438 (-0.157 [-0.254,-0.079])** | 1.459 | 4,3,5 / 0 | 0.433 (-0.104) | 24.4 / 18.3 M |
| fb 1.0 px | 0.996 | -0.083 [-0.30,+0.13] | 0.483 (-0.112) | 1.452 | 5,5,4 / 0 | 0.424 | 24.2 / 18.7 M |
| **fbh** (FB on alternate frames, 0.5 px) | **0.931 (0.950/0.943/0.900)** | **-0.149 [-0.305,+0.024]** | **0.466 (-0.129 [-0.252,-0.036])** | 1.344 (-0.166 [-0.47,+0.15]) | 4,5,4 / 0,1,0 | 0.441 (-0.096 [-0.256,0.000]) | 22.0 / 17.1 M |
| norm | 1.089 | +0.010 | 0.552 | 1.566 | 4,4,5 / 1,0,0 | 0.556 | 28.9 / 17.3 M |
| rs (2-pt RANSAC) | 1.002 | -0.078 [-0.21,+0.05] | 0.579 | 1.377 | 3,3,4 / 0 | 0.673 (+0.136 [+0.035,+0.252] WORSE) | 21.1 / 15.1 M |

Fresh set (711 flights, run_fresh.py, vs C1 0.733 / static 0.471 / mid 0.995, unperturbed build, scene bootstrap):
| arm | all | static | mid | >5 / >10 | max | peak fuel |
|---|---|---|---|---|---|---|
| fb (every frame) | 0.622, d -0.111 [-0.179,-0.040] | 0.399 (-0.072) | 0.845 (-0.150) | 6 / 2 (new >10: max 11.4) | 11.4 | 26.8 M |
| **fbh** | **0.618, d -0.114 [-0.167,-0.064]** | 0.409 (-0.062 [-0.096,-0.029]) | 0.829 (-0.166 [-0.258,-0.078]) | 8 / 0 | 6.9 | 24.5 M (static pool); 21.8 M mid |

## Verdict
ADOPT candidate: **FE_FB with FE_FB_HALF=1** (`adopted_fbh.patch`, 6 lines in `track_all`, diff vs inventive/adopted.c; `adopted_fbh.c`). Evidence: search -0.149 (static CI excludes zero,
all-CI touches zero at +0.024), all 3 replicates below the reference mean, val -0.096 (not contradicted), fresh 711 -0.114 [-0.167,-0.064] with no >10 m flight (max 6.9 m),
effect concentrated where it should be (static -0.13, mid -0.17). Mechanism: the backward track rejects drifting/aperture-slid tracks that otherwise enter the MSCKF as slow-leaking outliers.
Fuel: search/val peak 22.0 M (unchanged vs 21.7-22.1), but fresh static-pool peak 24.5 M and max p95 17.1 M vs ~15 M: the backward KLT adds ~+2 to 3 M in the worst frames and ~+13% p95 (half-rate check; every-frame costs 24.4 M search, 26.8 M fresh). On the fuel rewrite the backward KLT should reuse the same fast patch code (cost scales with KLT cost, roughly half of it with FB_HALF).
Do NOT adopt: every-frame FB (new >10 m flights on fresh, +10% fuel), RS (val worse), norm (+fuel 29 M, no gain), radw, grid bigger, KLT_R=5, L3, rmax, cellfall (static +0.04, val +0.06).
Caveat: the arms' search all-CI includes zero; effect sizes (0.1-0.15 m) are close to replicate noise on search, so the fresh-set result is the main evidence.
