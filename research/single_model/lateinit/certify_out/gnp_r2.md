# gnp_r2: custom candidate

## 1. Overall
| set | n | mean | median | p90 | max | >3 m | >5 m | >10 m | honesty |
|--|--|--|--|--|--|--|--|--|--|
| fresh | 711 | 0.331 | 0.25 | 0.59 | 2.8 | 0/711 0.0% [0.0,0.5] | 0/711 0.0% [0.0,0.5] | 0 | never tuned on, but partly used in adoption decisions (mildly optimistic) |

## 2. Per-class failure shares (primary classes exclusive; overlay tags not exclusive)
### fresh

| class | n | mean ATE | >3 m (Wilson 95%) | >5 m (Wilson 95%) | >3 m scene-boot 95% |
|--|--|--|--|--|--|
| static | 352 | 0.27 | 0/352 0.0% [0.0,1.1] | 0/352 0.0% [0.0,1.1] | [0.0,0.0] |
| mid slow (v0<0.3) | 64 | 0.32 | 0/64 0.0% [0.0,5.7] | 0/64 0.0% [0.0,5.7] | [0.0,0.0] |
| mid fwd (0.3<=v0<1.8, <90deg) | 219 | 0.35 | 0/219 0.0% [0.0,1.7] | 0/219 0.0% [0.0,1.7] | [0.0,0.0] |
| mid wrongdir (0.3<=v0<1.8, >=90deg) | 41 | 0.41 | 0/41 0.0% [0.0,8.6] | 0/41 0.0% [0.0,8.6] | [0.0,0.0] |
| mid fast (v0>=1.8) | 22 | 0.78 | 0/22 0.0% [0.0,14.9] | 0/22 0.0% [0.0,14.9] | [0.0,0.0] |
| flat/dark scene | 13 | 0.65 | 0/13 0.0% [0.0,22.8] | 0/13 0.0% [0.0,22.8] | [0.0,0.0] |
| ALL | 711 | 0.33 | 0/711 0.0% [0.0,0.5] | 0/711 0.0% [0.0,0.5] | [0.0,0.0] |
| *overlay tags (not exclusive)* | | | | | |
| reverse>=135 | 12 | 0.58 | 0/12 0.0% [0.0,24.3] | 0/12 0.0% [0.0,24.3] | [0.0,0.0] |
| flat>0.05 | 72 | 0.64 | 0/72 0.0% [0.0,5.1] | 0/72 0.0% [0.0,5.1] | [0.0,0.0] |
| path<45 | 357 | 0.27 | 0/357 0.0% [0.0,1.1] | 0/357 0.0% [0.0,1.1] | [0.0,0.0] |
| path45-65 | 348 | 0.40 | 0/348 0.0% [0.0,1.1] | 0/348 0.0% [0.0,1.1] | [0.0,0.0] |
| path>=65 | 6 | 0.36 | 0/6 0.0% [0.0,39.0] | 0/6 0.0% [0.0,39.0] | [0.0,0.0] |
| extent<3 | 413 | 0.28 | 0/413 0.0% [0.0,0.9] | 0/413 0.0% [0.0,0.9] | [0.0,0.0] |
| extent3-5 | 233 | 0.38 | 0/233 0.0% [0.0,1.6] | 0/233 0.0% [0.0,1.6] | [0.0,0.0] |
| extent>=5 | 65 | 0.47 | 0/65 0.0% [0.0,5.6] | 0/65 0.0% [0.0,5.6] | [0.0,0.0] |
| cat:hssd-train | 76 | 0.26 | 0/76 0.0% [0.0,4.8] | 0/76 0.0% [0.0,4.8] | [0.0,0.0] |
| cat:hssd-val | 57 | 0.32 | 0/57 0.0% [0.0,6.3] | 0/57 0.0% [0.0,6.3] | [0.0,0.0] |
| cat:procthor | 578 | 0.34 | 0/578 0.0% [0.0,0.7] | 0/578 0.0% [0.0,0.7] | [0.0,0.0] |
| set:K | 366 | 0.35 | 0/366 0.0% [0.0,1.0] | 0/366 0.0% [0.0,1.0] | [0.0,0.0] |
| set:K2 | 345 | 0.31 | 0/345 0.0% [0.0,1.1] | 0/345 0.0% [0.0,1.1] | [0.0,0.0] |

## 3. P(all 12 server episodes <= 3 m)
Estimators (all INFERENCE-based; chaos between replicate builds moves single-set rates by +-15% relative, see NOTES.md):

| estimator | set | pm=0.5 | pm=0.75 |
|--|--|--|--|
| path-matched 12-draw proxy (K=60 nearest paths; 90% scene-bootstrap) | fresh | 1.00 [1.00,1.00] | 1.00 [1.00,1.00] |
| flat rate, (1-r)^12, r=Jeffreys 0.1% (Wilson-upper r=0.5% -> 0.94) | fresh | 0.99 | 0.99 |

Class-conditional (per-episode class posterior from the server (B0, G) results, INFERENCE; class rates Jeffreys-smoothed; 90% interval from Beta draws of class rates):

| rates from | pm | P(12 clean) | 90% interval | expected # episodes >3 m |
|--|--|--|--|--|
| fresh (Jeffreys) | 0.5 | 0.95 | [0.89,0.99] | 0.05 |
| fresh (Jeffreys) | 0.75 | 0.94 | [0.88,0.99] | 0.06 |
| pooled all sets (Jeffreys) | 0.5 | 0.95 | [0.90,0.99] | 0.05 |
| pooled all sets (Jeffreys) | 0.75 | 0.94 | [0.89,0.99] | 0.06 |

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
| fastmid-ProcTHOR-Train-151-03 | 2.81 | mid fast (v0>=1.8) | v0 1.86 ang 50 path 46 flat 0.00 dark 0.00 | diag: startup fast (>1.8 m/s) |
| fastmid-ProcTHOR-Train-64-01 | 2.81 | mid fast (v0>=1.8) | v0 2.65 ang 127 path 56 flat 0.07 dark 0.08 | rule: fast start (suspect startup runaway) |
| fastmid-ProcTHOR-Train-74-02 | 2.53 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.40 ang 24 path 47 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-ProcTHOR-Train-166-04 | 2.21 | mid fwd (0.3<=v0<1.8, <90deg) | v0 1.03 ang 2 path 45 flat 0.12 dark 0.05 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fast-ProcTHOR-Train-166-05 | 2.08 | static | v0 0.03 ang 62 path 41 flat 0.07 dark 0.08 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-166-00 | 2.03 | mid wrongdir (0.3<=v0<1.8, >=90deg) | v0 0.93 ang 144 path 48 flat 0.07 dark 0.07 | diag: starved coasting (low live tracks) |
| fastmid-ProcTHOR-Train-176-11 | 1.87 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.98 ang 11 path 34 flat 0.00 dark 0.00 | rule: regular mid start (startup chaos or late drift; needs diag.c) |
| fastmid-ProcTHOR-Train-85-02 | 1.83 | mid fwd (0.3<=v0<1.8, <90deg) | v0 0.93 ang 70 path 37 flat 0.13 dark 0.10 | diag: starved coasting (low live tracks) |
