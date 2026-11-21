# tc_base_r1: custom candidate

## 1. Overall
| set | n | mean | median | p90 | max | >3 m | >5 m | >10 m | honesty |
|--|--|--|--|--|--|--|--|--|--|
| fresh | 711 | 0.529 | 0.33 | 0.86 | 9.3 | 12/711 1.7% [1.0,2.9] | 4/711 0.6% [0.2,1.4] | 0 | never tuned on, but partly used in adoption decisions (mildly optimistic) |
| sel | 144 | 0.755 | 0.39 | 1.47 | 7.8 | 10/144 6.9% [3.8,12.3] | 1/144 0.7% [0.1,3.8] | 0 | used for tuning/selection (optimistic) |

## 2. Per-class failure shares (primary classes exclusive; overlay tags not exclusive)
### fresh

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 352 | 0.41 | 2/352 0.6% [0.2,2.0] | 1/352 0.3% [0.1,1.6] | [0.0,1.5] |
| mid slow (v0<0.3) | 64 | 0.66 | 2/64 3.1% [0.9,10.7] | 0/64 0.0% [0.0,5.7] | [0.0,9.4] |
| mid fwd (0.3<=v0<1.8, <90deg) | 219 | 0.54 | 4/219 1.8% [0.7,4.6] | 2/219 0.9% [0.3,3.3] | [0.4,4.1] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 41 | 0.54 | 0/41 0.0% [0.0,8.6] | 0/41 0.0% [0.0,8.6] | [0.0,0.0] |
| mid fast (v0>=1.8) | 22 | 1.48 | 2/22 9.1% [2.5,27.8] | 1/22 4.5% [0.8,21.8] | [0.0,22.7] |
| flat/dark scene | 13 | 1.37 | 2/13 15.4% [4.3,42.2] | 0/13 0.0% [0.0,22.8] | [0.0,44.4] |
| ALL | 711 | 0.53 | 12/711 1.7% [1.0,2.9] | 4/711 0.6% [0.2,1.4] | [0.6,3.2] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 12 | 0.71 | 0/12 0.0% [0.0,24.3] | 0/12 0.0% [0.0,24.3] | [0.0,0.0] |
| flat>0.05 | 72 | 1.32 | 9/72 12.5% [6.7,22.1] | 2/72 2.8% [0.8,9.6] | [2.7,27.3] |
| path<45 | 357 | 0.46 | 7/357 2.0% [1.0,4.0] | 3/357 0.8% [0.3,2.4] | [0.0,4.4] |
| path45-65 | 348 | 0.60 | 5/348 1.4% [0.6,3.3] | 1/348 0.3% [0.1,1.6] | [0.2,3.2] |
| path>=65 | 6 | 0.60 | 0/6 0.0% [0.0,39.0] | 0/6 0.0% [0.0,39.0] | [0.0,0.0] |
| extent<3 | 413 | 0.49 | 8/413 1.9% [1.0,3.8] | 3/413 0.7% [0.2,2.1] | [0.4,4.2] |
| extent3-5 | 233 | 0.54 | 3/233 1.3% [0.4,3.7] | 0/233 0.0% [0.0,1.6] | [0.0,3.7] |
| extent>=5 | 65 | 0.74 | 1/65 1.5% [0.3,8.2] | 1/65 1.5% [0.3,8.2] | [0.0,5.2] |
| cat:hssd-train | 76 | 0.34 | 0/76 0.0% [0.0,4.8] | 0/76 0.0% [0.0,4.8] | [0.0,0.0] |
| cat:hssd-val | 57 | 0.58 | 1/57 1.8% [0.3,9.3] | 1/57 1.8% [0.3,9.3] | [0.0,6.3] |
| cat:procthor | 578 | 0.55 | 11/578 1.9% [1.1,3.4] | 3/578 0.5% [0.2,1.5] | [0.5,3.6] |
| set:K | 366 | 0.53 | 7/366 1.9% [0.9,3.9] | 2/366 0.5% [0.1,2.0] | [0.3,4.4] |
| set:K2 | 345 | 0.53 | 5/345 1.4% [0.6,3.3] | 2/345 0.6% [0.2,2.1] | [0.3,2.8] |

### sel

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 67 | 0.40 | 0/67 0.0% [0.0,5.4] | 0/67 0.0% [0.0,5.4] | [0.0,0.0] |
| mid slow (v0<0.3) | 5 | 1.44 | 1/5 20.0% [3.6,62.4] | 0/5 0.0% [0.0,43.4] | [0.0,60.0] |
| mid fwd (0.3<=v0<1.8, <90deg) | 52 | 0.70 | 3/52 5.8% [2.0,15.6] | 0/52 0.0% [0.0,6.9] | [0.0,13.0] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 5 | 0.60 | 0/5 0.0% [0.0,43.4] | 0/5 0.0% [0.0,43.4] | [0.0,0.0] |
| mid fast (v0>=1.8) | 10 | 1.09 | 1/10 10.0% [1.8,40.4] | 0/10 0.0% [0.0,27.8] | [0.0,33.3] |
| flat/dark scene | 5 | 4.88 | 5/5 100.0% [56.6,100.0] | 1/5 20.0% [3.6,62.4] | [100.0,100.0] |
| ALL | 144 | 0.75 | 10/144 6.9% [3.8,12.3] | 1/144 0.7% [0.1,3.8] | [1.4,14.7] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 4 | 0.75 | 0/4 0.0% [0.0,49.0] | 0/4 0.0% [0.0,49.0] | [0.0,0.0] |
| flat>0.05 | 12 | 2.79 | 6/12 50.0% [25.4,74.6] | 1/12 8.3% [1.5,35.4] | [0.0,77.8] |
| path<45 | 11 | 0.32 | 0/11 0.0% [0.0,25.9] | 0/11 0.0% [0.0,25.9] | [0.0,0.0] |
| path45-65 | 113 | 0.80 | 9/113 8.0% [4.2,14.4] | 1/113 0.9% [0.2,4.8] | [1.6,16.9] |
| path>=65 | 20 | 0.73 | 1/20 5.0% [0.9,23.6] | 0/20 0.0% [0.0,16.1] | [0.0,15.8] |
| extent<3 | 41 | 0.40 | 0/41 0.0% [0.0,8.6] | 0/41 0.0% [0.0,8.6] | [0.0,0.0] |
| extent3-5 | 71 | 1.00 | 8/71 11.3% [5.8,20.7] | 1/71 1.4% [0.2,7.6] | [3.2,23.0] |
| extent>=5 | 32 | 0.68 | 2/32 6.2% [1.7,20.1] | 0/32 0.0% [0.0,10.7] | [0.0,22.2] |
| cat:hssd-train | 40 | 0.62 | 2/40 5.0% [1.4,16.5] | 0/40 0.0% [0.0,8.8] | [0.0,12.2] |
| cat:hssd-val | 26 | 1.21 | 4/26 15.4% [6.1,33.5] | 1/26 3.8% [0.7,18.9] | [0.0,41.4] |
| cat:procthor | 78 | 0.67 | 4/78 5.1% [2.0,12.5] | 0/78 0.0% [0.0,4.7] | [0.0,11.0] |
| set:K | 60 | 0.70 | 5/60 8.3% [3.6,18.1] | 0/60 0.0% [0.0,6.0] | [3.1,15.3] |
| set:K2 | 84 | 0.79 | 5/84 6.0% [2.6,13.2] | 1/84 1.2% [0.2,6.4] | [0.0,14.5] |

## 3. P(all 12 server episodes <= 3 m)
Estimators (all INFERENCE-based; chaos between replicate builds moves single-set rates by +-15% relative, see NOTES.md):

| estimator | set | pm=0.5 | pm=0.75 |
|--|--|--|--|
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | fresh | 0.75 [0.52,0.97] | 0.80 [0.63,0.96] |
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | sel | 0.38 [0.14,0.76] | 0.26 [0.06,0.70] |
| flat rate, (1-r)^12, r=Jeffreys 1.8% (Wilson-upper r=2.9% -> 0.70) | fresh | 0.81 | 0.81 |
| flat rate, (1-r)^12, r=Jeffreys 7.2% (Wilson-upper r=12.3% -> 0.21) | sel | 0.41 | 0.41 |

Class-conditional (per-episode class posterior from the server (B0, G) results, INFERENCE; class rates Jeffreys-smoothed; 90% interval from Beta draws of class rates):

| rates from | pm | P(12 clean) | 90% interval | expected # episodes >3 m |
|--|--|--|--|--|
| fresh (Jeffreys) | 0.5 | 0.75 | [0.65,0.85] | 0.28 |
| fresh (Jeffreys) | 0.75 | 0.73 | [0.63,0.84] | 0.31 |
| sel (Jeffreys) | 0.5 | 0.40 | [0.23,0.59] | 0.88 |
| sel (Jeffreys) | 0.75 | 0.35 | [0.18,0.56] | 1.01 |
| pooled all sets (Jeffreys) | 0.5 | 0.70 | [0.60,0.78] | 0.36 |
| pooled all sets (Jeffreys) | 0.75 | 0.67 | [0.57,0.77] | 0.39 |

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
| fastmid-106878858_174886965-01 | 9.30 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.41 ang 17 path 52 flat 0.08 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fast-ProcTHOR-Train-166-05 | 7.58 | static | v0 0.03 ang 62 path 41 flat 0.07 dark 0.08 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-176-05 | 5.81 | mid fast (v0>=1.8) | v0 2.29 ang 11 path 43 flat 0.00 dark 0.00 | diag: startup fast (>1.8 m/s) |
| fastmid-ProcTHOR-Train-176-11 | 5.11 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.98 ang 11 path 34 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-ProcTHOR-Train-64-01 | 4.80 | mid fast (v0>=1.8) | v0 2.65 ang 127 path 56 flat 0.07 dark 0.08 | rule: fast start (suspect startup runaway) |
| fastmid-ProcTHOR-Train-82-02 | 4.79 | mid slow (v0<0.3) | v0 0.30 ang 55 path 54 flat 0.00 dark 0.00 | rule: slow/ambiguous mid start (suspect heading-prior over-speed/scale) |
| fastmid-ProcTHOR-Train-166-04 | 4.13 | mid fwd (0.3<=v0<1.8, <90deg) | v0 1.03 ang 2 path 45 flat 0.12 dark 0.05 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-ProcTHOR-Train-85-01 | 4.13 | mid slow (v0<0.3) | v0 0.25 ang 113 path 39 flat 0.18 dark 0.20 | diag: starved coasting (low live tracks) |
| **sel** | | | | |
| fastmid-106366104_174226329-00 | 7.83 | flat/dark scene | v0 1.07 ang 6 path 59 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-106366104_174226329-02 | 4.85 | flat/dark scene | v0 0.11 ang 47 path 57 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-ProcTHOR-Train-5-02 | 4.76 | mid slow (v0<0.3) | v0 0.20 ang 56 path 65 flat 0.00 dark 0.00 | rule: slow/ambiguous mid start (suspect heading-prior over-speed/scale) |
| fastmid-ProcTHOR-Train-100-02 | 4.25 | flat/dark scene | v0 0.69 ang 115 path 52 flat 0.20 dark 0.43 | diag: starved coasting (low live tracks) |
| fastmid-103997478_171030525-00 | 4.09 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.56 ang 66 path 78 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-102344280-01 | 4.06 | mid fwd (0.3<=v0<1.8, <90deg) | v0 1.42 ang 10 path 56 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fast-106366104_174226329-00 | 3.91 | flat/dark scene | v0 0.03 ang 62 path 64 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-106366104_174226329-01 | 3.56 | flat/dark scene | v0 0.02 ang 35 path 62 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
