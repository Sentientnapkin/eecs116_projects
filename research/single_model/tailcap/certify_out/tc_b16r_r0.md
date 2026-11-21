# tc_b16r_r0: custom candidate

## 1. Overall
| set | n | mean | median | p90 | max | >3 m | >5 m | >10 m | honesty |
|--|--|--|--|--|--|--|--|--|--|
| fresh | 711 | 0.354 | 0.24 | 0.62 | 5.8 | 4/711 0.6% [0.2,1.4] | 1/711 0.1% [0.0,0.8] | 0 | never tuned on, but partly used in adoption decisions (mildly optimistic) |
| sel | 144 | 0.557 | 0.34 | 0.79 | 5.1 | 6/144 4.2% [1.9,8.8] | 1/144 0.7% [0.1,3.8] | 0 | used for tuning/selection (optimistic) |

## 2. Per-class failure shares (primary classes exclusive; overlay tags not exclusive)
### fresh

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 352 | 0.28 | 1/352 0.3% [0.1,1.6] | 0/352 0.0% [0.0,1.1] | [0.0,1.0] |
| mid slow (v0<0.3) | 64 | 0.37 | 0/64 0.0% [0.0,5.7] | 0/64 0.0% [0.0,5.7] | [0.0,0.0] |
| mid fwd (0.3<=v0<1.8, <90deg) | 219 | 0.36 | 1/219 0.5% [0.1,2.5] | 0/219 0.0% [0.0,1.7] | [0.0,1.6] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 41 | 0.47 | 1/41 2.4% [0.4,12.6] | 0/41 0.0% [0.0,8.6] | [0.0,9.1] |
| mid fast (v0>=1.8) | 22 | 0.73 | 0/22 0.0% [0.0,14.9] | 0/22 0.0% [0.0,14.9] | [0.0,0.0] |
| flat/dark scene | 13 | 1.09 | 1/13 7.7% [1.4,33.3] | 1/13 7.7% [1.4,33.3] | [0.0,27.3] |
| ALL | 711 | 0.35 | 4/711 0.6% [0.2,1.4] | 1/711 0.1% [0.0,0.8] | [0.1,1.2] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 12 | 0.79 | 1/12 8.3% [1.5,35.4] | 0/12 0.0% [0.0,24.3] | [0.0,27.3] |
| flat>0.05 | 72 | 0.87 | 4/72 5.6% [2.2,13.4] | 1/72 1.4% [0.2,7.5] | [1.2,12.8] |
| path<45 | 357 | 0.29 | 1/357 0.3% [0.0,1.6] | 0/357 0.0% [0.0,1.1] | [0.0,1.1] |
| path45-65 | 348 | 0.42 | 3/348 0.9% [0.3,2.5] | 1/348 0.3% [0.1,1.6] | [0.0,2.0] |
| path>=65 | 6 | 0.33 | 0/6 0.0% [0.0,39.0] | 0/6 0.0% [0.0,39.0] | [0.0,0.0] |
| extent<3 | 413 | 0.30 | 1/413 0.2% [0.0,1.4] | 0/413 0.0% [0.0,0.9] | [0.0,0.9] |
| extent3-5 | 233 | 0.40 | 2/233 0.9% [0.2,3.1] | 1/233 0.4% [0.1,2.4] | [0.0,2.3] |
| extent>=5 | 65 | 0.52 | 1/65 1.5% [0.3,8.2] | 0/65 0.0% [0.0,5.6] | [0.0,5.2] |
| cat:hssd-train | 76 | 0.25 | 0/76 0.0% [0.0,4.8] | 0/76 0.0% [0.0,4.8] | [0.0,0.0] |
| cat:hssd-val | 57 | 0.38 | 1/57 1.8% [0.3,9.3] | 0/57 0.0% [0.0,6.3] | [0.0,6.3] |
| cat:procthor | 578 | 0.36 | 3/578 0.5% [0.2,1.5] | 1/578 0.2% [0.0,1.0] | [0.0,1.2] |
| set:K | 366 | 0.37 | 1/366 0.3% [0.0,1.5] | 0/366 0.0% [0.0,1.0] | [0.0,0.9] |
| set:K2 | 345 | 0.34 | 3/345 0.9% [0.3,2.5] | 1/345 0.3% [0.1,1.6] | [0.0,2.1] |

### sel

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 67 | 0.36 | 0/67 0.0% [0.0,5.4] | 0/67 0.0% [0.0,5.4] | [0.0,0.0] |
| mid slow (v0<0.3) | 5 | 0.66 | 0/5 0.0% [0.0,43.4] | 0/5 0.0% [0.0,43.4] | [0.0,0.0] |
| mid fwd (0.3<=v0<1.8, <90deg) | 52 | 0.43 | 1/52 1.9% [0.3,10.1] | 0/52 0.0% [0.0,6.9] | [0.0,6.2] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 5 | 0.49 | 0/5 0.0% [0.0,43.4] | 0/5 0.0% [0.0,43.4] | [0.0,0.0] |
| mid fast (v0>=1.8) | 10 | 0.89 | 1/10 10.0% [1.8,40.4] | 0/10 0.0% [0.0,27.8] | [0.0,33.3] |
| flat/dark scene | 5 | 3.77 | 4/5 80.0% [37.6,96.4] | 1/5 20.0% [3.6,62.4] | [75.0,100.0] |
| ALL | 144 | 0.56 | 6/144 4.2% [1.9,8.8] | 1/144 0.7% [0.1,3.8] | [0.7,9.3] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 4 | 0.54 | 0/4 0.0% [0.0,49.0] | 0/4 0.0% [0.0,49.0] | [0.0,0.0] |
| flat>0.05 | 12 | 2.10 | 4/12 33.3% [13.8,60.9] | 1/12 8.3% [1.5,35.4] | [0.0,58.8] |
| path<45 | 11 | 0.28 | 0/11 0.0% [0.0,25.9] | 0/11 0.0% [0.0,25.9] | [0.0,0.0] |
| path45-65 | 113 | 0.58 | 5/113 4.4% [1.9,9.9] | 1/113 0.9% [0.2,4.8] | [0.8,10.7] |
| path>=65 | 20 | 0.60 | 1/20 5.0% [0.9,23.6] | 0/20 0.0% [0.0,16.1] | [0.0,15.8] |
| extent<3 | 41 | 0.36 | 0/41 0.0% [0.0,8.6] | 0/41 0.0% [0.0,8.6] | [0.0,0.0] |
| extent3-5 | 71 | 0.61 | 4/71 5.6% [2.2,13.6] | 0/71 0.0% [0.0,5.1] | [1.3,11.5] |
| extent>=5 | 32 | 0.69 | 2/32 6.2% [1.7,20.1] | 1/32 3.1% [0.6,15.7] | [0.0,22.2] |
| cat:hssd-train | 40 | 0.44 | 1/40 2.5% [0.4,12.9] | 0/40 0.0% [0.0,8.8] | [0.0,8.3] |
| cat:hssd-val | 26 | 0.94 | 3/26 11.5% [4.0,29.0] | 1/26 3.8% [0.7,18.9] | [0.0,31.0] |
| cat:procthor | 78 | 0.49 | 2/78 2.6% [0.7,8.9] | 0/78 0.0% [0.0,4.7] | [0.0,7.0] |
| set:K | 60 | 0.47 | 2/60 3.3% [0.9,11.4] | 1/60 1.7% [0.3,8.9] | [0.0,8.3] |
| set:K2 | 84 | 0.62 | 4/84 4.8% [1.9,11.6] | 0/84 0.0% [0.0,4.4] | [0.0,10.9] |

## 3. P(all 12 server episodes <= 3 m)
Estimators (all INFERENCE-based; chaos between replicate builds moves single-set rates by +-15% relative, see NOTES.md):

| estimator | set | pm=0.5 | pm=0.75 |
|--|--|--|--|
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | fresh | 0.82 [0.63,1.00] | 0.89 [0.79,1.00] |
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | sel | 0.53 [0.26,0.93] | 0.43 [0.18,0.88] |
| flat rate, (1-r)^12, r=Jeffreys 0.6% (Wilson-upper r=1.4% -> 0.84) | fresh | 0.93 | 0.93 |
| flat rate, (1-r)^12, r=Jeffreys 4.5% (Wilson-upper r=8.8% -> 0.33) | sel | 0.58 | 0.58 |

Class-conditional (per-episode class posterior from the server (B0, G) results, INFERENCE; class rates Jeffreys-smoothed; 90% interval from Beta draws of class rates):

| rates from | pm | P(12 clean) | 90% interval | expected # episodes >3 m |
|--|--|--|--|--|
| fresh (Jeffreys) | 0.5 | 0.89 | [0.81,0.95] | 0.12 |
| fresh (Jeffreys) | 0.75 | 0.88 | [0.79,0.95] | 0.13 |
| sel (Jeffreys) | 0.5 | 0.59 | [0.39,0.79] | 0.51 |
| sel (Jeffreys) | 0.75 | 0.56 | [0.36,0.76] | 0.57 |
| pooled all sets (Jeffreys) | 0.5 | 0.84 | [0.78,0.91] | 0.17 |
| pooled all sets (Jeffreys) | 0.75 | 0.83 | [0.75,0.90] | 0.18 |

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
| fast-ProcTHOR-Train-100-02 | 5.76 | flat/dark scene | v0 0.03 ang 62 path 58 flat 0.18 dark 0.32 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-166-00 | 4.33 | mid wrongdir (0.3<=v0<1.8, >=90deg) | v0 0.93 ang 144 path 48 flat 0.07 dark 0.07 | diag: starved coasting (low live tracks) |
| fast-ProcTHOR-Train-85-01 | 4.19 | static | v0 0.03 ang 62 path 37 flat 0.18 dark 0.10 | diag: starved coasting (low live tracks) |
| fastmid-106878858_174886965-01 | 3.57 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.41 ang 17 path 52 flat 0.08 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fast-ProcTHOR-Train-166-05 | 2.72 | static | v0 0.03 ang 62 path 41 flat 0.07 dark 0.08 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-151-03 | 2.45 | mid fast (v0>=1.8) | v0 1.86 ang 50 path 46 flat 0.00 dark 0.00 | diag: startup fast (>1.8 m/s) |
| fastmid-ProcTHOR-Train-176-01 | 2.42 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.44 ang 53 path 43 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-ProcTHOR-Train-85-01 | 1.97 | mid slow (v0<0.3) | v0 0.25 ang 113 path 39 flat 0.18 dark 0.20 | diag: starved coasting (low live tracks) |
| **sel** | | | | |
| fastmid-106366104_174226329-01 | 5.07 | flat/dark scene | v0 0.02 ang 35 path 62 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-106366104_174226329-00 | 4.92 | flat/dark scene | v0 1.07 ang 6 path 59 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-ProcTHOR-Train-143-01 | 4.45 | mid fast (v0>=1.8) | v0 1.84 ang 19 path 60 flat 0.00 dark 0.00 | rule: fast start (suspect startup runaway) |
| fast-106366104_174226329-00 | 3.51 | flat/dark scene | v0 0.03 ang 62 path 64 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-103997478_171030525-00 | 3.11 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.56 ang 66 path 78 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-ProcTHOR-Train-100-02 | 3.03 | flat/dark scene | v0 0.69 ang 115 path 52 flat 0.20 dark 0.43 | diag: starved coasting (low live tracks) |
| fastmid-106366104_174226329-02 | 2.30 | flat/dark scene | v0 0.11 ang 47 path 57 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fast-ProcTHOR-Train-57-00 | 2.25 | static | v0 0.03 ang 62 path 52 flat 0.08 dark 0.00 | rule: static (starved coasting / late drift; needs diag.c) |
