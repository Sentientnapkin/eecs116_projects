# Learned components as ensemble members, second opinions, or selectors

All sources are local repo files (paths relative to `/data/backups/rganapa/Sebastian/eecs116_projects/`). "Measured" means a number from a log, table or my offline run. "Estimated" means arithmetic I did on measured numbers. New offline analysis: `research/single_model/ensemble/learned_sel.py` produces `research/single_model/ensemble/learned_sel.json`. It uses existing tables only: no holdout, no fold 4 and no server data. Score arithmetic used throughout: area = 0.28·log2(17/peak) − 2.24·ln(ATE/0.356), so each doubling of peak fuel costs 0.28 points ([filtcons NOTES](research/single_model/filtcons/NOTES.md)). The shipped reference build is GSLV-linejac: server 0.633 m at 4.2 M peak, holdout 0.380 m at 4.30 M ([LOOP_LOG](research/single_model/LOOP_LOG.md)).

## Q1. Inventory: each learned model's inputs, outputs, accuracy, fuel, in-filter effect and error independence

### Takeaway
Only two learned components have improved the shipped filter. The first is the startup net lcJ (B10: holdout −0.144 m vs B7). The second is the periodic velocity re-anchor (v700b in GSLV: −3% to −12% on the server-like pools, a tie on the holdout). Neither works by being accurate on average. The net's errors are nearly independent of the filter's, so it helps most where the filter fails. Every larger or more accurate model (teachers, ensembles of nets, the gravity net, the displacement student) was neutral or worse in-filter, or was much worse on the server.

### Cited Findings
**Startup velocity net lcJ** (2 gray frames at anchors k and k+5, 64×48, width 1, ~1.79 M MAC; outputs body velocity plus per-axis log-variance)
- Direct error on fold-3 val is 0.188 m/s. By speed (<0.3 / 0.3-1 / 1-1.5 / >1.5 m/s) it is 0.078 / 0.161 / 0.264 / 0.399. The sigma is over-confident on fast starts. — [learned_c NOTES](research/single_model/learned_c/NOTES.md)
- Fuel: the forward pass adds about 4.7 M fuel on frame 6, and preprocessing adds 2.0 M on frame 0 and 5.3 M on frame 5 after the exact rewrite. It does not set the peak of B11. — [learned_c NOTES](research/single_model/learned_c/NOTES.md)
- In-filter: B10 holdout 0.738 vs B7 0.882, paired −0.144 [−0.290, −0.016]. — [LOOP_LOG](research/single_model/LOOP_LOG.md) l.91
- Net-to-net spread in-filter is about ±0.05 m on f3 and about ±0.1 m on val, across 9 seeds of the same recipe. That is larger than any claimed effect. — [learned_c NOTES](research/single_model/learned_c/NOTES.md)
- A 3-net ensemble (lcJ/J1/J2) gave −7% direct error (0.1747 vs 0.188) but was worse in-filter: f3 0.705 vs 0.606, and peak 20.7 M if run in one frame. — [learned_c NOTES](research/single_model/learned_c/NOTES.md)
- The server diagnosis attributes B16's bad server episodes to a rigid offset made by lcJ in the first second. G (no net) beats lcJ builds on exactly those episodes. On the server, 33% of episodes have B16 worse than G by >0.5 m, vs 3-4% on HF. — [proxy NOTES](research/single_model/proxy/NOTES.md)

**Startup teacher T1 → students S0/S1/S2** (same input as lcJ; T1 at 128 resolution, width 2)
- Direct error, all anchors / >2.5 m/s: lcJ 0.235/0.744, S0 0.239/0.613, S1 (KD from T1) 0.240/0.588, S2 (self-distillation) 0.233/0.640. T1 overfits 102 flights (z-rms 2.3). — [proxy NOTES](research/single_model/proxy/NOTES.md)
- In-filter, m7+S2+LC_SPD_K=0.3 vs m7 gives +0.003 [−0.060, +0.080] on HF folds 3-4 and −0.027 [−0.118, +0.043] on 26 proxy flights. This is a tie, and S2 was not submitted. — [proxy NOTES](research/single_model/proxy/NOTES.md), [STUDENT_TEACHER](research/single_model/STUDENT_TEACHER.md)

**Periodic velocity net v700b** (lcJ architecture, beta-NLL, +700 fast flights; fires every 10 frames with sigma ×3 in GSLV)
- Direct error on st2dev: 0.240 m/s (b2 0.258); >2 m/s: 0.55; speed scale 0.81. — [learnvel NOTES](research/single_model/learnvel/NOTES.md)
- Net vs filter (lcJ on HM40, 37 k st2dev anchors): net 0.255 vs filter 0.147 overall. Where filter error >0.5 (4% of anchors): net 0.42 vs filter 0.82. Where filter error >1.0: 0.44 vs 1.41. — [learnvel NOTES](research/single_model/learnvel/NOTES.md); reproduced in `learned_sel.json`
- In-filter, GSLV vs GSLM (3 reps): st2dev −8.8%, st3 −12.4%, st2conf −4.9%, fresh f0-2 −3.4%, f3 −11.3%, st1 −7.6/−2.9%. Holdout 0.379 vs 0.382, a tie. Peak about 7 M before linejac. — [learnvel NOTES](research/single_model/learnvel/NOTES.md), [LOOP_LOG](research/single_model/LOOP_LOG.md)
- The net used alone (HM40 schedule, no periodic firing) gives +1.4%: "the net alone does nothing; it pays only with periodic re-anchoring". A chi2 gate on the net hurts, because it rejects the net exactly when the filter has drifted (P20G 0.709 vs P20 0.637). — [learnvel NOTES](research/single_model/learnvel/NOTES.md)

**Gravity-direction net g64 / g128** (single frame plus IMU means → body gravity, 2 dof plus sigma)
- Direct angle error on st2dev, mean/median: g64 2.53/1.78°, g128 2.03/1.29°. The filter's own tilt error is about 1° normally. Net errors decorrelate within 1 s (lag-4 correlation −0.07), and sigma is calibrated (rms 0.82). — [learnvel NOTES](research/single_model/learnvel/NOTES.md)
- Fuel is about 10.5 M per inference for g64, spread by the governor (peak 3.42 M). g128 is estimated at about 40 M per inference. In-filter, GR10 (every 10 frames) gives +4.4% and GRR9 +40%. Dropped. — [learnvel NOTES](research/single_model/learnvel/NOTES.md)

**STLONG velocity teachers and students** (stopped run)
- teacher4 (4 frames, 128×96, width 2, deep; **83.6 M MAC** measured by `params/macs` in the logs) has direct error 0.170 (st2dev) / 0.167 (st3), against 0.241/0.236 for v700b. At >2 m/s it gets 0.324 vs 0.547, and its speed scale is 0.94. teacher_final reaches 0.167. teacher2 (2 frames, 80.0 M MAC) reaches 0.180. — [stlong NOTES](research/single_model/stlong/NOTES.md), `stlong/runs/*/result.json`, `stlong/logs/*.log`
- Students: width-1.5 students (3.56 M MAC) reach direct 0.224-0.226 on st2dev, about 7% better than v700b. Their in-filter screens never ran (`wide_screen.log` and `lcj_screen.log` stop at "Waiting…"). — `stlong/runs/wide{0,1,2}/result.json`, `stlong/logs/`
- In-filter screens that did run (r0, pooled st2dev+st3, 390 flights, vs GSLV 0.4254): baseline retrain 0.4474 (+5.2%), pilot student 0.4438 (+4.3%), pilot_mm 0.4437 (+4.3%). All CIs straddle 0. — [stlong NOTES](research/single_model/stlong/NOTES.md)

**Displacement teacher → student (B17)** (3 derotated frames at 128×96, gravity and IMU preintegration → 1 s metric displacement with Laplace sigma)
- Teacher is about 400 M MAC; a call makes its frame about 1.27 G fuel (measured). The student is about 100 M MAC; B17 peak is 418 M with one call every 4th frame. — [disp_teacher NOTES](research/single_model/disp_teacher/NOTES.md)
- Direct 1 s error on folds 2-3: fine-tuned teacher 0.293 m, s3 0.254 m. B16's own 1 s displacement error is 0.164 m, so the net is worse than the filter at short horizons. — [disp_teacher NOTES](research/single_model/disp_teacher/NOTES.md)
- In-filter, B17 −0.173 [−0.448, −0.013] on HF folds 2-3 (selection-biased), but **server 0.992 m vs B16 0.782**. Teacher-in-filter "fixes B16's tails" (7 of 9 flights >1.5 m improve) and costs accuracy on typical flights. — [disp_teacher NOTES](research/single_model/disp_teacher/NOTES.md), [STUDENT_TEACHER](research/single_model/STUDENT_TEACHER.md)
- STLEARN (a larger displacement run, stopped) has teacher **992.4 M MAC** and students S100/S25/S6/S2 at 106/30/6.6/2.3 M MAC. The t2 reproduction reached 0.336 m (a safe subset, not an exact replay). No in-filter result. — [stlearn NOTES](research/single_model/stlearn/NOTES.md), `stlearn/tables/architecture.json`

**N2 learned odometry** (guard_fusion's learned estimator)
- On the selected 171 flights, N2 mean is 3.51 m, median 3.24 m, with 25 flights >5 m. For comparison, VINS is 5.51/0.62 and OpenVINS 28.5/0.58. It is a bounded but imprecise fallback. — `research/results/eval/guard-fusion/v2-safe/summary-s217.json`
- Its "error is uncorrelated with VIO error" (bounded at about 3.5 m on the 60 m pool). — [vio_fixes_and_yaw](research_notes/Drone%20VIO%20implementation%20plan/vio_fixes_and_yaw.md)

**New offline measurements (`learned_sel.json`)**
- lcJ vs HM40 filter at 37,284 anchors (156 st2dev flights, 13 scenes): Spearman correlation of error magnitudes is **0.21**. The net is better on 29% of anchors. A per-anchor min() oracle gives 0.108 vs filter 0.147 (−27%).
- Within-flight autocorrelation of error, demeaned, at anchor lags of 0.25 s each. Net: 0.66 / 0.43 / 0.11 / −0.03 at lags 1/2/4/8. Filter: 0.88 / 0.78 / 0.56 / 0.25 at the same lags, and about 0 at lag 20 (5 s). **The net's error is forgotten within about 1 s. The filter's error persists for about 2-5 s.**
- teacher4 vs v700b (36,972 matched anchors on st2dev, 55,458 on st3): component error correlation is **0.61-0.62**. An inverse-variance fusion of the two (0.170) is no better than teacher4 alone (0.170). Teacher4 is better on 68% of anchors, and on 0.376 vs 0.732 where v700b's error is >0.5.

### Inferences
- A learned model's value here comes from being an **independent second opinion that is accurate when the filter fails**, not from its average accuracy. Each net is a member of a two-member "filter + net" ensemble, already fused by the Kalman update. Ensembles of nets add little, because the nets share failure modes (corr 0.61). They also add net-to-net chaos.
- Direct-accuracy gains of ≤7% have never transferred in-filter (stlong +4-5%, learned_c n400 / K / 3-net ensemble worse). teacher4's −30% is a much larger change and has never been tested in-filter, so its transfer is unknown.
- Candidate roles:
  - Member/measurement: v700b (in use) and, conditionally, a width-1.5 student (untested).
  - Second-opinion/monitor: v700b disagreement, N2.
  - Avoid as members: gravity net, displacement nets, OpenVINS.

### Gaps
- No in-filter number for teacher4, teacher_final, the wide students, or any STLEARN model. The jobs were stopped.
- The net-vs-filter error table is for HM40 (an older base), not GSLV-linejac. GSLV's filter fails less often, so the net's comparative advantage is probably smaller there.
- No fuel/MAC measurement for teacher4. The fuel figures in Q2 are extrapolated.

## Q2. Can the big teachers be used despite fuel (time-sliced or amortised)?

### Takeaway
No, not at any rate that keeps their value. Even spread perfectly, teacher4 (est. 0.2-0.35 G per call) costs about 28 M per frame at the current 10-frame re-anchor period. At about 2 M per frame of free headroom, it could only fire once every 5-8 s. Our measurements show the re-anchor gain disappears at a 1.5 s period (P30 neutral). The displacement teacher, at about 1.27 G per call, is hopeless. The only viable route is a student of at most about 4-10 M MAC.

### Cited Findings
- Measured fuel/MAC conversion points:
  - lcJ: 1.79 M MAC → +4.7 M fuel per forward pass, about 2.6 fuel/MAC with int16-quantized conv. — [learned_c NOTES](research/single_model/learned_c/NOTES.md), [learnvel NOTES](research/single_model/learnvel/NOTES.md)
  - Displacement teacher: 400 M MAC → frame 1.27 G, about 3.1 fuel/MAC in f32 SIMD GEMM. — [disp_teacher NOTES](research/single_model/disp_teacher/NOTES.md)
  - Displacement student: 100 M MAC → 418 M peak frame, about 4 fuel/MAC including warp. — [disp_teacher NOTES](research/single_model/disp_teacher/NOTES.md)
- Time-slicing precedent: the gravity module runs 66 cost-aware micro-steps on the governor's leftover units with a delayed update (peak 3.42 M). The disp notes estimate that spreading the student over 4 frames gives about 110-150 M peak (not done). — [learnvel NOTES](research/single_model/learnvel/NOTES.md), [disp_teacher NOTES](research/single_model/disp_teacher/NOTES.md)
- Re-anchor period matters, from pooled HM40 dev results over 3 reps: P10S2 −6.1%, P20S2 −4.3%, P30S2 about neutral. — [learnvel NOTES](research/single_model/learnvel/NOTES.md)
- Filter error decorrelates over about 2-5 s, and failure bursts last seconds. For example, on 100-009 the filter's velocity error grows from 0.3 to 3.8 m/s over 3.6-9 s. — `learned_sel.json`; [filtcons NOTES](research/single_model/filtcons/NOTES.md)
- Extra peak budget does not pay by itself: the HM40 ladder buys 6-9% and saturates at about 8 M, with no ladder point positive in area. — [filtcons NOTES](research/single_model/filtcons/NOTES.md)

### Inferences (estimates)
Fuel per call is MAC × 2.6-4. Amortised per frame is that call cost / N.

| model | MAC | est. fuel/call | N=10 (0.5 s) | N=20 | N=100 (5 s) | N=200 |
|---|---|---|---|---|---|---|
| teacher4 / teacher_final | 83.6 M | 0.22-0.33 G | 22-33 M | 11-17 M | 2.2-3.3 M | 1.1-1.7 M |
| disp teacher (measured frame) | ~400 M | 1.27 G | 127 M | 64 M | 12.7 M | 6.4 M |
| STLEARN teacher | 992 M | 2.6-4 G | 260-400 M | — | 26-40 M | 13-20 M |
| disp student s3 / S100 | 100-106 M | 0.3-0.42 G | 30-42 M | 15-21 M | 3-4 M | 1.5-2 M |
| S25 | 30 M | 80-120 M | 8-12 M | 4-6 M | ~1 M | — |
| wide student (w1.5) | 3.56 M | 9-14 M | 0.9-1.4 M | — | — | — |

- Break-even ATE cut for raising the peak from 4.3 M to P is 1 − (P/4.3)^−0.125. That gives 8% at 8.6 M, 16% at 17 M, 23% at 34 M and 35% at 130 M.
  - teacher4 at N=10 needs a ≥20% ATE cut. Measured re-anchor gains are 3-12% in total, with a direct-accuracy gain whose in-filter value is unproven.
- At N ≥ 100, teacher4 fits within about 2-3 M/frame of headroom. That headroom is approximate: the peak is 4.2-4.3 M and p99 is about 3.2 M on GSLV-linejac, so free per-frame headroom is probably 1-2 M; the median frame is not logged here.
  - At one call per 5 s the re-anchor is at a rate already shown to be neutral (P30 = 1.5 s).
  - The measurement would also be 5 s stale. It needs the anchor's state clone to still be in the window, which is not checked (TC_MAXANCH=400 anchors exist, but the cost of the cross-covariance is unknown).
- A "teacher on demand" (call only when a monitor fires) still has a latency of about N frames, i.e. seconds, and arrives after the position damage. Multihyp shows that damage persists in raw ATE.
- The realistic paths are:
  1. A width-1.5 student (3.6 M MAC, direct −7%) screened in-filter now. Its C code exists and switch-off identity passed.
  2. Students in the S6/S25 range (6.6-30 M MAC, i.e. 17-120 M per call) re-trained from teacher4 targets, spread over 10 frames: about 2-12 M per frame. S6 is the only one that plausibly stays under about 6 M peak.

### Gaps
- Fuel/MAC for an 83 M MAC conv net in our SIMD int16 kernel is not measured. The stlong width-1.5 C kernel's peak was also never measured.
- No experiment tested a delayed (multi-second-stale) velocity update in the MSCKF.

## Q3. A learned weighting/selector: signals, data, label, model, evidence

### Takeaway
A tiny per-anchor selector is learnable from existing logs: AUC about 0.83 with scene-held-out CV, using 6 causal features, logistic regression (~15 ops) or 60 stumps (~120 ops). But most of its signal is the filter's own velocity covariance (Pv alone gives AUC 0.81), which the Kalman update already uses. A hard switch to the net on the top 10% of anchors cuts anchor velocity error only from 0.147 to 0.136 (−7.5%), against a −27% oracle. A learned *re-weighting of the net's sigma* (Pv/live/speed-dependent re-anchor strength) is the plausible form. **A new logging run on the shipped build is needed:** no per-frame logs exist for GSLV or GSLV-linejac.

### Cited Findings
- Logged signals and where they exist (all single-rep, st2dev unless noted):
  - **TC_LOG 'D'** per frame: f, t, live, used, u20, att, gate, tri, nis, sp, psp, nanch, fire, Pv, v, p. Present in `lv_hm40log` (HM40, 156 st2dev), `fc_nlog`/`fc_nlog2`/`fc_nlog3` (156), `fc_nlog4` (30), `fc_nlog5`/`fc_nlog6` (st2bad+st2good, 60), `lv_dbg2`/`lv_dbg3`/`lv_RS16dbg` (single flights). `u20` is always 0 because tc_used is never incremented in sa.c. — `research/results/single_model/*/…/stderr.txt`, [filtcons NOTES](research/single_model/filtcons/NOTES.md)
  - **FC_LOG** 'N' per frame: camera position/velocity and covariances in the output frame, yaw/tilt/bias variance, gravity direction. 'L' per re-anchor: net mu/sd and filter V_K plus covariance. 'FO' per feature: clone-pose residual (nlog6). Logging does not change outputs. — [filtcons NOTES](research/single_model/filtcons/NOTES.md)
  - **GSLM-era debug** (`gs_dA`, `gs_eBd`, 156 st2dev): 'G' lines (live, mean intensity, black fraction, g8/g20 gradient texture, edges, rows, used) plus D lines. `gs_ln*` / `gs_lv*` add 'L'/'K' line-feature lines (few flights). — directory scan of `research/results/single_model/`
  - **LV_DBG 'E'** (accel/gyro bias, gravity Rz): single-flight debugging only. — [learnvel NOTES](research/single_model/learnvel/NOTES.md)
  - **multihyp 'M'** (windowed NIS, nisk, pn, fs, fn) plus D: `mh_h0`/`h0r`/`h1`/`h2` on 171 selected flights, and `fresh_mh_*` on fresh 711 (includes fold 4, so do not use for training). — [multihyp NOTES](research/single_model/multihyp/NOTES.md)
- Data size: st2dev has 156 flights, about 1200 frames and about 239 re-anchor anchors per flight, so about 187 k frames and 37 k anchors per logged build, but only **13 scenes**. — `learned_sel.json`
- Selector experiment (`learned_sel.py`):
  - Label: filter error − net error > 0.1 m/s (10.6% positive).
  - Features: log live, log Pv, log net sigma, net speed, texture, log(sigma/Pv). CV: 5 scene-hash folds.
  - AUC: logistic 0.833, 60 stumps 0.834, Pv alone 0.815, live alone 0.69, net speed alone 0.62.
  - Hard selection, top 10%: 0.136-0.137 vs filter 0.147, net 0.255, oracle 0.108.
- Earlier evidence:
  - Net-vs-filter disagreement as a failure monitor: AUC for ATE >1 m is 0.81/0.87/0.95 from the first 6/10/20 s, and flags 8/9 bad flights with 0/98 false alarms. Detection comes only after the error is already 1.25-3.9 m. — [LOOP_LOG](research/single_model/LOOP_LOG.md) l.112
  - Multihyp: accepted-feature rate over 3/5 s chooses the better hypothesis with 85%/93% accuracy (non-causal, whole-flight). — [multihyp NOTES](research/single_model/multihyp/NOTES.md)
  - NEES: flights with ATE >1 have median velocity NEES 6.3 vs 2.5 on flights with ATE <0.5, and a starved fraction of 0.70 vs 0.14. — [filtcons NOTES](research/single_model/filtcons/NOTES.md)
- Hand-tuned reweightings of the net's sigma have all been neutral or worse:
  - resp12 (floor + 0.12·speed): 0.692 vs 0.660, worse.
  - resp06: neutral.
  - Chi2 gate: worse.
  - LV_RESET: no gain.
  - The useful reweight was blunt: sigma ×3 at period 10.
  — [filtcons NOTES](research/single_model/filtcons/NOTES.md), [learnvel NOTES](research/single_model/learnvel/NOTES.md)

### Inferences
- The best label for ATE is *per-anchor velocity-error advantage* (as above) or segment RPE over 1-2 s. A whole-flight choice is wrong (see Q4). Failure-onset labels are rare (about 4% of anchors with filter error >0.5) and come late.
- Best form: a learned function sigma_net_eff = f(Pv, live, net sigma, net speed, texture, NIS), applied at each periodic re-anchor (~1 k ops, about 0 fuel). It replaces the fixed ×3 and is trained offline to minimise post-update velocity error, or tuned in-filter on a few parameters. A hard selector of output poses is not recommended: raw ATE punishes switching.
- Given that hand-shaped sigma rules failed, expected gain is small (estimated 0-5%). The noise floor is about ±3.5% per rep on st2dev, so 3 reps on ≥390 flights are needed.
- **New logging run needed:**
  - Rebuild GSLV-linejac with TC_LOG+FC_LOG and the fc_uring u20 fix, logging off-switch verified byte-identical.
  - Run on st2dev+st3+st2conf+fresh f0-3+st1 (about 1,450 flights, about 1.7 M frames, 290 k anchors, more than 113 scenes), with 1-3 reps.
  - Estimated cost: about 2 min per 156 flights at 32 workers, i.e. about 20-40 min at 24 workers per rep.
  - Also log v700b's raw mu/sigma at every anchor, plus filter V_K/Pv, so the weighting can be fit without rerunning.

### Gaps
- Selector evidence is velocity-level on HM40, not ATE-level on GSLV. There are only 13 st2dev scenes, so the AUC may not transfer.
- No experiment has tested a learned (vs hand-shaped) re-anchor sigma in-filter.

## Q4. Lessons from guard_fusion, multihyp and the self-ensemble on causal selection failure

### Takeaway
Hindsight best-of-K bounds are inflated by chaos (winner's curse). Causal selection recovers little of them, and whole-flight or late switches are punished by raw unaligned ATE, because position error already emitted stays. Selection works only as continuous, per-frame, soft fusion of sources whose errors are independent. That is exactly what the periodic net re-anchor is.

### Cited Findings
- **Multihyp** (fresh 711, B6):
  - Oracle (h0, h0r), where h0r is the same filter nudged, is 0.552 vs 0.618. That is −11% from pure chaos.
  - All-four oracle 0.426.
  - Causal splice at 1/1.5/3 s gives 0.650/0.666/0.682, all worse than B6.
  - The perfect-oracle switch gain decays from −0.122 at t=0 to −0.052 at 1 s and 0 at 3 s.
  — [multihyp NOTES](research/single_model/multihyp/NOTES.md)
- **guard_fusion** (VINS-Mono, OpenVINS, N2; 171 selected flights):
  - Per-flight 3-source oracle 0.759 mean / 0.464 median. Causal policies: held-out means 0.97-1.01, medians 0.475-0.479.
  - G1 fails: the policy is no worse than the best single source on only about 50% of flights (target 70%).
  - Of 7 held-out flights >5 m: 4 have both VIOs bad, 3 select the wrong VIO, and 5 also have a bad learned fallback. "The dominant remaining issue is sustained source selection, not switch smoothing."
  - The 75 candidate rules were pre-declared, with scene-disjoint fold selection.
  — [guard_fusion README](research/guard_fusion/README.md)
- **Self-ensemble** of GSLV chaos replicas (ens.py):
  - Causal per-frame mean/median: st2conf 0.333 → 0.310/0.318 (−5 to −7%), fconf −6%. Hindsight best-of-3 is −16%.
  - Break-even for 3× fuel is about −18%.
  - OpenVINS as a member: mean 143 m on st2conf, better than GSLV on 2/84 flights. Dead.
  — [LOOP_LOG](research/single_model/LOOP_LOG.md), `research/single_model/ensemble/ens.py`
- B17 was the best of about 10 variants on 56 flights and lost on the server. The proxy and HF sets do not reproduce the server's startup-offset failure. — [disp_teacher NOTES](research/single_model/disp_teacher/NOTES.md), [proxy NOTES](research/single_model/proxy/NOTES.md)

### Inferences
- Any reported "oracle" must subtract a chaos control (same build, nudged).
- A learned selector must be judged causally, on scene-held-out pools, with ≥3 reps. It is preferable to fuse members continuously rather than switch whole flights or segments.
- Members must have *independent* errors that are accurate in the filter's failure regime. The velocity net meets this (Spearman 0.21; decorrelates in about 1 s). Chaos replicas partly do (−6% causal) but cost 3× fuel. Teacher/student pairs and net ensembles do not (corr 0.61).
- Startup is the one regime where no causal selector can help after the fact. Improvements there must come from a better first estimate (lcJ/S2 class), not from selection.

### Gaps
- No causal soft-fusion test exists of net-derived positions (vs velocity re-anchors) against the filter output.
- No local set reproduces the server's startup-offset failures, so selector gains on that mode cannot be validated locally.
