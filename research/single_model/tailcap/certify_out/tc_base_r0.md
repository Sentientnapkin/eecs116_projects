# tc_base_r0: custom candidate

## 1. Overall
| set | n | mean | median | p90 | max | >3 m | >5 m | >10 m | honesty |
|--|--|--|--|--|--|--|--|--|--|
| fresh | 711 | 0.523 | 0.33 | 0.89 | 12.9 | 12/711 1.7% [1.0,2.9] | 5/711 0.7% [0.3,1.6] | 1 | never tuned on, but partly used in adoption decisions (mildly optimistic) |
| sel | 144 | 0.787 | 0.39 | 1.64 | 7.6 | 11/144 7.6% [4.3,13.2] | 3/144 2.1% [0.7,5.9] | 0 | used for tuning/selection (optimistic) |

## 2. Per-class failure shares (primary classes exclusive; overlay tags not exclusive)
### fresh

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 352 | 0.38 | 2/352 0.6% [0.2,2.0] | 1/352 0.3% [0.1,1.6] | [0.0,1.5] |
| mid slow (v0<0.3) | 64 | 0.58 | 2/64 3.1% [0.9,10.7] | 0/64 0.0% [0.0,5.7] | [0.0,8.2] |
| mid fwd (0.3<=v0<1.8, <90deg) | 219 | 0.55 | 4/219 1.8% [0.7,4.6] | 2/219 0.9% [0.3,3.3] | [0.4,3.9] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 41 | 0.47 | 0/41 0.0% [0.0,8.6] | 0/41 0.0% [0.0,8.6] | [0.0,0.0] |
| mid fast (v0>=1.8) | 22 | 1.75 | 2/22 9.1% [2.5,27.8] | 1/22 4.5% [0.8,21.8] | [0.0,22.7] |
| flat/dark scene | 13 | 1.60 | 2/13 15.4% [4.3,42.2] | 1/13 7.7% [1.4,33.3] | [0.0,44.4] |
| ALL | 711 | 0.52 | 12/711 1.7% [1.0,2.9] | 5/711 0.7% [0.3,1.6] | [0.6,3.2] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 12 | 0.60 | 0/12 0.0% [0.0,24.3] | 0/12 0.0% [0.0,24.3] | [0.0,0.0] |
| flat>0.05 | 72 | 1.27 | 8/72 11.1% [5.7,20.4] | 4/72 5.6% [2.2,13.4] | [2.4,25.0] |
| path<45 | 357 | 0.48 | 7/357 2.0% [1.0,4.0] | 3/357 0.8% [0.3,2.4] | [0.3,4.3] |
| path45-65 | 348 | 0.57 | 5/348 1.4% [0.6,3.3] | 2/348 0.6% [0.2,2.1] | [0.2,3.2] |
| path>=65 | 6 | 0.45 | 0/6 0.0% [0.0,39.0] | 0/6 0.0% [0.0,39.0] | [0.0,0.0] |
| extent<3 | 413 | 0.50 | 7/413 1.7% [0.8,3.5] | 3/413 0.7% [0.2,2.1] | [0.2,3.9] |
| extent3-5 | 233 | 0.53 | 4/233 1.7% [0.7,4.3] | 1/233 0.4% [0.1,2.4] | [0.0,4.3] |
| extent>=5 | 65 | 0.67 | 1/65 1.5% [0.3,8.2] | 1/65 1.5% [0.3,8.2] | [0.0,5.2] |
| cat:hssd-train | 76 | 0.37 | 0/76 0.0% [0.0,4.8] | 0/76 0.0% [0.0,4.8] | [0.0,0.0] |
| cat:hssd-val | 57 | 0.58 | 1/57 1.8% [0.3,9.3] | 1/57 1.8% [0.3,9.3] | [0.0,6.3] |
| cat:procthor | 578 | 0.54 | 11/578 1.9% [1.1,3.4] | 4/578 0.7% [0.3,1.8] | [0.6,3.8] |
| set:K | 366 | 0.54 | 8/366 2.2% [1.1,4.3] | 2/366 0.5% [0.1,2.0] | [0.3,4.5] |
| set:K2 | 345 | 0.50 | 4/345 1.2% [0.5,2.9] | 3/345 0.9% [0.3,2.5] | [0.3,2.4] |

### sel

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 67 | 0.39 | 0/67 0.0% [0.0,5.4] | 0/67 0.0% [0.0,5.4] | [0.0,0.0] |
| mid slow (v0<0.3) | 5 | 1.63 | 1/5 20.0% [3.6,62.4] | 1/5 20.0% [3.6,62.4] | [0.0,60.0] |
| mid fwd (0.3<=v0<1.8, <90deg) | 52 | 0.71 | 2/52 3.8% [1.1,13.0] | 1/52 1.9% [0.3,10.1] | [0.0,9.8] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 5 | 0.63 | 0/5 0.0% [0.0,43.4] | 0/5 0.0% [0.0,43.4] | [0.0,0.0] |
| mid fast (v0>=1.8) | 10 | 1.65 | 3/10 30.0% [10.8,60.3] | 0/10 0.0% [0.0,27.8] | [0.0,60.0] |
| flat/dark scene | 5 | 4.52 | 5/5 100.0% [56.6,100.0] | 1/5 20.0% [3.6,62.4] | [100.0,100.0] |
| ALL | 144 | 0.79 | 11/144 7.6% [4.3,13.2] | 3/144 2.1% [0.7,5.9] | [2.2,14.5] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 4 | 0.78 | 0/4 0.0% [0.0,49.0] | 0/4 0.0% [0.0,49.0] | [0.0,0.0] |
| flat>0.05 | 12 | 2.66 | 5/12 41.7% [19.3,68.0] | 1/12 8.3% [1.5,35.4] | [0.0,76.5] |
| path<45 | 11 | 0.32 | 0/11 0.0% [0.0,25.9] | 0/11 0.0% [0.0,25.9] | [0.0,0.0] |
| path45-65 | 113 | 0.84 | 10/113 8.8% [4.9,15.5] | 3/113 2.7% [0.9,7.5] | [2.9,16.8] |
| path>=65 | 20 | 0.73 | 1/20 5.0% [0.9,23.6] | 0/20 0.0% [0.0,16.1] | [0.0,15.8] |
| extent<3 | 41 | 0.41 | 0/41 0.0% [0.0,8.6] | 0/41 0.0% [0.0,8.6] | [0.0,0.0] |
| extent3-5 | 71 | 1.03 | 8/71 11.3% [5.8,20.7] | 3/71 4.2% [1.4,11.7] | [4.2,20.9] |
| extent>=5 | 32 | 0.74 | 3/32 9.4% [3.2,24.2] | 0/32 0.0% [0.0,10.7] | [0.0,25.9] |
| cat:hssd-train | 40 | 0.69 | 2/40 5.0% [1.4,16.5] | 1/40 2.5% [0.4,12.9] | [0.0,12.2] |
| cat:hssd-val | 26 | 1.22 | 5/26 19.2% [8.5,37.9] | 1/26 3.8% [0.7,18.9] | [0.0,45.2] |
| cat:procthor | 78 | 0.69 | 4/78 5.1% [2.0,12.5] | 1/78 1.3% [0.2,6.9] | [1.2,9.5] |
| set:K | 60 | 0.74 | 5/60 8.3% [3.6,18.1] | 2/60 3.3% [0.9,11.4] | [2.0,14.6] |
| set:K2 | 84 | 0.82 | 6/84 7.1% [3.3,14.7] | 1/84 1.2% [0.2,6.4] | [1.1,16.7] |

## 3. P(all 12 server episodes <= 3 m)
Estimators (all INFERENCE-based; chaos between replicate builds moves single-set rates by +-15% relative, see NOTES.md):

| estimator | set | pm=0.5 | pm=0.75 |
|--|--|--|--|
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | fresh | 0.74 [0.51,0.96] | 0.78 [0.60,0.94] |
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | sel | 0.35 [0.14,0.66] | 0.23 [0.06,0.53] |
| flat rate, (1-r)^12, r=Jeffreys 1.8% (Wilson-upper r=2.9% -> 0.70) | fresh | 0.81 | 0.81 |
| flat rate, (1-r)^12, r=Jeffreys 7.9% (Wilson-upper r=13.2% -> 0.18) | sel | 0.37 | 0.37 |

Class-conditional (per-episode class posterior from the server (B0, G) results, INFERENCE; class rates Jeffreys-smoothed; 90% interval from Beta draws of class rates):

| rates from | pm | P(12 clean) | 90% interval | expected # episodes >3 m |
|--|--|--|--|--|
| fresh (Jeffreys) | 0.5 | 0.75 | [0.65,0.85] | 0.28 |
| fresh (Jeffreys) | 0.75 | 0.73 | [0.63,0.84] | 0.31 |
| sel (Jeffreys) | 0.5 | 0.40 | [0.25,0.59] | 0.87 |
| sel (Jeffreys) | 0.75 | 0.35 | [0.20,0.55] | 1.00 |
| pooled all sets (Jeffreys) | 0.5 | 0.69 | [0.60,0.77] | 0.37 |
| pooled all sets (Jeffreys) | 0.75 | 0.66 | [0.56,0.75] | 0.41 |

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
| fastmid-ProcTHOR-Train-176-05 | 12.89 | mid fast (v0>=1.8) | v0 2.29 ang 11 path 43 flat 0.00 dark 0.00 | diag: startup fast (>1.8 m/s) |
| fastmid-106878858_174886965-01 | 8.25 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.41 ang 17 path 52 flat 0.08 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-ProcTHOR-Train-85-02 | 5.98 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.93 ang 70 path 37 flat 0.13 dark 0.10 | diag: starved coasting (low live tracks) |
| fast-ProcTHOR-Train-166-05 | 5.33 | static | v0 0.03 ang 62 path 41 flat 0.07 dark 0.08 | diag: starved coasting (low live tracks) |
| fast-ProcTHOR-Train-100-02 | 5.03 | flat/dark scene | v0 0.03 ang 62 path 58 flat 0.18 dark 0.32 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-176-11 | 4.08 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.98 ang 11 path 34 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fast-ProcTHOR-Train-85-01 | 3.48 | static | v0 0.03 ang 62 path 37 flat 0.18 dark 0.10 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-85-01 | 3.39 | mid slow (v0<0.3) | v0 0.25 ang 113 path 39 flat 0.18 dark 0.20 | diag: starved coasting (low live tracks) |
| **sel** | | | | |
| fastmid-106366104_174226329-00 | 7.60 | flat/dark scene | v0 1.07 ang 6 path 59 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-102344280-01 | 5.66 | mid fwd (0.3<=v0<1.8, <90deg) | v0 1.42 ang 10 path 56 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-ProcTHOR-Train-5-02 | 5.06 | mid slow (v0<0.3) | v0 0.20 ang 56 path 65 flat 0.00 dark 0.00 | rule: slow/ambiguous mid start (suspect heading-prior over-speed/scale) |
| fastmid-ProcTHOR-Train-143-01 | 4.50 | mid fast (v0>=1.8) | v0 1.84 ang 19 path 60 flat 0.00 dark 0.00 | rule: fast start (suspect startup runaway) |
| fastmid-103997478_171030525-00 | 4.19 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.56 ang 66 path 78 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-ProcTHOR-Train-57-01 | 4.19 | mid fast (v0>=1.8) | v0 2.12 ang 102 path 55 flat 0.05 dark 0.00 | rule: fast start (suspect startup runaway) |
| fastmid-106366104_174226329-02 | 3.99 | flat/dark scene | v0 0.11 ang 47 path 57 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fast-106366104_174226329-00 | 3.93 | flat/dark scene | v0 0.03 ang 62 path 64 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
