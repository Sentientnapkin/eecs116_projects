# Requirements: flight-level >3 m failure rates needed for P(no server episode >3 m)

Equal-rate benchmark: r = 1-p^(1/12): p>=0.5: 5.61%, p>=0.8: 1.84%, p>=0.9: 0.87%. B11 holdout point rate 8/240 = 3.33% (Wilson 95% [1.7, 6.4]%).

Class-conditional model (server class posteriors, INFERENCE). Starting from the B11 shrunk holdout class rates, scale all classes by a common factor f so that P(12 clean) hits the target:

| pm | target | f | overall flight-level rate (prior-weighted) | static | mid slow | mid fwd | mid wrongdir | mid fast | flat/dark scene |
|--|--|--|--|--|--|--|--|--|--|
| 0.5 | now | 1.00 | 3.86% (P=0.64) | 0.9% | 6.4% | 2.8% | 1.0% | 12.9% | 79.2% |
| 0.5 | 0.5 | 1.61 | 5.73% | 1.4% | 10.4% | 4.5% | 1.5% | 20.8% | 100.0% |
| 0.5 | 0.8 | 0.50 | 1.94% | 0.4% | 3.2% | 1.4% | 0.5% | 6.5% | 39.8% |
| 0.5 | 0.9 | 0.24 | 0.92% | 0.2% | 1.5% | 0.7% | 0.2% | 3.1% | 18.9% |
| 0.75 | now | 1.00 | 4.94% (P=0.61) | 0.9% | 6.4% | 2.8% | 1.0% | 12.9% | 79.2% |
| 0.75 | 0.5 | 1.44 | 6.82% | 1.2% | 9.3% | 4.0% | 1.4% | 18.7% | 100.0% |
| 0.75 | 0.8 | 0.46 | 2.28% | 0.4% | 3.0% | 1.3% | 0.4% | 6.0% | 36.5% |
| 0.75 | 0.9 | 0.22 | 1.08% | 0.2% | 1.4% | 0.6% | 0.2% | 2.8% | 17.3% |

Interpretation: the target rows are the per-class rates a build must reach (same relative profile as B11); p>=0.9 needs a ~4-5x lower failure rate in every class (and flat/dark is a ~17-19% class rate by itself), which is at or below the measured chaos floor (new-failure rate 0.9-2.2% per flight per build change, PERSISTENCE.md).

Exact-binomial 95% evidence needed (flights n so that observing k failures excludes a true rate above r): 

| r (target) | k=0 | k=1 | k=2 |
|--|--|--|--|
| 5.61% (p>=0.5) | 52 | 83 | 111 |
| 1.84% (p>=0.8) | 162 | 256 | 340 |
| 0.87% (p>=0.9) | 342 | 541 | 719 |

The existing holdout (n=240, B11 k=8) cannot certify p>=0.8 or 0.9; only a new clean set can, and it can be used once per candidate.
