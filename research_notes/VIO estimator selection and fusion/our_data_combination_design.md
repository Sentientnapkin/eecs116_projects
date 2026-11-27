# Combination design for our drone VIO submission: selecting or weighting estimator variants under a peak-fuel score

Scope: what our own repo measures about failures, which causal signals our filter already has, how candidate "combination" designs fare under the peak-fuel area score, and a plan of offline tests that use only logged runs. Repo facts cite file + entry. Anything marked **(estimate)** is my own arithmetic or judgement, not a measurement. No estimators were run, the holdout was not touched, and no private server data was used. The server numbers are the user-pasted submission results already recorded in the repo.

Abbreviations: GSLV = our current final build (GSLM + periodic net re-anchor + gyro-bias clamp, with exact line Jacobians = "LJARITH", submitted to the server). GSLM = RSOFT + 3-D lines + Manhattan constraints. st2dev/st2conf/st3 = server-like sets of fast flights in starved (untextured) scenes. fconf/f3 = fresh confirmation sets.

---

## Q1. Measured evidence: when do our estimator and OpenVINS fail?

### Takeaway
The server mean (0.633 m) is dominated by three hard episodes (1.53/2.03/1.78 m, about 70% of the error sum; the other nine average about 0.25 m). Locally, these failures reproduce as fast flights in vision-starved scenes. The mechanism is tilt drift from a corrupted gyro-bias estimate, which leaks gravity into velocity, plus bad tracks that pass the chi2 gate. The failures are partly chaotic: the same flight can go from fine to bad across replicas. OpenVINS (4.2 G peak) is far worse than GSLV on our hard local set, and a GSLV+OpenVINS combination is dead. A cheap self-ensemble of GSLV replicas gives only -5 to -7% causally because replica errors are highly correlated.

### Cited Findings
**Server results (user-pasted, recorded in the loop log and memory)**
- GSLV-linejac on the server: mean 0.633 / median 0.237 / Sim3 0.179 at 4.2 M peak (p95 2.8 M), 12/12 completed, 0 filled, claimed area 5.8% (team best). Per-episode: 004c 3.46->1.53, cd6d 2.69->2.03, 2149 2.28->1.78, e7aa 0.55, other 8 at 0.16-0.26. Server/holdout ratio 1.67 — [LOOP_LOG.md, entry "SERVER RESULT GSLV-linejac"](research/single_model/LOOP_LOG.md)
- Baselines on the server: VINS-Mono 0.475 m @ 3.40 G; OpenVINS 0.553 m @ 3.96 G; identity pose 4.694 — [memory server-baseline-anchors.md](/data/backups/rganapa/Sebastian/.claude/projects/-data-backups-rganapa-Sebastian-eecs116-projects/memory/server-baseline-anchors.md)
- Earlier build HFG: 0.948 @ 3.97 M. The same three episodes carried 74% of its total error (3.46/2.69/2.28), and the other 9 averaged 0.34 — [LOOP_LOG.md, "SERVER RESULT HFG"](research/single_model/LOOP_LOG.md)
- Per-episode server ATE for B17-teammate/B16/friend/G/base builds is stored in [proxy/server_results.json](research/single_model/proxy/server_results.json). For example, B16 = [2.22, 0.24, 2.44, 0.135, 0.171, 0.928, 0.142, 0.272, 1.83, 0.289, 0.501, 0.22], in the episode order 004c, 1c6e, 2149, 7264, 78ed, 8950, 89f8, a61a, cd6d, dd7a, e7aa, f7c2. The hard set (004c, 2149, cd6d) is the same across most builds. G is the exception: its worst episode was e7aa at 7.7.
- Teammate claim: B16's bad server episodes are a rigid offset made in the first second by the startup net. Our servertail diagnosis is different: fast flights in starved scenes with velocity/tilt drift — [LOOP_LOG.md, "MERGED teammate branch"](research/single_model/LOOP_LOG.md)

**Mechanism of GSLV-family failures (local, server-like sets)**
- Bad server class = fast flights in starved (untextured ProcTHOR) scenes, where velocity is unobserved. st2 (240 fast flights in the 20 hardest non-holdout scenes) reproduces the server tails. Long fast textured flights are easy — [LOOP_LOG.md, "SERVERTAIL DONE"](research/single_model/LOOP_LOG.md)
- On untextured flights, 15-24% of accepted features are >2 px wrong. They pass chi2 because P is large. Other findings: velocity runaway bursts (3.8 m/s error with sd 0.2-0.4); tilt 0.10-0.15 rad from an unestimated gyro bias on mid starts; the net under-predicts at high speed (net/true 0.76). Inflation (Q, RW, Huber, Schmidt) was all neutral or worse — [LOOP_LOG.md, "FILTCONS DONE"](research/single_model/LOOP_LOG.md); [filtcons/NOTES.md lines 23-34, 106-110](research/single_model/filtcons/NOTES.md)
- Gyro-bias error at 3-5 s on mid starts is often 1.5-3.2 sigma (100-009: 0.036 vs sd 0.011). The bias sd shrinks without real information — [filtcons/NOTES.md l.41-44](research/single_model/filtcons/NOTES.md)
- Catastrophic flights show tilt 6-8 deg from gyro bias pushed beyond its physical range by starved vision (bg_y 0 -> 0.038 > physical 0.02). This is attributed mostly to starved vision updates (+0.025) — [learnvel/NOTES.md, "Filter tilt diagnosis"](research/single_model/learnvel/NOTES.md)
- Per-flight mean tilt error grows with ATE on st2dev: ATE<0.3: 1.8 deg; 0.3-0.6: 2.8; 0.6-1: 5.4; 1-2: 6.5; >2: 6.9. Correlation of log ATE with log tilt is 0.54. With no drag, the accelerometer carries no tilt information — [learnvel/NOTES.md, "KEY DIAGNOSIS"](research/single_model/learnvel/NOTES.md)
- Flights with median live tracks <15 (22/156 on st2dev) average 1.73 m, which is 39% of the ATE sum. By live-track bin: 15-25 -> 0.56; 25-40 -> 0.35 — [geomstarve/NOTES.md l.21-22](research/single_model/geomstarve/NOTES.md)
- In starved scenes corner life is about 0.4 s (<3 clone observations), with live 11/frame and 1.44 new corners/frame — [geomstarve/NOTES.md l.59](research/single_model/geomstarve/NOTES.md)
- Chaos: the worst flight scored 6.2/5.9/10.3 m over three replicas — [learnvel/NOTES.md](research/single_model/learnvel/NOTES.md). Only 50-65% of failures persist across builds, and a changed build newly fails 1-2% of previously solved flights — [LOOP_LOG.md, "SCORECARD DONE"](research/single_model/LOOP_LOG.md)

**OpenVINS locally**
- On st2conf (84 hard flights), OpenVINS (baselines/openvins-9b1b079) scored mean 143 m, with 36 flights >3 m and 23 >10 m, at 4.2 G peak. It beat GSLV on only 2/84 flights. Excluding its >10 m blowups, hindsight best-of-2 was 0.271 vs GSLV 0.276 — [LOOP_LOG.md, "ENSEMBLE FEASIBILITY (a)"](research/single_model/LOOP_LOG.md). From the stored per-flight file: GSLV median 0.239 m on these flights, and OpenVINS was <=1 m on only 28/84 (my read of [ensemble/ens_st2conf_lv_glNP+lv_ovins.json](research/single_model/ensemble/)).
- On the earlier 171-flight pool, OpenVINS scored mean 28.5 / median 0.58 (gp_msckf 2.21/0.80; VINS-Mono 5.51/0.62). Hindsight oracles: VINS+OpenVINS+N2 = 0.759; adding gp_msckf = 0.670 — [reports/Single model plan v2.md, l.11 and l.17](reports/Single%20model%20plan%20v2.md)
- Three-source causal guard (VINS-Mono + OpenVINS + learned N2) on scene-disjoint folds: held-out mean 0.993/1.012/0.973 vs a per-flight oracle of 0.759. "The dominant remaining issue is sustained source selection, not switch smoothing." Of the 7 held-out flights >5 m, 4 had both VIOs bad and 3 selected the wrong VIO — [research/guard_fusion/README.md](research/guard_fusion/README.md)

**Self-ensemble (GSLV replicas)**
- 3 GSLV chaos replicas, causal per-frame mean/median: st2conf 0.333 -> 0.310 / 0.318 (-5 to -7%); fconf 0.270 -> 0.255 (-6%); hindsight best-of-3 -16%; adding 3 GSLM runs (6 runs) -8% causal. Break-even for 3x fuel is about -18%, so it is not worth it — [LOOP_LOG.md, "ENSEMBLE FEASIBILITY (b)"](research/single_model/LOOP_LOG.md)
- My recomputation from the stored per-flight files ([research/single_model/ensemble/*.json](research/single_model/ensemble/)):
  - Correlation of per-flight log-ATE between GSLV replicas is 0.80-0.90 (st2conf) and 0.87-0.88 (fconf).
  - The median per-flight max/min ratio across replicas is 1.28-1.29.
  - The fused gain lands mostly on ordinary flights, not tails. On st2conf (3 reps), the top-10% worst flights move 0.85 -> 0.82 under mean fusion while the rest move 0.271 -> 0.249. On fconf the top 10% move 0.687 -> 0.669.
  - Mixing families (3 GSLV + 3 GSLM) helps the tail more. On st2conf the top 10% move 0.85 -> 0.731, the overall mean is 0.306, and the per-coordinate median is 0.303.
  - The per-frame medoid gave 0.319 (3 reps) / 0.310 (6 runs) on st2conf.
- Multi-hypothesis startup (K filters with different velocity priors) on fresh-711: oracle best-of-(h0,h2) 0.485 vs B6 0.618. But the causal splice is worse than B6 at every switch time (1 s: 0.650; 3 s: 0.682). The perfect-oracle switch bound decays to 0 by 3 s. "Hypotheses are only distinguishable after the damage is done." The in-filter K-instance version was not built — [multihyp/NOTES.md](research/single_model/multihyp/NOTES.md)

### Inferences
- **(estimate)** On the server, 0.633 x 12 = 7.6 m total. The three hard episodes sum to 5.34 m (70%), and the other nine average about 0.25 m. Any combination design has to cut the tail episodes. The replica ensemble mostly improves the already-good flights, which is the wrong place.
- Failures are correlated across replicas of one build (log-ATE r = 0.8-0.9). Families with different mechanisms (GSLV vs GSLM) decorrelate the tail more. Diversity of mechanism, not seeds, is what a combination needs.
- OpenVINS gives no complementary information on our failure class: it fails more often on the same starved/fast flights. Its server 0.553 comes from different and probably easier per-frame conditions on the full server mix. On our hard local set it is not a useful second opinion at any cost.

### Gaps
- No per-frame (as opposed to per-flight) hindsight oracle has been computed for the replica or family ensembles.
- The server per-episode cause for GSLV (rigid early offset vs starved drift) cannot be checked without private data. Our local st2 evidence supports the drift explanation, while the teammate's proxy evidence supports an early offset for B16.
- VINS-Mono was never run on st2 sets, so its complementarity to GSLV on our failure class is unknown.

---

## Q2. Score rule: what ATE gain pays for extra peak fuel?

### Takeaway
Break-even under gain = 0.28 log2(peak_old/peak_new) - 2.24 ln(ATE_new/ATE_old) is ATE_new/ATE_old = k^-0.180 for a peak-fuel multiplier k. That means -7.0% ATE for 1.5x fuel, -11.8% for 2x, -18.0% for 3x, and about -71% for adding a 4 G estimator to our 4.2 M build. Only designs whose extra work is time-sliced under the existing peak, or costs at most about 10-20% more, are realistic. A 10% fuel increase needs only -1.7% ATE.

### Cited Findings
- Area-score proxy: 0.28*log2(17/peak) - 2.24*ln(fresh/0.356) was used in TIER1M — [LOOP_LOG.md, "TIER1M DONE"](research/single_model/LOOP_LOG.md). "Each further 10% fuel ~ +0.07 points" — [LOOP_LOG.md l.75](research/single_model/LOOP_LOG.md)
- Peak is the max over frames. The peak frames are clone frames, which carry the spawn pass and edge rows — [geomstarve/NOTES.md l.51, 62](research/single_model/geomstarve/NOTES.md). The existing governor already amortises a gravity-net inference (about 10.5 M) across 66 micro-steps on leftover units, giving 3.42 M peak — [learnvel/NOTES.md, "C gravity module"](research/single_model/learnvel/NOTES.md)
- GSLV-linejac fuel: peak 4.2 M, p95 2.8 M on the server; p99 about 3.2 M locally — [LOOP_LOG.md, "LINEJAC" and "SERVER RESULT GSLV-linejac"](research/single_model/LOOP_LOG.md)

### Inferences (all estimate, derived from the stated formula)
| Peak multiplier k | Fuel cost (pts) | Break-even ATE change | GSLV server 0.633 must reach |
|---|---|---|---|
| 1.1x | -0.039 | -1.7% | 0.622 |
| 1.2x | -0.074 | -3.2% | 0.613 |
| 1.5x | -0.164 | -7.0% | 0.589 |
| 2x | -0.28 | -11.8% | 0.559 |
| 3x | -0.444 | -18.0% | 0.519 |
| 6x (6-run ensemble) | -0.724 | -27.6% | 0.458 |
| +4 G (4.2 M -> ~4004 M, k ~ 953) | -2.77 | -71% | 0.184 |

- The measured replica ensemble at 3x (-5 to -7% causal) has a net score of about -0.28 to -0.33 pts. Even its hindsight best-of-3 (-16%) is below the 3x break-even.
- Adding any OpenVINS/VINS-class estimator (3.4-4 G) would need ATE 0.18 m, below the course's best geometric baselines (0.475). That design is infeasible under this score.
- A per-frame selector MLP on about 10 scalar signals costs about 1 k MAC, roughly 0.03% of 4.2 M, so it is free. The cost of any combination lies in what it selects between, not in the selector.
- Where the gain must come from: if the three hard episodes were halved (5.34 -> 2.67), the mean would drop to about 0.41 (-35%), worth about +0.97 pts. That would justify up to about 11x peak fuel. Tail-targeted mechanisms can afford fuel, but replica/bulk averaging cannot.
- Time-slicing a second component under the governor (like the gravity net) keeps k near 1. The headroom between p95 (2.8 M) and peak (4.2 M) is about 1.4 M on typical frames, but clone frames have almost none.

### Gaps
- The exact server area formula was not re-derived here. The 0.28 and 2.24 coefficients are the repo's local approximation.
- A per-frame fuel profile of GSLV-linejac (how many frames sit near the peak, and their slack) was not read.

---

## Q3. Which causal per-frame signals exist, and what predicts failure?

### Takeaway
The filter already exposes starvation counters (live tracks, accepted/gated/triangulation-failed features, after the tc_used fix), NIS/dof, Pv, net-vs-filter disagreement, gyro-bias magnitude, clone-reprojection rms, line counts and a scene-texture measure. Several of these separate bad flights from good ones at the flight level. Accepted-feature rate is the best measured selector (85-93% decision accuracy over 3-5 s windows). But nothing yet shows a per-frame signal that predicts the coming runaway early enough to act. Every attempt to *switch behaviour* on these signals inside the filter (gated Q, Schmidt, chi2 gate on the net, tilt-noise boost) made ATE worse.

### Cited Findings
- **Accepted-feature rate (used/attempted)** was the best selector between startup hypotheses: (h0,h2) Tw=3 s 0.545, Tw=5 s 0.511, with decision accuracy 85%/93% on flights where hypotheses differ by >0.5 m. NIS/dof gave 0.581/0.526; prior-NIS was useless (0.80). The control best selector between replicas was 0.599 — [multihyp/NOTES.md](research/single_model/multihyp/NOTES.md)
- **Accepted-feature counter bug:** tc_used is never incremented in sa.c/fc.c, so u20 (TC_LOG 'u20', tc_uring, the TC_STARTUP_MON lock-out) is always 0. Fixed only inside filtcons switches: fc_uring = att - gate - tri — [filtcons/NOTES.md l.61-64](research/single_model/filtcons/NOTES.md). The runaway still happens with 2-4 accepted features per frame (NIS 0.04-0.3), so count alone does not flag it — [filtcons/NOTES.md l.83-85](research/single_model/filtcons/NOTES.md)
- **Live track count / texture:** flight median live <15 -> mean ATE 1.73 m (39% of the ATE sum on st2dev); live<10 in 16% of frames — [geomstarve/NOTES.md l.21-24](research/single_model/geomstarve/NOTES.md). At texture <0.03 the net error is 0.35 vs the filter's 0.27 — [learnvel/NOTES.md "DIAG 1"](research/single_model/learnvel/NOTES.md)
- **Clone-pose reprojection rms:** inlier median 0.34 px vs outlier 1.31 px. It is useful as a soft weight (RSOFT: -10/-12% on st2), but hard thresholds hurt (rmx075 0.965) — [filtcons/NOTES.md l.114, 123](research/single_model/filtcons/NOTES.md); [LOOP_LOG.md "FILTCONS DONE"](research/single_model/LOOP_LOG.md)
- **Velocity covariance Pv:** where Pv>0.5, the net error is 0.24 vs the filter's 0.63. But during runaway Pv stays 0.2-0.3, about 13 sigma overconfident — [learnvel/NOTES.md "DIAG 1", "KEY DIAGNOSIS"](research/single_model/learnvel/NOTES.md)
- **Net-vs-filter disagreement:** where filter error is >0.5 m/s (4% of anchors), the net error is 0.42 vs the filter's 0.82; where filter error is >1.0, 0.44 vs 1.41. But a chi2 gate on the net "rejects the net exactly when the filter drifted" (gate-only 0.700 vs 0.660), and LV_RESET (inflate on disagreement) gave -3.3%, "no real gain" — [learnvel/NOTES.md](research/single_model/learnvel/NOTES.md)
- **Gyro-bias magnitude:** a runaway shows |bg_y| 0.038 > physical 0.02. Clamping at 0.021 was neutral to slightly helpful (rsB +0.6%; part of GSLV) — [learnvel/NOTES.md](research/single_model/learnvel/NOTES.md)
- **Tilt NEES** (truth-only diagnostic): median 1.5 on good flights, 3.5 on ATE>1 flights, up to 10-27 in starved stretches — [filtcons/NOTES.md l.32](research/single_model/filtcons/NOTES.md). There is no causal tilt observable apart from lines/Manhattan (vertical lines) and the gravity net, which was less accurate than the filter (about 2.5 deg vs about 1 deg) and hurt in the filter (+4.4%, or +40% with reset) — [learnvel/NOTES.md "Gravity in-filter"](research/single_model/learnvel/NOTES.md)
- **Line counts:** 3-10 lines alive, 1-6 accepted/s in starved scenes — [geomstarve/NOTES.md l.74](research/single_model/geomstarve/NOTES.md)
- **Speed:** net error by speed is 0.11/0.21/0.34/0.64/1.15 m/s for <0.3/0.3-1/1-2/2-3/>3 m/s (scale under-estimate) — [learnvel/NOTES.md](research/single_model/learnvel/NOTES.md)
- **Gated in-filter modes that failed:**
  - starved-only velocity random walk qv03u 0.840 vs 0.631
  - starved-only Schmidt schu10b 0.749
  - starved-only tilt random walk qt01u 0.690 and qt03u 0.761
  - Huber hub3 0.708
  - TQ tilt-Q boost while live<20: 0.722/0.866
  - LV_PLIVE (net re-anchor only while live<N) neutral

  Sources: [filtcons/NOTES.md](research/single_model/filtcons/NOTES.md); [learnvel/NOTES.md](research/single_model/learnvel/NOTES.md)

### Inferences
- **(estimate)** The available signals are good at "this flight is in starved conditions," which is a scene-level property. They are weak at "the estimate is diverging right now" because the filter's own consistency measures (NIS, Pv) stay small during the runaway. That is exactly the gap that matters for raw-ATE selection, since error accrued before a switch is kept.
- The only signal shown to carry information *during* failure is net-vs-filter velocity disagreement (net 2x better there). Hard gating on it fails, though, because the chi2 uses the overconfident Pv. A learned weighting that takes disagreement plus starvation counters as inputs, rather than chi2, has not been tried.
- Use the fixed counter (att - gate - tri), not u20, for any logged-signal analysis. Old TC_LOG u20 columns are all zero.

### Gaps
- There is no measured AUC or lead time for any per-frame signal predicting near-term error growth. Only flight-level bins and a 3-5 s startup selector exist.
- It is unclear which logged runs contain per-frame TC_LOG/GS_DIAG/LV_DBG streams for GSLV specifically. Most diagnostics were logged on HM40/RSOFT/eB builds.

---

## Q4. Design options and their expected fuel cost vs the ATE gain needed

### Takeaway
Ranked by expected value **(estimate)**:
1. A within-filter learned *measurement weighting* (soft, never hard gating) of components that already run, such as net re-anchor sigma and line/feature weights. Cost about 1.0x; it pays with any positive gain.
2. A persistent-landmark/line mode that targets the starved tail. Cost about 1.1-1.5x if budgeted, so it needs -2 to -7%.
3. Consensus over 2-3 *mechanism-diverse* cheap variants with the OpenVINS-baseline-style geometric median and 2 s observer. Cost 2-3x, needs -12 to -18%, and current replica evidence gives -5 to -8%.
4. Per-frame learned selection among full variants (same cost as 3, worse causal behaviour).
5. IMM over noise modes (cost about 1.3-2x for covariance; the mode set it would mix has been measured neutral or harmful).
6. Gated second opinion (the warm-start problem; it sets the peak whenever it fires).

### Cited Findings
**OpenVINS-baseline consensus (coordinator request)**
- The course OpenVINS example is itself an ensemble. Two OpenVINS frontends (ordinary frame-to-frame KLT, and direct keyframe-to-keyframe matching) initialise three Ceres fixed-lag smoothers: ordinary tracking; direct tracking; and ordinary tracking with weaker visual weight (pixel sigma 1.5 / Huber 1 vs 0.75 / 2, "one-quarter of the visual objective"). The third shares the ordinary frontend but keeps its own states, landmarks and prior — [openvins/README.md](/data/backups/rganapa/Sebastian/baselines/viobench-upstream/viobench/solution/examples/native/openvins/README.md)
- How consensus_output.h works — [consensus_output.h](/data/backups/rganapa/Sebastian/baselines/viobench-upstream/viobench/solution/examples/native/openvins/consensus_output.h):
  - Each frame takes the three hypotheses' positions and world-frame velocities (R*v) in the common first-camera frame. It computes the **equal-weight geometric median** of the three points in closed form. If any triangle angle is >=120 deg (or two points coincide), the median is that vertex, so a single far outlier is ignored. Otherwise it is the interior Fermat point via barycentric weights proportional to 1/[4*area + sqrt(3)*(b^2+c^2-a^2)].
  - Rotation is the **intrinsic (Karcher) mean**: up to 30 iterations of log/exp averaging. It returns failure if it does not converge ("widely inconsistent rotations may have no locally unambiguous mean").
  - Angular velocity is the plain mean in the world frame.
  - **Anti-jump observer:** it predicts position = previous emitted position + trapezoid of (previous raw median velocity, current raw median velocity) x dt. It then moves toward the raw median position with alpha = 1 - exp(-dt/2 s), a 2 s time constant (about 2.5% per frame at 20 Hz). The reported linear velocity is the median velocity plus the correction rate (candidate - predicted)/dt, so twist and pose stay consistent.
  - A jump in the median position (for example, when the median switches from one hypothesis to another) is therefore bled in over about 2 s, while velocity tracks immediately.
  - Equal weights, no quality weighting, no feedback into any estimator. If any input is invalid or timestamps disagree, the observer and output keep their previous values (hold).
- Measured effect in the README (8 public episodes, vs a previous single smoother): median ATE 1.535 -> 0.849 (-45%) and median RPE 0.123 -> 0.094 (-23%). ATE improved on 7/8. Median per-episode median fuel 96 M -> 224 M (2.3x); p95 1.224 B -> 2.648 B — [openvins/README.md "Results"](/data/backups/rganapa/Sebastian/baselines/viobench-upstream/viobench/solution/examples/native/openvins/README.md). The README states these are "correlated hypotheses, not independent measurements."
- Our earlier guard used a related absolute-consensus idea: average VIO positions when they agree within a + b*|p|, with a 0.5 s decaying offset at switches. Held-out mean 0.99 vs oracle 0.759, limited by "sustained source selection, not switch smoothing" — [guard_fusion/README.md](research/guard_fusion/README.md)
- ens.py tested per-coordinate mean, per-coordinate median and per-frame medoid on raw estimate.tum positions with no smoothing observer and no geometric median — [ensemble/ens.py](research/single_model/ensemble/ens.py)

**Other designs (repo evidence)**
- Startup multi-hypothesis: causal splice is worse than the base at all decision times, and the perfect-oracle bound is about 0 by 3 s — [multihyp/NOTES.md](research/single_model/multihyp/NOTES.md)
- Noise-mode switching inside the filter (starvation-gated Q, Schmidt, tilt random walk, Huber, chi2 strictness, hard residual rejection): all neutral or worse — [filtcons/NOTES.md "Negative results" l.177](research/single_model/filtcons/NOTES.md)
- Mechanisms that did pay were always-on and added *information* (lines/Manhattan -31% st2dev; periodic net re-anchor -8.8%/-12.4%; RSOFT soft weighting -10/-12%) — [LOOP_LOG.md GEOMSTARVE/LEARNVEL/FILTCONS](research/single_model/LOOP_LOG.md)
- More fuel without new logic saturates: a budget beyond 4 M buys 6-9%, and the logic saturates at about 8 M — [LOOP_LOG.md "FILTCONS DONE"](research/single_model/LOOP_LOG.md). A clone-rate increase was harmful (c2m8 0.942, peak 13 M) — [geomstarve/NOTES.md l.50](research/single_model/geomstarve/NOTES.md)

**Literature**
- IMM (Blom & Bar-Shalom 1988) handles hypothesis management for systems with Markov-switching coefficients by mixing model-conditioned estimates with model probabilities. It is reported to perform well at low computational load, at roughly one filter per mode — [TU Delft repository record](https://repository.tudelft.nl/record/uuid:f08e0b04-6d46-44f7-b71a-7201479a9252)
- AI-IMU (Brossard, Barrau, Bonnabel, IEEE T-IV 2020): a small network maps raw IMU signals to the measurement noise covariances of a Kalman filter's pseudo-measurements, without needing a state estimate. It reports 1.10% translational error on KITTI and says the adapter "greatly improves the filter's robustness" — [arXiv 1904.06064](https://arxiv.org/pdf/1904.06064)
- Backprop KF (Haarnoja et al., NeurIPS 2016) trains a network that outputs observations and their noise covariances by backpropagating through the Kalman filter end to end. It beat generative and plain recurrent baselines on synthetic image tracking and KITTI VO — [arXiv 1605.07148](https://www.arxiv.org/pdf/1605.07148)
- Hybrid MSCKF + EKF-SLAM (Li & Mourikis): per feature, choose MSCKF processing (cheap for many short tracks) or in-state SLAM landmark (efficient for few long tracks) to minimise predicted computation. They report it beats each pure method "by a wide margin" and runs in real time on a phone — [Li & Mourikis RSS 2012](https://roboticsproceedings.org/rss08/p31.html); [IROS 2012 PDF](https://intra.ece.ucr.edu/~mourikis/papers/Li2012IROS.pdf); [IJRR 2013](https://intra.ece.ucr.edu/~mourikis/papers/Li2013IJRR.pdf)
- OpenVINS supports in-state SLAM landmarks (anchored/inverse-depth representations, anchor change on marginalisation) alongside MSCKF features — [OpenVINS GitHub](https://github.com/rpng/open_vins); [UpdaterSLAM source](https://docs.ros.org/en/api/ov_msckf/html/UpdaterSLAM_8cpp_source.html)
- IV-SLAM (Rabiee & Biswas) learns a context-dependent reprojection-noise model from self-collected data. It reports >70% fewer failures than the base V-SLAM on challenging data — [arXiv 2008.02760](https://arxiv.org/pdf/2008.02760v2). Introspective perception (Daftry et al. 2016) learns to predict vision-system failures for MAV flight directly from sensor input — [CMU RI](https://www.ri.cmu.edu/publications/introspective-perception-learning-to-predict-failures-in-vision-systems-2)

### Inferences (design-by-design, estimates unless cited)
| Design | Peak fuel k | Needed ATE | Evidence-based expectation | Verdict |
|---|---|---|---|---|
| A. Learned per-frame weighting of K full variants | K (2-3x) | -12 to -18% | Replica causal -5 to -7%, hindsight -16% (below 3x break-even); 6 mixed runs causal -8%, hindsight -26% vs needed -27.6% | No, unless variants are far more diverse than seeds |
| A'. Consensus as in the OpenVINS baseline (geometric median + 2 s observer) over 3 *mechanism-diverse* cheap variants | ~3x (or ~1.5-2x if variants share the frontend, as hypothesis 3 there does) | -18% (3x) / -7 to -12% (shared frontend) | The upstream -45% median ATE came from diverse frontends vs a weaker single smoother. Our diverse-family tail gain (top 10% 0.85 -> 0.73) is the closest local analogue. Only offline replay can settle it | Test offline first (T1, T2); plausible only with a shared frontend |
| B. Gated second opinion | sets the peak whenever it fires; cold start mid-flight | -12% if 2x | The second estimator would be cold exactly when needed; multihyp showed decisions made after damage do not recover raw ATE | No |
| C. IMM over noise modes (normal / starved) | ~1.3-2x (K covariance propagations + updates) | -4 to -12% | Every single mode it would mix (inflated Q/RW/Schmidt) is neutral or worse; mixing harmful modes is unlikely to help. IMM over "trust net vs trust vision" is untested | Low priority |
| D. Mode switching inside one filter (hard switch on starvation) | ~1.0x | >0 | Measured repeatedly worse (qv03u, schu10b, qt01u/03u, TQ, PLIVE) | No (as hard switches) |
| D'. Learned *soft* measurement weighting (AI-IMU / Backprop-KF style): tiny MLP maps causal signals (fixed accepted count, live, texture, speed, line count, net-filter disagreement, \|bg\|) to the net re-anchor sigma and the visual/line noise scale | ~1.0x (about 1 k MAC) | >0 | Closest to what worked (RSOFT soft weighting, net sigma scaling P10S3). The net is 2x better than the filter exactly where the filter fails, and its sd is too small at speed | **Best first bet** |
| E. Persistent-landmark mode (hybrid MSCKF-SLAM: keep a few long-lived points/lines in state across starved stretches) | ~1.1-1.5x if capped at a handful of landmarks and budgeted on non-clone frames | -2 to -7% | Starved scenes have short corner life (0.4 s), so MSCKF features rarely reach 3 observations. Lines are long-lived and very accurate. Li & Mourikis say SLAM processing suits few long tracks. Attacks the tilt/heading drift that drives the tail | **Second bet** (needs code; check whether line_mod lines are already in state) |

- Why the OpenVINS-style consensus helped them more than seeds help us: their three hypotheses differ in *frontend and weighting*, and its baseline single smoother had a 1.5 m median. Our replicas differ only by chaos, and our median is already about 0.24 m. **(estimate)**
- The 2 s observer mainly suppresses jumps when the median changes hypothesis. Our ens.py medoid result (0.319 vs 0.333) did not include it, so per-frame switching noise may have been understating the consensus gain somewhat. This is cheap to check offline.
- The geometric median of 3 needs at least 2 of 3 hypotheses to be right. On our tail flights replicas fail together (r 0.8-0.9), so the median follows them. Consensus can only fix the tail if a variant fails on *different* flights.

### Gaps
- No full-text reading of the IMM, AI-IMU, Backprop-KF or Li & Mourikis papers. The cost models and architectures above come from abstracts and secondary summaries.
- The state dimension and covariance-op share of GSLV fuel were not measured here, so the costs for IMM and persistent landmarks are rough.
- Whether GSLM's 3-D lines are in-state persistent landmarks or MSCKF-style marginalised features was not checked in line_mod.c.
- The upstream consensus's gain was measured on 8 public episodes against a weaker single smoother, and the README does not give a per-component ablation (frontend diversity vs averaging).

---

## Q5. Proposed concrete, testable plan (offline first, from logged runs)

### Takeaway
Run four cheap offline tests on existing logs before writing estimator code:
- **T1** replays consensus with the geometric median and 2 s observer on the stored ensembles.
- **T2** measures cross-family error correlation and per-frame oracles.
- **T3** fits a scene-disjoint failure/weight predictor on logged per-frame signals.
- **T4** profiles fuel slack for time-slicing.

Only if T3 shows a usable predictor (and T1/T2 show diversity) should we build the soft learned-weighting variant D'. The persistent-landmark mode E is a separate tail-targeted track.

### Cited Findings
- Existing logged runs usable offline: results/single_model/lv_glNP{,_r1,_r2}, lv_gl{,_r1,_r2}, lv_ovins on st2conf/fconf, with estimate.tum per flight — [ensemble/ens.py](research/single_model/ensemble/ens.py). Per-frame diagnostics exist via TC_LOG (filtcons: nees.py/ts.py), GS_DIAG (geomstarve), LV_DBG/TC_LOG (learnvel lv_diag.py, an1-3.py) — [filtcons/NOTES.md l.14-15](research/single_model/filtcons/NOTES.md); [learnvel/NOTES.md "Tools"](research/single_model/learnvel/NOTES.md); [geomstarve/NOTES.md l.12, 41](research/single_model/geomstarve/NOTES.md)
- Evaluation conventions: 3 replicas (PIXEL_STD/DETECT_MIN_SCORE nudges), paired whole-pool means, scene-bootstrap CIs. Avoid per-difficulty-bin comparisons, which regress to the mean — [learnvel/NOTES.md "CAUTION"](research/single_model/learnvel/NOTES.md)

### Inferences (plan; all thresholds are my estimates from Q2)
1. **T1 consensus replay (no estimator runs).**
   - Port consensus_output.h logic (3-point geometric median, Karcher mean is unnecessary for position-only ATE, 2 s observer with velocity from finite-differenced estimate.tum or logged twist) to Python.
   - Run it on the stored 3-GSLV and 3-GSLV+3-GSLM ensembles (st2conf, fconf); for 6 runs use a Weiszfeld geometric median.
   - Report mean, top-10% and >3 m. Kill criterion: K=3 needs <= -18%; a shared-frontend 1.5x variant needs <= -7%.
2. **T2 diversity / oracle.**
   - Compute pairwise per-flight log-ATE correlations across all logged families on the same pools (HM40, RSOFT, GSLM, GSLV, eB edgelets, lng, the P20S2 net arms). Replicas are r = 0.8-0.9.
   - Compute the per-frame hindsight oracle and a "causal-with-2 s-observer" oracle.
   - Shortlist pairs with r < ~0.6 whose per-flight hindsight best-of-2 is <= -12%. Without such a pair, drop designs A/A'/B.
3. **T3 signal predictability (scene-disjoint).**
   - From TC_LOG/GS_DIAG runs (using the fixed counter att - gate - tri, not u20), build per-frame features: accepted, live, gate rate, triangulation failures, line counts, NIS/dof, sqrt tr Pv, net-filter velocity disagreement, |bg|, texture, speed.
   - Train on st2dev+st3 and evaluate on st2conf/fconf. Targets: (a) position-error growth over the next 2 s > 0.3 m; (b) "net velocity better than filter velocity" (the oracle weight for re-anchor sigma).
   - Report AUC and lead time. Go criterion: AUC >= 0.8 with >= 1 s lead for (a), or a weight regression whose offline-replayed velocity error beats the current fixed P10S3 sigma by >= 10% on the failure stretches.
4. **T4 fuel slack.**
   - From per-frame fuel logs, take the distribution of (peak - frame fuel) on non-clone vs clone frames. This bounds how much of a second component or landmark update can be time-sliced (the gravity-net governor pattern) while staying under 4.2 M.
5. **Build order if the gates pass.**
   - D' first: a tiny MLP producing the re-anchor sigma scale and the line/feature noise scale, trained offline on T3 targets, about 1 k MAC, preflighted like the other builds. Evaluate 3 reps on st2dev+st3 / st2conf / f3. Any gain >= 2% with CI excluding 0 is worth it at about 1.0x.
   - E in parallel: a cap of 4-8 persistent landmarks/lines in state during starved stretches, budgeted on non-clone frames. Target -5% on st2 at <= 1.2x peak.
   - A' only if T1/T2 found a diverse pair or triplet that clears break-even offline.
   - Never select on the holdout. Do one holdout shot per final candidate, as the loop has done.

### Gaps
- I did not verify which result directories still contain per-frame TC_LOG streams for GSLV-family builds. T3 may need one diagnostic logging run on dev sets, which is allowed but was outside this read-only task.
- VINS-Mono complementarity on st2 is unknown, but at 3.4 G it fails the score break-even regardless.
