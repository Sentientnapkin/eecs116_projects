# cheap agent NOTES (low-fuel solution: the goats EKF + our components; CPU only, <= 14 eval workers, v3 TEST never used, no git / uploads)

## SUMMARY (final)
**No build recommended. Both tracks are killed: the goats filter, with our net (A), our non-net components (B), or both, stays at
~3.3-3.6 m on v3val (358) against 0.906 m for net_auto_727_sp10. That is about -2 points of estimated area even after the fuel credit.**
- Their filter alone (cg_goats, builds/goats0 = their unmodified code): v3val raw 3.551 / sw 3.087 (rooms 0.682, warehouse 5.12, forest 5.89),
  v1val 3.802; peak 0.42 M, p95 0.37 M. Est. -1.93 pts vs the best build.
- Track B (each component alone on goats, v3val 358 paired; d vs goats [95% CI]): speed+vertical+lateral priors -0.015 [-0.22,+0.18];
  moving-start detection + startup tilt + hover hold -0.060 [-0.30,+0.17]; vision ZUPT +0.024; gyro-bias clamp + thrust 0.05 -0.003;
  Manhattan lines (vertical VP tilt + Manhattan yaw) -0.110 [-0.34,+0.13]; ALL (bAll) -0.119 [-0.36,+0.11] v3val, -0.693 [-1.03,-0.39]
  v1val (significant: rooms 0.67 -> 0.49, warehouse 5.6 -> 4.4, forest 7.9 -> 6.8), peak 0.62 M, p95 0.51 M.
- Track A (our net as a delayed velocity measurement on a velocity clone; per-frame net budget NET_FB):
  FB 0.3 M: 3.618 @ 0.92 M peak | FB 0.6 M: 3.559 @ 1.24 M | FB 1.0 M: 3.562 @ 1.54 M (all n.s. vs goats; v1val FB 0.6: -0.56 [-0.97,-0.19]).
  Net size at FB 0.6 M: X80 (32,48,64,96, netv2) 3.499 @ 1.23 M | auto_727 (ref) 3.559 @ 1.24 M | smallnet S_lo (ref shape, lo-prep)
  3.433 @ 1.48 M | smallnet A_lo (8,12,16,24) 3.870 @ 1.21 M (+0.32 worse) | smallnet C_lo32b (16,24,32 @32x24) 4.104 @ 0.97 M (+0.55 worse).
- Combination (all B + ref net FB 0.6 M, cAll6): v3val 3.340 / sw 2.922, d -0.211 [-0.444,+0.015]; v1val 3.093, d -0.709 [-1.13,-0.32];
  peak 1.42 M, p95 1.21 M. Best ATE of this agent, but est. -2.30 pts vs the best build (break-even at 1.4 M would need <= ~1.1 m local).
- WHY it cannot work (ORACLE test, below): with PERFECT (ground-truth) velocity every 6 frames, their filter still scores 4.25 / 1.97 / 2.64 / 1.18 m
  on 4 hard forest/warehouse flights where GSLV scores 1.17 / 1.00 / 0.80 / 0.72. In open scenes their filter updates 0-6 features per frame
  (24 slots, depth prior 0.5), attitude error grows to 3-6 deg (GSLV 1-2), and the feature updates pull the velocity off right after
  each correction. The limit is the visual front end and heading, not the velocity, so no net (bigger or smaller) can bring it near 1 m.
- final/: trackB_bAll.wasm (sha 79045d66..., flags HYB=1) and combo_cAll6.wasm (sha c16b3d18..., flags HYB=1 HYB_NET=1 VIO_NC=20
  NET_PSCALE=1.0 NET_PFVMIN=0.3 NET_FB=600e3) are kept for reference only. They are NOT recommended, and they CONTAIN THE GOATS TEAM'S CODE.
- Tier1m fuel tricks were not ported. Their filter is already fuel-lean (byte-shuffle pyramid, f32 SIMD covariance, work budget;
  0.42 M peak), and fuel is not what limits it.
- Full tables: logs/rep_v3val.txt, logs/rep_v1val.txt; flags: logs/flags.txt.

## CREDIT / LICENSING (read first)
Every build in builds/ except none contains the OTHER TEAM's ("goats") stage-2 filter: src/vio.cpp, src/vio.h, src/solution.cpp,
src/parameters.h are copies of /data/backups/rganapa/Sebastian/tmp/goats/submission_stage2/ (their code), MODIFIED by us:
- vio.h: NC configurable (VIO_NC, 20 = + velocity clone), feature fields mframe/pframe/ppx/ppy, hybrid members + methods;
- vio.cpp: hooks (#if HYB) in step(), clone in inject()/inflate_scale()/restart(), px bookkeeping, #include "hyb.inc";
- solution.cpp: static Vio storage instead of operator new (=> 0 wasm imports), net glue (#if HYB_NET).
Our own code: src/hyb.inc (ported GSLV priors / ZUPT / hover hold / bias clamp / Manhattan line constraints / velocity clone),
src/net.c (generated, our learned velocity net), tools/. Any submission from here must credit the goats team.
builds/goats0 = their unmodified code (sha 781affb8 = initializer's builds/goats, reproduced).

## Net interface (for the small-net agent) -- tools/mknet.py
`python tools/mknet.py src/net.c (--gslv SOLUTION_C | --run RUNDIR | --npz FILE) [--sigscale s]` regenerates src/net.c; then rebuild.
- Architecture contract (= learned/train.py Net with nf=2, nvec=19): input 5 channels at PH x PW (PW = res, PH = 3/4 res):
  [frame s gray normalised, frame s+K gray gyro-derotated into frame s and normalised x mask, mask, u-coord, v-coord] (exactly GSLV's
  prep: gray = mean of RGB area-resampled from 320x240 to 2*res x 1.5*res, derotated at gray res, 2x2 pooled);
  NL = log2(res/4) conv layers 3x3 stride 2 pad 1 (+ folded BN) + ReLU, channels C0..C{NL-1} (any, multiples of 4);
  final map 3x4xC_last flattened in (h, w, c) order, concatenated with fv = ReLU(Linear(19 -> 32)) of the IMU vector;
  head Linear(12*C_last + 32 -> HID) + ReLU + Linear(HID -> 12). Output used: [6..8] = body (IMU-axes) velocity at frame s+K (m/s),
  [9..11] = per-axis log-variance (clamped to [-7, 4]). K = NET_K = 5 (20 Hz frames).
  IMU vector (19): mean specific force/9.81 and mean gyro of frame s's IMU rows, same for frame s+K's rows, integral of R a dt over
  s..s+K in frame-s axes / (0.05*K*9.81), rotation vector s->s+K, fx/100.
- --npz contract: float32 arrays LC_W{i} (3,3,ci,co) [BN folded], LC_B{i} (co), LC_FW0 (19,32), LC_FB0 (32), LC_H1W (12*C_last+32, HID)
  rows in (h,w,c) order then the 32 embedding rows, LC_H1B (HID), LC_H2W (HID,12), LC_H2B (12); optional scalar `res` (default 64).
  --run takes a netv2/lv4 run dir (best.pt + result.json args chs/hidden; res 64).
- C API: src/net.h (net_cam, net_begin, net_feed, net_tick, net_cost, net_out). The micro-step schedule is built from the shapes
  (conv chunks of NET_VB = 55296 MACs, head chunks of NET_HB = 40000 MACs); the caller runs steps while their estimated cost fits
  the per-frame budget NET_FB. Fast exact gray path for res 64 (gray 128x96), generic float area path otherwise.

## Log
- Setup: pools/v3val (358), pools/v1val (120) = symlinks to the existing zips of gen3/pools (the gen3 pool dirs still list deleted
  zips). Eval names prefixed cg_ (to not overwrite other agents' evals). tools/qd.sh = serial eval queue (14 workers, waits on load).
- cg_goats (their filter, unmodified, goats0): v3val 358 + v1val 120 -> see results table.
- Build tooling: tools/mk.sh NAME "DEFS" (= tools/build.py + import check), tools/dev.sh (12-flight dev pool pools/smoke), tools/rep.py
  (paired table + est. score), tools/fuel.py / tools/pk.py (fuel), tools/diag.py (pos / rot / vel error over time + stderr), tools/oracle.sh
  (TEST ONLY per-flight builds with ground-truth velocity in place of the net). Flags of every queued build: logs/flags.txt.
- 0 wasm imports: their solution.cpp used operator new (-> 4 WASI imports); replaced by static storage. All builds here have 0 imports.
- Net port verified: generic net.c (reference shape) gives the same output as GSLV's LV_NET on the same frames (first inference,
  fo-9010516: 1.442 0.124 0.320 both; wa-9300309: -1.426 0.102 0.273 both).
- Measured fuel: memcpy is memory.copy (bulk memory, 1 op) -> stashing the two RGB frames is ~free. Lines module (edgelets on level 1,
  grid step 6) cost ~+0.2 M/frame (first version, with trig in the yaw learning) -> step 8 and trig-free: ~+0.08 M (peak 0.48-0.50 M).

### Dev pool (12 flights: 6 v3val classes x start, 3 v1val; goats 3.247, GSLV best 0.872)
| build | flags | mean | peak |
| hyb_full (all B + net, watchdog on, PSCALE 3) | HYB=1 HYB_NET=1 VIO_NC=20 | 3.043 | 1.46 M |
| d1 (+ WD off, PSCALE 1.5, PFVMIN .3, scale infl .3 at every landing) | | 316 (diverges, 1000+ m) | 1.47 M |
| d2 (WD off) | | 7.32 (one 62 m) | 1.46 M |
| d3 (WD off, PSCALE 1, PFVMIN .3) | | 3.093 | 1.46 M |
| d4 (WD on, PSCALE 1, PFVMIN .3) | | 3.273 | 1.46 M |
| b0 (all hooks off) | | 3.247 (= goats, identical) | 0.42 M |
| b1 (all B, no net) | HYB=1 | 3.249 | 0.64 M |
| a1 (net only, defaults) | | 3.714 | 1.22 M |
Diagnosis (tools/diag.py, debug builds HB_DBG=1): in forest/warehouse their filter updates only 0-6 features per frame (n_updated); the first
net measurement corrects the velocity (fo-9010516: v err 1.55 -> 0.48 m/s at frame 20) but within 20 frames the feature updates pull it
back (1.15 at frame 40); the watchdog restarts (9 in 300 frames there) wipe the velocity clone so the startup net is often dropped; with the
watchdog off the starved filter runs away (5 m/s) and the periodic net (sd x3) cannot hold it.
### ORACLE upper bound (TEST ONLY: ground-truth body velocity instead of the net, 4 hard flights; GSLV best 1.17 / 1.00 / 0.80 / 0.72)
- o1: net cadence (~20 frames), sd 0.1, PFVMIN 0.3, WD off: 4.47 / 2.97 / 3.58 / 1.40
- o2: every 6 frames, no latency, sd 0.05, velocity floor 1.0 (oracle dominates): 4.25 / 1.97 / 2.64 / 1.18
  (fo-9300471: rotation error 3-6 deg vs GSLV 1-2 deg; velocity error still ~0.4 m/s between oracle fixes)
=> even PERFECT velocity at 3 Hz leaves their filter 1.6-3.6x worse than GSLV on hard open-scene flights: attitude/heading and
   feature-starved updates, not velocity, limit it. Track A (net into their filter) cannot reach the break-even line (~1.18 m local
   at ~1 M peak, ~1.09 at 1.5 M). KILLED as a submission path; the full evals below are run for the record.

### Full evals (v3val 358 / v1val 120, paired; est pts = +0.404 ln(4.1M/peak) - 2.2 ln(sw/sw_best))
pool v3val, flights in common 358
net_auto_727_sp10    raw 0.906 sw 0.845 med 0.716 >3m   9 | ro 0.489 wa 1.381 fo 0.934 | d_goats -2.645 [-3.011,-2.300] | peak 4.80M p95 3.02M | est pts vs best +0.00
cg_goats             raw 3.551 sw 3.087 med 2.092 >3m 160 | ro 0.682 wa 5.119 fo 5.888 | d_goats +0.000 [+0.000,+0.000] | peak 0.42M p95 0.37M | est pts vs best -1.93
cg_bP                raw 3.535 sw 3.033 med 2.118 >3m 162 | ro 0.610 wa 4.893 fo 6.223 | d_goats -0.015 [-0.219,+0.182] | peak 0.49M p95 0.42M | est pts vs best -1.95
cg_bD                raw 3.490 sw 3.050 med 1.957 >3m 148 | ro 0.643 wa 4.913 fo 5.979 | d_goats -0.060 [-0.300,+0.174] | peak 0.48M p95 0.37M | est pts vs best -1.96
cg_bZ                raw 3.575 sw 3.125 med 2.313 >3m 164 | ro 0.681 wa 5.416 fo 5.605 | d_goats +0.024 [-0.136,+0.190] | peak 0.44M p95 0.37M | est pts vs best -1.98
cg_bG                raw 3.547 sw 3.109 med 2.160 >3m 156 | ro 0.727 wa 5.076 fo 5.861 | d_goats -0.003 [-0.219,+0.208] | peak 0.43M p95 0.37M | est pts vs best -1.95
cg_bL                raw 3.441 sw 3.003 med 2.132 >3m 154 | ro 0.744 wa 4.709 fo 5.899 | d_goats -0.110 [-0.342,+0.125] | peak 0.54M p95 0.45M | est pts vs best -1.97
cg_bAll              raw 3.432 sw 3.029 med 2.353 >3m 158 | ro 0.621 wa 5.052 fo 5.619 | d_goats -0.119 [-0.358,+0.110] | peak 0.62M p95 0.51M | est pts vs best -2.05
cg_aN3               raw 3.618 sw 3.203 med 2.500 >3m 162 | ro 0.746 wa 4.893 fo 6.330 | d_goats +0.067 [-0.152,+0.285] | peak 0.92M p95 0.75M | est pts vs best -2.33
cg_aN6               raw 3.559 sw 3.097 med 2.818 >3m 173 | ro 0.824 wa 4.792 fo 6.120 | d_goats +0.009 [-0.229,+0.238] | peak 1.24M p95 1.14M | est pts vs best -2.37
cg_aN10              raw 3.562 sw 3.108 med 3.106 >3m 185 | ro 0.773 wa 5.011 fo 5.930 | d_goats +0.011 [-0.213,+0.236] | peak 1.54M p95 1.42M | est pts vs best -2.47
cg_aX6b              raw 3.499 sw 3.150 med 2.551 >3m 166 | ro 0.811 wa 4.756 fo 5.959 | d_goats -0.051 [-0.259,+0.152] | peak 1.23M p95 1.07M | est pts vs best -2.41
cg_aS6               raw 3.433 sw 2.987 med 2.764 >3m 171 | ro 0.803 wa 4.729 fo 5.754 | d_goats -0.118 [-0.342,+0.130] | peak 1.48M p95 1.38M | est pts vs best -2.37
cg_aA6               raw 3.870 sw 3.332 med 3.327 >3m 195 | ro 0.781 wa 5.522 fo 6.434 | d_goats +0.319 [+0.058,+0.575] | peak 1.21M p95 1.12M | est pts vs best -2.53
cg_aC6               raw 4.104 sw 3.547 med 3.534 >3m 192 | ro 0.841 wa 5.920 fo 6.723 | d_goats +0.554 [+0.295,+0.815] | peak 0.97M p95 0.87M | est pts vs best -2.57
cg_cAll6             raw 3.340 sw 2.922 med 2.829 >3m 171 | ro 0.663 wa 4.575 fo 5.809 | d_goats -0.211 [-0.444,+0.015] | peak 1.42M p95 1.21M | est pts vs best -2.30

pool v1val, flights in common 120
net_auto_727_sp10    raw 0.653 sw 0.615 med 0.545 >3m   0 | ro 0.336 wa 1.025 fo 0.898 | d_goats -3.149 [-3.882,-2.474] | peak 4.44M p95 2.95M | est pts vs best +0.00
cg_goats             raw 3.802 sw 3.374 med 1.302 >3m  54 | ro 0.673 wa 5.616 fo 7.926 | d_goats +0.000 [+0.000,+0.000] | peak 0.42M p95 0.37M | est pts vs best -2.83
cg_bAll              raw 3.109 sw 2.739 med 1.301 >3m  49 | ro 0.488 wa 4.415 fo 6.759 | d_goats -0.693 [-1.029,-0.388] | peak 0.59M p95 0.51M | est pts vs best -2.51
cg_aN6               raw 3.238 sw 3.046 med 2.048 >3m  50 | ro 0.616 wa 5.088 fo 6.395 | d_goats -0.564 [-0.973,-0.190] | peak 1.24M p95 1.14M | est pts vs best -3.04
cg_cAll6             raw 3.093 sw 2.861 med 1.546 >3m  52 | ro 0.470 wa 4.680 fo 6.489 | d_goats -0.709 [-1.130,-0.320] | peak 1.41M p95 1.21M | est pts vs best -2.95

- aX6 (first X80 build) was identical to goats: one X80 conv row (221k MAC, ~620k est. fuel) exceeded NET_FB, so the schedule stalled
  and the net never landed. Fixed with column-split conv steps and a rule of at least one step per frame (aX6b).
- Small nets: generated with agents/smallnet/tools/mkcheap.py (their net.h-API exporter), runs at epoch ~69: S_lo 0.3275 direct err,
  A_lo 0.384, C_lo32b 0.400. In the hybrid, worse direct error gave worse ATE. None helps.
