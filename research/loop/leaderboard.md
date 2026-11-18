# Teacher leaderboard

Selection score = mean of nominal and moving-start unaligned ATE on the fixed
development set (lower is better). Sim(3) ATE is the course-scorer alignment.

| Rank | Run | Score (m) | Nominal (m) | Moving (m) | Sim(3) (m) | Best epoch | Params | Note |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | data-teacher-v3-ssm-recipe | 1.260 | 1.152 | 1.367 | 0.4778 | 6/6 | 1286355 | ssm-recipe config on teacher-v3: 322 train shards (+200 generated) |
| 2 | ssm-recipe | 1.292 | 1.219 | 1.364 | 0.5027 | 12/12 | 1286355 | v1 SSM + same recipe (baseline ssm-v1 best 1.51) |
| 3 | data-teacher-v2-gru-recipe | 1.388 | 1.271 | 1.504 | 0.512 | 7/10 | 1848979 | gru-recipe config on teacher-v2: 224 train shards (+100 generated) |
| 4 | ssm-w160-h6 | 1.435 | 1.401 | 1.470 | 0.5033 | 12/12 | 1286355 | leader SSM + longer context and 6 s horizon (equal compute) |
| 5 | gru-recipe | 1.446 | 1.326 | 1.566 | 0.4805 | 12/12 | 1848979 | v1 GRU + weight EMA, cosine LR, 12 ep (baseline gru-v1 best 1.48) |
| 6 | ssm-att | 1.516 | 1.430 | 1.603 | 0.4712 | 2/7 | 1286547 | leader SSM + AirIO attitude input (10 epochs to finish by morning) |
| 7 | gru-blind | 1.594 | 1.467 | 1.721 | 0.4722 | 3/6 | 1848979 | diagnostic: identical to gru-recipe with images blanked; tests whether vision contributes |

Failed: data-teacher-v4-ssm-recipe
