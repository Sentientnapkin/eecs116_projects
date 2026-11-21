# simprior: simulator-derived dynamics priors on B7 (sp.c = fuel/adopted_c1_fbh_exact.c + #ifndef SP_P1..P4 blocks)
Session restarted once; nothing had been run before restart. Scripts: run.sh (search/val), rep.sh (3 replicates), fresh.py (711 fresh), fit.py (P1 coefficients), ana.py (tails/classes).
P1 coefficients fit on DEV scene folds 0-2 only (fit.py, simstruct t5.pkl): dev-fit on confirm fold-3 truth: 3D vel rms 0.728 vs 1.054 const prior (relation transfers across scenes).
P5 (soft accel/tilt bounds) not implemented/tested (low priority per study).
## Frames (verified in code)
Camera axes: x=-body y, y=-body z, z=+body x (R_bc cols). Body lateral (left) = body y. gyro rows are body FLU; filter state vel is world, R = world<-body. LAT uses vb=R^T v, vb[1].
P1 uses first-window mean gyro (body) in t7 regression; P2 uses frame-mean gyro z - bg_z and world horizontal |v|; mean treated as input (no state derivative).
P3: TH block diag(x-rot 0.074, y-rot 0.110) (up-vector x_cam (right) comp = roll = rot about forward axis... world~body axes at init since align_to_z keeps yaw).
## Results
Bit identity: sp.c with all SP_* off = B7: search/val per-flight ATE identical to mx_B7 (max abs diff 0.0, 144 visible flights); sp_base search 0.950 val 0.442.
Single-run search/val (static is deterministic, mid chaotic ~ +-0.2):
| arm | search | static | mid | >5/>10 | val |
| sp_base (B7) | 0.950 | 0.494 | 1.354 | 4/0 | 0.442 |
| P1 gyro start prior (SP_P1=1) | 1.086 | 0.494 | 1.612 | 6/1 | 0.663 |
| P2r (coordinated turn replaces LAT) | 0.882 | 0.439 | 1.276 | 5/0 | 0.431 |
| P2a (turn + LAT) | 0.883 | 0.440 | 1.277 | 4/1 | 0.433 |
| P3 aniso tilt | 0.989 | 0.494 | 1.429 | 3/2 | 0.439 |
| P4 hold 2.5 s + vel ZUPT 0.1 | 0.939 | 0.472 | 1.354 | 4/0 | 0.424 |
## Transfer analysis (t11_transfer.py, truth only; fold-4 scenes skipped; 25 flights/group, t>2 s, |vh|>0.2)
vy = k wz |vh|: fresh pool K k=1.03 R2 .84 | K2 1.06 .86 | holdout(final, same K/K2 generator) K .99 .83 | K2 .99 .84 (residual rms .21-.23, raw .50-.62): fresh vs holdout agree.
Speed pool (planner settings A-M = slower/other planners): k=0.60 (A, slowest, |vh| 0.44, raw lat rms 0.05), .85 (B-E), .96-.98 (F,G,M), R2 .70-.86; |wz| saturation level 0.64 rad/s in all sets (policy property), saturated fraction 0.07-0.66 grows with speed.
=> relation transfers qualitatively; slope depends on planner speed (0.6 at 0.4 m/s to ~1.0 at 0.9 m/s). A +-30% slope error raises residual rms 0.21 -> 0.25 (K), still half of the zero-model 0.525.
## Fresh-711 (B7 ref 0.618, >3/5/10 = 21/8/0; dev folds0-2 n=475 / confirm folds3-4 n=236)
| arm | all | dev d | confirm d | static d | >3/5/10 | new>10 | newly>3/fixed |
| P1 (full) | 0.694 | +0.063 | +0.102 | 0 | 35/13/1 | 1 | 25/11 |
| P1 lateral-only (search/val only) | search 0.952 val 0.435 (neutral) | | | | | | |
| P2r turn replaces LAT | 0.608 | -0.014 | -0.004 | -0.009 | 15/7/2 | 2 (151-04 11.1, 176-05 13.7) | 6/12 |
| P2a turn + LAT | 0.603 | -0.018 | -0.010 | -0.005 | 18/3/1 | 1 (176-05 12.4) | 6/9 |
| P2s sigma x2 | 0.600 | -0.018 | -0.018 | | 20/7/1 | 1 | 5/6 |
| P2m mean only, sigma .5 | 0.621 | +0.009 | -0.009 | | 18/7/1 | 1 | 5/8 |
| P3 aniso tilt | 0.618 | +0.010 | -0.022 | 0 | 20/5/0 | 0 | 9/10 |
| P4 hold 2.5 s + vel ZUPT | 0.649 | +0.034 | +0.023 | +0.061 | 21/10/0 | 0 | 0/0 |
P4 static regression: the fresh pool has hold_seconds 0.2 for ~half the flights (rest ~1.2 s, not 2.7 s): a long hold is wrong there; server hold unknown.
By class (P2a vs B7, mean): mid a>90 1.80 -> 1.47 (>3: 8 -> 5), a45-90 .94 -> .88, a0-45 .678 -> .685, mid<0.5 .675 -> .710, static .409 -> .404.
3-rep search/val (cmprep): P2a search 0.876 vs B7 0.931 (d -0.054 [-0.20,+0.13]), >3 per rep 9/9/8 vs 12/10/11, val 0.443 vs 0.441.
Slope sensitivity P2r search/val single run: K 0.69 -> 0.818, 0.99 -> 0.882, 1.29 -> 1.033 (2 >10): overshoot hurts, undershoot safe/better.
## Decisions
P1 REJECT (worse, tails +14; same finding as inventive idea d). P2 NOT ADOPTED (dev -0.015..-0.018 < 0.03, new >10 flights 151-04/176-05, mid<0.5 slightly worse); best candidate P2a K~0.7 untested on fresh. P3 REJECT (neutral). P4 REJECT (static +0.061). P5 not tested. No B11 port, no preflight (nothing adopted).
