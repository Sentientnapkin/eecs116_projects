
## Refined profile: fees
60 st2dev flights, 72000 frames; p99 3.211 M. Host-marker build (small instrumentation overhead).
| phase | peak frame M | mean of top 1% frames M |
|---|---:|---:|
| line tracking/detection | 0.256 | 0.228 |
| line GN fit | 0.593 | 0.043 |
| line update Jacobians | 0.138 | 0.012 |
| line null-space/gating/row output | 0.392 | 0.064 |
| velocity net | 0.004 | 1.698 |
| rest MSCKF update | 2.265 | 0.583 |
| other | 0.446 | 0.708 |
| total | 4.095 | 3.335 |
