# netv2 agent NOTES (stage-3 GSLV net upgrade: learning curve, capacity, recipe; own dir only; GPU 5 only; no git; v3 TEST never used)
## SUMMARY (netv2; GPU 5 only; v3 TEST never used; selection on v3val, regression on v1val)
BEST BUILD: builds/A160ft/solution.wasm  sha256 c0bb89402393a028ca3fd762a147b33b9d51dc7bd5964a386de9775445686b9c
  source src/A160ft.c = agents/priors/gslv_s3.c with weights runs/A160ft/best.pt (same net shape as v700b/ft2, drop-in, tools/mkgslv2.py),
  flags -DPRIOR_MODE=1 -DSTART_STD=2.0 -DSPEED_STD=1.0 (= F_sp10 flags). Reps: builds/A160ft_r1 (PIXEL_STD 1.515 DMS 1010), A160ft_r2 (1.485/990).
- Direct head-K error, v3val 749 flights (179k anchors): ft2 0.413 | auto_727 0.343 | auto_2414 0.324 | auto_3924 0.312 | A160ft 0.2985 (B240 0.2965).
- In-filter, v3val SUBSET 358 (after the coordinator's disk shrink), 3 reps, paired bootstrap 95% CI (tools/rep3.py):
  vs F_sp10 (0.933): A160ft 0.888, d=-0.045 [-0.092,-0.004]; vs net_auto_727_sp10 (0.920, reference per coordinator): d=-0.031 [-0.067,+0.002]
  (S80: -0.032 [-0.059,-0.005]; A80 -0.031 [-0.066,+0.005]). Peak max over 3 reps x 358: A160ft 5.32M, auto_727 5.35M, F_sp10 4.85M
  (same code/cost per frame; peak is a single-flight chaos max). >3 m: 10 (auto_727) -> 6.
  v1val 120 (1 run): A160ft 0.617 vs auto_727 0.653 (d -0.035 [-0.077,+0.005]) vs F_sp10 0.630 -> no regression.
  NOTE: local in-filter is a weak, noisy proxy (auto_727 is only -0.013 locally vs F_sp10 but -0.078 on the server); direct error transfers.
WHAT HELPED (direct): training from scratch (S80 0.327 vs v700b-init L80 0.342), longer schedules (40->80->160 ep: 0.357->0.327->0.318 @727 flights),
  lr 4e-3 onecycle (0.320 vs 2e-3 0.327; 8e-3 0.328), more data at enough compute (727 -> 2868 flights @lr4e-3: 0.320 -> 0.309 (80 ep) / 0.3005 (160 ep);
  4154: 0.2985 by warm-start fine-tune, 0.2965 scratch 240 ep). Data alone at the old 40-ep schedule saturates (360 -> 727: -0.003).
WHAT DID NOT: bigger nets in-filter (X 32,48,64,96 direct 0.288 but in-filter 0.917 vs S80 0.841; v1val +0.071) -- the net runs as governor-
  scheduled micro-steps, a 2x costlier net lands ~1.5x later and re-anchors ~30% less; same-weights latency test (lc727_slow) costs +0.044
  [+0.004,+0.084]. Measured-cost governor (NS_GCOST, lower latency) also not better (+0.03). beta 1.0 / 0.25, alpha 0.25 / 0.75, EMA,
  blur+gamma aug, class weights, old-data share 0 vs 0.15-0.3: all neutral or worse. Calibration: z-rms ~1.0 already; LV_PSCALE 2.0 (periodic
  re-anchor sigma x2 instead of x3) on S80: d -0.013 [-0.027,+0.001] (borderline, filter knob, worth checking on the final net).
  Seed ensemble: an output ensemble doubles net cost (latency penalty above); weight averaging of independent scratch runs is not valid -> not done.
RECOMMENDED RECIPE for the final full-data round (tools/lv4.py; can replace lv3.py in autotrain):
  same shape (--chs 16,24,32,48 --hidden 128), --lr 4e-3 onecycle, --old 0.15, --rev 0.3, --alpha 0.5 --beta 0.5, mirror 0.5, bs 256 x 400 steps/ep;
  either scratch (--init none) with >=160 ep (240 ep at ~4k flights: 0.2965), or warm start from the previous best with --lr 1e-3 60 ep
  (A160ft: 0.2985, ~3x cheaper; autotrain's lr 1e-3 warm start from the old chain reaches only 0.312 at 3924 because the chain started from
  v700b/ft2 with short schedules -> restart the chain once from a scratch 160-240 ep run, e.g. runs/A160ft or runs/B240). Use OMP_NUM_THREADS=3
  (torch defaults used ~12 cores/process). Select by direct error (low noise, transfers to server); in-filter 3-rep only as regression check.
  At ~10k flights: frames live in RAM (~12 KB/anchor, 2 phases) -> ~250-300 GB per process; keep one process or drop phase 2.
- C tooling for other shapes (if ever needed): src/gslv_v2.c (NS_GEN generic schedule, NS_GCOST, NSPROF; defaults reproduce eb2799cb) + tools/mkgslv2.py.

## Setup
- tools copied from agents/net/tools (lv3.py -> lv4.py extended; mkgslv.py, build.py (OUT -> netv2/builds), evalnet.py, ev.sh, pcmp.py).
- lv4.py additions: --list (frozen train list lists/train727.txt = the 727 HF train flights cached at start, fixed random order, so --nnew N
  gives nested subsets), --chs/--deep/--hidden (capacity), --ema, --sched cos, --blur/--gamma (image aug), --clsw (class weights),
  --mirror, partial init for changed shapes. Val (selection) = lists/val749.txt (agents/net/cache/val, 749 v3val flights, 179011 anchors).
- tools/tr.sh NAME args -> CUDA_VISIBLE_DEVICES=5 lv4.py -> logs/NAME.log.

## Net cost in GSLV (gslv_s3ft2.c)
- Net = 4 conv s2 (5->16->24->32->48 at 48x64 input) + fv 19->32 + head 608->128->12; ~1.8 M MAC. Run as NET_SLICE micro-steps (97 steps:
  gray0 16, gray5 16, prep 24, var 4, pool 2, conv0 12, conv1 12, conv2 6, conv3 3, head 2), each charged GC_UNIT=160e3 by the governor
  (GOV_B 3.6e6, up to GOV_UMAX=40 units/frame after vision). Net runs at startup (frame K=5) and as periodic re-anchor every LV_PERIOD=10 frames.

## Log
### 1. Learning curve (direct head-K error on val749, init v700b, old share 0.3, rev 0.3, 40 ep x 400 x 256, onecycle 1e-3)
| run | new flights | all | fast | zrms | f/s/b | room/wh/forest | best ep |
| (ft2, ref) | 139 (older v1-train) | 0.413 | 0.529 | 1.50 | 0.384/0.506/0.457 | 0.434/0.409/0.387 | - |
| lc90 | 90 | 0.3815 | 0.482 | 1.22 | 0.377/0.448/0.408 | 0.397/0.372/0.370 | 34 |
| lc180 | 180 | 0.3681 | 0.465 | 1.12 | 0.363/0.432/0.399 | 0.384/0.361/0.354 | 35 |
| lc360 | 360 | 0.3601 | 0.452 | 1.06 | 0.356/0.422/0.389 | 0.375/0.351/0.349 | 36 |
| lc727 | 727 | 0.3572 | 0.450 | 1.04 | 0.353/0.419/0.385 | 0.374/0.346/0.346 | 39 |
=> strongly diminishing with data at fixed net/compute (360 -> 727: -0.003); best epoch = last for 727 -> compute/capacity-limited, not data-limited.
- In-filter lc727 (v3val 749, F_sp10 flags, paired vs nv2_base = F_sp10 wasm 40355ed9 re-run on 749): base 0.927 / sw 0.857 / >3m 17 / peak 4.79M;
  lc727 0.889 / 0.826 / 12 / 5.46M, d=-0.037 [-0.100,+0.014]. v1val 210: base 0.665 -> lc727 0.664, d=-0.002 [-0.046,+0.041].
  => direct 0.413 -> 0.357 (-14%) buys only ~-4% ATE (n.s.).
### 2. Capacity / schedule (direct val749; 727 new + old 0.3; 80 ep x 400 x 256; scratch = --init none --lr 2e-3)
| run | chs (hidden 128) | init | all | fast | zrms | f/s/b | room/wh/forest |
| L80 | 16,24,32,48 | v700b | 0.3422 | 0.432 | 1.05 | 0.341/0.400/0.368 | 0.359/0.331/0.332 |
| S80 | 16,24,32,48 | scratch | 0.3267 | 0.414 | 1.06 | 0.324/0.383/0.350 | 0.348/0.313/0.312 |
| W80 | 24,32,48,64 | scratch | 0.3052 | 0.389 | 1.07 | 0.304/0.358/0.327 | 0.332/0.286/0.289 |
| X80 | 32,48,64,96 | scratch | 0.2884 | 0.367 | 1.10 | 0.287/0.338/0.309 | 0.319/0.266/0.271 |
=> all best at the last epoch (longer helps: lc727 40 ep 0.357 -> L80 0.342); scratch beats v700b init; width helps a lot (S 0.327 -> X 0.288).
### C support for other shapes: src/gslv_v2.c = priors/gslv_s3.c + `#if NS_GEN` generic micro-step schedule (conv layers split into pixel ranges,
  NS_VB=13824 f32x4 MACs per step = reference conv1..3 row step; head split into NS_KH row chunks; LC_HID). Exporter tools/mkgslv2.py (any --chs/--hidden).
  - No-define build of gslv_v2.c == eb2799cb (reference) VERIFIED; mkgslv2(ft2) into gslv_v2.c + F_sp10 flags == 40355ed9 (F_sp10) VERIFIED.
  - NS_GEN=1 with reference splits (NS_K0=12 K1=12 K2=6 K3=3 KH=2) on 30 v3val flights: ATE bit-identical 30/30 vs F_sp10 (peak within 14k).
  - Step counts NS_STEPS = 62 (gray/prep) + K0..K3 + KH: ref shape 97 (NS_GEN default splits: 93); W 24,32,48,64 -> 62+15+24+12+6+3=122;
    X 32,48,64,96 -> 62+20+48+24+12+4=170.
- In-filter X80 (v3val 749, F_sp10 flags + NS_GEN=1): 0.917 / sw 0.854 / >3m 19 / peak 4.89M, d vs base -0.009 [-0.066,+0.036] (worse than lc727 0.889
  despite direct 0.288 vs 0.357).
### Measured net fuel (tools/prof.py on NSPROF builds: host mark() around every micro-step; 6 v3val flights x 400 frames)
| step | ref (16,24,32,48) fuel/step | total/run | X (32,48,64,96) fuel/step | total/run |
| gray0+gray5 (32) | 45k | 1.45M | same | 1.45M |
| prep+var+pool (30) | 55-117k | 1.99M | same | 1.98M |
| conv0 | 101k x12 | 1.21M | 112k x20 | 2.23M |
| conv1 | 156k x12 | 1.87M | 136k x48 | 6.54M |
| conv2 | 138k x6 | 0.83M | 125k x24 | 3.01M |
| conv3 | 117k x3 | 0.35M | 108k x12 | 1.30M |
| head | 231k x2 (max 296k) | 0.46M | 201k x4 (max 274k) | 0.81M |
| total per net run | | ~8.2M | | ~17.3M |
- ~11 fuel per f32x4 MAC. Net steps/frame (governor) ~5-8 -> startup latency ref 9-11 frames, X 14-19 frames; periodic re-anchor runs take
  19-270 frames (budget-starved) -> X does ~30% fewer re-anchors (16 vs 23 runs in 6x400 frames). Frame-fuel max on these 6x400: 3.72M ref, 4.05M X.
- In-filter S80 (ref shape 16,24,32,48 from scratch, 80 ep; drop-in, no C change; v3val 749 vs base): 0.841 / sw 0.775 / >3m 9 / peak 5.21M,
  d=-0.086 [-0.141,-0.038]  (rooms 0.494->0.429, wh 1.411->1.252, forest 0.967->0.942, hover 1.031->0.939, mid 0.874->0.791). FIRST CLEAR WIN.
  => at fixed shape, better training transfers; wider X80 does not (latency/fewer re-anchors suspected; lc727_slow test queued).
- In-filter W80 (24,32,48,64; NS_GEN): 0.878 / sw 0.814 / >3m 13 / 5.13M, d=-0.048 [-0.109,+0.004]. X80 v1val 0.736 vs base 0.665: d=+0.071 [+0.008,+0.129] (REGRESSION).
  => in-filter ranking S80 (0.841) < W80 (0.878) < X80 (0.917) is monotone in net COST, opposite to direct error -> bigger nets lose on latency /
  re-anchor frequency. Capacity increase is NOT the way at the current scheduling. (Y80 48,64,96,128: direct 0.271; XH80 X+hidden 256: 0.274; not built.)
- Recipe (direct, S shape scratch 80 ep): beta 1.0 0.3371 (worse) | old 0 0.3269 (= S80 0.3267) | EMA 0.999 0.3321 (worse). Seed noise ~0.001 (X80 vs X80s1).
- NOTE: until here my trainings ran with torch default threads (~10-13 cores each, I was the main load contributor); since then tr.sh sets
  OMP_NUM_THREADS=3 + torch.set_num_threads(3) (~1.2 cores, 18 s/epoch). X160 killed (capacity dropped), S160 restarted.
### Measured-cost governor for the net (src/gslv_v2.c NS_GCOST=1, default 0; ns_cost(k) table from the profile x NS_GCOST_M=1.1)
- Governor charged a flat GC_UNIT=160k per micro-step though gray/prep steps cost 45-60k -> net latency was over-throttled.
  NS_GCOST=1 charges measured cost. Profile S80 (6x400 frames): startup latency 9-11 -> 7-8 frames, net runs 25 -> 34, frame-fuel max 3.82M -> 3.74M.
  No-define build still eb2799cb; S80 via gslv_v2.c without NS_GCOST == g_S80 sha 16350298.
- LATENCY TEST: lc727 weights with X-like step counts (NS_GEN=1 NS_K0=20 K1=48 K2=24 K3=12 KH=4 -> 170 steps; v2_lc727_slow):
  0.933 / sw 0.854 / >3m 17 / 4.98M vs lc727 0.889 (same weights, 97 steps) -> latency alone costs ~+0.044. CONFIRMED: net latency /
  re-anchor frequency is a first-order factor in-filter.
### EVAL SET SHRINK (coordinator, user-approved, disk full; ~07:40)
- Local v3val zips not in gen3/pools/v3val_keep.txt (358 stratified) and v1val zips not in pools/v1val_keep.txt (120) are deleted.
  From now on in-filter evals run on the 358 / 120 subsets; paired comparisons (score.py / pcmp.py) use common flights and earlier per-flight
  results are cached, so the 749 / 210 results above stay valid (re-scored on the subset where compared). Direct-error val cache
  (agents/net/cache/val, 749 flights) is preprocessed and unaffected.
- My eval queue is held during the deletion (logs/queue_hold.txt) and released by tools/resume_after_shrink.sh after refresh_pools.sh.
  Profiling pool moved to pools/nv2sub30k (30 keep-list flights); old pools/nv2sub30 links will dangle (not used anymore).
- In-filter (v3val 749, 1 run): S80gc (NS_GCOST=1) 0.870 (+0.030 [-0.005,+0.069] vs S80), S80gcs (NS_GCOST=2, startup only) 0.883 (+0.042),
  S80ps2 (LV_PSCALE=2.0) 0.829 (-0.012 vs S80, n.s.). => measured-cost governor does NOT help (dropped); the lc727_slow loss shows a slower
  net hurts, but speeding the reference schedule further does not gain. LV_PSCALE 2 kept as a candidate for replicates.
- v1val 210: S80 0.668 vs base 0.665, d=+0.002 [-0.039,+0.039] (no regression); lc727 0.664.
- Recipe batch 2 (direct, S shape scratch 80 ep, 727 new): beta 0.25 0.3283 | alpha 0.25 0.3263 | alpha 0.75 0.3360 | lr 4e-3 0.3198 (best) |
  blur 3 px + gamma 0.3 aug 0.3303 (no gain: stage-3 train data already spans blur/FoV/brightness). Defaults beta 0.5 / alpha 0.5 stay.
- lists/trainall1.txt: all cached HF train flights at 07:5x (2850, s3tr only). Launched S80lr8, A80 (all data, lr 4e-3, old 0.15, 80 ep), A160 (160 ep).
- Direct: S80lr8 0.3277 (lr 8e-3 too high), S160 (lr 2e-3, 160 ep) 0.3180, A80 (ALL 2868 train flights, lr 4e-3, old 0.15, 80 ep) 0.3088.
### 3-replicate in-filter (v3val SUBSET 358; r0 + PIXEL_STD 1.515/DMS 1010 + 1.485/990; tools/rep3.py: per-flight rep mean, paired bootstrap)
- base (F_sp10) reps 0.947/0.941/0.910 -> mean 0.933. S80 reps 0.878/0.921/0.864 -> 0.887.
  S80 vs base: d=-0.0455 [-0.0963,-0.0059], >3m 8 -> 6, peak max 4.85M -> 5.01M; rooms 0.548->0.472, wh 1.387->1.347, forest 0.939->0.932,
  hover 0.963->0.979, mid-flight 0.918->0.841.
- Coordinator (09:xx): server calibration GSLV+auto_727 0.586 vs GSLV+ft2 0.664 at ~same fuel -> net quality transfers strongly to the server;
  in-filter reference from now on = net_auto_727_sp10 (wasm 9a468ce9; my rebuild from net/src/g_auto_727.c reproduces the sha; reps auto727_r1/_r2).
  Direct val749: ft2 0.413 -> auto_727 0.3427 (server -0.078); auto_2414 0.3238.
- A80 3-rep (358): 0.888 vs base 0.933: d=-0.0444 [-0.0869,-0.0043], peak 4.74M; A80 vs S80 d=+0.001 [-0.030,+0.036] (local in-filter
  cannot resolve direct 0.327 -> 0.309). A80 r0 vs auto_727 r0: 0.907 vs 0.906. v1val 120: A80 0.639, auto_727 0.653 (no regression).
- S80ps2 (LV_PSCALE=2.0) vs S80, 3 reps: d=-0.0126 [-0.0269,+0.0011] (borderline; filter knob, worth a check on the final net).
- Since local in-filter (358, sd ~0.02-0.03/run) is too noisy for the direct gains that the server rewards, selection = direct error (low noise:
  seed sd ~0.001), with in-filter 3-rep as a regression/sanity check.
- Direct: A160 (2868 flights, lr 4e-3, 160 ep) 0.3005 (A80 0.3088). A80cw (class weights warehouse/forest 1.5) 0.3085 = A80 -> no targeted
  class sampling needed (direct per-class errors are balanced: room 0.33 > wh/forest 0.29; in-filter warehouse/forest weakness is not net-driven).
- lists/trainall2.txt = 4154 train flights (s3v3tr 4015 + s3tr 139; split=train only). Train/val scene check: 222 train vs 36 val scenes, only the
  generic labels 'Warehouse'/'Forest' shared, no seed overlap. Launched B240 (all 4154, scratch, lr 4e-3, 240 ep) and A160ft (warm start from
  A160 on 4154, lr 1e-3, 60 ep = autotrain style) to decide scratch-vs-incremental for the final round.
- A160ft (warm start A160, all 4154, lr 1e-3, 60 ep): direct 0.2985 (best ep 49) -> incremental fine-tuning keeps up with scratch. In-filter queue switched from A160 to A160ft (3 reps + v1val).
- Final: A160ft 3 reps (358): 0.888; vs F_sp10 d=-0.0447 [-0.0917,-0.0037]; vs auto_727 3 reps d=-0.0313 [-0.0672,+0.0018]; v1val 120: 0.617
  (auto_727 0.653, F_sp10 0.630). B240 (scratch 240 ep, 4154 flights) direct 0.2965 (not built). autotrain auto_3924 direct 0.3117.
