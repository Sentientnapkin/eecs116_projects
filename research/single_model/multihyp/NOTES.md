# multihyp: multi-hypothesis (K parallel filters) inside one estimator
Step 1 (feasibility): B6 (frontend/adopted_fbh.c) builds with different startup hypotheses (-D START_MEAN_FWD / START_STD_*),
debug build logs per-frame NIS / feature stats to stderr; oracle best-of-K and causal selector computed offline.
(log below)
- created dir; dbg.c = b6fix/diag.c + NIS counters (mk.py).
- Hypotheses built from dbg.c (B6 + NIS/feature stderr logging; behaviour unchanged): h0 = B6 (fresh 0.6184 = B6 reproduced exactly), h1 = zero-mean broad prior (MEAN_FWD=0, STD_XYZ=1), h2 = reverse prior (MEAN_FWD=-0.9), h0r = B6 nudged replicate (PIXEL_STD=1.515 DETECT_MIN_SCORE=1010; control for chaos/winner's-curse).
  run1.sh name "defines" -> 171 (results/single_model/mh_<name>) + fresh 711 (fresh_mh_<name>); ana.py/sel1.py = per-frame features (windowed NIS/dof of MSCKF updates, per-feature chi2, accepted-feature rate, Pv) and selectors.
- h1 fresh 0.871 (static identical 0.409, mid 1.334 vs 0.829). oracle(h0,h1) 0.521. Selector first pass (h0,h1): accepted-feature rate over first 3 s -> 0.574 (but NOT yet controlled for chaos; see h0r control).

## STEP 1 RESULT (fresh 711; B6 = h0 0.618; tables in multihyp/tables/)
means: h0 0.618 | h1 zero-broad 0.871 | h2 reverse(-0.9) 0.755 | h0r (B6 nudged replicate) 0.628. >3 m: 21/45/32/25.
Oracle best-of-K (per-flight min of final ATE): (h0,h0r) 0.552 [pure chaos winner's-curse control] | (h0,h1) 0.521 | (h0,h2) 0.485 | (h0,h1,h2) 0.459 | (h0,h2,h0r) 0.444 | all four 0.426.
h2 is the genuinely complementary hypothesis: 135-180 deg bin mean 0.80 vs 2.04 (h0), 90-135 0.89 vs 1.05; worse in 0-45 (1.29 vs 0.68).
Non-causal selectors (commit one hypothesis for the whole flight, decided from features over first Tw s): accepted-feature rate (used/attempted) is best: (h0,h2) Tw=3 0.545, Tw=5 0.511 (decision accuracy 85%/93% on flights where hypotheses differ by >0.5 m); NIS/dof 0.581/0.526; prior-NIS useless (0.80). Control (h0,h0r) best selector 0.599.
BUT these are not causal outputs: the output must be emitted every frame, so before the decision the default hypothesis' poses are already emitted, and the position error accrued under the wrong velocity prior persists (ATE is raw, unaligned).
Causal splice (output h0 until Ts, then chosen hypothesis' relative motion carried on h0's pose at Ts; splice.py/causal.py, estimate.tum based, ATE re-evaluated with the pinned evaluator):
 Ts=1.0 s: 0.650 | 1.5 s: 0.666 | 3 s: 0.682 (all WORSE than B6 0.618; non-causal commit 0.581/0.568/0.545).
PERFECT-oracle switch bound (choose the truly better of h0/h2 per flight, switch at frame k): switch at 0 s -0.122 (=oracle), 0.5 s -0.095, 1 s -0.052, 2 s -0.011, 3 s +0.000 vs B6 on 711 fresh. MSCKF updates start only after ~0.6 s (3 clones x 4 frames), a reliable decision needs >=1-3 s, so the achievable causal gain with an imperfect (75-85%) selector is <= 0 .
CONCLUSION: in-filter K-instance version NOT BUILT (step 2-4 skipped). The redundancy idea is blocked by causality + raw ATE: hypotheses are only distinguishable after the damage is done. Possible residual ideas (not pursued, expected small): (a) hedge by emitting the pose-average of h0/h2 until decided; (b) better single prior mean (h2 is better on 90-180 deg but costs 0.3-0.6 m on 0-90 deg).
