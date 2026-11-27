# anchors agent NOTES (stage-3 GSLV: net anchor rate, long-lived points, warehouse heading; CPU only, 14 workers, v3 TEST never used)

## SUMMARY
(in progress)

## Setup
- base.c = sweep/baseA160.c + one switch AN_NETB (extra governor budget usable ONLY by net micro-steps; default 0).
  mk.py ref "Z" base.c -> 670bc1da == sweep a1_Ze0 (VERIFIED, also after the AN_NETB patch).
  Z = PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0 (runq.sh prepends Z to every build).
- base_sn.c = smallnet/src/g_A2_kd.c (auto_727 lineage + SN A2_kd splice) + AN_NETB in the NS_GCOST loop.
  mk.py "F SN=1 EDGE=0 GOV_B=2.8e6 NS_GCOST=1" -> 83cffddf == smallnet s3_A2_e0b28 (VERIFIED). With SN=1 the big net is unused.
- runq.sh pops "NAME POOL [SRC:file] DEFS" from queue.txt -> evals/an_NAME__POOL.json (14 workers, load wait >170).
- Pools: v3val/v1val = sweep's frozen pools (358/120); wa = the 120 warehouse flights of v3val; s60 = 20/20/20 stratified subset (instrumentation).
- rep.py (venv python): paired vs Ze0 3-rep mean (sw_a1_Ze0{,_r1,_r2}; v1val: sw_a1_Ze0_v1) on the same flights; peak = max over reps,
  p95 pooled frames, area = 0.4*log2(3.77/peak) - 2.2*ln((0.665+d)/0.665).
- lcstat.py: net landings/flight from LC_DEBUG=1 builds (stderr "LC apply" lines; LC_DEBUG changes nothing in the trajectory).

## Results log
### 1. Net anchor rate - instrumentation (s60, LC_DEBUG builds)
- Fire condition is inside `tc_frame - tc_last_fire > TC_GAP (9)` and needs `lc_applied` (single net instance; frame pair 0/K=5).
  => LV_PERIOD < 10 is inert unless TC_GAP is lowered too, and the period can never be shorter than the landing latency (>= K+2 = 7 frames).
| build | landings/flight (1201 frames) | every | latency (frames fire->land) | innov rms (sd units) | ATE s60 (ref 0.636) | peak |
| dbg_ref (Ze0) | 48.6 | 24.7 frames | 22.7 | 0.57 | 0.631 | 3.70M |
| dbg_p6 (LV_PERIOD 6 TC_GAP 5) | identical to ref (budget-limited) | | | | 0.631 | |
| dbg_p1 (LV_PERIOD 1 TC_GAP 0) | identical to ref | | | | 0.631 | |
| dbg_p1nb (p1 + AN_NETB 6e6) | 145.7 | 8.2 frames | 7.0 (structural min) | 0.44 | 0.614 | 7.58M |
=> At GOV_B 3.6e6 the net is budget-starved: it lands only every ~25 frames, ~23 frames after its fire. Rate needs net budget.
### Error decomposition of the reference (sw_a1_Ze0 r0, v3val 358; tools/decomp.py): ATE after removing the best yaw about the
### start / the best displacement scale / both; RMS horizontal vs vertical error components (m)
| class/start | n | raw | yaw-fixed | scale-fixed | both | horiz rms | vert rms | path m |
| room hover | 23 | 0.430 | 0.422 | 0.381 | 0.373 | 0.301 | 0.288 | 60 |
| room mid | 120 | 0.476 | 0.457 | 0.443 | 0.426 | 0.358 | 0.292 | 62 |
| warehouse hover | 59 | 0.803 | 0.784 | 0.732 | 0.712 | 0.544 | 0.553 | 89 |
| warehouse mid | 61 | 0.856 | 0.833 | 0.751 | 0.725 | 0.642 | 0.524 | 89 |
| forest hover | 38 | 0.608 | 0.566 | 0.565 | 0.519 | 0.451 | 0.380 | 81 |
| forest mid | 57 | 0.789 | 0.757 | 0.693 | 0.657 | 0.584 | 0.478 | 82 |
- Warehouse median |yaw error| only 0.6 deg; a perfect global heading fix would remove just ~0.02 m of the 0.83 m warehouse ATE
  (scale fix ~0.09). => direction 3 (heading anchors) has a low ceiling. The VERTICAL component is as large as the whole 2-D
  horizontal one in every class (warehouse 0.54 vs 0.59): altitude drift is a big, under-addressed share of the error.
### 3. Warehouse heading (lines / Manhattan yaw), wa pool (120 warehouse flights), single runs, d vs Ze0 3-rep on the same flights
| name | flags (Z +) | wa ATE (ref 0.841) | d [CI] | peak |
| e1 | EDGE=1 (all line features incl. Manhattan yaw/vert/horiz) | 0.828 | -0.013 [-0.061,+0.037] | 3.63M |
| e1on30 | EDGE=1 EDGE_ON_LIVE=30 (lines only when < 30 live corner tracks) | 0.826 | -0.015 [-0.057,+0.025] | 3.64M |
| e1on45 | EDGE=1 EDGE_ON_LIVE=45 | 0.835 | -0.006 [-0.052,+0.036] | 3.63M |
| e1pix2 | EDGE=1 EDGE_PIX=0.2 (stronger line rows) | 0.837 | -0.005 [-0.055,+0.043] | 3.65M |
| e1myth10 | EDGE=1 EDGE_MYTH=10 (wider Manhattan snap) | 0.819 | -0.022 [-0.068,+0.022] | 3.67M |
### Screening on v3val (358), single runs, d vs Ze0 3-rep (0.665); area = 0.4 log2(3.77/peak) - 2.2 ln((0.665+d)/0.665)
| name | flags (Z +) | raw | d [CI] | peak | p95 | mean fuel | area | ro/wa/fo (ref 0.476/0.841/0.728) |
| p1b2 | LV_PERIOD=1 TC_GAP=0 AN_NETB=2e6 | 0.643 | -0.022 [-0.042,-0.001] | 5.42M | 4.25M | 2.56M | -0.135 | 0.446/0.823/0.712 |
| p1b6 | LV_PERIOD=1 TC_GAP=0 AN_NETB=6e6 (lands every ~8 frames) | 0.645 | -0.020 [-0.043,+0.002] | 7.65M | 6.79M | 2.78M | -0.340 | 0.447/0.835/0.701 |
| mc8 | MAX_CLONES=8 MAX_OBS=10 | 0.633 | -0.033 [-0.053,-0.013] | 3.84M | 3.35M | 2.49M | +0.100 | 0.464/0.776/0.706 |
| mc10 | MAX_CLONES=10 MAX_OBS=12 | 0.632 | -0.033 [-0.055,-0.012] | 4.46M | 4.11M | 2.86M | +0.016 | 0.478/0.753/0.712 |
| mc8o8 | MAX_CLONES=8 (MAX_OBS 8) | 0.633 | -0.033 [-0.056,-0.011] | 3.86M | 3.14M | 2.43M | +0.097 | 0.460/0.792/0.690 |
| mc8g33 | MAX_CLONES=8 MAX_OBS=10 GOV_B=3.3e6 | 0.645 | -0.021 [-0.042,+0.003] | 3.58M | 3.04M | 2.34M | +0.099 | 0.478/0.796/0.705 |
| ce6 | CLONE_EVERY=6 | 0.675 | +0.010 [-0.021,+0.047] | 3.75M | 2.96M | 1.95M | -0.030 | 0.560/0.796/0.696 (rooms +0.08, wa/fo better) |
| p1b1 | LV_PERIOD=1 TC_GAP=0 AN_NETB=1e6 | 0.661 | -0.004 [-0.024,+0.016] | 4.76M | 3.57M | 2.39M | -0.121 | 0.453/0.863/0.720 |
| p1g30 | LV_PERIOD=1 TC_GAP=0 GOV_B=3.0e6 AN_NETB=0.6e6 (vision budget -> net) | 0.683 | +0.018 [-0.004,+0.038] | 3.79M | 2.79M | 2.07M | -0.061 | 0.490/0.885/0.717 |
wa: e1nov (EDGE=1 EDGE_VERT=0) 0.831, d -0.010 [-0.050,+0.031], peak 3.70M.
| p1b4 | LV_PERIOD=1 TC_GAP=0 AN_NETB=4e6 | 0.661 | -0.004 [-0.026,+0.017] | 6.64M | 5.71M | 2.73M | -0.312 | 0.459/0.844/0.735 |
| p10b2 | AN_NETB=2e6 (LV_PERIOD 10 kept) | 0.648 | -0.017 [-0.038,+0.004] | 5.33M | 4.23M | 2.51M | -0.142 | 0.456/0.833/0.704 |
| mc12 | MAX_CLONES=12 MAX_OBS=14 | 0.674 | +0.009 [-0.021,+0.037] | 5.45M | 4.90M | 3.30M | -0.242 | 0.520/0.774/0.781 |
| ce5 | CLONE_EVERY=5 | 0.668 | +0.003 [-0.023,+0.032] | 3.76M | 2.91M | 2.02M | -0.008 | 0.516/0.821/0.705 |
| ps2 | LV_PSCALE=2.0 | 0.657 | -0.008 [-0.027,+0.008] | 3.75M | 2.82M | 2.10M | +0.031 | 0.463/0.842/0.715 |
| md80 | MAX_DEPTH=80 | 0.675 | +0.009 [-0.009,+0.027] | 3.74M | 2.82M | 2.11M | -0.026 | 0.467/0.854/0.761 |
| mc8_r1 | mc8 + PIXEL_STD=1.515 DETECT_MIN_SCORE=1010 | 0.641 | -0.025 [-0.045,-0.005] | 3.87M | 3.35M | 2.49M | +0.068 | 0.483/0.788/0.692 |
| mc8_r2 | mc8 + PIXEL_STD=1.485 DETECT_MIN_SCORE=990 | 0.655 | -0.011 [-0.032,+0.012] | 3.80M | 3.35M | 2.49M | +0.031 | 0.477/0.804/0.734 |
| **MC8 3-rep** (edd8166b, d4d7b1f0, 5f03695a) | MAX_CLONES=8 MAX_OBS=10 | 0.643 | -0.023 [-0.039,-0.006] | 3.87M | 3.35M | 2.49M | +0.061 | 0.475/0.789/0.711 |
| mc8 v1val (120) | | 0.561 (ref 0.556) | +0.006 [-0.028,+0.040] | 3.78M | 3.32M | | -0.023 | ro/wa/fo 0.352/0.817/0.715 (ref 0.337/0.847/0.696) |
### Small net (SN A2_kd, base_sn.c), s60 instrumentation
| sndbg (Z + SN=1 NS_GCOST=1) | 95.8 landings/flight = every 12.5 frames, latency 8.7 | s60 ATE 0.624 (ref 0.636) | peak 3.40M |
| sndbg_p1b1 (+LV_PERIOD=1 TC_GAP=0 AN_NETB=1e6) | 180.6 = every 6.7 frames, latency 5.4 | 0.637 | 3.96M |
| snz (v3val) | Z + SN=1 NS_GCOST=1 (A2_kd small net, GOV_B 3.6e6) | 0.657 | d -0.008 [-0.032,+0.016] | peak 3.36M p95 2.68M mean 1.85M | area +0.092 | 0.448/0.872/0.701 |
| snz_p1b1 (v3val) | + LV_PERIOD=1 TC_GAP=0 AN_NETB=1e6 | 0.675 | d +0.009 [-0.019,+0.038] | 3.96M / 3.27M / 1.96M | -0.060 | 0.425/0.913/0.749 |
=> Even with the cheap net, anchoring every ~7 frames instead of ~12 does NOT help (warehouse worse).
| snz_mc8 | SN=1 NS_GCOST=1 MAX_CLONES=8 MAX_OBS=10 | 0.642 | -0.023 [-0.048,+0.001] | 3.67M | 3.34M | 2.24M | +0.093 | 0.457/0.783/0.743 |
| mc7 | MAX_CLONES=7 | 0.645 | -0.021 [-0.041,+0.001] | 3.79M | 3.12M | 2.29M | +0.067 | 0.478/0.781/0.723 |
| mc9 | MAX_CLONES=9 MAX_OBS=10 | 0.635 | -0.030 [-0.051,-0.007] | 4.17M | 3.70M | 2.66M | +0.044 | 0.454/0.794/0.708 |
| mc8ce5 | MAX_CLONES=8 MAX_OBS=10 CLONE_EVERY=5 | 0.638 | -0.028 [-0.051,-0.002] | 3.87M | 3.26M | 2.33M | +0.078 | 0.538/0.733/0.667 (rooms +0.06, wa -0.11, fo -0.06) |
| e1on30m10 | EDGE=1 EDGE_ON_LIVE=30 EDGE_MYTH=10 | 0.693 | +0.028 [-0.009,+0.074] | 3.76M | 2.75M | 2.15M | -0.089 | 0.568/0.824/0.717 (lines still cost rooms 0.09) |
=> Direction 3 closed: line/Manhattan features help warehouse only ~0.01-0.02 (noise level, consistent with the 0.6 deg median yaw
   error) and cost rooms ~0.09 even when gated by live-track count.
- NEW SWITCH AN_ACE (base.c): adaptive clone spacing. EMA (AN_DA 0.1 per clone) of mean log triangulated depth (last observation);
  CLONE_EVERY while exp(EMA) <= AN_DTH m, else AN_CEF. Motivated by mc8ce5 (longer clone spacing helps wa/fo, hurts rooms). Default
  off -> 670bc1da unchanged (VERIFIED). State reset at (re)initialisation.
- acedbg (s60): per-flight median EMA depth: rooms 1.1-3.1 m, warehouse 5.0-11.3 m, forest 5.8-12.9 m -> clean split, AN_DTH=4.0.
| ps15 | LV_PSCALE=1.5 | 0.676 | +0.011 [-0.008,+0.030] | 3.76M | 2.82M | 2.10M | -0.033 | 0.488/0.841/0.750 |
| ps5 | LV_PSCALE=5.0 | 0.681 | +0.015 [-0.004,+0.035] | 3.74M | 2.82M | 2.10M | -0.045 | 0.517/0.846/0.717 |
| **ace5** | MAX_CLONES=8 MAX_OBS=10 AN_ACE=1 AN_DTH=4 AN_CEF=5 | 0.615 | -0.050 [-0.071,-0.028] | 3.83M | 3.29M | 2.39M | +0.162 | 0.470/0.729/0.691 |
| **ace6** | ... AN_CEF=6 | 0.609 | -0.056 [-0.076,-0.034] | 3.83M | 3.23M | 2.30M | +0.183 | 0.472/0.701/0.701 |
| **snace5** | SN=1 NS_GCOST=1 + ace5 (base_sn.c) | 0.613 | -0.052 [-0.078,-0.029] | 3.67M | 3.20M | 2.07M | +0.195 | 0.454/0.727/0.709 |
| ace8 | MAX_CLONES=8 MAX_OBS=10 ACE DTH4 CEF=8 | 0.613 | -0.053 [-0.075,-0.032] | 3.85M | 3.21M | 2.18M | +0.168 | 0.471/0.702/0.713 |
| ace7 | ... CEF=7 | 0.615 | -0.051 [-0.075,-0.026] | 3.84M | 3.21M | 2.23M | +0.164 | 0.471/0.695/0.730 |
| ace6mc6 | MAX_CLONES=6 + ACE DTH4 CEF6 | 0.628 | -0.037 [-0.058,-0.016] | 3.70M | 2.93M | 2.01M | +0.136 | 0.485/0.778/0.656 |
| ace6mc10 | MAX_CLONES=10 MAX_OBS=12 + ACE CEF6 | 0.610 | -0.056 [-0.080,-0.033] | 4.46M | 3.73M | 2.58M | +0.096 | 0.480/0.684/0.710 |
| **snace6** | SN=1 NS_GCOST=1 + MAX_CLONES=8 MAX_OBS=10 ACE DTH4 CEF6 | 0.608 | -0.058 [-0.083,-0.034] | 3.67M | 3.11M | 1.93M | +0.215 | 0.452/0.708/0.715 |
| p1b2s15 | LV_PERIOD=1 TC_GAP=0 AN_NETB=2e6 LV_PSCALE=1.5 | 0.722 | +0.057 [+0.023,+0.092] | 5.32M | 4.25M | 2.56M | -0.379 | 0.458/0.986/0.787 (tighter anchors at high rate: bad, warehouse) |
### AUTOPILOT (autopilot.py, setsid; resumable): stage A screens (snace6 at GOV_B 3.3/3.0/2.7e6, DTH 3/6, MAX_CLONES 7, +EDGE MYTH10 combos,
### +p1b2, +ps2) -> stage B 3 reps + v1val for snace6, ace6 and up to 3 stage-A runs with d<-0.02 and area>+0.215. Lines -> results.tsv.
| p1b2s5 | p1b2 + LV_PSCALE=5 | 0.691 | +0.026 [+0.006,+0.048] | 5.34M | | | -0.284 | 0.511/0.878/0.726 |
| p1b2s1 | p1b2 + LV_PSCALE=1 | 0.849 | +0.184 [+0.136,+0.234] | 5.35M | | | -0.739 | 0.490/1.258/0.873 |
| snz_mc8g33 | SN + MAX_CLONES=8 GOV_B=3.3e6 | 0.657 | -0.009 [-0.036,+0.017] | 3.43M | 3.00M | 2.14M | +0.083 | 0.458/0.827/0.741 |
- AUTO stage A (screens) done, lines in results.tsv
- AUTO 3rep snace6: snace6+snace6_r1+snace6_r2 n358 raw 0.610 (ref 0.665) d -0.056 [-0.078,-0.035] peak 3.71M p95 3.11M mean 1.93M area +0.202 | cls 0.452/0.722/0.705 (ref 0.476/0.841/0.728) >3m 0
- AUTO v1val snace6: snace6                 n120 raw 0.514 (ref 0.556) d -0.042 [-0.081,-0.003] peak 3.60M p95 3.10M mean 1.86M area +0.199 | cls 0.363/0.672/0.648 (ref 0.337/0.847/0.696) >3m 0
- AUTO 3rep ace6: ace6+ace6_r1+ace6_r2   n358 raw 0.617 (ref 0.665) d -0.048 [-0.066,-0.031] peak 3.87M p95 3.23M mean 2.30M area +0.152 | cls 0.481/0.715/0.698 (ref 0.476/0.841/0.728) >3m 0
- AUTO v1val ace6: ace6                   n120 raw 0.555 (ref 0.556) d -0.001 [-0.038,+0.035] peak 3.80M p95 3.21M mean 2.25M area -0.001 | cls 0.364/0.762/0.717 (ref 0.337/0.847/0.696) >3m 0
- AUTO 3rep snace6g27: snace6g27+snace6g27_r1+snace6g27_r2 n358 raw 0.628 (ref 0.665) d -0.037 [-0.059,-0.018] peak 3.02M p95 2.44M mean 1.78M area +0.255 | cls 0.467/0.751/0.713 (ref 0.476/0.841/0.728) >3m 0
- AUTO v1val snace6g27: snace6g27              n120 raw 0.561 (ref 0.556) d +0.006 [-0.038,+0.049] peak 2.91M p95 2.40M mean 1.72M area +0.127 | cls 0.389/0.752/0.707 (ref 0.337/0.847/0.696) >3m 0
- AUTO 3rep snace6e1: snace6e1+snace6e1_r1+snace6e1_r2 n358 raw 0.562 (ref 0.665) d -0.104 [-0.133,-0.073] peak 4.26M p95 3.06M mean 2.18M area +0.303 | cls 0.467/0.594/0.663 (ref 0.476/0.841/0.728) >3m 1
- AUTO v1val snace6e1: snace6e1               n120 raw 0.495 (ref 0.556) d -0.061 [-0.112,-0.008] peak 4.10M p95 3.03M mean 2.14M area +0.205 | cls 0.338/0.591/0.698 (ref 0.337/0.847/0.696) >3m 0
- AUTO 3rep snace6g30: snace6g30+snace6g30_r1+snace6g30_r2 n358 raw 0.623 (ref 0.665) d -0.042 [-0.062,-0.023] peak 3.20M p95 2.64M mean 1.84M area +0.240 | cls 0.463/0.750/0.703 (ref 0.476/0.841/0.728) >3m 0
- AUTO v1val snace6g30: snace6g30              n120 raw 0.563 (ref 0.556) d +0.007 [-0.036,+0.049] peak 3.15M p95 2.60M mean 1.77M area +0.076 | cls 0.386/0.762/0.709 (ref 0.337/0.847/0.696) >3m 0
