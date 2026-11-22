
## Initial GSLV profile
60 st2dev flights, 72000 frames; p99 3.532 M. Host-marker build (small instrumentation overhead).
| phase | peak frame M | mean of top 1% frames M |
|---|---:|---:|
| line tracking/detection | 0.102 | 0.248 |
| line GN fit | 0.557 | 0.275 |
| line update Jacobians | 0.383 | 0.165 |
| velocity net | 0.004 | 0.127 |
| rest MSCKF update | 4.178 | 2.387 |
| other | 0.741 | 0.756 |
| total | 5.965 | 3.957 |
