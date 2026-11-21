# tc_b13_r0: custom candidate

## 1. Overall
| set | n | mean | median | p90 | max | >3 m | >5 m | >10 m | honesty |
|--|--|--|--|--|--|--|--|--|--|
| fresh | 711 | 0.405 | 0.25 | 0.73 | 8.7 | 10/711 1.4% [0.8,2.6] | 5/711 0.7% [0.3,1.6] | 0 | never tuned on, but partly used in adoption decisions (mildly optimistic) |
| sel | 144 | 0.644 | 0.35 | 1.08 | 6.2 | 8/144 5.6% [2.8,10.6] | 2/144 1.4% [0.4,4.9] | 0 | used for tuning/selection (optimistic) |

## 2. Per-class failure shares (primary classes exclusive; overlay tags not exclusive)
### fresh

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 352 | 0.28 | 1/352 0.3% [0.1,1.6] | 0/352 0.0% [0.0,1.1] | [0.0,1.0] |
| mid slow (v0<0.3) | 64 | 0.42 | 1/64 1.6% [0.3,8.3] | 0/64 0.0% [0.0,5.7] | [0.0,4.7] |
| mid fwd (0.3<=v0<1.8, <90deg) | 219 | 0.42 | 2/219 0.9% [0.3,3.3] | 1/219 0.5% [0.1,2.5] | [0.0,2.6] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 41 | 0.52 | 1/41 2.4% [0.4,12.6] | 1/41 2.4% [0.4,12.6] | [0.0,9.1] |
| mid fast (v0>=1.8) | 22 | 1.44 | 3/22 13.6% [4.7,33.3] | 2/22 9.1% [2.5,27.8] | [0.0,28.6] |
| flat/dark scene | 13 | 1.28 | 2/13 15.4% [4.3,42.2] | 1/13 7.7% [1.4,33.3] | [0.0,44.4] |
| ALL | 711 | 0.40 | 10/711 1.4% [0.8,2.6] | 5/711 0.7% [0.3,1.6] | [0.6,2.5] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 12 | 0.92 | 1/12 8.3% [1.5,35.4] | 1/12 8.3% [1.5,35.4] | [0.0,27.3] |
| flat>0.05 | 72 | 1.08 | 7/72 9.7% [4.8,18.7] | 4/72 5.6% [2.2,13.4] | [2.2,21.8] |
| path<45 | 357 | 0.34 | 4/357 1.1% [0.4,2.8] | 1/357 0.3% [0.0,1.6] | [0.0,2.5] |
| path45-65 | 348 | 0.48 | 6/348 1.7% [0.8,3.7] | 4/348 1.1% [0.4,2.9] | [0.4,3.5] |
| path>=65 | 6 | 0.34 | 0/6 0.0% [0.0,39.0] | 0/6 0.0% [0.0,39.0] | [0.0,0.0] |
| extent<3 | 413 | 0.34 | 4/413 1.0% [0.4,2.5] | 1/413 0.2% [0.0,1.4] | [0.0,2.3] |
| extent3-5 | 233 | 0.46 | 4/233 1.7% [0.7,4.3] | 3/233 1.3% [0.4,3.7] | [0.0,4.3] |
| extent>=5 | 65 | 0.59 | 2/65 3.1% [0.8,10.5] | 1/65 1.5% [0.3,8.2] | [0.0,6.9] |
| cat:hssd-train | 76 | 0.25 | 0/76 0.0% [0.0,4.8] | 0/76 0.0% [0.0,4.8] | [0.0,0.0] |
| cat:hssd-val | 57 | 0.46 | 1/57 1.8% [0.3,9.3] | 1/57 1.8% [0.3,9.3] | [0.0,6.3] |
| cat:procthor | 578 | 0.42 | 9/578 1.6% [0.8,2.9] | 4/578 0.7% [0.3,1.8] | [0.5,2.9] |
| set:K | 366 | 0.42 | 6/366 1.6% [0.8,3.5] | 1/366 0.3% [0.0,1.5] | [0.5,3.2] |
| set:K2 | 345 | 0.38 | 4/345 1.2% [0.5,2.9] | 4/345 1.2% [0.5,2.9] | [0.3,2.4] |

### sel

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 67 | 0.36 | 0/67 0.0% [0.0,5.4] | 0/67 0.0% [0.0,5.4] | [0.0,0.0] |
| mid slow (v0<0.3) | 5 | 1.15 | 0/5 0.0% [0.0,43.4] | 0/5 0.0% [0.0,43.4] | [0.0,0.0] |
| mid fwd (0.3<=v0<1.8, <90deg) | 52 | 0.54 | 2/52 3.8% [1.1,13.0] | 0/52 0.0% [0.0,6.9] | [0.0,9.8] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 5 | 0.47 | 0/5 0.0% [0.0,43.4] | 0/5 0.0% [0.0,43.4] | [0.0,0.0] |
| mid fast (v0>=1.8) | 10 | 0.91 | 1/10 10.0% [1.8,40.4] | 0/10 0.0% [0.0,27.8] | [0.0,33.3] |
| flat/dark scene | 5 | 4.63 | 5/5 100.0% [56.6,100.0] | 2/5 40.0% [11.8,76.9] | [100.0,100.0] |
| ALL | 144 | 0.64 | 8/144 5.6% [2.8,10.6] | 2/144 1.4% [0.4,4.9] | [0.7,12.4] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 4 | 0.55 | 0/4 0.0% [0.0,49.0] | 0/4 0.0% [0.0,49.0] | [0.0,0.0] |
| flat>0.05 | 12 | 2.49 | 5/12 41.7% [19.3,68.0] | 2/12 16.7% [4.7,44.8] | [0.0,76.5] |
| path<45 | 11 | 0.31 | 0/11 0.0% [0.0,25.9] | 0/11 0.0% [0.0,25.9] | [0.0,0.0] |
| path45-65 | 113 | 0.66 | 7/113 6.2% [3.0,12.2] | 2/113 1.8% [0.5,6.2] | [0.9,14.2] |
| path>=65 | 20 | 0.73 | 1/20 5.0% [0.9,23.6] | 0/20 0.0% [0.0,16.1] | [0.0,15.8] |
| extent<3 | 41 | 0.37 | 0/41 0.0% [0.0,8.6] | 0/41 0.0% [0.0,8.6] | [0.0,0.0] |
| extent3-5 | 71 | 0.78 | 6/71 8.5% [3.9,17.2] | 1/71 1.4% [0.2,7.6] | [2.2,17.4] |
| extent>=5 | 32 | 0.71 | 2/32 6.2% [1.7,20.1] | 1/32 3.1% [0.6,15.7] | [0.0,22.2] |
| cat:hssd-train | 40 | 0.55 | 2/40 5.0% [1.4,16.5] | 0/40 0.0% [0.0,8.8] | [0.0,12.2] |
| cat:hssd-val | 26 | 1.14 | 4/26 15.4% [6.1,33.5] | 2/26 7.7% [2.1,24.1] | [0.0,41.4] |
| cat:procthor | 78 | 0.53 | 2/78 2.6% [0.7,8.9] | 0/78 0.0% [0.0,4.7] | [0.0,7.0] |
| set:K | 60 | 0.58 | 3/60 5.0% [1.7,13.7] | 1/60 1.7% [0.3,8.9] | [0.0,11.3] |
| set:K2 | 84 | 0.69 | 5/84 6.0% [2.6,13.2] | 1/84 1.2% [0.2,6.4] | [0.0,14.7] |

## 3. P(all 12 server episodes <= 3 m)
Estimators (all INFERENCE-based; chaos between replicate builds moves single-set rates by +-15% relative, see NOTES.md):

| estimator | set | pm=0.5 | pm=0.75 |
|--|--|--|--|
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | fresh | 0.76 [0.52,0.97] | 0.80 [0.66,0.95] |
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | sel | 0.45 [0.18,0.88] | 0.33 [0.09,0.74] |
| flat rate, (1-r)^12, r=Jeffreys 1.5% (Wilson-upper r=2.6% -> 0.73) | fresh | 0.84 | 0.84 |
| flat rate, (1-r)^12, r=Jeffreys 5.9% (Wilson-upper r=10.6% -> 0.26) | sel | 0.48 | 0.48 |

Class-conditional (per-episode class posterior from the server (B0, G) results, INFERENCE; class rates Jeffreys-smoothed; 90% interval from Beta draws of class rates):

| rates from | pm | P(12 clean) | 90% interval | expected # episodes >3 m |
|--|--|--|--|--|
| fresh (Jeffreys) | 0.5 | 0.78 | [0.68,0.87] | 0.25 |
| fresh (Jeffreys) | 0.75 | 0.76 | [0.65,0.86] | 0.27 |
| sel (Jeffreys) | 0.5 | 0.51 | [0.33,0.71] | 0.65 |
| sel (Jeffreys) | 0.75 | 0.47 | [0.28,0.68] | 0.73 |
| pooled all sets (Jeffreys) | 0.5 | 0.74 | [0.65,0.82] | 0.30 |
| pooled all sets (Jeffreys) | 0.75 | 0.72 | [0.63,0.81] | 0.32 |

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
| fastmid-ProcTHOR-Train-176-05 | 8.73 | mid fast (v0>=1.8) | v0 2.29 ang 11 path 43 flat 0.00 dark 0.00 | diag: startup fast (>1.8 m/s) |
| fastmid-106878858_174886965-01 | 7.63 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.41 ang 17 path 52 flat 0.08 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-ProcTHOR-Train-64-01 | 5.77 | mid fast (v0>=1.8) | v0 2.65 ang 127 path 56 flat 0.07 dark 0.08 | rule: fast start (suspect startup runaway) |
| fast-ProcTHOR-Train-100-02 | 5.76 | flat/dark scene | v0 0.03 ang 62 path 58 flat 0.18 dark 0.32 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-166-00 | 5.70 | mid wrongdir (0.3<=v0<1.8, >=90deg) | v0 0.93 ang 144 path 48 flat 0.07 dark 0.07 | diag: starved coasting (low live tracks) |
| fast-ProcTHOR-Train-85-01 | 4.19 | static | v0 0.03 ang 62 path 37 flat 0.18 dark 0.10 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-85-02 | 3.88 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.93 ang 70 path 37 flat 0.13 dark 0.10 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-64-00 | 3.47 | flat/dark scene | v0 0.83 ang 99 path 47 flat 0.22 dark 0.13 | diag: starved coasting (low live tracks) |
| **sel** | | | | |
| fastmid-106366104_174226329-00 | 6.24 | flat/dark scene | v0 1.07 ang 6 path 59 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-106366104_174226329-01 | 5.03 | flat/dark scene | v0 0.02 ang 35 path 62 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-106366104_174226329-02 | 4.83 | flat/dark scene | v0 0.11 ang 47 path 57 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-ProcTHOR-Train-143-01 | 3.79 | mid fast (v0>=1.8) | v0 1.84 ang 19 path 60 flat 0.00 dark 0.00 | rule: fast start (suspect startup runaway) |
| fastmid-102344280-01 | 3.74 | mid fwd (0.3<=v0<1.8, <90deg) | v0 1.42 ang 10 path 56 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-103997478_171030525-00 | 3.60 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.56 ang 66 path 78 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-ProcTHOR-Train-100-02 | 3.56 | flat/dark scene | v0 0.69 ang 115 path 52 flat 0.20 dark 0.43 | diag: starved coasting (low live tracks) |
| fast-106366104_174226329-00 | 3.51 | flat/dark scene | v0 0.03 ang 62 path 64 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
