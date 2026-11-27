# smallnet agent NOTES (cheaper learned velocity net for GSLV; GPU 5 only; <= 14 eval workers; v3 TEST never used; no git/uploads)

## SUMMARY
- WHAT: a family of small learned-velocity nets with a NEW cheap input pipeline ("lo": box-pool the gray to the net resolution first,
  derotate/normalise there) + generated int16 wasm-SIMD C (q16) -> the net costs 0.55-2.4 M fuel per run instead of 8.7 M
  (ref-size S_lo_kd1: 2.4 M at the SAME direct error 0.321 vs 0.327; A2_kd 8,16,24,32: 1.23 M at 0.350; A_lo_kd1: 1.25 M at 0.379).
- WHERE FUEL GOES: at GOV_B 3.6 M the net is ~11% of mean frame fuel (0.24 M) but ~0 of PEAK (governor gives the net only leftover
  budget). Net off at 3.6M: peak 4.69 vs 4.80. => a cheap net does not lower peak by itself; it lets the budget (GOV_B) go down while the
  net still lands fast (startup landing frame 6-7 vs 19-23 at GOV_B 1.8 M) and re-anchors more often. At 1.8 M the net is worth
  -0.58 m (off 1.855 vs on 1.277) and net speed another -0.18 (free units 1.100).
- BEST AREA POINTS (v3val 358; area vs auto_727_sp10 @ 4.80M/0.906/sw 0.845, 0.28*log2(P0/P) - 2.2*ln(A/A0)):
  | point | build | peak | raw | sw | area raw / sw |
  | ~3 M | SN A2_kd, EDGE=0 GOV_B=2.8e6, 3 reps | 2.99M | 0.935 | 0.858 | +0.12 / +0.16 |
  | ~3.2 M | SN E_lo, EDGE=0 GOV_B=3.0e6, 3 reps | 3.22M | 0.924 | 0.854 | +0.12 / +0.14 |
  | ~2.6 M | SN A_lo_kd1, EDGE=0 GOV_B=2.4e6 (1 run) | 2.62M | 1.017 | 0.933 | -0.01 / +0.03 |
  | ~2 M | SN A_lo_kd1, EDGE=0 GOV_B=1.8e6 (1 run) | 1.99M | 1.152 | 1.053 | -0.17 / -0.13 |
  | ~1 M | not reachable inside GSLV (vision alone ~1.3 M mean at 1.8M; ref e0b12 = 2.6 m): use the cheap agent's EKF + C32/C32c nets |
  The ~3 M point is the optimum: same-budget comparison with 3 reps each, A2 @2.8M vs ref net @2.8M: d raw -0.035 [-0.067,-0.002],
  d sw -0.037 [-0.071,-0.002] (SIGNIFICANT), peak 2.99 vs 3.08 M; E @3.0M vs ref net @3.0M: d -0.019 [-0.052,+0.014] (n.s.).
  vs the 3.6M reference: A2 @2.8M x3 d raw +0.029 [-0.026,+0.089], sw +0.013 [-0.043,+0.067] at 38% lower peak.
  v1val 120: ref 3.6M 0.653 | ref net @3.0M 0.712 | SN E @3.0M 0.670 | SN A2 @2.8M 0.698 (+0.045 [-0.007,+0.097] vs 3.6M ref).
  At 3.6 M itself SN S_lo_kd1 gives 0.877 / sw 0.800 (-0.029 [-0.076,+0.020], 1 run) at unchanged peak.
- BUILDS TO USE (all: src/v2_727.c base + mkgsn.py splice; flags F = PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0):
  * 3 M: builds/s3_A2_e0b28/solution.wasm sha 83cffddf59a78eb4a98d8fa4d2c72af421d17877a8815cec40a822f9d59b7263
    = src/g_A2_kd.c with F SN=1 EDGE=0 GOV_B=2.8e6 NS_GCOST=1 ; weights runs/A2_kd/best.pt (8,16,24,32, lo, 64x48, hid 128, kd Y80, 120 ep).
  * 3.2 M: builds/s2_E_e0b30/solution.wasm sha 18b3e17c14f0c0dc9c8bafa79acc31f256572ed2f067a4dfde2abf757b859044
    = src/g_E_lo.c with F SN=1 EDGE=0 GOV_B=3.0e6 NS_GCOST=1 ; weights runs/E_lo/best.pt (12,16,24,32).
  * 2 M: builds/s1_A_e0b18 sha 40bac8d2559800adfa1dd3e3ed124b48b008a656dda23296da1a70698fab6ca1 = src/g_A_lo_kd1.c F SN=1 EDGE=0
    GOV_B=1.8e6 SN_GCG=200e3 (rebuild verified identical).
  Without -DSN the generated sources build byte-identical to the base (9a468ce9 with F). EDGE=0 is required below ~3.2 M (sweep: EDGE=1
  at GOV_B 2.4/3.0 M diverges on warehouse).
- For the cheap agent (goats EKF, net.h API): cheap_export/net_*.c (mkcheap.py; standalone, compiles against cheap/src/net.h). Try
  net_C32c_kd.c (24,32,48 @32x24, direct 0.362, 0.83 M steps + 2 x 0.13 M grays) and net_C_lo32_kd1.c (8,16,24 @32x24, 0.440,
  0.29 M + 2 x 0.13 M) for the 1 M tier; net_A2_kd.c (0.350, 1.01 M + 2 x 0.21 M) if the budget allows. Interface differences: the
  low-res gray is computed inside net_begin / net_feed (no RGB stash, ~0.13-0.21 M in those calls), net_cost(k) = snbench fuel per step.
- Did not help: distillation (Y80 teacher) only -0.005..-0.010 direct; hidden 32 (+0.045 direct); coordinate channels are free in C
  (folded into a conv0 bias map); flat GC_UNIT charging of SN steps (peak overshoot; fixed with NS_GCOST=1 + per-step cost table).

## Setup / tools (agents/smallnet/tools)
- lv5.py: trains SEVERAL small nets in lockstep on the same batches (one data load; netv2 lv4.py data/sampling/time-reversal/report
  reused by import). Config per net: chs (any depth), pre=ref|lo, res=64|32, cin=5|3|2, hid, fvd, gp, kd (distillation from a lv4
  teacher, e.g. netv2:Y80), lr. Data = netv2 lists/train727.txt + old share 0.3, val = netv2 lists/val749.txt (direct head-K error).
  pre=lo = NEW cheap preprocessing: the gray frames are box-pooled to the net resolution FIRST (64x48: 5x5 box of the 320x240 RGB mean;
  32x24: 10x10), derotated + normalised at that resolution (no 128x96 gray, no 2x2 pool). In training = avg_pool of the 128x96 cache.
- mksn.py: C generator for a trained lv5 net (pre=lo): BN-folded weights + specialised unrolled wasm-SIMD code, micro-step schedule
  sn_step(k). q16=1 (default for GSLV): convs in int16 (i32x4.dot_i16x8_s, 8 MAC/op), per-out-channel weight scales, per-layer
  activation scales calibrated on 24 val flights; the constant u/v coordinate channels folded into a per-pixel conv0 bias map (conv0
  reads x0, x1w, mask only). Only the head-K outputs (lc_out[6..11]) are computed.
- sntest.py RUN: C (wasi-sdk, wasmtime) vs torch on synthetic inputs -> float path max |d mu| 6e-8 (exact), q16 path 2-5e-5. VERIFIED.
- snbench.py RUN [--q16 1]: wasmtime fuel per component of the generated block.
- mkgsn.py RUN OUT.c: splices the SN block into src/v2_727.c (= netv2 gslv_v2.c + auto_727 weights) behind -DSN=1 (default 0):
  frame-0 / frame-K stash = low-res gray directly (instead of the 230 KB RGB memcpy), SN_STEPS micro-steps in place of the 97 NS steps.
  v2_727.c + F flags == 9a468ce9 (net_auto_727_sp10) VERIFIED; mkgsn output without SN == 9a468ce9 VERIFIED.
- mkcheap.py RUN OUT_net.c: standalone net.c implementing agents/cheap's net.h API from an lv5 run (see "For the cheap agent").
- build.py (netv2 toolchain, out -> smallnet/builds), qd.sh / ev.sh (queue, 14 workers, load wait), fuelstats.py (per-frame fuel
  stats from viobench reports), prof.py (netv2 NSPROF profiler, works on SN builds too).
- F = PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0. Reference = net_auto_727_sp10 (9a468ce9) = sw_b7_ref = sn_c_ref (bit-identical evals).

## Log
### 1. Where the fuel goes (v3val 358, reports' per-frame fuel)
| build | max | mean flight-max | mean p99 | mean p95 | mean frame |
| net_auto_727_sp10 (GOV_B 3.6M) | 4.80 | 3.76 | 3.36 | 2.98 | 2.23 |
| lcoff_sp10 (net fully off) | 4.69 | 3.71 | 3.16 | 2.74 | 1.97 |
| sw_g_e0b18 (EDGE=0 GOV_B 1.8M) | 2.08 | 1.91 | 1.78 | 1.64 | 1.34 |
| c_e0b18_off (same, net off) | 1.96 | 1.84 | 1.72 | 1.59 | 1.25 |
- The net costs ~0.24 M/frame on AVERAGE (11%) and ~0.2-0.25 M of p95/p99, but ~0 of PEAK: the governor runs net micro-steps only
  in the budget left after vision (NS_RESERVE 0), so peak = vision + overshoot. => a cheaper net cannot lower peak at GOV_B 3.6M;
  it can (a) land sooner / re-anchor more often (latency), (b) keep working when GOV_B is lowered.
- Measured ref net per run: gray 1.45 M + prep/var/pool 1.99 M + convs 4.26 M + head 0.46 M = 8.2 M (+0.47 M RGB stashes).
- Value of the net at low budget (EDGE=0, GOV_B 1.8M, v3val 358): net off 1.855 | ref net 1.277 | ref net with free/fast units
  (GOV_FREE_NET: 12 uncharged units/frame, peak 3.72M) 1.100 (d=-0.177 [-0.277,-0.093] vs 1.277). => at low budgets the net is
  essential AND its latency/throughput is first-order: room for a cheap net.

### 2. SN C cost (snbench, wasmtime fuel; q16)
| net | gray (x2 per run) | prep | norm | convs | head | steps total | total per run incl. 2 grays |
| A 8,12,16,24 @64x48 cin5 hid128 | 213k | 193k | 50k | 469k | 108k | 0.82M | 1.25M |
| 8,16 @32x24 cin3 gp hid32 | 130k | 49k | 10k | 79k | 20k | 0.16M | 0.42M |
| (ref NS net, prof) | 0.72M+0.235 stash | 1.99M | - | 4.26M | 0.46M | - | 8.7M |

### 3. Direct error (val749 head-K, 80 ep scratch lr 4e-3, train727 + old 0.3; kd = distilled from netv2 Y80, weight 1)
| run | chs | pre | res | cin | hid | MAC | direct all | fast | f/s/b |
| S_lo_kd1 | 16,24,32,48 | lo | 64 | 5 | 128 | 1.79M | 0.321 | 0.410 | 0.319/0.380/0.342 |
| S_lo | 16,24,32,48 | lo | 64 | 5 | 128 | 1.79M | 0.326 | 0.413 | (netv2 S80, ref pre: 0.327) |
| E_lo | 12,16,24,32 | lo | 64 | 5 | 128 | 1.05M | 0.354 | 0.447 | 0.351/0.415/0.381 |
| A (ref pre) | 8,12,16,24 | ref | 64 | 5 | 128 | 0.61M | 0.374 | 0.471 | |
| A_lo_c3 | 8,12,16,24 | lo | 64 | 3 | 128 | 0.50M | 0.375 | 0.472 | |
| A_lo_kd1 | 8,12,16,24 | lo | 64 | 5 | 128 | 0.61M | 0.379 | 0.485 | 0.374/0.449/0.406 |
| A_lo | 8,12,16,24 | lo | 64 | 5 | 128 | 0.61M | 0.382 | 0.484 | |
| A_lo_kd3 | (kd 3) | | | | | | 0.382 | | |
| B_lo_kd1 | 8,8,16,16 | lo | 64 | 5 | 128 | 0.50M | 0.398 | 0.504 | (B_lo 0.407) |
| C_lo32b | 16,24,32 | lo | 32 | 5 | 128 | 0.44M | 0.398 | 0.497 | |
| A_lo_h32 | 8,12,16,24 hid 32 | lo | 64 | 5 | 32 | 0.58M | 0.424 | 0.534 | |
| C_lo32_kd1 | 8,16,24 | lo | 32 | 5 | 128 | 0.21M | 0.440 | 0.559 | (C_lo32 0.445) |
| D_lo32 | 8,12,16 | lo | 32 | 3 | 64 | 0.12M | 0.486 | 0.604 | |
=> pre=lo costs ~0 in accuracy at the ref size (0.326 vs 0.327) and ~+0.008 at A size; distillation from Y80 gives only -0.005..-0.010;
   dropping the coordinate channels is free (A_lo_c3); hidden 32 hurts (+0.045); width is what matters (S 0.32 > E 0.35 > A 0.38 > B/C32b 0.40 > C32 0.44).
- C cost per run (q16, snbench; + 2 grays 213k at 64x48 / 130k at 32x24): S 1.96+0.43 = 2.39M | E 1.33+0.43 = 1.76M | A 0.82+0.43 = 1.25M |
  B 0.68+0.43 = 1.11M | C32b 0.54+0.26 = 0.80M | C32 0.29+0.26 = 0.55M  (ref NS net 8.7M). q16 vs torch float: max |d mu| 0.006-0.012 m/s.

### 4. In-filter (v3val 358, F flags, paired vs the same-budget ref-net build; 1 run)
| build | budget | raw | sw | >3m | peak | mean frame | d raw vs ref [CI] |
| ref net (sw_b7_ref) | 3.6M | 0.906 | 0.845 | 9 | 4.80M | 2.23 | - |
| SN S_lo_kd1 (s1_S_f36) | 3.6M | 0.877 | 0.800 | 6 | 4.88M | 2.13 | -0.029 [-0.076,+0.020] |
| ref net (sw_g_e0b18) | EDGE=0 1.8M | 1.277 | 1.175 | 21 | 2.08M | 1.34 | - |
| ref net, free units (c_e0b18_free) | 1.8M+net | 1.100 | 1.029 | 9 | 3.72M | 1.94 | -0.177 [-0.277,-0.093] |
| SN A_lo_kd1 @ epoch 6 (t6_e0b18) | 1.8M | 1.246 | 1.138 | 21 | 2.04M | 1.29 | -0.032 [-0.140,+0.062] |
| SN S_lo_kd1 (s1_S_e0b18) | 1.8M | 1.181 | 1.068 | 16 | 2.32M (!) | 1.32 | -0.097 [-0.199,-0.006] |
| ref net (sw_g_e0b24) | EDGE=0 2.4M | 1.068 | 0.987 | 11 | 2.71M | 1.64 | - |
| net off (c_e0b24_off) | 2.4M | 1.713 | 1.654 | 56 | 2.49M | 1.48 | +0.645 |
| ref net free units (c_e0b24_free) | 2.4M+net | 0.991 | 0.917 | 6 | 4.28M | 2.17 | -0.077 [-0.132,-0.023] |
- Profile (6 flights x 400 frames, EDGE=0 GOV_B 1.8M): SN A lands the startup net at frame 6-7 (ref net: frame 19-23) and completes 16 net
  runs vs 7.
- s1_S_e0b18 peak 2.32M > 2.08M: SN steps were charged a flat GC_UNIT 160k but S conv steps cost up to 238k -> overshoot. FIX: mkgsn now
  embeds the snbench per-step costs (sn_costtab) as ns_cost(k) (use with -DNS_GCOST=1, x1.1 margin) and SN_GCG = gray cost x 1.1.
- (cont.) all SN runs below: mkgsn per-step cost table + -DNS_GCOST=1 (charges measured step cost x1.1) -> peak back at budget + ~0.1-0.2M.
| SN S_lo_kd1 (s2_S_e0b18) | EDGE=0 1.8M | 1.243 | 1.117 | 22 | 2.08M | 1.31 | -0.034 [-0.104,+0.032] |
| SN A_lo_kd1 (s1_A_e0b18, flat GC_UNIT) | 1.8M | 1.152 | 1.053 | 14 | 1.99M | 1.29 | -0.125 [-0.233,-0.028] |
| SN S_lo_kd1 (s2_S_e0b24) | 2.4M | 1.045 | 0.953 | 8 | 2.64M | 1.57 | -0.023 vs e0b24 ref |
| SN E_lo (s2_E_e0b24) | 2.4M | 1.048 | 0.953 | 15 | 2.67M | 1.55 | |
| SN E_lo (s2_E_e0b26) | 2.6M | 0.990 | 0.902 | 9 | 2.83M | 1.63 | |
| ref net (sw_g_e0b30) | EDGE=0 3.0M | 0.944 | 0.876 | 7 | 3.24M | 1.95 | - |
| SN S_lo_kd1 (s2_S_e0b30) | 3.0M | 0.935 | 0.864 | 6 | 3.17M | 1.82 | -0.008 |
| SN A_lo_kd1 (s2_A_e0b30) | 3.0M | 0.933 | 0.869 | 5 | 3.12M | 1.78 | -0.011 |
| SN E_lo (s2_E_e0b30) | 3.0M | 0.910 | 0.837 | 6 | 3.17M | 1.80 | -0.034 [-0.074,+0.005] |
| SN A2_kd (s3_A2_e0b30) | 3.0M | 0.931 | 0.850 | 7 | 3.13M | 1.78 | |
| SN S_kd120 (s3_S120_e0b30) | 3.0M | 0.927 | 0.862 | 6 | 3.20M | 1.82 | |
| SN A2_kd (s3_A2_e0b28) | 2.8M | 0.924 | 0.849 | 7 | 2.99M | 1.71 | +0.018 vs 3.6M ref |
- 3 REPLICATES at 3.0M (repcmp.py, per-flight rep means): ref net e0b30 x3 0.943 / sw 0.869 / 3.24M; SN E_lo e0b30 x3 0.924 / sw 0.854 / 3.22M:
  d raw -0.019 [-0.052,+0.014], d sw -0.014 [-0.050,+0.021] (n.s.). vs the 3.6M reference (sw_b7_ref, 0.906 / 0.845 / 4.80M):
  E e0b30 x3 d raw +0.018 [-0.026,+0.063], d sw +0.009 [-0.037,+0.056] at 33% lower peak => area ~ +0.16 - 0.02 = +0.14.
- v1val 120: auto_727_sp10 (3.6M) 0.653 | ref net e0b30 0.712 | SN E_lo e0b30 0.670 (the small fast net recovers most of the v1val loss of the 3.0M budget).
- b3 (120 ep, kd Y80): E_kd 0.3505 | A2_kd (8,16,24,32; 0.80M MAC) 0.3502 | S_kd120 0.3175 | C32c_kd (24,32,48 @32x24) 0.362 | C32b_kd 0.388 | C32b_h64 0.410.

### 5. Final in-filter points (v3val 358; 1 run unless x3)
| build | budget | peak | raw | sw | >3m | note |
| SN A_lo_kd1 e0b24 | 2.4M | 2.62M | 1.017 | 0.933 | 9 | d -0.050 [-0.094,-0.005] vs ref net e0b24 |
| SN C32c_kd e0b24 | 2.4M | 2.62M | 1.033 | 0.943 | 8 | d -0.034 [-0.077,+0.009] |
| SN A2_kd e0b26 | 2.6M | 2.81M | 0.991 | 0.908 | 14 | |
| SN A2_kd e0b28 x3 | 2.8M | 2.99M | 0.935 | 0.858 | 5 | vs ref net e0b28 x3 (0.969 / 0.895 / 3.08M): d -0.035 [-0.067,-0.002] |
| SN E_lo e0b18 | 1.8M | 2.09M | 1.163 | 1.053 | 15 | d -0.114 [-0.194,-0.038] vs ref net e0b18 |
| SN C_lo32_kd1 e0b18 | 1.8M | 2.02M | 1.213 | 1.104 | 13 | d -0.064 |
