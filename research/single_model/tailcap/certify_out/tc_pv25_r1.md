# tc_pv25_r1: custom candidate

## 1. Overall
| set | n | mean | median | p90 | max | >3 m | >5 m | >10 m | honesty |
|--|--|--|--|--|--|--|--|--|--|
| fresh | 711 | 0.482 | 0.33 | 0.79 | 7.6 | 9/711 1.3% [0.7,2.4] | 3/711 0.4% [0.1,1.2] | 0 | never tuned on, but partly used in adoption decisions (mildly optimistic) |
| sel | 144 | 0.601 | 0.40 | 1.14 | 5.3 | 4/144 2.8% [1.1,6.9] | 1/144 0.7% [0.1,3.8] | 0 | used for tuning/selection (optimistic) |

## 2. Per-class failure shares (primary classes exclusive; overlay tags not exclusive)
### fresh

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 352 | 0.41 | 2/352 0.6% [0.2,2.0] | 1/352 0.3% [0.1,1.6] | [0.0,1.5] |
| mid slow (v0<0.3) | 64 | 0.47 | 0/64 0.0% [0.0,5.7] | 0/64 0.0% [0.0,5.7] | [0.0,0.0] |
| mid fwd (0.3<=v0<1.8, <90deg) | 219 | 0.47 | 2/219 0.9% [0.3,3.3] | 1/219 0.5% [0.1,2.5] | [0.0,2.6] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 41 | 0.48 | 0/41 0.0% [0.0,8.6] | 0/41 0.0% [0.0,8.6] | [0.0,0.0] |
| mid fast (v0>=1.8) | 22 | 1.45 | 4/22 18.2% [7.3,38.5] | 1/22 4.5% [0.8,21.8] | [4.3,36.4] |
| flat/dark scene | 13 | 1.11 | 1/13 7.7% [1.4,33.3] | 0/13 0.0% [0.0,22.8] | [0.0,27.3] |
| ALL | 711 | 0.48 | 9/711 1.3% [0.7,2.4] | 3/711 0.4% [0.1,1.2] | [0.4,2.3] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 12 | 0.60 | 0/12 0.0% [0.0,24.3] | 0/12 0.0% [0.0,24.3] | [0.0,0.0] |
| flat>0.05 | 72 | 1.11 | 6/72 8.3% [3.9,17.0] | 2/72 2.8% [0.8,9.6] | [1.7,18.3] |
| path<45 | 357 | 0.42 | 5/357 1.4% [0.6,3.2] | 2/357 0.6% [0.2,2.0] | [0.2,3.0] |
| path45-65 | 348 | 0.55 | 4/348 1.1% [0.4,2.9] | 1/348 0.3% [0.1,1.6] | [0.3,2.3] |
| path>=65 | 6 | 0.59 | 0/6 0.0% [0.0,39.0] | 0/6 0.0% [0.0,39.0] | [0.0,0.0] |
| extent<3 | 413 | 0.44 | 6/413 1.5% [0.7,3.1] | 2/413 0.5% [0.1,1.7] | [0.3,3.1] |
| extent3-5 | 233 | 0.50 | 2/233 0.9% [0.2,3.1] | 0/233 0.0% [0.0,1.6] | [0.0,2.2] |
| extent>=5 | 65 | 0.66 | 1/65 1.5% [0.3,8.2] | 1/65 1.5% [0.3,8.2] | [0.0,5.2] |
| cat:hssd-train | 76 | 0.33 | 0/76 0.0% [0.0,4.8] | 0/76 0.0% [0.0,4.8] | [0.0,0.0] |
| cat:hssd-val | 57 | 0.53 | 1/57 1.8% [0.3,9.3] | 1/57 1.8% [0.3,9.3] | [0.0,6.3] |
| cat:procthor | 578 | 0.50 | 8/578 1.4% [0.7,2.7] | 2/578 0.3% [0.1,1.3] | [0.5,2.5] |
| set:K | 366 | 0.49 | 5/366 1.4% [0.6,3.2] | 1/366 0.3% [0.0,1.5] | [0.0,2.9] |
| set:K2 | 345 | 0.47 | 4/345 1.2% [0.5,2.9] | 2/345 0.6% [0.2,2.1] | [0.3,2.4] |

### sel

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 67 | 0.40 | 0/67 0.0% [0.0,5.4] | 0/67 0.0% [0.0,5.4] | [0.0,0.0] |
| mid slow (v0<0.3) | 5 | 0.62 | 0/5 0.0% [0.0,43.4] | 0/5 0.0% [0.0,43.4] | [0.0,0.0] |
| mid fwd (0.3<=v0<1.8, <90deg) | 52 | 0.51 | 0/52 0.0% [0.0,6.9] | 0/52 0.0% [0.0,6.9] | [0.0,0.0] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 5 | 0.47 | 0/5 0.0% [0.0,43.4] | 0/5 0.0% [0.0,43.4] | [0.0,0.0] |
| mid fast (v0>=1.8) | 10 | 0.84 | 0/10 0.0% [0.0,27.8] | 0/10 0.0% [0.0,27.8] | [0.0,0.0] |
| flat/dark scene | 5 | 3.87 | 4/5 80.0% [37.6,96.4] | 1/5 20.0% [3.6,62.4] | [75.0,100.0] |
| ALL | 144 | 0.60 | 4/144 2.8% [1.1,6.9] | 1/144 0.7% [0.1,3.8] | [0.0,7.7] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 4 | 0.58 | 0/4 0.0% [0.0,49.0] | 0/4 0.0% [0.0,49.0] | [0.0,0.0] |
| flat>0.05 | 12 | 2.21 | 4/12 33.3% [13.8,60.9] | 1/12 8.3% [1.5,35.4] | [0.0,58.8] |
| path<45 | 11 | 0.28 | 0/11 0.0% [0.0,25.9] | 0/11 0.0% [0.0,25.9] | [0.0,0.0] |
| path45-65 | 113 | 0.63 | 4/113 3.5% [1.4,8.7] | 1/113 0.9% [0.2,4.8] | [0.0,9.5] |
| path>=65 | 20 | 0.61 | 0/20 0.0% [0.0,16.1] | 0/20 0.0% [0.0,16.1] | [0.0,0.0] |
| extent<3 | 41 | 0.37 | 0/41 0.0% [0.0,8.6] | 0/41 0.0% [0.0,8.6] | [0.0,0.0] |
| extent3-5 | 71 | 0.70 | 2/71 2.8% [0.8,9.7] | 1/71 1.4% [0.2,7.6] | [0.0,7.8] |
| extent>=5 | 32 | 0.67 | 2/32 6.2% [1.7,20.1] | 0/32 0.0% [0.0,10.7] | [0.0,22.2] |
| cat:hssd-train | 40 | 0.46 | 0/40 0.0% [0.0,8.8] | 0/40 0.0% [0.0,8.8] | [0.0,0.0] |
| cat:hssd-val | 26 | 1.03 | 3/26 11.5% [4.0,29.0] | 1/26 3.8% [0.7,18.9] | [0.0,31.0] |
| cat:procthor | 78 | 0.53 | 1/78 1.3% [0.2,6.9] | 0/78 0.0% [0.0,4.7] | [0.0,4.2] |
| set:K | 60 | 0.52 | 1/60 1.7% [0.3,8.9] | 0/60 0.0% [0.0,6.0] | [0.0,5.5] |
| set:K2 | 84 | 0.66 | 3/84 3.6% [1.2,10.0] | 1/84 1.2% [0.2,6.4] | [0.0,9.5] |

## 3. P(all 12 server episodes <= 3 m)
Estimators (all INFERENCE-based; chaos between replicate builds moves single-set rates by +-15% relative, see NOTES.md):

| estimator | set | pm=0.5 | pm=0.75 |
|--|--|--|--|
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | fresh | 0.75 [0.54,0.97] | 0.80 [0.66,0.96] |
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | sel | 0.65 [0.35,1.00] | 0.58 [0.23,1.00] |
| flat rate, (1-r)^12, r=Jeffreys 1.3% (Wilson-upper r=2.4% -> 0.75) | fresh | 0.85 | 0.85 |
| flat rate, (1-r)^12, r=Jeffreys 3.1% (Wilson-upper r=6.9% -> 0.42) | sel | 0.69 | 0.69 |

Class-conditional (per-episode class posterior from the server (B0, G) results, INFERENCE; class rates Jeffreys-smoothed; 90% interval from Beta draws of class rates):

| rates from | pm | P(12 clean) | 90% interval | expected # episodes >3 m |
|--|--|--|--|--|
| fresh (Jeffreys) | 0.5 | 0.78 | [0.68,0.86] | 0.25 |
| fresh (Jeffreys) | 0.75 | 0.77 | [0.66,0.87] | 0.26 |
| sel (Jeffreys) | 0.5 | 0.71 | [0.54,0.86] | 0.33 |
| sel (Jeffreys) | 0.75 | 0.69 | [0.48,0.85] | 0.37 |
| pooled all sets (Jeffreys) | 0.5 | 0.80 | [0.73,0.88] | 0.22 |
| pooled all sets (Jeffreys) | 0.75 | 0.80 | [0.71,0.87] | 0.23 |

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
| fast-ProcTHOR-Train-166-05 | 7.58 | static | v0 0.03 ang 62 path 41 flat 0.07 dark 0.08 | diag: starved coasting (low live tracks) |
| fastmid-106878858_174886965-01 | 6.77 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.41 ang 17 path 52 flat 0.08 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-ProcTHOR-Train-176-05 | 5.63 | mid fast (v0>=1.8) | v0 2.29 ang 11 path 43 flat 0.00 dark 0.00 | diag: startup fast (>1.8 m/s) |
| fastmid-ProcTHOR-Train-64-01 | 4.43 | mid fast (v0>=1.8) | v0 2.65 ang 127 path 56 flat 0.07 dark 0.08 | rule: fast start (suspect startup runaway) |
| fastmid-ProcTHOR-Train-85-02 | 4.28 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.93 ang 70 path 37 flat 0.13 dark 0.10 | diag: starved coasting (low live tracks) |
| fast-ProcTHOR-Train-100-02 | 3.45 | flat/dark scene | v0 0.03 ang 62 path 58 flat 0.18 dark 0.32 | diag: starved coasting (low live tracks) |
| fast-ProcTHOR-Train-85-01 | 3.41 | static | v0 0.03 ang 62 path 37 flat 0.18 dark 0.10 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-161-00 | 3.13 | mid fast (v0>=1.8) | v0 2.20 ang 63 path 46 flat 0.00 dark 0.00 | diag: startup fast (>1.8 m/s) |
| **sel** | | | | |
| fastmid-106366104_174226329-00 | 5.32 | flat/dark scene | v0 1.07 ang 6 path 59 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fast-106366104_174226329-00 | 3.91 | flat/dark scene | v0 0.03 ang 62 path 64 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-106366104_174226329-01 | 3.84 | flat/dark scene | v0 0.02 ang 35 path 62 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-ProcTHOR-Train-100-02 | 3.67 | flat/dark scene | v0 0.69 ang 115 path 52 flat 0.20 dark 0.43 | diag: starved coasting (low live tracks) |
| fastmid-106366104_174226329-02 | 2.61 | flat/dark scene | v0 0.11 ang 47 path 57 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-ProcTHOR-Train-143-01 | 1.89 | mid fast (v0>=1.8) | v0 1.84 ang 19 path 60 flat 0.00 dark 0.00 | rule: fast start (suspect startup runaway) |
| fastmid-ProcTHOR-Train-57-02 | 1.84 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.81 ang 31 path 58 flat 0.10 dark 0.00 | diag: late scale/bias drift |
| fastmid-103997478_171030525-00 | 1.73 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.56 ang 66 path 78 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
