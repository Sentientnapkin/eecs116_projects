# Fusion mechanics and fuel feasibility for an ensemble of our VIO filter variants

Scope: offline replay of causal fusion rules on stored runs (st2conf: 84 flights, fconf: 107 flights; no holdout, no fold 4, no server data), per-frame fuel profiling, and a recommended fusion architecture. All scripts and outputs are in `research/single_model/ensemble/`: `cons.py` (rules), `cons_sum.py`, `vsprim.py`, `lag.py`, `pairs.py`, `fuelprof.py`. Outputs: `cons_{st2conf,fconf}.json`, `cons_summary.json`, `cons_sum.log`, `vsprim.log`, `lag.log`, `pairs.log`, `fuelprof.log`, `fuelprof.json`. Nothing is left running.

Members used: GSLV `lv_glNP{,_r1,_r2}` (V), GSLV-linejac arithmetic, the final build's arithmetic, `lj_ajc{,_r1,_r2}` (J), and GSLM `lv_gl{,_r1,_r2}` (M). Replicas r1 and r2 are 1% parameter nudges: `PIXEL_STD=1.515/1.485` and `DETECT_MIN_SCORE=1010/990` ([geomstarve/bp.sh](../../research/single_model/geomstarve/bp.sh) line 7). One nudge is in the back end (pixel sigma) and one is in the front end (detector threshold). That matters for the shared-front-end design (see Q3).

Score law: points = 0.28·log2(peak_old/peak_new) − 2.24·ln(ATE_new/ATE_old). Reference: GSLV-linejac, 0.633 m at 4.2 M on the server ([LOOP_LOG](../../research/single_model/LOOP_LOG.md) "SERVER RESULT GSLV-linejac").

**Labels: [M] = measured on stored data in this study. [E] = estimate or model. [S] = taken from a cited source.**

## T1: replay of the baseline consensus and other causal rules

### Takeaway
The course baseline's consensus (geometric median plus 2 s anti-jump observer) **makes our ensembles worse**. Its observer costs +10 to +15% ATE against plain per-frame fusion on every member set and both pools [M]. The reason is that our filters' position "jumps" are EKF corrections toward the truth, not hypothesis switches. The best causal rules are the plain per-frame **mean** or **geometric median (GM)**, with no observer:
- **3 same-family replicas: −6.3% pooled** (st2conf −7.0%, fconf −5.7%) against the single-run family average.
- **Same-family pairs: −3.8 to −5.8%.**
- 6 runs (3 GSLV + 3 GSLM) with GM: −7.6% pooled.

Mixing in GSLM helps on st2conf but is neutral to harmful on fconf [M]. No causal rule approaches the hindsight best-of-3 (−14 to −16%). None changes the count of flights above 1 m, and no run on these pools exceeds 3 m. The local tail signal is therefore only the worst-10% mean.

### Cited Findings
- **Baseline mechanism** [S]:
  - Each frame takes the equal-weight GM of 3 positions and of 3 world-frame velocities, plus a rotation mean.
  - The observer predicts `prev + 0.5(v_prev+v)·dt` and corrects with α = −expm1(−dt/2.0).
  - Consensus "never feeds a posterior"; the README calls the members "correlated hypotheses, not independent measurements."
  - On 8 episodes, median ATE fell 1.535 → 0.849 m (−45%) against a *single previous smoother*, not against the average of its members. ATE regressed on 1 of 8 episodes. Median per-frame fuel rose 96 M → 224 M (2.3x).
  - Sources: [README.md](/data/backups/rganapa/Sebastian/baselines/viobench-upstream/viobench/solution/examples/native/openvins/README.md) lines 99-145; [consensus_output.h](/data/backups/rganapa/Sebastian/baselines/viobench-upstream/viobench/solution/examples/native/openvins/consensus_output.h) lines 140-170.
- **Our port** (`cons.py`): Weiszfeld (60 iterations) plus the exact vertex-optimality test, so a vertex with an angle of 120° or more is returned. For K=3 this equals the closed-form Fermat point. Member velocity = R(q)·twist. This convention was verified: RMS error against finite-differenced ground-truth velocity is 0.164 m/s with R, against 1.54 with Rᵀ [M].
- **Single runs** [M] ([cons_sum.log](../../research/single_model/ensemble/cons_sum.log)):

  | Family | st2conf mean ATE | fconf mean ATE |
  |---|---|---|
  | V (GSLV) | 0.336 / 0.341 / 0.324 | 0.280 / 0.264 / 0.266 |
  | J (GSLV-linejac) | 0.354 / 0.330 / 0.348 | 0.276 / 0.263 / 0.265 |
  | M (GSLM) | 0.337 / 0.339 / 0.377 | 0.322 / 0.297 / 0.295 |

  No single run exceeds 3 m on either pool. Flights above 1 m number 2 on st2conf and 1 on fconf, per run.
- **Per-flight log-ATE correlation** [M]:

  | Pair of families | st2conf | fconf |
  |---|---|---|
  | V-V | 0.83 | 0.87 |
  | J-J | 0.89 | 0.88 |
  | M-M | 0.85 | 0.87 |
  | V-J | 0.88 | 0.91 |
  | V-M | 0.75 | 0.79 |
  | J-M | 0.78 | 0.79 |

  GSLV and linejac are effectively the same model. GSLM is the only partially decorrelated family.
- **Rule sweep on 3 GSLV replicas (V3), st2conf**, change against the member average 0.333 m (scene-bootstrap 95% CI) [M]:

  | Rule | Mean ATE | Change [95% CI] | Worst-10% mean |
  |---|---|---|---|
  | Member average (reference) | 0.333 | — | 0.93 |
  | mean | 0.310 | −7.0% [−8.6, −5.2] | 0.86 |
  | GM | 0.315 | −5.5% [−8.6, −2.7] | 0.92 |
  | coordinate median | — | −4.5% | — |
  | trimmed mean (drop farthest from GM) | — | −3.7% | — |
  | weighted by causal EMA of distance to GM (wdis) | — | −5.5% | — |
  | medoid | — | −4.3% | — |
  | GM + observer τ=0.5 s | — | −0.3% | — |
  | GM + observer τ=1 s | — | +4.4% | — |
  | **GM + observer τ=2 s (the baseline)** | — | **+12.5% [+8.0, +16.4]** | 1.00 |
  | GM + observer τ=4 s | — | +25.8% | — |
  | GM + observer τ=8 s | — | +47.4% | — |
  | integrate GM velocity only | — | +232% | — |
  | observer on GM of backward-difference increments, τ=0.5 / 2 / ∞ | — | −4.4% / −2.0% / +42.8% | — |
  | weighted GM + observer τ=2 s | — | +13.5% | — |
  | velocity-disagreement weights + observer τ=2 s | — | +12.0% | — |

  On fconf the pattern is the same: mean −5.7%, GM −5.9%, wdis −6.5%, GM+obs2 +13.3% ([cons_sum.log](../../research/single_model/ensemble/cons_sum.log)).
- **Why the observer hurts** [M]:
  - The filter's twist does not contain its position corrections. Finite-differenced estimate positions disagree with the rotated twist by 0.39 m/s RMS, mostly through update jumps (p99 1.43 m/s).
  - The twist carries a slow bias: mean velocity error of up to 0.033 m/s per axis on one flight. Integrating it alone gives about 1 m ATE.
  - Any observer that predicts with velocity and bleeds position therefore discards part of each correction for several τ.
- **Against what we would actually submit** (primary family's single-run average; [vsprim.log](../../research/single_model/ensemble/vsprim.log)) [M]:

  | Member set | st2conf | fconf | Pooled |
  |---|---|---|---|
  | V3, mean | −7.0% | −5.7% | **−6.3% [−7.4, −5.3]** |
  | J3, mean | −6.1% | −6.4% | **−6.2% [−7.2, −5.3]** |
  | V3M3 (6 runs), GM | −9.4% | −5.9% | −7.6% [−11.0, −4.6] |
  | V2M1, GM | −3.8% | −4.8% | −4.3% |
  | J2M1, GM | −6.3% | −4.9% | −5.6% |
  | **V1M1 (GSLV + GSLM), mean** | −6.2% | **+4.1%** | −1.0% [−6.2, +3.8] |
  | V1M2, mean | −7.0% | +1.5% | −2.7% |
  | V1J1M1, mean | −4.6% | +0.2% | −2.2% |
  | VJ6, GM | −6.1% | −7.2% | −6.7% |

  GSLM is the weaker family on fconf (0.305 against 0.270), so mixing it in dilutes accuracy there.
- **Hindsight best-of-K** [M]:
  - 3 replicas: −14 to −16%.
  - Mixed triples: −18 to −23%.
  - 6 runs: −26 to −28%.

  Causal rules capture only about 40% of the hindsight best-of-3.
- **Worst 10% of flights, pooled** [M]:
  - V3 mean: 0.755 against 0.777.
  - J3 mean: 0.810 against 0.829.
  - V3M3 wdis: 0.738 against 0.777.
  - J2M1 on st2conf: 0.884 against 1.011.
  - V1M1 and V1M2: worse in the tail on fconf (0.705–0.772 against 0.687).
- **Same-family pairs, mean of 2** ([pairs.log](../../research/single_model/ensemble/pairs.log)) [M]:
  - st2conf: −3.8% to −5.8%.
  - fconf: −4.0% to −5.1%.
  - Average about −4.6%; with the secondary lagged 5 frames, about −4.1%.

### Inferences
- The baseline's −45% came from fixed-lag smoothers whose trajectories are smooth and whose members differ in *front end* (frame-to-frame versus keyframe-direct tracking, and vision weight). That is a different regime from ours on both counts. Its observer is a fix for hypothesis switching between smooth members. On EKF outputs that carry correction jumps, it is a low-pass filter on the corrections themselves.
- Under raw-ATE scoring, a discontinuous output is free. The only reason to smooth would be to keep pose consistent with the reported twist, which the score does not use. **Recommendation: output the per-frame mean (K=2) or GM/mean (K≥3) with no observer.** If the members' twist must be reported, report the mean twist separately and do not integrate it.
- Weighting by causal disagreement adds at most about 1 percentage point over the plain mean or GM. A causal trust signal therefore has little to work with when the members are this correlated.
- The prior estimate of "−5 to −7% causal for 3 replicas" ([VIO estimator selection and fusion](../../reports/VIO%20estimator%20selection%20and%20fusion.md)) is confirmed with CIs. The tail claim for 3 GSLV + 3 GSLM (top 10%: 0.85 → 0.73 on st2conf) holds only on st2conf. On fconf, mixing in GSLM does not help.

### Gaps
- Neither pool has any flight above 3 m, so the >3 m counts are uninformative (all 0). Whether fusion fixes server-style 1.5–2 m tails (004c, cd6d, 2149) cannot be tested locally beyond the worst-10% proxy.
- The replicas' diversity comes partly from a front-end nudge (`DETECT_MIN_SCORE`). It is unknown how much fusion gain survives when the members share one front end, so that only `PIXEL_STD`-type back-end nudges or seeds differ. This needs a new 3-rep run with only back-end nudges.
- Rotation fusion was not replayed: ATE is translation-only, and our outputs are scored on position.

## T4: per-frame fuel profile and K-back-end peak

### Takeaway
The per-frame peak is a rare spike. On the final-build arithmetic (J):
- Pool peak is 4.3–5.0 M, while p99 is 3.2 M, median 2.1–2.2 M and mean 2.05–2.10 M [M].
- 1.3–1.5 frames per flight exceed 3.5 M, and 98–99% of per-flight peaks occur after frame 60 [M].
- Spikes are only weakly synchronized across replicas: per-frame fuel correlation is 0.37–0.38 [M].

Running K back ends at the same time without sharing costs 1.65–1.72x for K=2 and 2.4–2.5x for K=3 [M, from summed real profiles]. With a shared front end (an assumed 0.6–0.9 M per frame), the primary computed on time, and the secondary back ends **time-sliced with at most 2–5 frames of lag** [E: queueing model on the real profiles]:
- **K=2 fits under the existing peak (1.00x)** on both pools.
- K=3 costs 1.09–1.32x.

Without time slicing, a shared front end alone still costs 1.5–1.6x for K=2 and 2.0–2.25x for K=3 [E].

### Cited Findings
- **Fuel distribution** (all frames, pooled per run; [fuelprof.log](../../research/single_model/ensemble/fuelprof.log)) [M]:

  | Runs | Pool | Peak (M) | p99.9 | p99 | p95 | Median | Mean | Per-flight peak, median |
  |---|---|---|---|---|---|---|---|---|
  | J | st2conf | 4.26–4.70 | 3.5 | 3.22 | 2.90 | 2.11 | 2.05 | 3.6 |
  | J | fconf | 4.42–5.04 | 3.5 | 3.18 | 2.85 | 2.17 | 2.10 | 3.6 |
  | V | st2conf | 6.0–6.6 | 4.4 | 3.6 | 3.1 | 2.2 | — | — |
  | M | st2conf | 6.1–6.3 | 4.4 | 3.5 | 2.9 | 1.7 | — | — |

  - J frames below 1.0 M: 4–6%. M frames below 1.0 M: 10–16%.
  - Mean slack (peak − frame) / peak: 0.52–0.58 for J and 0.6–0.7 for V and M.
  - The server reported 4.2 M peak and 2.8 M p95 for the same build [S] ([LOOP_LOG](../../research/single_model/LOOP_LOG.md)).
- **Split between front end and back end** [S]:
  - T4uB-era profile: zero-row frames cost 0.87–0.90 M (KLT 0.22, pyramid 0.21, detection 0.175, priors 0.146, map 0.03, propagation 0.03). Each MSCKF row costs about 80 k (update 44 k + solve_dx 23 k + gate about 10 k) ([fuelpush/NOTES.md](../../research/single_model/fuelpush/NOTES.md) lines 9-13).
  - On peak frames, update() 1.59 + solve_dx 0.78 are about 63% of the 3.77 M frame; KLT 0.38 and pyramid 0.21 are the front end ([audit/NOTES.md](../../research/single_model/audit/NOTES.md) lines 17-20).
  - The net under NET_SLICE costs about 0.12 M per gray pair-step ([tier1m/NOTES.md](../../research/single_model/tier1m/NOTES.md) line 28).
  - GSLV adds lines, whose per-line fit costs 80–357 k for n=3–7 ([linejac/NOTES.md](../../research/single_model/linejac/NOTES.md) line 114). Line *extraction* cost for GSLV was not found itemized, so the shareable front end FE is bracketed at 0.6 M (KLT + pyramid + detection) and 0.9 M (adding priors, map and propagation) [E].
- **K-back-end model** (`fuelprof.py`) [E]:
  - Secondary back-end work at frame t = max(f_k(t) − FE, 0), taken from a *different replica's real profile* on the same flight, so spike timing is realistic.
  - The primary is served on its frame. Secondary work is FIFO with deadline D frames, checked with an exact demand-bound test.
  - Minimum capacity C, as a ratio to the primary's pool peak:

  | Combination | FE (M) | Pool | D=0 | D=1 | D=2 | D=5 | D=20 | No sharing, D=0 |
  |---|---|---|---|---|---|---|---|---|
  | J+J | 0.6 | st2conf | 1.59 | 1.08 | 1.02 | **1.00** | 1.00 | 1.72 |
  | J+J | 0.6 | fconf | 1.53 | 1.01 | **1.00** | 1.00 | 1.00 | 1.65 |
  | J+J+J | 0.6 | st2conf | 2.15 | 1.46 | 1.40 | 1.31 | 1.25 | 2.41 |
  | J+J+J | 0.9 | st2conf | 2.02 | 1.35 | 1.28 | 1.19 | 1.13 | 2.41 |
  | J+J+J | 0.6 | fconf | 2.25 | 1.39 | 1.27 | 1.21 | 1.18 | 2.49 |
  | J+J+J | 0.9 | fconf | 2.13 | 1.31 | 1.17 | 1.10 | 1.07 | 2.49 |
  | J+M | 0.6 / 0.9 | st2conf | 2.0 | 1.2 | 1.0–1.05 | 1.00 | 1.00 | 2.15 |
  | J+J+M | 0.6 / 0.9 | st2conf | 2.3–2.5 | 1.4–1.5 | 1.3–1.4 | 1.20–1.30 | 1.1–1.25 | 2.72 |
  | J+M+M | 0.6 / 0.9 | st2conf | 2.7–2.9 | 1.6–1.7 | 1.4–1.5 | 1.22–1.32 | 1.1–1.25 | 3.13 |

- **Cost of the lag in ATE** (`lag.py`; the secondary is used D frames late and propagated with the primary's increment) [M]:

  | Member set | D=0 | D=2 | D=5 | D=10 | D=20 |
  |---|---|---|---|---|---|
  | V3 mean, st2conf | −7.0% | −6.7% | −6.3% | −5.8% | −5.1% |
  | V1M1, st2conf | −7.0% | −6.8% | −6.6% | — | −5.6% |
  | J2M1 GM, fconf | −11.2% | −10.9% | −10.7% | — | −9.9% |

  About 0.1 percentage point of gain is lost per frame of lag.
- **The fuel governor is the existing mechanism for a per-frame budget** [S]:
  - GOV_B caps per-frame work, splits MSCKF features, and defers detection cells and net units ([tier1m/NOTES.md](../../research/single_model/tier1m/NOTES.md) lines 52-54).
  - The measured overshoot over GOV_B is about 0.2–0.3 M ([fuelpush/NOTES.md](../../research/single_model/fuelpush/NOTES.md) line 35).
  - Squeezing a *single* filter's budget is costly: GOV_B 3.6 M gives +0.039, 2.7 M +0.057 and 1.8 M +0.313 ATE against an unbudgeted run ([tier1m/NOTES.md](../../research/single_model/tier1m/NOTES.md) lines 64-69).
  - The delay of the net measurement, not its arithmetic, made NET_SLICE bad ([tier1m/NOTES.md](../../research/single_model/tier1m/NOTES.md) line 45).

### Inferences
- **The secondaries must be lagged, not squeezed.** Splitting the budget so each of K members gets about 4.2/K M every frame would push each member into the GOV_B 1.8–2.7 M regime, which costs +6 to +31% ATE per member. That is larger than any fusion gain measured here. The workable design gives the primary its normal governed budget and runs secondary back ends in the primary's slack frames, at most 2–5 frames late. Their results enter the fused output after a lag; they are not fed back into the primary.
- The headroom comes from the primary's spike being rare (1.3–1.5 frames per flight above 3.5 M). The server peak is a max over all frames of all episodes, so the secondary scheduler must be work-conserving and never preempt the primary. A governor overshoot of 0.2–0.3 M on a secondary step would land on top of the primary's frame. The secondary budget should therefore be the primary governor's GOV_B minus primary use minus about 0.3 M margin [E].
- Memory is not a constraint for 2–3 copies of a 24+6·clones state covariance (inference; not measured).

### Gaps
- The GSLV line-extraction cost (front end) is not itemized in the notes found. FE = 0.6–0.9 M is a bracket and is the largest uncertainty in the K=3 ratio (1.1x against 1.3x).
- The time-slicing model assumes secondary back-end work is divisible into roughly 80 k-instruction row steps that can be paused across frames. The existing governor splits by feature and row (tier1m), but a mid-update pause (Cholesky, solve_dx) would need new code.
- Profiles are local, single-run frame alignments. The server's 4.2 M peak and the 4.3–5.0 M local peaks indicate local profiles are a slightly pessimistic proxy.

## Which fusion level is best for us: pose consensus, measurement-level, or feedback

### Takeaway
The best architecture is **one shared front end (KLT, pyramid, detection, velocity net) + a primary GSLV-linejac back end on the normal governed budget + one time-sliced secondary back end (K=2), lagged by 2–5 frames, with per-frame mean of the two positions as the output, no observer and no feedback.**
- Expected change: **about −4% ATE at about 1.00x peak**, worth **+0.09 points** (server 0.633 → about 0.607 m). This holds only if back-end-only diversity reproduces the replicas' chaos [E from M].
- K=3 with GM or mean: about −5.7% (lag included) at 1.1–1.3x peak, worth about +0.02 to +0.09 points [E]. That is not better than K=2 and is riskier.
- Measurement-level velocity fusion and member re-anchoring (feedback) both measured as weak or negative in proxy form.
- Pairing with GSLM is not robust: +4.1% on fconf.

### Cited Findings
- **Score arithmetic** [E], using the law in the header:

  | Design | Assumed peak | Assumed ATE change | Points |
  |---|---|---|---|
  | **K=2 time-sliced** | 1.00x | −4.1% | **+0.094** |
  | K=2 time-sliced, if peak slips | 1.05x | −4.1% | +0.074 |
  | K=3 replicas, mean, D=5 | 1.10x (FE 0.9) | −5.7% | +0.093 |
  | K=3 replicas, mean, D=5 | 1.31x (FE 0.6, st2conf) | −5.7% | +0.022 |
  | K=2, no time slicing, shared front end | 1.47–1.59x | −4.6% | −0.05 to −0.08 (net negative) |
  | Plain 3x copies, no sharing | 2.4x | −6.3% | −0.21 |
  | 6-run GM, no sharing | about 5x | −7.6% | about −0.47 |

  Break-even for K=2 at a peak of p: ATE must fall by 1 − p^(−0.18).
- **Measurement-level velocity fusion has little information to add** [M]:
  - The GM of member velocities has an RMS error against ground-truth velocity of 0.148 (st2conf) and 0.128 (fconf), against 0.150–0.154 and 0.131–0.133 for single runs: only 2–4% better ([cons_sum.log](../../research/single_model/ensemble/cons_sum.log)).
  - Velocity-disagreement weighting plus the observer gave +10 to +14% (worse).
  - The members share the same velocity bias, so feeding one member's velocity into another as a soft measurement mostly double-counts correlated information. It needs an inflated or Schmidt-style covariance, which earlier soft-mode tests also found neutral to harmful [S] ([VIO estimator selection and fusion](../../reports/VIO%20estimator%20selection%20and%20fusion.md); [learnvel/NOTES.md](../../research/single_model/learnvel/NOTES.md)).
  - By contrast, the velocity net's error during filter failures is 0.44 against the filter's 1.41 m/s [S] ([learnvel/NOTES.md](../../research/single_model/learnvel/NOTES.md), via the prior report). The net is the measurement worth fusing, and it already is fused.
- **Feedback proxy** (each member shifted onto the consensus every P seconds, then keeping its own increments) [M]:

  | Member set | Pool | Re-anchor every 1 s | Every 5 s | No feedback, GM |
  |---|---|---|---|---|
  | V3 | st2conf | +2.1% | −2.4% | −5.5% |
  | V3 | fconf | +0.4% | −3.8% | −5.9% |
  | V3M3 | st2conf | −5.6% | −10.2% | −11.7% |

  Re-anchoring collapses the members onto one point, which destroys the diversity the consensus needs. Every proxy variant was worse than no feedback.
- **Hard-switch and selection precedent** [S]: hard mode switches keyed on starvation made GSLV-family filters worse, and multi-hypothesis startup splicing was worse than baseline at every switch time ([VIO estimator selection and fusion](../../reports/VIO%20estimator%20selection%20and%20fusion.md); multihyp notes). Here, the medoid (causal selection) was consistently below the mean or GM [M].
- **Handling discontinuities** [M, E]:
  - With K=2 mean fusion, the output is as continuous as the members, so there is no switching.
  - GM with K≥3 can jump when the median changes vertex. That costs nothing under raw ATE, while the baseline's smoothing costs +10 to +15%.
  - Lagged secondaries are brought to time t with the primary's increment: s_k(t−D) + p0(t) − p0(t−D). This adds about 0.1 percentage point of ATE per frame of lag.
- **Hypothetical diversity from member choice** [M]: GSLM is the only partially decorrelated family (r 0.75–0.79 against GSLV), but it is the weaker model on fconf. Mixing it in is −6% on st2conf and +4% on fconf for K=2, so it is not robust.

### Inferences
- **Recommended build** [E]:
  1. Front end once.
  2. Primary = GSLV-linejac, unchanged, on its governed budget.
  3. Secondary = the same back end with a different back-end-only perturbation (pixel sigma ×1.01, or a different chi² or row-subsampling seed), fed the same tracks. It runs in a work-conserving slack scheduler with deadline D ≤ 5 frames and a budget of GOV_B − primary use − 0.3 M margin.
  4. Output = mean of the primary at t and the secondary propagated from t−D.
  5. Twist output = the primary's twist.
  6. No feedback.
- **Go/no-go test before building:**
  1. Run 3 reps of a variant with **only `PIXEL_STD` nudged** (DETECT fixed) and replay `pairs.py`. If the pair gain stays at about −4% or better, build it.
  2. If the gain falls toward 0, the chaos lives in the front end. A shared front end then kills the ensemble, and K separate front ends cost 1.65x or more (no sharing), which is net negative.
- **Expected score** [E]: K=2 at about 1.0x with −4% gives about +0.09 points, a modest gain. The −4% comes mostly from bulk flights. The worst 10% improve by about the same percentage, not more. The server tails (004c, cd6d, 2149, 70% of error) would improve proportionally (about −4%), not be rescued. Larger gains need mechanism-diverse members whose failures differ on the tail flights. None of our stored families provides that: V and J correlate at r = 0.88–0.91 and are the same model.
- K=3 or more does not earn its extra peak unless FE is at the high end (0.9 M) and lag stays at 5 frames or fewer. Expected net change against K=2 is −0.07 to +0.00 points [E].

### Gaps
- Back-end-only diversity (shared tracks) is untested. All replica chaos measured here includes a front-end detector nudge. This is the decisive unknown.
- The time-sliced secondary scheduler and pausable back-end steps do not exist in code. Their real overhead and peak overshoot (the governor's is 0.2–0.3 M today) are unmeasured.
- Local pools have no >3 m flights, so the effect on server-style 1.5–2 m tail episodes cannot be measured. Server per-episode transfer is assumed proportional.
- No primary-literature search was done in this task (scope was offline replay). External citations are inherited from the prior report.
