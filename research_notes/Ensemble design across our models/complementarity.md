# Ensemble complementarity of our existing estimator builds (measured from logged estimate.tum only)

Scope and method (applies to every section). Everything below is **measured** from per-flight `estimate.tum` files already on disk, except items explicitly labelled *estimate*. No new estimator runs; no holdout_* dirs, no fold 4, no server data. Ground truth = `episodes([zip]).ground_truth_state()[:, :3]`, aligned by frame index (20 Hz) and truncated to the shorter length, as in the existing `ens.py`. Metric = per-flight unaligned position RMSE (m), averaged over flights (the team metric). Scripts (new, all in `research/single_model/ensemble/`): `inventory.py` (coverage), `comp.py POOL` (per-flight metrics, 48 workers), `comp_report.py POOL [DEVPOOL]` (tables), `shortlist.py` (cross-pool candidates). Outputs: `inventory.json`, `comp_<pool>.pkl`, `comp_summary_<pool>.json`, `rep_<pool>.txt`, `shortlist.json`. Nothing left running.

Definitions used in the tables:
- **Family** = one mechanism-distinct build; up to 3 chaos replicas r0/r1/r2 (r1: PIXEL_STD 1.515, DETECT_MIN_SCORE 1010; r2: 1.485/990 — the standard rep nudges, [learnvel NOTES](research/single_model/learnvel/NOTES.md)).
- Every family-set metric is computed for replica index i = 0,1,2 (each member uses its own r_i; single-rep families reuse r0) and averaged over i, so every number is a 3-draw average rather than one chaotic draw.
- **corr** = Pearson correlation of per-flight log-ATE between two families (avg over i). **EVC** = per-flight error-vector correlation Σ(e_a·e_b)/sqrt(Σ|e_a|²Σ|e_b|²), averaged over flights (how much per-frame averaging can cancel).
- **hind** = per-flight hindsight best-of-K; **w5s/w1s/frame** = oracle that picks the best member per 5 s / 1 s window / per frame (ceiling for a causal selector, not achievable). **Causal** = per-frame mean, median (K≥3), medoid (K≥3: member closest to the others at each frame). Gains "g" are relative to the **best single member's** pool mean (3-rep mean).
- **Tail** = worst 10 % of flights in the pool by GSLV (3-rep mean ATE) — HFG on probe.
- *Estimated* score: tier1m area formula from [LOOP_LOG](research/single_model/LOOP_LOG.md): Δ = −2.24·ln(ATE_ens/ATE_ref) + 0.28·log2(peak_ref/peak_ens), with peak_ens = **sum of member peaks** (upper bound; peaks approximate, from NOTES). Break-even by my arithmetic: 2× fuel needs ≥11.7 % ATE cut, 3× needs ≥18.0 %, 4× needs ≥22.0 %.

## 1. Which build families have per-flight estimates on shared pools (coverage)

### Takeaway
Of 1,867 result dirs, 1,000+ runs have estimate.tum on the eight shared pools, but mechanism diversity concentrates on **st2dev (156 flights) / st2conf (84)**: 15 families × 3 replicas there, plus stlong learned-net variants (st2dev) and OpenVINS (st2conf). st3 (234) has 11 families; st1dev/st1conf 12 (many single-rep); fdev (475)/fconf (107) only the 4 line-based families (GSLV/LJA/LJB4/GSLM); probe (57) only pre-GSLM builds.

### Cited Findings
- Pool sizes: st2dev 156, st2conf 84, st1dev 244 (221 usable with all families), st1conf 156 (141 usable), probe 57, fdev 475, fconf 107, st3 234 — [inventory.json](research/single_model/ensemble/inventory.json), [comp_run.log](research/single_model/ensemble/comp_run.log). On st1, 23/15 flights lack st_* (HFG/C30/B17X/GB6) runs and were dropped.
- Runs with estimates per pool (excl. holdout_*): st2dev 267, st2conf 126, st3 60, st1dev/st1conf 31, probe 12, fdev/fconf 12 — [inventory.json](research/single_model/ensemble/inventory.json).
- Family → run dirs used (all under `research/results/single_model/` unless noted; mechanism from NOTES):

| Family | Runs (r0,r1,r2) | Mechanism | ~peak | Pools covered |
|---|---|---|---|---|
| GSLV | lv_glNP{,_r1,_r2} | GSLM + periodic v700b-net re-anchor + gyro-bias clamp (numeric line Jacobians) | 6.0–7.4 M | st2dev, st2conf, st3, st1dev/conf, fdev, fconf |
| LJA | lj_ajc{,_r1,_r2} | GSLV + exact analytic line Jacobians (= submitted build, server 0.633 @ 4.2 M) | 4.3–5.0 M | same as GSLV |
| LJB4 | lj_ajgb4{,…} | LJA + measured-cost governor, 3.4 M budget | 4.1 M | same as GSLV |
| GSLM | lv_gl{,…} | RSOFT + 3-D lines + Manhattan constraints + KLT_VEL | ~7 M | same as GSLV |
| LGVHY | gs_lgVHY{,…} | earlier lines+Manhattan (PIX 1) on HM40 | ~7 M | st2dev/conf (3 reps), st1 (1 rep) |
| LYPK | gs_lYpK | lgVHY + PIX 0.5 + KLT_VEL (pre-GSLM) | 6.6–7.5 M | st1 only (1 rep) used |
| RSOFT | fc_rsoft1t0{,…}; lv_rs on st3; fc_rsoft1t0s on st1 | HM40 + soft down-weighting of >1 px features (no lines) | 4.0 M | st2, st3, st1 (1 rep) |
| RSLV | lv_rsNP10B | RSOFT + v700b net periodic re-anchor (no lines) | ~4 M | st3 |
| HM40 | st_hm40 (st2); lv_hm40 (st3); fc_hm40/gs_hm40b(st1) | HFG + TC_MAXANCH 40 (m40s1) | 4.0 M | st2, st3, st1 |
| HM40P | lv_P10S2 | HM40 + periodic lcJ re-anchor | 4.0 M | st3 |
| HFG | st_hfg{,…} | T4uB + harden + gate off (server 0.948) | 4.0 M | st2, st1, probe |
| B17X | st_b17x, fc_b17x_r1/_r2 | B17 exact (full fuel, no m40s1, no lines) | 16.1 M | st2, st1 (1 rep), probe |
| BM40 | fc_Bm40s1{,…} | B17 + m40s1 | 15.3 M | st2 |
| EDGE | gs_eB{,…} | HM40 + always-on edgelets | 5.4 M | st2 |
| KV1 | gs_kv1{,…} | HM40 + KLT_VEL=1 | 4.0 M | st2 |
| G24M | st_G24m{,…} | low-fuel cheap rows (2.4 M budget) + m40s1 | ~3 M | st2 |
| C30M / C30 | st_C30m{,…} / st_C30{,…} | cheap rows 3.0 M budget (+/− m40s1) | ~4 M | st2 / st1, probe |
| L8 | fc_L8{,…} | HM40 at GOV_B 7.2 M | ~7 M | st2 |
| GB6, K30, C34 | st_GB6, st_K30, st_C34 | HFG at 6 M budget; cheap-row variants | 4–6 M | probe (+st1 GB6) |
| SLBASE/SLPILOT/SLPMM | `research/single_model/stlong/results/{baseline,pilot,pilot_mm}` | GSLV with retrained / distilled student velocity nets (learned-net variants) | ~7 M | st2dev, st3 (1 rep each) |
| OVINS | lv_ovins | OpenVINS baseline | ~4.2 G | st2conf only |

  Sources: [learnvel NOTES](research/single_model/learnvel/NOTES.md), [geomstarve NOTES](research/single_model/geomstarve/NOTES.md), [filtcons NOTES](research/single_model/filtcons/NOTES.md), [servertail NOTES](research/single_model/servertail/NOTES.md), [linejac NOTES](research/single_model/linejac/NOTES.md), [stlong NOTES](research/single_model/stlong/NOTES.md), [LOOP_LOG](research/single_model/LOOP_LOG.md).
- Single-family pool means (3-rep mean) reproduce the NOTES: e.g. st2dev GSLV 0.4154 / GSLM 0.4553 / HM40 0.6604; st2conf GSLV 0.3334 / LJA 0.3438; st3 GSLV 0.4156; fconf GSLV 0.2701 — [rep_st2dev.txt](research/single_model/ensemble/rep_st2dev.txt), [rep_st2conf.txt](research/single_model/ensemble/rep_st2conf.txt), [rep_st3.txt](research/single_model/ensemble/rep_st3.txt), [rep_fconf.txt](research/single_model/ensemble/rep_fconf.txt); matches [learnvel NOTES](research/single_model/learnvel/NOTES.md) FINAL table (0.4154/0.4553, 0.3334, 0.4156, 0.2701).
- Not usable for ensembling: tier1m T4uB/G24 low-fuel and audit (aud_*), atepush (ap_*) runs are on fresh-711 / fresh pools that include fold 4 or are not among the shared pools (no estimates on the 8 pools in the inventory) — [inventory.json](research/single_model/ensemble/inventory.json).

### Inferences
- The only pools where line-based (GSLV-generation) and no-line (RSOFT/HM40/HFG/B17-generation) families coexist with 3 replicas are st2dev, st2conf and st3; conclusions about mechanism diversity rest mainly on these 474 flights (and st1 with mostly single-rep old builds).
- G24M/C30M are the only low-fuel (≤4 M) "cheap-row" builds with st2 coverage; there is no T4uB/G24 run on any shared pool.

### Gaps
- No stlong final students (teacher_final/wide0-2) had in-filter estimates on disk at analysis time (only baseline/pilot/pilot_mm).
- HM40 "replicas" on st1 are fc_hm40 + gs_hm40b + gs_hm40b_r1, where gs_hm40b is byte-identical to HM40 r0 → only 2 distinct draws (median/medoid = r0 there).

## 2. Measured complementarity: correlation, hindsight, segment oracle, causal fusion (mean and tail)

### Takeaway
Low correlation exists only **between generations** (line-based GSLV/LJA/GSLM vs old no-line builds, log-ATE corr 0.51–0.62 on st2conf), and every pair that meets "corr < 0.6 and hindsight ≥ 12 %" is made of **old/weak builds** (B17X/BM40 × RSOFT/EDGE/KV1/HM40…) whose fused result (≥0.41 m) is still worse than GSLV alone (0.333). Pairs/triples that include GSLV or LJA reach hindsight gains of 9–19 % but **causal** gains of only 0–8 %, and causal fusion barely helps (often hurts) the worst-10 % tail; only the oracle selectors (1–5 s windows: 16–27 %) show large headroom.

### Cited Findings
- **Correlation structure (st2conf, log-ATE corr):** GSLV–LJA 0.93, GSLV–LJB4 0.85, GSLV–GSLM 0.76, GSLV–LGVHY 0.71; GSLV vs RSOFT/HM40/HFG/B17X/BM40/EDGE/G24M/C30M/L8 0.50–0.57; among old builds 0.69–0.94 (HM40–HFG 0.90, B17X–BM40 0.94). Error-vector corr GSLV–LJA 0.88, GSLV–GSLM 0.71, GSLV–old 0.53–0.58 — [rep_st2conf.txt](research/single_model/ensemble/rep_st2conf.txt).
- **On the harder dev pools correlations are much higher**: st2dev log-ATE corr is 0.72–0.96 for every family pair (GSLV vs old 0.73–0.81; no pair < 0.6); st3 0.77–0.96 — hard starved flights are hard for every build — [rep_st2dev.txt](research/single_model/ensemble/rep_st2dev.txt), [rep_st3.txt](research/single_model/ensemble/rep_st3.txt). No pair < 0.6 on st1dev, st1conf, fdev, fconf, probe either.
- **Pairs meeting corr<0.6 and hindsight ≥12 % (st2conf only)**, best-member ref / hindsight / 1 s oracle / causal mean: B17X+EDGE 0.457 → 0.367 (−19.9 %) / 0.338 (−26.1 %) / 0.416 (−9.0 %); RSOFT+B17X 0.451 → 0.362 (−19.8 %) / 0.336 / 0.412 (−8.5 %); BM40+EDGE −19.9 % / −25.8 % / −8.3 %; BM40+KV1 −18.8 % / −24.2 % / −7.2 %; RSOFT+BM40 −17.9 % / −24.2 % / −7.1 %; HM40+B17X −19.0 % / −25.0 % / −5.5 %; B17X+G24M −19.1 % / −25.0 % / −4.9 % (17 pairs total) — [rep_st2conf.txt](research/single_model/ensemble/rep_st2conf.txt).
- Same weak pairs on st2dev (corr 0.75–0.80 there): B17X+EDGE hindsight −22.2 %, causal mean −10.3 %; B17X+C30M −23.3 % / −8.2 % — [rep_st2dev.txt](research/single_model/ensemble/rep_st2dev.txt).
- **Pairs containing the best family** (causal = per-frame mean):
  - st2conf (GSLV best): GSLV+GSLM hind −14.0 %, 1 s oracle −19.0 %, causal −4.3 % (0.318); GSLV+LJB4 −9.3 % / −13.7 % / −2.3 %; GSLV+LJA −4.6 % / −7.1 % / ±0 %; GSLV+B17X (corr 0.55) −11.0 % / −17.3 % / **+7.9 % worse**; GSLV+RSOFT (0.57) −9.9 % / −16.1 % / +5.9 % worse — [rep_st2conf.txt](research/single_model/ensemble/rep_st2conf.txt).
  - st2dev (LJA best, 0.4086): LJA+SLPMM hind −12.7 %, causal −6.3 %; LJA+GSLM −11.4 % / −3.9 %; GSLV+LJA −5.4 % / −1.7 % — [rep_st2dev.txt](research/single_model/ensemble/rep_st2dev.txt).
  - st3 (GSLV best): GSLV+{SLBASE,SLPILOT,LJB4,GSLM,SLPMM} hindsight −11 to −12 %, causal −0.4 % to +3.0 %; GSLV+RSLV causal +7.8 % worse — [rep_st3.txt](research/single_model/ensemble/rep_st3.txt).
  - fconf: LJA+GSLM hind −11.0 %, causal ±0 %; GSLV+LJA −5.2 % / −1.8 % — [rep_fconf.txt](research/single_model/ensemble/rep_fconf.txt). st1conf: GSLV+GSLM −9.1 % / −4.8 %; GSLV+B17X −11.9 % / −2.5 % — [rep_st1conf.txt](research/single_model/ensemble/rep_st1conf.txt).
- **Triples with the best family**: st2conf GSLV+LJB4+GSLM hindsight −18.8 %, 1 s oracle −25.9 %, causal mean −5.3 % (0.315); GSLV+GSLM+B17X −18.4 % / −26.7 % / median −5.3 % (0.315); st3 best causal triple GSLV+SLBASE+SLPILOT −4.9 % (median); st1dev LJA+LJB4+B17X median −6.5 %; fconf GSLV+LJA+GSLM −2.9 % — [rep_st2conf.txt](research/single_model/ensemble/rep_st2conf.txt), [rep_st3.txt](research/single_model/ensemble/rep_st3.txt), [rep_st1dev.txt](research/single_model/ensemble/rep_st1dev.txt), [rep_fconf.txt](research/single_model/ensemble/rep_fconf.txt).
- **K=4**: best absolute causal on st2conf GSLV+LJB4+GSLM+B17X median 0.312 (−6.3 % vs GSLV; hindsight −22.0 %, 1 s oracle −31.9 %); best relative gain RSOFT+B17X+EDGE+KV1 median −13.9 % but absolute 0.387 — [rep_st2conf.txt](research/single_model/ensemble/rep_st2conf.txt). st2dev best absolute K=4: LJA+BM40+SLPILOT+SLPMM median 0.371 (−8.6 %) — [rep_st2dev.txt](research/single_model/ensemble/rep_st2dev.txt).
- **Causal median vs mean vs medoid**: for K=3/4 sets mixing quality levels the median beats the mean (e.g. GSLV+GSLM+B17X mean −0.6 % vs median −5.3 % on st2conf); the medoid is consistently 1–3 points worse than the median — [rep_st2conf.txt](research/single_model/ensemble/rep_st2conf.txt).
- **Fixed-weight pair blends transfer dev→conf** (w chosen on dev, w ∈ {0,…,1}): chosen weights are 0.4–0.7 and conf gains equal the w=0.5 gains within ~1 point (st2dev→st2conf B17X+EDGE +9.0 %, RSOFT+B17X +8.5 %; fdev→fconf LJA+GSLM +1.4 %, GSLV+GSLM +1.2 %; st2dev→st3 GSLV+SLBASE +3.8 %) — [rep_st2conf.txt](research/single_model/ensemble/rep_st2conf.txt), [rep_fconf.txt](research/single_model/ensemble/rep_fconf.txt), [rep_st3.txt](research/single_model/ensemble/rep_st3.txt).
- **Tail (worst 10 % by GSLV)**: hindsight still helps the tail (st2conf GSLV+GSLM+B17X tail 0.703 → 0.543, −22.7 %; GSLV+B17X −20.7 %), but causal fusion does not: GSLV+GSLM tail 0.720 (best member) → 0.790 mean (−9.6 % i.e. worse); GSLV+LJB4+GSLM 0.720 → 0.839 (−16.5 % worse); GSLV+GSLM+B17X median 0.698 (+0.7 %). On st2dev, LJA+KV1+SLPMM median gives tail +11.1 % and LJA+BM40+SLPMM +7.5 % (largest causal tail gains with the best family) — [rep_st2conf.txt](research/single_model/ensemble/rep_st2conf.txt), [rep_st2dev.txt](research/single_model/ensemble/rep_st2dev.txt).
- **OpenVINS** (st2conf): lowest correlations of all (log-ATE corr 0.26–0.32 with our builds) yet hindsight gain only +1.7–2.7 % and any causal fusion explodes (OpenVINS mean 143 m, 36/84 flights >3 m, NaN frames) — [rep_st2conf.txt](research/single_model/ensemble/rep_st2conf.txt), [LOOP_LOG](research/single_model/LOOP_LOG.md).

### Inferences
- Low log-ATE correlation is a poor selection criterion here: it is mostly produced by *quality gaps* (a much weaker member fails on different flights), which raises the best-of-K oracle but drags a causal mean toward the weak member. OpenVINS is the extreme case (corr ~0.3, useless). The "corr<0.6 & ≥12 % hindsight" filter selects only old-generation pairs.
- Causal fusion gains scale with *similar-quality* members with moderate EVC (~0.7–0.78), not with the lowest correlation.
- The 1 s / 5 s oracle exceeds per-flight hindsight by ~5–8 points, so there is within-flight switching headroom (−16 to −27 % with GSLV-including sets), but realising it needs a causal quality signal that none of the measured fusions (mean/median/medoid) provides; on tails, median/mean is roughly neutral to harmful.

### Gaps
- No causal *selector* using filter-internal quality signals (Pv, live-feature count, net-vs-filter disagreement) could be tested: those signals are not logged alongside these estimates on the shared pools (twist.txt exists, not evaluated).
- Tail statistics use only 8–23 flights per pool; tail gains swing ±10 points between pools.

## 3. Replicate (chaos) diversity vs mechanism diversity

### Takeaway
Chaos replicas of the *same* build (PIXEL_STD/DETECT_MIN_SCORE nudges) are about as complementary as different mechanisms: GSLV r0/r1/r2 have log-ATE corr 0.83–0.91 and EVC 0.72–0.80 — *lower* than GSLV vs LJA (0.93–0.96 / 0.87–0.89) — and a 3-replica causal mean (−5.7 to −9.1 %) matches or beats every mechanism-diverse triple that includes GSLV (−2.9 to −8.6 %). Hindsight best-of-3 replicas is −14 to −18 %, the same as mechanism triples.

### Cited Findings
- Replica log-ATE corr / EVC: GSLV st2dev 0.90/0.76, st2conf 0.83/0.77, st3 0.91/0.80, fconf 0.87/0.79; B17X/BM40 replicas are the most deterministic (0.87–0.95 / 0.87) — [rep_st2dev.txt](research/single_model/ensemble/rep_st2dev.txt), [rep_st2conf.txt](research/single_model/ensemble/rep_st2conf.txt), [rep_st3.txt](research/single_model/ensemble/rep_st3.txt), [rep_fconf.txt](research/single_model/ensemble/rep_fconf.txt).
- GSLV 3-replica ensembles (avg single → hind3 / 1 s oracle / causal mean3 / median3 / mean of 2 reps / tail mean3):
  - st2dev 0.4154 → 0.341 (−17.8 %) / 0.306 (−26.4 %) / 0.378 (−9.1 %) / 0.383 (−7.8 %) / −7.4 % / tail 1.443 → 1.264 (−12.4 %)
  - st2conf 0.3334 → 0.279 (−16.4 %) / −23.1 % / 0.310 (−7.0 %) / −4.5 % / −3.0 % / tail −3.5 %
  - st3 0.4156 → −17.0 % / −23.1 % / −6.7 % / −6.8 % / −2.9 % / tail −7.2 %
  - st1dev −14.7 % / −23.5 % / −8.8 %; st1conf −14.4 % / −21.7 % / −6.4 %; fdev −16.9 % / −24.1 % / −6.8 %; fconf −14.0 % / −20.9 % / −5.7 %
  — [rep_*.txt](research/single_model/ensemble/) (replicate section in each).
- LJA 3-replica mean: st2dev −8.4 %, st2conf −6.1 %, st3 −7.7 %, st1conf −11.4 % (tail −20.3 %, driven by one flight), fdev −6.9 %, fconf −6.4 % — same files.
- Equal-K comparison, causal mean vs avg single (st2conf): GSLV r0+r1 −3.0 % vs GSLV+GSLM pair −4.3 % (vs GSLV); 3 GSLV reps −7.0 % vs best mechanism triple with GSLV −5.3 %. st3: GSLV r0+r1 −2.9 % vs best GSLV pair −3.0 %; 3 reps −6.7 % vs best triple −4.9 % — [rep_st2conf.txt](research/single_model/ensemble/rep_st2conf.txt), [rep_st3.txt](research/single_model/ensemble/rep_st3.txt).
- Earlier logged 6-run ensemble (3 GSLV + 3 GSLM reps) gave only −8 % causal vs −5 to −7 % for 3 GSLV reps — [LOOP_LOG](research/single_model/LOOP_LOG.md) (ENSEMBLE FEASIBILITY entry).
- stlong learned-net variants behave like replicas: GSLV vs SLBASE/SLPILOT/SLPMM log-ATE corr 0.86–0.89 (st2dev, st3), EVC 0.72–0.76; LJA+SLPMM causal −6.3 % on st2dev but GSLV+SLPMM −0.4 % on st3 (no consistent gain) — [rep_st2dev.txt](research/single_model/ensemble/rep_st2dev.txt), [rep_st3.txt](research/single_model/ensemble/rep_st3.txt).

### Inferences
- The per-flight chaos of the filter (one-pixel-noise nudges flip which flight blows up) is the dominant source of exploitable diversity; mechanism changes within the line generation (numeric→analytic Jacobians) produce *less* diversity than a replica nudge because LJA r_i and GSLV r_i share the same nudge and nearly the same trajectory.
- Consequently the cheapest "ensemble" design is K perturbed copies of the best build, not a mix of builds; a mix only helps when members are of comparable accuracy (GSLV/LJA/LJB4/GSLM).

### Gaps
- Whether replicas could share the front end (KLT, detection) and duplicate only the filter is untested; the fuel cost of a K-replica ensemble is therefore only bounded (≤ K× peak), not measured.

## 4. Ranked shortlist of ensemble member sets (hindsight and simple causal gains)

### Takeaway
Ranked by causal gain over the deployed single build LJA, the best sets are: (1) 3 GSLV replicas (−5.0 to −9.8 %), (2) GSLV+LJB4+GSLM / LJA+LJB4+GSLM / GSLV+LJA+GSLM triples (−3 to −9 %), (3) 3 LJA replicas (−6 to −11 %), (4) mechanism pairs with GSLM (−0 to −7 %). None reaches the fuel break-even (≥11.7 % for 2×, ≥18 % for 3×); *estimated* score deltas are −0.11 to −0.48 for every candidate on every pool. Hindsight (−14 to −19 %) and 1–5 s oracle selection (−20 to −27 %) would pay only if a causal selector captured most of that headroom.

### Cited Findings
- Cross-pool shortlist (causal ATE, Δ vs LJA 3-rep single; hindsight; *estimated* area Δ with summed peaks) — [shortlist.py output / shortlist.json](research/single_model/ensemble/shortlist.json):

| Candidate (K, ~sum peak) | st2dev (LJA 0.409) | st2conf (0.344) | st3 (0.421) | st1conf (0.239) | fdev (0.256) | fconf (0.268) |
|---|---|---|---|---|---|---|
| GSLV ×3 reps, mean/median (3, ~20 M) | 0.378 −7.6 % / hind 0.341 / est −0.41 | 0.310 −9.8 % / 0.279 / −0.35 | 0.387 −8.0 % / 0.345 / −0.40 | 0.218 −8.9 % / −0.38 | 0.239 −6.4 % / −0.44 | 0.255 −5.0 % / −0.47 |
| LJA ×3 reps (3, ~14 M) | 0.374 −8.4 % / 0.338 / −0.25 | 0.323 −6.1 % / 0.290 / −0.30 | 0.389 −7.7 % / −0.27 | 0.212 −11.4 % / −0.17 | 0.237 −7.4 % / −0.27 | 0.251 −6.4 % / −0.30 |
| LJA r0+r1 mean (2, ~9.6 M) | −6.2 % / −0.14 | −4.5 % / −0.18 | −6.3 % / −0.14 | −5.0 % / −0.16 | −4.9 % / −0.17 | −4.6 % / −0.17 |
| GSLV+LJB4+GSLM (3, ~18 M) | 0.389 −4.8 % / 0.346 / −0.42 | 0.315 −8.3 % / 0.270 / −0.34 | 0.401 −4.9 % / −0.42 | 0.219 −8.6 % / −0.33 | 0.238 −6.8 % / −0.37 | 0.259 −3.4 % / −0.46 |
| LJA+LJB4+GSLM (3, ~16 M) | 0.385 −5.8 % / 0.342 / −0.35 | 0.319 −7.2 % / 0.276 / −0.32 | 0.403 −4.3 % / −0.38 | 0.217 −9.1 % / −0.27 | 0.238 −6.9 % / −0.32 | 0.260 −3.0 % / −0.41 |
| GSLV+LJA+GSLM (3, ~19 M) | −5.2 % / −0.43 | −7.4 % / −0.37 | −3.7 % / −0.46 | −7.9 % / −0.36 | −5.6 % / −0.42 | −2.9 % / −0.48 |
| LJA+GSLM pair (2, ~12 M) | −3.9 % / −0.27 | −5.5 % / −0.24 | −0.6 % / −0.35 | −6.8 % / −0.21 | −4.6 % / −0.26 | −0.1 % / −0.36 |
| LJA+LJB4 pair (2, ~9 M) | −3.6 % / −0.17 | −3.8 % / −0.16 | −2.7 % / −0.19 | −6.0 % / −0.11 | −5.2 % / −0.13 | −0.3 % / −0.24 |
| GSLV+GSLM+B17X (3, ~30 M) | −3.1 % / −0.67 | −8.3 % / −0.54 | – | −8.9 % / −0.53 | – | – |
| GSLV+B17X pair (2, ~23 M) | **+11.5 % worse** / −0.88 | +4.6 % / −0.73 | – | −5.1 % / −0.51 | – | – |
| RSOFT+B17X+EDGE (weak-only, best relative gain) | +27.7 % worse | +14.0 % worse / −0.97 | – | – | – | – |

- Context for the break-even: the logged ensemble-feasibility entry already concluded "break-even for 3× fuel is ~−18 % ⇒ NOT WORTH IT" for GSLV replica fusion — [LOOP_LOG](research/single_model/LOOP_LOG.md). Score formula and per-doubling fuel cost (−0.28) from the tier1m entry in the same log.
- Oracle headroom for the top sets (st2conf): GSLV+LJB4+GSLM hindsight −18.8 %, 5 s oracle −23.7 %, 1 s oracle −25.9 %; GSLV ×3 reps hindsight −16.4 %, 1 s oracle −23.1 % — [rep_st2conf.txt](research/single_model/ensemble/rep_st2conf.txt).

### Inferences
- *Estimate:* even capturing the full per-flight hindsight gain (~−17 %) with 3 GSLV replicas would give Δ ≈ +0.42 (ATE) − 0.59 (fuel, 20 M vs 4.8 M) ≈ −0.17; with LJA replicas (14.4 M) ≈ +0.40 − 0.44 ≈ −0.04, i.e. break-even only with an oracle-quality selector. A 2× LJA ensemble would need ≥11.7 %; the measured causal mean of 2 replicas is 4.5–6.3 %.
- The only plausible route to a positive score is a shared-front-end multi-hypothesis filter (duplicate only the back-end at ≪2× fuel) plus a causal selector approaching the 1–5 s oracle; the measured data say mixing builds adds nothing beyond what replica perturbation already provides.
- If an ensemble is pursued for ATE alone (ignoring fuel), the recommended member set is GSLV/LJA replicas (+ optionally LJB4 and GSLM), fused by per-frame **median** for K≥3; avoid B17X/BM40/old builds and OpenVINS (they lower correlation but drag causal fusion).

### Gaps
- Peaks used for the estimated score are approximate per-family values from NOTES (e.g. GSLV 6.8, LJA 4.8, LJB4 4.1, GSLM 7.0, B17X 16.1 M), and "sum of peaks" is an upper bound; true co-scheduled peak was not measured.
- Local-pool gains have not been validated against server episodes (no server data used); the server's three hard episodes may respond differently.
- K≥5 sets and quality-signal-weighted fusions were not evaluated.
