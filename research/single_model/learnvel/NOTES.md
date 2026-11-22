# learnvel NOTES (learned-velocity agent; own dir only; no git; holdout/fold-4/sealed/st2-conf never trained on; never probe server)
Base HM40 = servertail/final/hfg_m40s1.c (sha 4920835f...), = servertail/sa.c + HFG defines + TC_MAXANCH=40 TC_RE_SCALE=1.0.
Net in HM40 = learned_c lcJ (2 frames, anchor k and k+5, 64x48 w1, ~1.7 M MAC). NOTE: the net is already trained on ALL anchors of
each flight (valid_starts = every stride-5 anchor), not only the start; training pools raw-fast/raw-speed (folds 0-2).
## Session log
- S1: read servertail/learned_c/tailcap/lateinit/atepush notes. Plan: (1) prep st2dev into an eval-only cache + TC_LOG run of HM40
  on st2dev -> net error vs filter error in starved stretches; (2) generate starved/fast training flights; (3) retrain; (4) filter use.
- Tools (learnvel/): lv_prep.py (prep2 cache for any pool -> tmp/lv_cache), lv_eval.py (net predictions per anchor), lv_diag.py + an1/an2.py
  (net error vs HM40 filter twist error, with TC_LOG signals), bp.sh/rp.sh/runpool.py/mkwasm.py (build to results/lv_NAME, tables/NAME__POOL.json),
  pools tmp/lv_pools/{fresh03,fdev,fconf} (fold 4 excluded by symlink), st2dev/st2conf from tmp/st_pools. hm40.c = copy of servertail/final/hfg_m40s1.c.
  Reps: r1 PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0, r2 1.485/990.0. HM40 r0 st2dev 0.6308 reproduced (TC_LOG build). st2dev run = 2 min @32 workers.
- DIAG 1 (lcJ net on all st2dev anchors, 37 k; HM40 TC_LOG; tables/diag_lcJ_st2dev.json):
  overall net err 0.255 vs filter (twist) 0.147 m/s; net beats filter only where filter is bad: filter err>0.5 (4%): net 0.42 vs 0.82;
  filter>1.0: net 0.44 vs 1.41. Pv>0.5: net 0.24 vs 0.63. By speed: net 0.11/0.21/0.34/0.64/1.15 for <0.3/0.3-1/1-2/2-3/>3 m/s
  (filter 0.13-0.24 flat). Net error at speed = MAGNITUDE UNDER-ESTIMATE: along-truth scale 0.91 (1-2 m/s), 0.76 (2-3), 0.65 (>3); perp
  error only 0.13. Low texture (tex<0.03): net 0.35 vs filter 0.27. sigma overconfident (z rms 1.3, 1.9 at 2-3 m/s).
  Newer learned_c nets (1195 flights incl. K2 pool) barely better: d2_n800 0.246, w2 0.233 (2-3 m/s 0.57-0.61; scale 0.77-0.79).
  Bad st2dev flights (ATE 1.4-6.2): filter err>0.5 in 15-100 of 239 anchors, net err there 0.3-0.6, filter 0.7-1.2, speed ~1 m/s, live ~10.
  => ceiling: net is ~2x better than the filter exactly in the failure stretches; improve net at speed (scale) + starved scenes.
- Training (lv_train.py; rows = learned_c train rows + gen/lv_rows.json MINUS all st2 scenes, folds 0-2 only; selection = st2dev direct err):
  runs b2 (nf2), b2w2 (width 2), n3 (3 frames 0/5/10), n4 (4 frames, 0.75 s), g2 (2 frames 10 apart). GPUs 3-7.
- GENERATION roster gen/roster_a.json (600 fast flights, variants K/P1/P4/P5/K1, scenes = eligible fold 0-2 non-holdout non-st2, weighted to low
  texture (tables/scenetex.json); seeds 4700000+); driver gen/driver.py -> raw gen/raw-learnvel, cache tmp/lv_cache_train, rows gen/lv_rows.json, zip deleted.
- Net training round 1+2 (direct st2dev error, honest: no st2 scenes in training; lcJ 0.255 is contaminated by st2-dev-scene flights):
  b2 0.258 | b2w2 0.245 | n3 (3 frames) 0.270 | n4 0.277 | g2 (10-frame gap) 0.288 | bn05 (beta-NLL 0.5) 0.254 | bn05w2 0.240 | n3w2 0.240 |
  b2a75 0.260. Speed>2: b2 0.685 (scale 0.74) -> bn05w2 0.564 (0.80). Gains are modest (<=7%). More frames do not help at w1.
  NOTE: in-filter conv is int16-quantised ns_convq with acc[12] => CO<=48: width-2 nets need C changes (Nb2w2 run INVALID, peak 10.5 M).
- Filter arms with lcJ (lv.c switches: LV_PERIOD (fire every N frames, fire=6), LV_PSCALE (sigma scale for periodic fires), LV_PLIVE
  (periodic only while live<N), LV_GATE (chi2 gate on re-anchor updates; int)). lv.c with no defines == HM40 wasm 4920835f (verified).
  1 rep st2dev (HM40 reps 0.631/0.650/0.700, mean 0.660): P20 0.637, P20G (gate 11) 0.709, G11 (gate only) 0.700 => GATE HURTS (rejects
  the net exactly when the filter drifted); P20S2 0.627, P20L20 0.637, P20L20S15 0.643, P20L15S2 0.618, P20S100 (net ignored: sd x100) 0.655.
  CAUTION: per-difficulty-bin comparisons vs the base 3-rep mean are biased by regression to the mean (P20S100 'improves' the worst bin
  3.07->2.58 with no information). Use whole-pool means, 3 reps, paired.
- st3 eval pool generating: 234 more flights in the 13 st2-DEV scenes (K/P1/P4, half mid, seeds 4800000+), gen/st3.json, raw-learnvel-st3 (zips kept).
- 3 reps st2dev (vs HM40 0.6604): P20 0.6437 (-2.5%), P20S2 0.6328 (-4.2%), P20S100 (no-info machinery) 0.6841 (+3.6%) => net info worth ~-8%
  vs null machinery; Nb2P20 (honest b2 net) 0.681, Nbn05P20 0.692 (worse than lcJ: lcJ trained on 6 of 13 st2dev scenes; on the 7 honest
  st2dev scenes direct err lcJ 0.253 / b2 0.251 / bn05 0.247 / bn05w2 0.234 => in-filter net-to-net spread dominates small direct gains).
  LV_RESET (net-vs-filter disagreement: chi2>LV_RCHI -> inflate V,VK fully correlated by dw^2, then update): RS16 (P20S2+reset) 0.6386 (-3.3%),
  RS9 0.6710. No real gain. Per-flight chaos is huge (worst flight 6.2/5.9/10.3 m over reps).
- KEY DIAGNOSIS (100-009 time series, LC_DEBUG): the net corrects velocity, but within ~1 s the filter returns to the wrong velocity.
  Cause = TILT error: relative-rotation tilt error 4-6 deg at 3-5 s (gravity leak ~1 m/s^2) -> 2-3 m/s velocity divergence at 4-8 s, filter Pv
  stays 0.2-0.3 (13 sigma overconfident). st2dev per-flight mean tilt err (tilt.py/tiltall.py, from estimate.tum vs truth, z-up):
  ATE<0.3: 1.8 deg, 0.3-0.6: 2.8, 0.6-1: 5.4, 1-2: 6.5, >2: 6.9 (corr log ATE vs log tilt 0.54). No drag => accelerometer carries no tilt info.
  => IDEA: learned GRAVITY-DIRECTION net (single frame -> gravity in body frame, 2 dof + sigma) as a periodic tilt measurement.
  Labels: grav.py -> tmp/lv_grav/<name>.npz (gb0/gb2 = R_wb^T (0,0,-1) at anchors); driver patched to label before deleting zips
  (lv batches 0-1 lost labels). Zips available: raw-fast 882 (skip fold 4), raw-speed 170, raw-servertail st1/probe, lv flights batches 2-5.
- (usage-limit interruption ~06:25 -> 10:29) roster_a DONE (600 flights cached), st3 DONE (234 zips).
- Gravity nets (grav_train.py; single gray frame + IMU means -> body gravity; train = fast/speed/lv flights with labels, no st2 scenes):
  st2dev angle error mean/median: constant-prediction 6.13/4.77 deg; g64 2.53/1.78; g128 2.03/1.29; g64w2 2.64/1.86. Starved (live<10)
  g64 3.45/2.54; errors decorrelate within 1 s (lag-4-anchor corr -0.07); sigma calibrated (err/sig rms 0.82).
- Filter tilt diagnosis (100-009, LV_DBG): absolute filter tilt error 1 deg normally, 6-8 deg in the 4-7.5 s catastrophe; grows ~1.5 deg/s
  smoothly = gyro-bias estimate corrupted (bg_y 0 -> 0.038 > physical 0.02), attributed (bgattr.py) mostly to starved VISION updates (+0.025),
  net updates -0.011. Arms: TQ (tilt process-noise boost while live<20) 3 reps: TQ3 0.722, TQ8 0.866 => HURTS. BGC (clamp |bg|<=0.025)
  0.666 (neutral), BGC2 (0.021) ~0.645 (2 reps).
- C gravity module gr_core.h (mkgrav.py inserts it + weights under #if LV_GRAV into lv.c -> lvg_<net>.c; off == HM40 wasm, verified):
  capture (stash RGB + R_k + IMU means) every LV_GPER frames, 66 cost-aware micro-steps on the governor's leftover units (fuel measured
  with LV_GBENCH: one inference ~10.5 M fuel, conv0 rows 110 k, conv1 rows 330 k ...), delayed update: r = g_net - R_k^T(0,0,-1),
  H_TH = [h_k]x R_k^T R. Parity C vs PyTorch: 0.000 deg on 8/12 captures, <=0.49 deg others. Peak 3.42 M on 100-009.
- Gravity in-filter (lvg_g64.c, 3 reps st2dev): GR10 (every 10 frames) 0.689 (+4.4%); GRR9 (+chi2>9 tilt-variance reset) 0.926 (+40%!).
  Debug: the gravity net (mean err ~2.5 deg, worse in maneuvers/starved: 4-9 deg) is LESS accurate than the filter's tilt (~1 deg) except in
  rare catastrophes, and trusting it raises mean tilt error (1.4 -> 2.3 deg on 100-009). g64e80/g64s1 no better (st2 mean 2.56).
  => gravity net at 64x48 NOT useful; g128 (1.3 deg median) would cost ~40 M fuel/inference. DROPPED.
- P20S2 on st3 (234 flights in st2-dev scenes), 3 reps: HM40 0.6506 -> 0.6222 (-4.4%), >3 m 20->12, >5 m 5->2 (summed over reps). Replicates st2dev -4.2%.
- Pooled dev = st2dev+st3 (390 flights x 3 reps; pooled.py): HM40 0.6545 | P20S2 -4.3% | P10S2 (period 10, scale 2) -6.1% CI [-0.077,-0.010]
  | PB (P20S2 + gyro-bias clamp 0.021) -5.5% | P30S2 ~neutral.
- COORDINATOR: build on RSOFT (filtcons/final/hm40_rsoft1t0.c, wasm 7ef3a329...). patchlv.py ports the minimal switches (LV_PERIOD/PSCALE/PLIVE/BGC)
  onto any base: rs.c (RSOFT) off == 7ef3a329 VERIFIED; lv2.c (HM40) off == 4920835f VERIFIED. Queues qE/qF: rs baseline + rsP10B/rsP6B/rsP10S2/rsP10S3B/rsB.
  (filtcons: tc_used never incremented -> u20 counters 0; net sd sits at floor at speed.) NEVER use pkill/pgrep -f with a pattern that is in the same command line.
- RSOFT base (rs.c, 3 reps): pooled st2dev+st3 0.5940 (HM40 0.6545, -9.2%). On top of RSOFT: rsP10S2 -2.1% [-0.041,+0.016], rsP10B -1.8%
  (gains mostly overlap with RSOFT's). New net v700b (beta-NLL, +700 lv flights, w1, direct st2dev 0.240 vs b2 0.258; >2 m/s 0.55, scale 0.81)
  queued in-filter (qG: rsNP10B, rsN).
- RSOFT arms pooled (3 reps, vs rs 0.5940): rsP10S3B (period 10, sigma x3, bg clamp 0.021) 0.5678 (-4.4%, CI [-0.049,-0.004]) |
  rsNP10B (v700b net + P10 S2 + clamp) 0.5615 (-5.5%, CI [-0.071,+0.006]) | rsP10S2 -2.1% | rsP10B -1.8% (rsP6B identical: fires gated by net landing)
  | rsB (clamp only) +0.6%.
- COORDINATOR (2nd): new base GSLM = geomstarve/final/gs_lines_manhattan.c (wasm 180ffa2b). gl.c = patchlv(GSLM): off == 180ffa2b VERIFIED;
  gln_v700b.c = gl.c with v700b net weights. Queues qH (gl, glP = P10S3B), qI (glNP = v700b+P10S3B, glN = v700b only).
- rsN (v700b net, HM40 schedule, on RSOFT) +1.4% => the net alone does nothing; it pays only with periodic re-anchoring.
- GSLM results (3 reps, st2dev / st3): gl 0.455 / 0.475 | glP (lcJ + P10S3B) ~0.440 / ~0.44 | glNP (v700b + P10S3B) 0.415 / 0.416 (~-11%) |
  glN (v700b alone) ~neutral. => periodic re-anchor COMPOSES with GSLM (larger gain than on HM40/RSOFT). Confirm queues qJ (gl) / qK (glNP)
  on st2conf, fconf, st1conf, st1dev, fdev.
- CANDIDATE final/gslm_lvnet.c (= GSLM via patchlv + LV_NET switchable weights; 7 #defines: TC_GAP=9 TC_MAXANCH=400 LV_PERIOD=10
  LV_PSCALE=3.0 LV_BGC=1 LV_BGMAX=0.021 LV_NET=1) -> final/gslm_lvnet.wasm sha 5e4d2a0d40333b3f5152d60de84a688abc5d0eec8c1c73fa402dc9907839d196
  (== define-built glNP wasm; glx.c with no defines == GSLM 180ffa2b). PREFLIGHT (final/preflight): ABI ok, zero imports, poison/prefix/repeat
  738/738 PASS (18 fixtures x 41 prefixes incl. 20/24/29-31/40/41/60-66/70/80/99-105 around periodic fires), reset 8/8 PASS.
## FINAL (3 reps each, means over reps; base GSLM = gl.c no defines = 180ffa2b; arm glNP = final/gslm_lvnet.wasm 5e4d2a0d)
| set | GSLM | glNP | d (scene-bootstrap 95% CI) | >3 m (sum 3 reps) | peak max |
| st2dev 156 | 0.4553 | 0.4154 | -8.8% [-0.057,-0.022] | 5/5 | 7.09/6.84 M |
| st3 234 (st2-dev scenes) | 0.4746 | 0.4156 | -12.4% [-0.133,-0.012] | 12/4 | 6.96/6.83 |
| st2conf 84 | 0.3507 | 0.3334 | -4.9% [-0.036,-0.001] | 0/0 | 6.33/6.56 |
| fresh f0-2 475 | 0.2658 | 0.2567 | -3.4% [-0.019,-0.000] | 3/1 | 6.94/6.96 |
| fresh f3 107 | 0.3046 | 0.2701 | -11.3% [-0.068,+0.003] | 0/0 | 6.51/6.75 |
| st1dev 244 | 0.1918 | 0.1773 | -7.6% [-0.028,-0.005] | 0/0 | 7.02/6.98 |
| st1conf 156 | 0.2532 | 0.2459 | -2.9% [-0.018,+0.003] | 0/0 | 7.40/6.41 |
No >10 m anywhere; filled 0; all completed. RECOMMENDED: final/gslm_lvnet.wasm sha256 5e4d2a0d40333b3f5152d60de84a688abc5d0eec8c1c73fa402dc9907839d196.
