# net agent NOTES (stage-3 retraining of the GSLV learned-velocity net; own dir only; no git; v3 TEST never used)
## SUMMARY (net agent; v3 test never used)
- The v700b net inside GSLV collapses on stage-3 (direct v3val err 0.884 m/s, speed scale 0.39, z-rms 7.2). Retrained net ft2 (same
  architecture/shapes; init v700b; old stage-1/2 data share 0.3 + 139 HF stage-3 v1-train flights; time-reversal + mirror aug):
  direct v3val(430) 0.416 m/s (>1.5 m/s 0.534, scale 0.90, z-rms 1.48; fwd/side/back 0.391/0.510/0.461).
- In-filter v3val 430 (paired, score.py): gslvlj 1.524 / sw 1.390 / >3m 55 / 5.13 M | LC_ENABLE=0 1.109 / 1.033 / 17 / 5.08 M |
  GSLV+ft2 0.940 / 0.906 / 12 / 4.56 M (reps 0.967, 0.973) d vs lcoff -0.169 [-0.246,-0.098] |
  GSLV+ft2 + PRIOR_MODE=1 START_STD=2.0: 0.904 / 0.879 / 6 / 4.71 M (rep r1 0.936/0.899/10/5.11 M), d vs lcoff -0.204 [-0.278,-0.136].
  Periodic-only (LC_START_EN=0) 1.134 (worse: startup role matters); periodic-only + iso 1.597 (bad).
- v1val 210: gslvlj 1.143 | lcoff 0.866 | +ft2 0.739 | +ft2+iso 0.733 / 0.714 / 1 / 4.65 M (d vs lcoff -0.133 [-0.206,-0.062]).
- BUILD TO USE: src/s3_ft2.c with -DPRIOR_MODE=1 -DSTART_STD=2.0 -> builds/s3ft2_iso/solution.wasm sha 70b4c500...;
  (no defines: builds/s3ft2 == builds/g_ft2 sha b09e0a16..., drop-in gslv_linejac_arith with new weights). Weights: runs/ft2/best.pt.
- Continuing: driver.py + autotrain.sh running (see log below). Old-domain (stage-2) in-filter check impossible (raw zips gone);
  direct st2dev 0.240 -> 0.278.

## Session log
- Build path: tools/build.py (same wasi-sdk toolchain + linejac CMakeLists as run_variant.build, output builds/NAME). No-change rebuild of
  linejac/final/gslv_linejac_arith.c -> builds/ref/solution.wasm sha eb2799cbdc8dd9fa... == reference. VERIFIED.
- Prep: learned_c/prep2.py pipeline unchanged (640x480 RGB -> INTER_AREA 320x240 -> gray -> area 128x96 uint8, per-episode K/fx).
  Stage-3 T_body_camera == old mount (checked). v3 val cache: cache/val (learnvel/lv_prep.py on pools/v3val, 16 workers).
  Train: tools/driver.py streams HF SentientNapkin/viobench-stage3 split=train (quality ok) -> cache/train + cache/train_meta.jsonl,
  raw zip deleted after prep (~30 s download + ~45 s prep per flight per worker). Re-reads manifest every 20 min.
- Trainer tools/lv3.py: same Net (nf2, res64, w1; exportable as-is), frames pinned on CPU; groups old (lc_cache+lv_cache_train) / new;
  speed x direction-vs-camera bin weights; mirror aug + NEW time-reversal aug (frames swapped, gyro negated, preintegral re-expressed,
  targets negated: exact under time reversal of the trajectory) -> backwards examples. Batch builder parity vs learned/train.build_batch: 0.0.
  Selection: v3 val direct head-K error (the head GSLV uses: lc_out[6..11]).
- Export: tools/mkgslv.py RUN OUT.c [--sigscale s] replaces the LV_NET=1 (v700b) block of gslv_linejac_arith.c. Round trip with v700b
  -> builds/rt_v700b sha eb2799cb... == reference (VERIFIED). NOTE: LC_SIGSCALE is unused by the C (and LC_SCALE is hard-#defined 1.0 at the
  top), so --sigscale is folded into the log-variance biases (head.2.bias[3:6], [9:12] += 2 ln s).
- DIRECT v3 val (152 flights, 36328 anchors, head K, phase 0): v700b all 0.888 m/s | >1.5 m/s 1.317 | along-truth scale (>1 m/s) 0.38 (!)
  | z-rms 7.4 | fwd/side/back (>0.5 m/s, vs camera axis) 0.881/1.114/1.075 | room/wh/forest 0.656/1.060/1.119 | benchmark/free-yaw 0.629/1.015.
  lcJ 1.000. Sanity: v700b on old st2dev cache via the new builder 0.2404 (== learnvel). => old net collapses on stage-3 (speed under-estimate
  by ~2.6x, low-texture rooms, bigger scenes), and is 7x overconfident.
- In-filter ablation (1 rep, v3val 152): gslvlj (baseline, refreshed pool) 1.672 / sw 1.460 / >3m 27 / peak 5.10 M;
  net_noper (LV_PERIOD 0: no periodic re-anchor) 1.650 / 1.441, d=-0.022 [-0.097,+0.056], rooms 0.762->0.831 worse, forest 2.48->2.30 better.
- ft1 (init v700b, old 3077 flights share 0.5 + 70 HF v1-train flights, rev 0.3, lr 1e-3, 30 ep x 400 x 256): direct 0.571 (fast 0.785, scale 0.73,
  zrms 3.7, fwd/side/back 0.592/0.698/0.610, room/wh/fo 0.476/0.959/0.399). ft1r0 (no time reversal) 0.592 (back 0.703) => reversal helps.
- In-filter v3val r0 (152; vs gslvlj 1.672 / sw 1.460 / >3m 27 / peak 5.10): net_ft1 (sig x1) 1.150 / 1.009 / 10 / 5.00, d=-0.523 [-0.675,-0.383];
  net_ft1 sig x2 1.197 (worse; keep x1).
- ft2 (old share 0.3, all 139 HF v1-train flights, rev 0.3, 40 ep): direct 0.411 (fast 0.524, scale 0.91, zrms 1.48, fwd/side/back 0.385/0.503/0.449,
  room/wh/fo 0.433/0.384/0.397, bench/free-yaw 0.285/0.472). ft2b (old 0.5, rev 0.5) 0.422.
  In-filter v3val: net_ft2 1.015 / sw 0.924 / >3m 4 / peak 4.56 M, d=-0.657 [-0.813,-0.508] (rooms 0.762->0.499, wh 2.457->1.579, fo 2.481->1.375,
  hover 0.930->0.802, mid 1.847->1.066). net_ft2b 1.003 / 0.928 / 4 / 5.13 M.
  v1val (210): gslvlj 1.143 / sw 1.047 / >3m 8 / peak 5.21 -> net_ft2 0.739 / 0.723 / 1 / 5.50 M, d=-0.404 [-0.539,-0.295].
- ft3 (=ft2, 60 ep) direct 0.4075; sc1 (from scratch, lr 3e-3, 60 ep) 0.4002 (zrms 1.69).
- Old-domain check (st2dev direct, lv_cache): v700b 0.240 (selected on it) -> ft2 0.278, ft3 0.276, sc1 0.279, ft2b 0.275 (+15%).
- Lead update: compare vs GSLV with LC_ENABLE=0 (priors 'lcoff': v3val152 1.247 / sw 1.076 / peak 4.54). net_ft2 vs pr_lcoff (152 paired):
  d=-0.232 [-0.417,-0.088]; net_ft2b -0.245 [-0.431,-0.100]. => the retrained net earns its place.
- Priors base: src/gslv_s3_copy.c (= priors/gslv_s3.c: top defines overridable, LC_START_EN). No-define build == eb2799cb (VERIFIED);
  + ft2 weights == g_ft2 b09e0a16 (VERIFIED). builds/lcoff (LC_ENABLE=0) == priors lcoff cc5f1c97 (VERIFIED).
- More in-filter (v3val; pool grew 152 -> 430 mid-session (someone refreshed), paired on common flights by score.py):
  net_ft3 1.059 (152), net_sc1 1.022 (152), gslvlj_r1 1.679 (152), net_ft2_r1 0.967 (430), gslvlj_r2 1.517 (430), net_ft2_r2 0.973 (430),
  net_s3ft2_iso (PRIOR_MODE=1 START_STD=2.0) 0.951 (152), net_s3ft2_nost (LC_START_EN=0: periodic only) 1.134 (430).
- st2dev / fdev / st1dev raw zips no longer exist locally (symlinks dangling) -> no old-domain in-filter check possible; direct st2dev only (above).
- Direct on v3val 430 (102770 anchors; 278 flights never used for selection): v700b 0.884 | ft1 0.587 | ft2 0.416 | ft2b 0.427 | ft3 0.412 |
  ft4 (old 0.15) 0.412 | ft5 (rev 0.5, seed 1) 0.414 | sc1 (scratch) 0.407. => recipes equivalent; data-limited (139 stage-3 flights).
- Continuing: tools/driver.py (PID in ps; 6 workers) streams HF train; tools/autotrain.sh 300 (PID logs/autotrain.pid) retrains every +300
  new flights from the previous best, exports/builds on src/gslv_s3_copy.c, evaluates vs gslvlj + net_lcoff -> logs/auto.log.
- 430-pool in-filter + v1val: see SUMMARY. autotrain restarted with plain + iso builds per round.
