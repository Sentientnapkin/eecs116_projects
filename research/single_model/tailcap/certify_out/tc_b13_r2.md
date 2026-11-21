# tc_b13_r2: custom candidate

## 1. Overall
| set | n | mean | median | p90 | max | >3 m | >5 m | >10 m | honesty |
|--|--|--|--|--|--|--|--|--|--|
| fresh | 711 | 0.394 | 0.25 | 0.69 | 6.7 | 11/711 1.5% [0.9,2.7] | 3/711 0.4% [0.1,1.2] | 0 | never tuned on, but partly used in adoption decisions (mildly optimistic) |
| sel | 144 | 0.606 | 0.33 | 0.92 | 6.2 | 7/144 4.9% [2.4,9.7] | 2/144 1.4% [0.4,4.9] | 0 | used for tuning/selection (optimistic) |

## 2. Per-class failure shares (primary classes exclusive; overlay tags not exclusive)
### fresh

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 352 | 0.29 | 2/352 0.6% [0.2,2.0] | 0/352 0.0% [0.0,1.1] | [0.0,1.5] |
| mid slow (v0<0.3) | 64 | 0.43 | 1/64 1.6% [0.3,8.3] | 0/64 0.0% [0.0,5.7] | [0.0,4.7] |
| mid fwd (0.3<=v0<1.8, <90deg) | 219 | 0.39 | 2/219 0.9% [0.3,3.3] | 0/219 0.0% [0.0,1.7] | [0.0,2.4] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 41 | 0.41 | 0/41 0.0% [0.0,8.6] | 0/41 0.0% [0.0,8.6] | [0.0,0.0] |
| mid fast (v0>=1.8) | 22 | 1.49 | 4/22 18.2% [7.3,38.5] | 2/22 9.1% [2.5,27.8] | [4.3,38.1] |
| flat/dark scene | 13 | 1.24 | 2/13 15.4% [4.3,42.2] | 1/13 7.7% [1.4,33.3] | [0.0,44.4] |
| ALL | 711 | 0.39 | 11/711 1.5% [0.9,2.7] | 3/711 0.4% [0.1,1.2] | [0.7,2.7] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 12 | 0.57 | 0/12 0.0% [0.0,24.3] | 0/12 0.0% [0.0,24.3] | [0.0,0.0] |
| flat>0.05 | 72 | 0.89 | 6/72 8.3% [3.9,17.0] | 2/72 2.8% [0.8,9.6] | [1.3,18.9] |
| path<45 | 357 | 0.33 | 5/357 1.4% [0.6,3.2] | 1/357 0.3% [0.0,1.6] | [0.3,2.9] |
| path45-65 | 348 | 0.46 | 6/348 1.7% [0.8,3.7] | 2/348 0.6% [0.2,2.1] | [0.3,3.5] |
| path>=65 | 6 | 0.39 | 0/6 0.0% [0.0,39.0] | 0/6 0.0% [0.0,39.0] | [0.0,0.0] |
| extent<3 | 413 | 0.35 | 6/413 1.5% [0.7,3.1] | 1/413 0.2% [0.0,1.4] | [0.3,3.0] |
| extent3-5 | 233 | 0.44 | 4/233 1.7% [0.7,4.3] | 2/233 0.9% [0.2,3.1] | [0.0,4.3] |
| extent>=5 | 65 | 0.49 | 1/65 1.5% [0.3,8.2] | 0/65 0.0% [0.0,5.6] | [0.0,3.9] |
| cat:hssd-train | 76 | 0.27 | 0/76 0.0% [0.0,4.8] | 0/76 0.0% [0.0,4.8] | [0.0,0.0] |
| cat:hssd-val | 57 | 0.33 | 0/57 0.0% [0.0,6.3] | 0/57 0.0% [0.0,6.3] | [0.0,0.0] |
| cat:procthor | 578 | 0.42 | 11/578 1.9% [1.1,3.4] | 3/578 0.5% [0.2,1.5] | [0.8,3.3] |
| set:K | 366 | 0.43 | 8/366 2.2% [1.1,4.3] | 1/366 0.3% [0.0,1.5] | [0.8,3.9] |
| set:K2 | 345 | 0.35 | 3/345 0.9% [0.3,2.5] | 2/345 0.6% [0.2,2.1] | [0.0,2.0] |

### sel

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 67 | 0.35 | 0/67 0.0% [0.0,5.4] | 0/67 0.0% [0.0,5.4] | [0.0,0.0] |
| mid slow (v0<0.3) | 5 | 0.83 | 0/5 0.0% [0.0,43.4] | 0/5 0.0% [0.0,43.4] | [0.0,0.0] |
| mid fwd (0.3<=v0<1.8, <90deg) | 52 | 0.52 | 2/52 3.8% [1.1,13.0] | 0/52 0.0% [0.0,6.9] | [0.0,9.8] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 5 | 0.42 | 0/5 0.0% [0.0,43.4] | 0/5 0.0% [0.0,43.4] | [0.0,0.0] |
| mid fast (v0>=1.8) | 10 | 0.67 | 0/10 0.0% [0.0,27.8] | 0/10 0.0% [0.0,27.8] | [0.0,0.0] |
| flat/dark scene | 5 | 4.73 | 5/5 100.0% [56.6,100.0] | 2/5 40.0% [11.8,76.9] | [100.0,100.0] |
| ALL | 144 | 0.61 | 7/144 4.9% [2.4,9.7] | 2/144 1.4% [0.4,4.9] | [0.6,11.6] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 4 | 0.53 | 0/4 0.0% [0.0,49.0] | 0/4 0.0% [0.0,49.0] | [0.0,0.0] |
| flat>0.05 | 12 | 2.49 | 5/12 41.7% [19.3,68.0] | 2/12 16.7% [4.7,44.8] | [0.0,76.5] |
| path<45 | 11 | 0.28 | 0/11 0.0% [0.0,25.9] | 0/11 0.0% [0.0,25.9] | [0.0,0.0] |
| path45-65 | 113 | 0.64 | 6/113 5.3% [2.5,11.1] | 2/113 1.8% [0.5,6.2] | [0.0,13.1] |
| path>=65 | 20 | 0.60 | 1/20 5.0% [0.9,23.6] | 0/20 0.0% [0.0,16.1] | [0.0,15.8] |
| extent<3 | 41 | 0.37 | 0/41 0.0% [0.0,8.6] | 0/41 0.0% [0.0,8.6] | [0.0,0.0] |
| extent3-5 | 71 | 0.71 | 5/71 7.0% [3.0,15.4] | 1/71 1.4% [0.2,7.6] | [1.4,15.6] |
| extent>=5 | 32 | 0.68 | 2/32 6.2% [1.7,20.1] | 1/32 3.1% [0.6,15.7] | [0.0,22.2] |
| cat:hssd-train | 40 | 0.55 | 2/40 5.0% [1.4,16.5] | 0/40 0.0% [0.0,8.8] | [0.0,12.2] |
| cat:hssd-val | 26 | 1.10 | 4/26 15.4% [6.1,33.5] | 2/26 7.7% [2.1,24.1] | [0.0,41.4] |
| cat:procthor | 78 | 0.47 | 1/78 1.3% [0.2,6.9] | 0/78 0.0% [0.0,4.7] | [0.0,4.2] |
| set:K | 60 | 0.54 | 3/60 5.0% [1.7,13.7] | 1/60 1.7% [0.3,8.9] | [0.0,11.3] |
| set:K2 | 84 | 0.65 | 4/84 4.8% [1.9,11.6] | 1/84 1.2% [0.2,6.4] | [0.0,13.3] |

## 3. P(all 12 server episodes <= 3 m)
Estimators (all INFERENCE-based; chaos between replicate builds moves single-set rates by +-15% relative, see NOTES.md):

| estimator | set | pm=0.5 | pm=0.75 |
|--|--|--|--|
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | fresh | 0.76 [0.52,0.97] | 0.81 [0.67,0.95] |
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | sel | 0.53 [0.22,0.93] | 0.42 [0.11,0.88] |
| flat rate, (1-r)^12, r=Jeffreys 1.6% (Wilson-upper r=2.7% -> 0.72) | fresh | 0.82 | 0.82 |
| flat rate, (1-r)^12, r=Jeffreys 5.2% (Wilson-upper r=9.7% -> 0.29) | sel | 0.53 | 0.53 |

Class-conditional (per-episode class posterior from the server (B0, G) results, INFERENCE; class rates Jeffreys-smoothed; 90% interval from Beta draws of class rates):

| rates from | pm | P(12 clean) | 90% interval | expected # episodes >3 m |
|--|--|--|--|--|
| fresh (Jeffreys) | 0.5 | 0.76 | [0.67,0.85] | 0.27 |
| fresh (Jeffreys) | 0.75 | 0.75 | [0.65,0.85] | 0.28 |
| sel (Jeffreys) | 0.5 | 0.54 | [0.34,0.75] | 0.60 |
| sel (Jeffreys) | 0.75 | 0.50 | [0.30,0.72] | 0.67 |
| pooled all sets (Jeffreys) | 0.5 | 0.75 | [0.66,0.83] | 0.29 |
| pooled all sets (Jeffreys) | 0.75 | 0.73 | [0.64,0.82] | 0.31 |

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
| fastmid-ProcTHOR-Train-176-05 | 6.68 | mid fast (v0>=1.8) | v0 2.29 ang 11 path 43 flat 0.00 dark 0.00 | diag: startup fast (>1.8 m/s) |
| fast-ProcTHOR-Train-100-02 | 5.35 | flat/dark scene | v0 0.03 ang 62 path 58 flat 0.18 dark 0.32 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-64-01 | 5.28 | mid fast (v0>=1.8) | v0 2.65 ang 127 path 56 flat 0.07 dark 0.08 | rule: fast start (suspect startup runaway) |
| fastmid-ProcTHOR-Train-161-00 | 4.68 | mid fast (v0>=1.8) | v0 2.20 ang 63 path 46 flat 0.00 dark 0.00 | diag: startup fast (>1.8 m/s) |
| fast-ProcTHOR-Train-166-05 | 3.80 | static | v0 0.03 ang 62 path 41 flat 0.07 dark 0.08 | diag: starved coasting (low live tracks) |
| fast-ProcTHOR-Train-85-01 | 3.73 | static | v0 0.03 ang 62 path 37 flat 0.18 dark 0.10 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-85-02 | 3.66 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.93 ang 70 path 37 flat 0.13 dark 0.10 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-64-00 | 3.62 | flat/dark scene | v0 0.83 ang 99 path 47 flat 0.22 dark 0.13 | diag: starved coasting (low live tracks) |
| **sel** | | | | |
| fastmid-106366104_174226329-00 | 6.24 | flat/dark scene | v0 1.07 ang 6 path 59 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-106366104_174226329-01 | 5.04 | flat/dark scene | v0 0.02 ang 35 path 62 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-106366104_174226329-02 | 4.78 | flat/dark scene | v0 0.11 ang 47 path 57 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-ProcTHOR-Train-100-02 | 4.08 | flat/dark scene | v0 0.69 ang 115 path 52 flat 0.20 dark 0.43 | diag: starved coasting (low live tracks) |
| fastmid-102344280-01 | 4.03 | mid fwd (0.3<=v0<1.8, <90deg) | v0 1.42 ang 10 path 56 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-103997478_171030525-00 | 3.59 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.56 ang 66 path 78 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fast-106366104_174226329-00 | 3.51 | flat/dark scene | v0 0.03 ang 62 path 64 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-ProcTHOR-Train-143-01 | 2.20 | mid fast (v0>=1.8) | v0 1.84 ang 19 path 60 flat 0.00 dark 0.00 | rule: fast start (suspect startup runaway) |
