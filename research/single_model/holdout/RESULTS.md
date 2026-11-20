# Holdout scores (one-shot)
## all
```
base    n=240 mean 1.724 med 0.67 p90 4.08 p95 6.66 max 16.92 | >3: 43 >5: 22 >10: 7 | nan 0
gate    n=240 mean 1.069 med 0.50 p90 2.09 p95 3.69 max 13.58 | >3: 19 >5: 8 >10: 2 | nan 0
gatec1  n=240 mean 0.972 med 0.51 p90 2.22 p95 3.48 max 10.44 | >3: 15 >5: 7 >10: 1 | nan 0
```
## static
```
base    n=120 mean 0.658 med 0.46 p90 1.20 p95 1.67 max 6.21 | >3: 3 >5: 1 >10: 0 | nan 0
gate    n=120 mean 0.623 med 0.42 p90 1.17 p95 1.47 max 6.21 | >3: 2 >5: 1 >10: 0 | nan 0
gatec1  n=120 mean 0.529 med 0.43 p90 0.82 p95 1.06 max 5.29 | >3: 1 >5: 1 >10: 0 | nan 0
```
## mid
```
base    n=120 mean 2.791 med 1.41 p90 6.68 p95 10.18 max 16.92 | >3: 40 >5: 21 >10: 7 | nan 0
gate    n=120 mean 1.515 med 0.63 p90 3.60 p95 6.03 max 13.58 | >3: 17 >5: 7 >10: 2 | nan 0
gatec1  n=120 mean 1.415 med 0.70 p90 3.30 p95 4.89 max 10.44 | >3: 14 >5: 6 >10: 1 | nan 0
```
## Paired scene-bootstrap (new - ref), 95% CI
```
gate   -base  all    -0.655 [-0.977, -0.360]  worse>1m 10 better>1m 48
gate   -base  static -0.035 [-0.084, -0.003]  worse>1m 0 better>1m 1
gate   -base  mid    -1.276 [-1.895, -0.679]  worse>1m 10 better>1m 47
gatec1 -base  all    -0.752 [-1.096, -0.436]  worse>1m 9 better>1m 52
gatec1 -base  static -0.129 [-0.219, -0.053]  worse>1m 0 better>1m 5
gatec1 -base  mid    -1.376 [-2.028, -0.778]  worse>1m 9 better>1m 47
gatec1 -gate  all    -0.097 [-0.259, +0.056]  worse>1m 8 better>1m 16
gatec1 -gate  static -0.094 [-0.170, -0.031]  worse>1m 0 better>1m 3
gatec1 -gate  mid    -0.100 [-0.414, +0.196]  worse>1m 8 better>1m 13
```
