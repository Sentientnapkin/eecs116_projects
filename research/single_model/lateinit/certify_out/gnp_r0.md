# gnp_r0: custom candidate

## 1. Overall
| set | n | mean | median | p90 | max | >3 m | >5 m | >10 m | honesty |
|--|--|--|--|--|--|--|--|--|--|
| fresh | 711 | 0.338 | 0.24 | 0.60 | 4.3 | 3/711 0.4% [0.1,1.2] | 0/711 0.0% [0.0,0.5] | 0 | never tuned on, but partly used in adoption decisions (mildly optimistic) |

## 2. Per-class failure shares (primary classes exclusive; overlay tags not exclusive)
### fresh

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 352 | 0.27 | 1/352 0.3% [0.1,1.6] | 0/352 0.0% [0.0,1.1] | [0.0,1.0] |
| mid slow (v0<0.3) | 64 | 0.35 | 0/64 0.0% [0.0,5.7] | 0/64 0.0% [0.0,5.7] | [0.0,0.0] |
| mid fwd (0.3<=v0<1.8, <90deg) | 219 | 0.35 | 1/219 0.5% [0.1,2.5] | 0/219 0.0% [0.0,1.7] | [0.0,1.6] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 41 | 0.47 | 1/41 2.4% [0.4,12.6] | 0/41 0.0% [0.0,8.6] | [0.0,9.1] |
| mid fast (v0>=1.8) | 22 | 0.73 | 0/22 0.0% [0.0,14.9] | 0/22 0.0% [0.0,14.9] | [0.0,0.0] |
| flat/dark scene | 13 | 0.75 | 0/13 0.0% [0.0,22.8] | 0/13 0.0% [0.0,22.8] | [0.0,0.0] |
| ALL | 711 | 0.34 | 3/711 0.4% [0.1,1.2] | 0/711 0.0% [0.0,0.5] | [0.0,1.1] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 12 | 0.79 | 1/12 8.3% [1.5,35.4] | 0/12 0.0% [0.0,24.3] | [0.0,27.3] |
| flat>0.05 | 72 | 0.76 | 3/72 4.2% [1.4,11.5] | 0/72 0.0% [0.0,5.1] | [0.0,12.3] |
| path<45 | 357 | 0.27 | 1/357 0.3% [0.0,1.6] | 0/357 0.0% [0.0,1.1] | [0.0,0.8] |
| path45-65 | 348 | 0.40 | 2/348 0.6% [0.2,2.1] | 0/348 0.0% [0.0,1.1] | [0.0,1.6] |
| path>=65 | 6 | 0.35 | 0/6 0.0% [0.0,39.0] | 0/6 0.0% [0.0,39.0] | [0.0,0.0] |
| extent<3 | 413 | 0.29 | 1/413 0.2% [0.0,1.4] | 0/413 0.0% [0.0,0.9] | [0.0,0.8] |
| extent3-5 | 233 | 0.38 | 1/233 0.4% [0.1,2.4] | 0/233 0.0% [0.0,1.6] | [0.0,1.4] |
| extent>=5 | 65 | 0.51 | 1/65 1.5% [0.3,8.2] | 0/65 0.0% [0.0,5.6] | [0.0,5.2] |
| cat:hssd-train | 76 | 0.25 | 0/76 0.0% [0.0,4.8] | 0/76 0.0% [0.0,4.8] | [0.0,0.0] |
| cat:hssd-val | 57 | 0.37 | 1/57 1.8% [0.3,9.3] | 0/57 0.0% [0.0,6.3] | [0.0,6.3] |
| cat:procthor | 578 | 0.35 | 2/578 0.3% [0.1,1.3] | 0/578 0.0% [0.0,0.7] | [0.0,1.1] |
| set:K | 366 | 0.35 | 0/366 0.0% [0.0,1.0] | 0/366 0.0% [0.0,1.0] | [0.0,0.0] |
| set:K2 | 345 | 0.32 | 3/345 0.9% [0.3,2.5] | 0/345 0.0% [0.0,1.1] | [0.0,2.4] |

## 3. P(all 12 server episodes <= 3 m)
Estimators (all INFERENCE-based; chaos between replicate builds moves single-set rates by +-15% relative, see NOTES.md):

| estimator | set | pm=0.5 | pm=0.75 |
|--|--|--|--|
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | fresh | 0.97 [0.90,1.00] | 0.97 [0.91,1.00] |
| flat rate, (1-r)^12, r=Jeffreys 0.5% (Wilson-upper r=1.2% -> 0.86) | fresh | 0.94 | 0.94 |

Class-conditional (per-episode class posterior from the server (B0, G) results, INFERENCE; class rates Jeffreys-smoothed; 90% interval from Beta draws of class rates):

| rates from | pm | P(12 clean) | 90% interval | expected # episodes >3 m |
|--|--|--|--|--|
| fresh (Jeffreys) | 0.5 | 0.89 | [0.81,0.96] | 0.11 |
| fresh (Jeffreys) | 0.75 | 0.89 | [0.80,0.96] | 0.12 |
| pooled all sets (Jeffreys) | 0.5 | 0.89 | [0.81,0.96] | 0.11 |
| pooled all sets (Jeffreys) | 0.75 | 0.89 | [0.80,0.95] | 0.12 |

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
| fastmid-ProcTHOR-Train-166-00 | 4.33 | mid wrongdir (0.3<=v0<1.8, >=90deg) | v0 0.93 ang 144 path 48 flat 0.07 dark 0.07 | diag: starved coasting (low live tracks) |
| fastmid-106878858_174886965-01 | 3.57 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.41 ang 17 path 52 flat 0.08 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fast-ProcTHOR-Train-166-05 | 3.07 | static | v0 0.03 ang 62 path 41 flat 0.07 dark 0.08 | diag: starved coasting (low live tracks) |
| fast-ProcTHOR-Train-85-01 | 2.63 | static | v0 0.03 ang 62 path 37 flat 0.18 dark 0.10 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-151-03 | 2.45 | mid fast (v0>=1.8) | v0 1.86 ang 50 path 46 flat 0.00 dark 0.00 | diag: startup fast (>1.8 m/s) |
| fastmid-ProcTHOR-Train-64-00 | 2.42 | flat/dark scene | v0 0.83 ang 99 path 47 flat 0.22 dark 0.13 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-85-01 | 1.97 | mid slow (v0<0.3) | v0 0.25 ang 113 path 39 flat 0.18 dark 0.20 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-74-02 | 1.91 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.40 ang 24 path 47 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
