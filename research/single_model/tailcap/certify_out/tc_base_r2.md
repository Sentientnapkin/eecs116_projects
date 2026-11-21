# tc_base_r2: custom candidate

## 1. Overall
| set | n | mean | median | p90 | max | >3 m | >5 m | >10 m | honesty |
|--|--|--|--|--|--|--|--|--|--|
| fresh | 711 | 0.537 | 0.34 | 0.90 | 9.2 | 16/711 2.3% [1.4,3.6] | 5/711 0.7% [0.3,1.6] | 0 | never tuned on, but partly used in adoption decisions (mildly optimistic) |
| sel | 144 | 0.781 | 0.40 | 1.54 | 10.3 | 9/144 6.2% [3.3,11.5] | 2/144 1.4% [0.4,4.9] | 1 | used for tuning/selection (optimistic) |

## 2. Per-class failure shares (primary classes exclusive; overlay tags not exclusive)
### fresh

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 352 | 0.39 | 2/352 0.6% [0.2,2.0] | 1/352 0.3% [0.1,1.6] | [0.0,1.5] |
| mid slow (v0<0.3) | 64 | 0.66 | 3/64 4.7% [1.6,12.9] | 0/64 0.0% [0.0,5.7] | [0.0,10.3] |
| mid fwd (0.3<=v0<1.8, <90deg) | 219 | 0.53 | 5/219 2.3% [1.0,5.2] | 1/219 0.5% [0.1,2.5] | [0.6,4.5] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 41 | 0.52 | 1/41 2.4% [0.4,12.6] | 0/41 0.0% [0.0,8.6] | [0.0,9.1] |
| mid fast (v0>=1.8) | 22 | 1.89 | 4/22 18.2% [7.3,38.5] | 2/22 9.1% [2.5,27.8] | [4.3,38.1] |
| flat/dark scene | 13 | 1.82 | 1/13 7.7% [1.4,33.3] | 1/13 7.7% [1.4,33.3] | [0.0,27.3] |
| ALL | 711 | 0.54 | 16/711 2.3% [1.4,3.6] | 5/711 0.7% [0.3,1.6] | [1.2,3.7] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 12 | 0.82 | 1/12 8.3% [1.5,35.4] | 0/12 0.0% [0.0,24.3] | [0.0,27.3] |
| flat>0.05 | 72 | 1.31 | 8/72 11.1% [5.7,20.4] | 3/72 4.2% [1.4,11.5] | [3.6,22.8] |
| path<45 | 357 | 0.49 | 8/357 2.2% [1.1,4.4] | 4/357 1.1% [0.4,2.8] | [0.6,4.1] |
| path45-65 | 348 | 0.59 | 8/348 2.3% [1.2,4.5] | 1/348 0.3% [0.1,1.6] | [0.7,4.0] |
| path>=65 | 6 | 0.59 | 0/6 0.0% [0.0,39.0] | 0/6 0.0% [0.0,39.0] | [0.0,0.0] |
| extent<3 | 413 | 0.50 | 9/413 2.2% [1.2,4.1] | 4/413 1.0% [0.4,2.5] | [0.8,4.2] |
| extent3-5 | 233 | 0.57 | 6/233 2.6% [1.2,5.5] | 1/233 0.4% [0.1,2.4] | [0.8,5.1] |
| extent>=5 | 65 | 0.64 | 1/65 1.5% [0.3,8.2] | 0/65 0.0% [0.0,5.6] | [0.0,5.2] |
| cat:hssd-train | 76 | 0.37 | 0/76 0.0% [0.0,4.8] | 0/76 0.0% [0.0,4.8] | [0.0,0.0] |
| cat:hssd-val | 57 | 0.51 | 1/57 1.8% [0.3,9.3] | 0/57 0.0% [0.0,6.3] | [0.0,6.3] |
| cat:procthor | 578 | 0.56 | 15/578 2.6% [1.6,4.2] | 5/578 0.9% [0.4,2.0] | [1.2,4.4] |
| set:K | 366 | 0.55 | 9/366 2.5% [1.3,4.6] | 3/366 0.8% [0.3,2.4] | [0.8,4.5] |
| set:K2 | 345 | 0.52 | 7/345 2.0% [1.0,4.1] | 2/345 0.6% [0.2,2.1] | [0.6,3.9] |

### sel

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 67 | 0.44 | 0/67 0.0% [0.0,5.4] | 0/67 0.0% [0.0,5.4] | [0.0,0.0] |
| mid slow (v0<0.3) | 5 | 0.87 | 0/5 0.0% [0.0,43.4] | 0/5 0.0% [0.0,43.4] | [0.0,0.0] |
| mid fwd (0.3<=v0<1.8, <90deg) | 52 | 0.66 | 2/52 3.8% [1.1,13.0] | 0/52 0.0% [0.0,6.9] | [0.0,9.8] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 5 | 0.51 | 0/5 0.0% [0.0,43.4] | 0/5 0.0% [0.0,43.4] | [0.0,0.0] |
| mid fast (v0>=1.8) | 10 | 1.28 | 2/10 20.0% [5.7,51.0] | 0/10 0.0% [0.0,27.8] | [0.0,50.0] |
| flat/dark scene | 5 | 5.86 | 5/5 100.0% [56.6,100.0] | 2/5 40.0% [11.8,76.9] | [100.0,100.0] |
| ALL | 144 | 0.78 | 9/144 6.2% [3.3,11.5] | 2/144 1.4% [0.4,4.9] | [1.4,13.3] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 4 | 0.64 | 0/4 0.0% [0.0,49.0] | 0/4 0.0% [0.0,49.0] | [0.0,0.0] |
| flat>0.05 | 12 | 3.29 | 5/12 41.7% [19.3,68.0] | 2/12 16.7% [4.7,44.8] | [0.0,76.5] |
| path<45 | 11 | 0.33 | 0/11 0.0% [0.0,25.9] | 0/11 0.0% [0.0,25.9] | [0.0,0.0] |
| path45-65 | 113 | 0.84 | 8/113 7.1% [3.6,13.4] | 2/113 1.8% [0.5,6.2] | [1.7,15.5] |
| path>=65 | 20 | 0.69 | 1/20 5.0% [0.9,23.6] | 0/20 0.0% [0.0,16.1] | [0.0,15.8] |
| extent<3 | 41 | 0.43 | 0/41 0.0% [0.0,8.6] | 0/41 0.0% [0.0,8.6] | [0.0,0.0] |
| extent3-5 | 71 | 1.04 | 7/71 9.9% [4.9,19.0] | 2/71 2.8% [0.8,9.7] | [2.9,19.0] |
| extent>=5 | 32 | 0.65 | 2/32 6.2% [1.7,20.1] | 0/32 0.0% [0.0,10.7] | [0.0,22.2] |
| cat:hssd-train | 40 | 0.67 | 2/40 5.0% [1.4,16.5] | 0/40 0.0% [0.0,8.8] | [0.0,12.2] |
| cat:hssd-val | 26 | 1.10 | 4/26 15.4% [6.1,33.5] | 1/26 3.8% [0.7,18.9] | [0.0,41.4] |
| cat:procthor | 78 | 0.73 | 3/78 3.8% [1.3,10.7] | 1/78 1.3% [0.2,6.9] | [0.0,8.5] |
| set:K | 60 | 0.63 | 3/60 5.0% [1.7,13.7] | 0/60 0.0% [0.0,6.0] | [0.0,11.3] |
| set:K2 | 84 | 0.89 | 6/84 7.1% [3.3,14.7] | 2/84 2.4% [0.7,8.3] | [1.1,16.7] |

## 3. P(all 12 server episodes <= 3 m)
Estimators (all INFERENCE-based; chaos between replicate builds moves single-set rates by +-15% relative, see NOTES.md):

| estimator | set | pm=0.5 | pm=0.75 |
|--|--|--|--|
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | fresh | 0.72 [0.48,0.93] | 0.74 [0.58,0.90] |
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | sel | 0.41 [0.16,0.79] | 0.29 [0.08,0.64] |
| flat rate, (1-r)^12, r=Jeffreys 2.3% (Wilson-upper r=3.6% -> 0.64) | fresh | 0.75 | 0.75 |
| flat rate, (1-r)^12, r=Jeffreys 6.6% (Wilson-upper r=11.5% -> 0.23) | sel | 0.44 | 0.44 |

Class-conditional (per-episode class posterior from the server (B0, G) results, INFERENCE; class rates Jeffreys-smoothed; 90% interval from Beta draws of class rates):

| rates from | pm | P(12 clean) | 90% interval | expected # episodes >3 m |
|--|--|--|--|--|
| fresh (Jeffreys) | 0.5 | 0.68 | [0.57,0.78] | 0.38 |
| fresh (Jeffreys) | 0.75 | 0.65 | [0.54,0.76] | 0.42 |
| sel (Jeffreys) | 0.5 | 0.48 | [0.30,0.68] | 0.71 |
| sel (Jeffreys) | 0.75 | 0.44 | [0.26,0.64] | 0.79 |
| pooled all sets (Jeffreys) | 0.5 | 0.65 | [0.55,0.74] | 0.42 |
| pooled all sets (Jeffreys) | 0.75 | 0.62 | [0.52,0.72] | 0.47 |

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
| fast-ProcTHOR-Train-100-02 | 9.20 | flat/dark scene | v0 0.03 ang 62 path 58 flat 0.18 dark 0.32 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-181-01 | 6.89 | mid fast (v0>=1.8) | v0 2.04 ang 53 path 38 flat 0.00 dark 0.00 | rule: fast start (suspect startup runaway) |
| fast-ProcTHOR-Train-166-05 | 6.72 | static | v0 0.03 ang 62 path 41 flat 0.07 dark 0.08 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-176-05 | 6.55 | mid fast (v0>=1.8) | v0 2.29 ang 11 path 43 flat 0.00 dark 0.00 | diag: startup fast (>1.8 m/s) |
| fastmid-ProcTHOR-Train-85-02 | 5.25 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.93 ang 70 path 37 flat 0.13 dark 0.10 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-64-01 | 4.53 | mid fast (v0>=1.8) | v0 2.65 ang 127 path 56 flat 0.07 dark 0.08 | rule: fast start (suspect startup runaway) |
| fastmid-ProcTHOR-Train-178-04 | 4.50 | mid slow (v0<0.3) | v0 0.11 ang 47 path 42 flat 0.00 dark 0.00 | rule: slow/ambiguous mid start (suspect heading-prior over-speed/scale) |
| fastmid-ProcTHOR-Train-171-03 | 4.38 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.46 ang 27 path 52 flat 0.07 dark 0.00 | diag: startup other (runaway, slow/ambiguous) |
| **sel** | | | | |
| fastmid-ProcTHOR-Train-100-02 | 10.28 | flat/dark scene | v0 0.69 ang 115 path 52 flat 0.20 dark 0.43 | diag: starved coasting (low live tracks) |
| fastmid-106366104_174226329-00 | 7.61 | flat/dark scene | v0 1.07 ang 6 path 59 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-102344280-01 | 4.25 | mid fwd (0.3<=v0<1.8, <90deg) | v0 1.42 ang 10 path 56 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-103997478_171030525-00 | 4.03 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.56 ang 66 path 78 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-ProcTHOR-Train-143-01 | 4.02 | mid fast (v0>=1.8) | v0 1.84 ang 19 path 60 flat 0.00 dark 0.00 | rule: fast start (suspect startup runaway) |
| fast-106366104_174226329-00 | 3.94 | flat/dark scene | v0 0.03 ang 62 path 64 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-106366104_174226329-02 | 3.91 | flat/dark scene | v0 0.11 ang 47 path 57 flat 1.00 dark 0.00 | diag: textureless (tracks dead) |
| fastmid-ProcTHOR-Train-57-01 | 3.59 | mid fast (v0>=1.8) | v0 2.12 ang 102 path 55 flat 0.05 dark 0.00 | rule: fast start (suspect startup runaway) |
