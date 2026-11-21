# tc_b13_r1: custom candidate

## 1. Overall
| set | n | mean | median | p90 | max | >3 m | >5 m | >10 m | honesty |
|--|--|--|--|--|--|--|--|--|--|
| fresh | 711 | 0.418 | 0.25 | 0.69 | 9.8 | 11/711 1.5% [0.9,2.7] | 6/711 0.8% [0.4,1.8] | 0 | never tuned on, but partly used in adoption decisions (mildly optimistic) |
| sel | 144 | 0.638 | 0.33 | 0.97 | 6.5 | 9/144 6.2% [3.3,11.5] | 4/144 2.8% [1.1,6.9] | 0 | used for tuning/selection (optimistic) |

## 2. Per-class failure shares (primary classes exclusive; overlay tags not exclusive)
### fresh

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 352 | 0.29 | 2/352 0.6% [0.2,2.0] | 1/352 0.3% [0.1,1.6] | [0.0,1.5] |
| mid slow (v0<0.3) | 64 | 0.52 | 2/64 3.1% [0.9,10.7] | 0/64 0.0% [0.0,5.7] | [0.0,7.9] |
| mid fwd (0.3<=v0<1.8, <90deg) | 219 | 0.40 | 2/219 0.9% [0.3,3.3] | 2/219 0.9% [0.3,3.3] | [0.0,2.6] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 41 | 0.42 | 0/41 0.0% [0.0,8.6] | 0/41 0.0% [0.0,8.6] | [0.0,0.0] |
| mid fast (v0>=1.8) | 22 | 1.53 | 3/22 13.6% [4.7,33.3] | 2/22 9.1% [2.5,27.8] | [0.0,30.5] |
| flat/dark scene | 13 | 1.63 | 2/13 15.4% [4.3,42.2] | 1/13 7.7% [1.4,33.3] | [0.0,44.4] |
| ALL | 711 | 0.42 | 11/711 1.5% [0.9,2.7] | 6/711 0.8% [0.4,1.8] | [0.7,2.8] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 12 | 0.55 | 0/12 0.0% [0.0,24.3] | 0/12 0.0% [0.0,24.3] | [0.0,0.0] |
| flat>0.05 | 72 | 1.13 | 7/72 9.7% [4.8,18.7] | 4/72 5.6% [2.2,13.4] | [2.2,22.8] |
| path<45 | 357 | 0.37 | 6/357 1.7% [0.8,3.6] | 4/357 1.1% [0.4,2.8] | [0.3,3.1] |
| path45-65 | 348 | 0.47 | 5/348 1.4% [0.6,3.3] | 2/348 0.6% [0.2,2.1] | [0.2,3.2] |
| path>=65 | 6 | 0.32 | 0/6 0.0% [0.0,39.0] | 0/6 0.0% [0.0,39.0] | [0.0,0.0] |
| extent<3 | 413 | 0.38 | 7/413 1.7% [0.8,3.5] | 4/413 1.0% [0.4,2.5] | [0.5,3.3] |
| extent3-5 | 233 | 0.43 | 3/233 1.3% [0.4,3.7] | 1/233 0.4% [0.1,2.4] | [0.0,3.7] |
| extent>=5 | 65 | 0.59 | 1/65 1.5% [0.3,8.2] | 1/65 1.5% [0.3,8.2] | [0.0,5.2] |
| cat:hssd-train | 76 | 0.26 | 0/76 0.0% [0.0,4.8] | 0/76 0.0% [0.0,4.8] | [0.0,0.0] |
| cat:hssd-val | 57 | 0.47 | 1/57 1.8% [0.3,9.3] | 1/57 1.8% [0.3,9.3] | [0.0,6.3] |
| cat:procthor | 578 | 0.43 | 10/578 1.7% [0.9,3.2] | 5/578 0.9% [0.4,2.0] | [0.6,3.3] |
| set:K | 366 | 0.44 | 6/366 1.6% [0.8,3.5] | 3/366 0.8% [0.3,2.4] | [0.5,3.0] |
| set:K2 | 345 | 0.40 | 5/345 1.4% [0.6,3.3] | 3/345 0.9% [0.3,2.5] | [0.3,2.8] |

### sel

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 67 | 0.34 | 0/67 0.0% [0.0,5.4] | 0/67 0.0% [0.0,5.4] | [0.0,0.0] |
| mid slow (v0<0.3) | 5 | 1.14 | 1/5 20.0% [3.6,62.4] | 0/5 0.0% [0.0,43.4] | [0.0,60.0] |
| mid fwd (0.3<=v0<1.8, <90deg) | 52 | 0.51 | 2/52 3.8% [1.1,13.0] | 0/52 0.0% [0.0,6.9] | [0.0,9.8] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 5 | 0.46 | 0/5 0.0% [0.0,43.4] | 0/5 0.0% [0.0,43.4] | [0.0,0.0] |
| mid fast (v0>=1.8) | 10 | 0.95 | 1/10 10.0% [1.8,40.4] | 1/10 10.0% [1.8,40.4] | [0.0,33.3] |
| flat/dark scene | 5 | 5.01 | 5/5 100.0% [56.6,100.0] | 3/5 60.0% [23.1,88.2] | [100.0,100.0] |
| ALL | 144 | 0.64 | 9/144 6.2% [3.3,11.5] | 4/144 2.8% [1.1,6.9] | [1.4,13.3] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 4 | 0.50 | 0/4 0.0% [0.0,49.0] | 0/4 0.0% [0.0,49.0] | [0.0,0.0] |
| flat>0.05 | 12 | 2.49 | 5/12 41.7% [19.3,68.0] | 3/12 25.0% [8.9,53.2] | [0.0,76.5] |
| path<45 | 11 | 0.37 | 0/11 0.0% [0.0,25.9] | 0/11 0.0% [0.0,25.9] | [0.0,0.0] |
| path45-65 | 113 | 0.67 | 8/113 7.1% [3.6,13.4] | 4/113 3.5% [1.4,8.7] | [1.8,15.0] |
| path>=65 | 20 | 0.63 | 1/20 5.0% [0.9,23.6] | 0/20 0.0% [0.0,16.1] | [0.0,15.8] |
| extent<3 | 41 | 0.34 | 0/41 0.0% [0.0,8.6] | 0/41 0.0% [0.0,8.6] | [0.0,0.0] |
| extent3-5 | 71 | 0.78 | 7/71 9.9% [4.9,19.0] | 3/71 4.2% [1.4,11.7] | [3.2,19.5] |
| extent>=5 | 32 | 0.70 | 2/32 6.2% [1.7,20.1] | 1/32 3.1% [0.6,15.7] | [0.0,22.2] |
| cat:hssd-train | 40 | 0.54 | 2/40 5.0% [1.4,16.5] | 0/40 0.0% [0.0,8.8] | [0.0,12.2] |
| cat:hssd-val | 26 | 1.09 | 4/26 15.4% [6.1,33.5] | 2/26 7.7% [2.1,24.1] | [0.0,41.4] |
| cat:procthor | 78 | 0.54 | 3/78 3.8% [1.3,10.7] | 2/78 2.6% [0.7,8.9] | [0.0,7.9] |
| set:K | 60 | 0.58 | 4/60 6.7% [2.6,15.9] | 1/60 1.7% [0.3,8.9] | [1.7,13.0] |
| set:K2 | 84 | 0.68 | 5/84 6.0% [2.6,13.2] | 3/84 3.6% [1.2,10.0] | [0.0,14.7] |

## 3. P(all 12 server episodes <= 3 m)
Estimators (all INFERENCE-based; chaos between replicate builds moves single-set rates by +-15% relative, see NOTES.md):

| estimator | set | pm=0.5 | pm=0.75 |
|--|--|--|--|
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | fresh | 0.74 [0.50,0.96] | 0.78 [0.63,0.93] |
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | sel | 0.42 [0.17,0.81] | 0.30 [0.08,0.68] |
| flat rate, (1-r)^12, r=Jeffreys 1.6% (Wilson-upper r=2.7% -> 0.72) | fresh | 0.82 | 0.82 |
| flat rate, (1-r)^12, r=Jeffreys 6.6% (Wilson-upper r=11.5% -> 0.23) | sel | 0.44 | 0.44 |

Class-conditional (per-episode class posterior from the server (B0, G) results, INFERENCE; class rates Jeffreys-smoothed; 90% interval from Beta draws of class rates):

| rates from | pm | P(12 clean) | 90% interval | expected # episodes >3 m |
|--|--|--|--|--|
| fresh (Jeffreys) | 0.5 | 0.78 | [0.69,0.87] | 0.25 |
| fresh (Jeffreys) | 0.75 | 0.76 | [0.66,0.86] | 0.27 |
| sel (Jeffreys) | 0.5 | 0.46 | [0.28,0.65] | 0.76 |
| sel (Jeffreys) | 0.75 | 0.40 | [0.23,0.62] | 0.88 |
| pooled all sets (Jeffreys) | 0.5 | 0.74 | [0.65,0.81] | 0.30 |
| pooled all sets (Jeffreys) | 0.75 | 0.71 | [0.62,0.80] | 0.33 |

## 5. Requirement check (flight-level >3 m rate r needed so that P(no episode >3 m among 12) >= target, equal rates)

| target | needed r | zero-failure flights for 95% upper bound <= r | holdout k/n (Wilson upper) |
|--|--|--|--|
| 0.5 | 5.61% | 52 |  |
| 0.8 | 1.84% | 162 |  |
| 0.9 | 0.87% | 342 |  |

## 6. Worst flights (>3 m listed first; mechanism tags: diag = b6fix mech_table for B6/B7-era flights; rule = observable-only suspicion, POST-HOC for holdout)

| flight | ATE | class | features | mechanism |
|--|--|--|--|--|
| **fresh** | | | | |
| fast-ProcTHOR-Train-100-02 | 9.82 | flat/dark scene | v0 0.03 ang 62 path 58 flat 0.18 dark 0.32 | diag: starved coasting (low live tracks) |
| fastmid-106878858_174886965-01 | 8.60 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.41 ang 17 path 52 flat 0.08 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-ProcTHOR-Train-181-01 | 8.07 | mid fast (v0>=1.8) | v0 2.04 ang 53 path 38 flat 0.00 dark 0.00 | rule: fast start (suspect startup runaway) |
| fastmid-ProcTHOR-Train-176-05 | 7.88 | mid fast (v0>=1.8) | v0 2.29 ang 11 path 43 flat 0.00 dark 0.00 | diag: startup fast (>1.8 m/s) |
| fastmid-ProcTHOR-Train-166-04 | 6.27 | mid fwd (0.3<=v0<1.8, <90deg) | v0 1.03 ang 2 path 45 flat 0.12 dark 0.05 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fast-ProcTHOR-Train-166-05 | 5.08 | static | v0 0.03 ang 62 path 41 flat 0.07 dark 0.08 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-82-02 | 4.71 | mid slow (v0<0.3) | v0 0.30 ang 55 path 54 flat 0.00 dark 0.00 | rule: slow/ambiguous mid start (suspect heading-prior over-speed/scale) |
| fastmid-ProcTHOR-Train-64-01 | 3.72 | mid fast (v0>=1.8) | v0 2.65 ang 127 path 56 flat 0.07 dark 0.08 | rule: fast start (suspect startup runaway) |
| **sel** | | | | |
| fastmid-106366104_174226329-00 | 6.52 | flat/dark scene | v0 1.07 ang 6 path 59 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-ProcTHOR-Train-100-02 | 5.19 | flat/dark scene | v0 0.69 ang 115 path 52 flat 0.20 dark 0.43 | diag: starved coasting (low live tracks) |
| fastmid-106366104_174226329-01 | 5.03 | flat/dark scene | v0 0.02 ang 35 path 62 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-ProcTHOR-Train-143-01 | 5.01 | mid fast (v0>=1.8) | v0 1.84 ang 19 path 60 flat 0.00 dark 0.00 | rule: fast start (suspect startup runaway) |
| fastmid-106366104_174226329-02 | 4.76 | flat/dark scene | v0 0.11 ang 47 path 57 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-102344280-01 | 3.72 | mid fwd (0.3<=v0<1.8, <90deg) | v0 1.42 ang 10 path 56 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fast-106366104_174226329-00 | 3.54 | flat/dark scene | v0 0.03 ang 62 path 64 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-103997478_171030525-00 | 3.50 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.56 ang 66 path 78 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
