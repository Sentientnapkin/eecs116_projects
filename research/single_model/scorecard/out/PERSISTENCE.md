# Failure persistence across builds (POST-HOC analysis of existing tables; not used to tune anything)

## holdout (n=240 flights scored by every build in ['B2', 'B4', 'B7', 'B10'])

| number of builds failing the flight (>3 m) | flights |
|--|--|
| 0 | 212 |
| 1 | 11 |
| 2 | 9 |
| 3 | 4 |
| 4 | 4 |

| later build | earlier build | P(later fails | earlier failed) | P(later fails | earlier ok) = "new-failure rate" |
|--|--|--|--|
| B4 | B2 | 11/19 = 58% | 4/221 = 1.8% |
| B7 | B4 | 10/15 = 67% | 5/225 = 2.2% |
| B10 | B7 | 5/15 = 33% | 3/225 = 1.3% |

B10 fails on 8 flights; 2 of them were OK (<=3 m) in ALL of ['B2', 'B4', 'B7'] (new/chaotic failures: rate 0.9% of 214 flights that all older builds solved) and 6 also failed in at least one older build (persistent).

## fresh (n=711 flights scored by every build in ['B2', 'B4', 'B7'])

| number of builds failing the flight (>3 m) | flights |
|--|--|
| 0 | 660 |
| 1 | 27 |
| 2 | 12 |
| 3 | 12 |

| later build | earlier build | P(later fails | earlier failed) | P(later fails | earlier ok) = "new-failure rate" |
|--|--|--|--|
| B4 | B2 | 20/37 = 54% | 9/674 = 1.3% |
| B7 | B4 | 15/29 = 52% | 6/682 = 0.9% |

B7 fails on 21 flights; 5 of them were OK (<=3 m) in ALL of ['B2', 'B4'] (new/chaotic failures: rate 0.8% of 665 flights that all older builds solved) and 16 also failed in at least one older build (persistent).

