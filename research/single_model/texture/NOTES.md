# C9 (textureless / track robustness) and C7 (consistency) - working notes

(Status: in progress, updated as runs finish. Baseline = submitted gp_msckf: search mean 2.307, mid 3.764, static 0.667; val 2.032.)

Files: `orig.c` = original solution.c; `texture.c` = original + switchable blocks (all default to original behaviour; -D flags
via `run_variant --defines`); `base_dbg.c` = original + counters/covariance log only (`-DTEX_DEBUG`, ATE identical to baseline);
`analyze.py` (stderr -> per-flight NEES/counters pickle), `nees_report.py`, `tracks_report.py/.txt`, `flights.py`, `summ.py`, `run_batch.sh`.

## Switches in texture.c
- `TEX_DETECT_BRIGHT=1`: Shi-Tomasi detection threshold x clamp((mean gray/130)^2, 0.15, 1) (adaptive to dark frames).
- `DETECT_MIN_SCORE=300/600`: fixed lower threshold. `KLT_MAX_ERR=40`: looser track-drop test.
- `TEX_KLT_NORM=1`: KLT residual with patch mean removed (brightness normalized); `=2`: mean removed and gain fitted (clamped 0.5..2).
- `TEX_KLT_RETRY=1`: a track lost from the gyro-predicted start is retried from its last position.
- `Q_TH_MULT`, `Q_V_MULT`: IMU white-noise process multipliers. `PIXEL_STD`; `TEX_PIX_LEN_K`: pixel std x (1+K(MAX_OBS-n)/(MAX_OBS-MIN_OBS)).
- `TEX_FEJ=1`: feature Jacobians at clone poses as at cloning time (first-estimate); `=2`: and the feature point re-triangulated there.
- `TEX_GATE_EARLY_Z/T`: looser per-feature gate in the first seconds (not run).
- `noise1/noise2` arms (DETECT_MIN_SCORE=1010, PIXEL_STD=1.51) are chaos controls: a ~1% perturbation.

## Chaos caveat (important)
Controls noise1/noise2 (1 % parameter nudges) move search mean by -0.03 / -0.19 and val by +0.05 / -0.015, but val mean in
many arms swings by -0.9..-1.1 (val 2.03 -> ~1.0-1.3), driven by 1-2 flights of the >10 m class flipping (val >10m 1 -> 0).
A search paired-CI that only just excludes zero and val-mid movements of +-1.5 m are within this chaos; only effects
repeated across independent mechanisms (and on the textureless/dark subset, where the mechanism is causal) are believable.

## Per-flight track-count analysis (search slice, baseline, `tracks_report.txt`)
See tracks_report.txt. Summary: mid-start flights bad (>3 m, n=23) have 43 live tracks vs 46 in good ones in the first 2 s;
long (>=MIN_OBS) tracks 16.9 vs 19.0; the bad flights are brighter-poorer (mean gray 117 vs 142) and flat fraction 0.15 vs 0.01.
Only 8 of 119 search flights have <6 long tracks on average in the first 2 s; 5 of those are all-flat 26329 scenes
(flat=1.0, gray 95) plus one very dark flight (R-Train-100-02 mid, gray 17, 16.6 m). So track starvation is a minor lever overall
but is a real lever for these tail flights, which is what detbright targets: 26329 static 8.04->4.87, mid 10.35->4.14,
7.24->5.38, 5.63->4.61, dark 16.59->8.01 (det300/det600 and retry give partial gains on a subset; norm1 mixed).

## NEES tool (C7)
`base_dbg.c -DTEX_DEBUG` writes per frame `T t pos(3) vel(3) poscov(6) velcov(6) | counters` to stderr (covariance rotated to the
output frame, lever-arm term ignored); `analyze.py` joins with truth, `nees_report.py` prints NEES. Baseline (texture_dbg, search):

| group | window | vel NEES mean / median of flight medians | pos NEES mean / median |
|---|---|---|---|
| static | 0-5 s | 8.9 / 3.0 | 15.3 / 4.4 |
| static | 5-60 s | 4.4 / 2.7 | 11.8 / 4.2 |
| mid | 0-5 s | 86.5 / 16.7 | 407 / 75 |
| mid | 5-60 s | 14.9 / 3.4 | 104 / 41 |
| all | 5-60 s | 10.0 / 3.1 | 60.5 / 12.2 |

Ideal is 3. Median velocity NEES in steady flight is about 3 (consistent); position NEES is 4x (static) to 14x (mid) overconfident
(position is a drift/unobservable direction so some excess is expected). The big excess is the mid-start startup transient.

## Arms table (search = 119 flights; paired d vs baseline with scene bootstrap 95 % CI)
Filled below by `summ.py`; see end of file.

(All fuel: peak per-frame 22.0-23.8 M, i.e. unchanged vs the 22.5 M baseline; nothing near the 40 M limit.)
S = search n=119 (static 56 / mid 63). d = paired scene-bootstrap vs submitted baseline (2.307). Val = fold 3, n=25 (noise ~0.3-0.4 m, and chaotic: see caveat).

| arm | change | S mean / med | static | mid | >5 / >10 m | paired d [95% CI] | val mean | verdict |
|---|---|---|---|---|---|---|---|---|
| ref/dbg | baseline rebuild / debug build | 2.307 / 0.83 | 0.667 | 3.764 | 17 / 6 | 0 | 2.032 | identical to submitted |
| detbright | TEX_DETECT_BRIGHT=1 (threshold x clamp((gray/130)^2,.15,1)) | 1.914 / 0.84 | 0.598 | 3.084 | 12 / 3 | -0.39 [-0.74,-0.09] | 1.930 (d -0.10 [-0.25,-0.02]) | ADOPT (causal: fixes flat/dark tail flights) |
| det300 | DETECT_MIN_SCORE=300 | 2.050 / 0.80 | 0.767 | 3.190 | 16 / 3 | -0.26 [-0.67,+0.09] | 1.126 | reject (static +0.10) |
| det600 | DETECT_MIN_SCORE=600 | 2.060 / 0.75 | 0.619 | 3.341 | 16 / 4 | -0.25 [-0.58,+0.06] | 0.966 | not significant |
| norm1 | KLT patch-mean removed | 1.976 / 0.71 | 0.654 | 3.151 | 13 / 4 | -0.33 [-0.68,-0.00] | 1.249 | borderline, no new tails; not adopted alone (mixed on starved flights) |
| norm2 | mean removed + gain | 2.149 | 0.822 | 3.328 | 17 / 4 | -0.16 [-0.62,+0.26] | 1.332 | reject (static +0.16) |
| err40 | KLT_MAX_ERR 40 | 2.376 | 0.666 | 3.896 | 19 / 8 | +0.07 [-0.27,+0.42] | 1.102 | reject (more >10 m) |
| retry | retry lost KLT from last position | 2.012 | 0.677 | 3.198 | 13 / 3 | -0.30 [-0.79,+0.09] | 1.180 | not significant |
| c1 | detbright + norm1 | 1.947 / 0.72 | 0.689 | 3.065 | 10 / 5 | -0.36 [-0.75,+0.01] | 1.334 | no better than detbright alone |
| c2 | c1 + retry | 2.570 | 0.751 | 4.187 | 21 / 6 | +0.26 [-0.39,+0.92] | 1.804 | reject |
| gate | looser early gate z=3, 5 s | 2.187 | 0.737 | 3.477 | 17 / 6 | -0.12 [-0.57,+0.30] | 1.667 | reject |
| noise1 / noise2 | chaos controls (1% nudges) | 2.276 / 2.115 | 0.667 / 0.635 | 3.71 / 3.43 | 16 / 5, 15 / 4 | -0.03 / -0.19 | 2.087 / 2.017 | shows noise floor ~0.2 on search |
| q2 / q4 | Q_TH=Q_V=2 / 4 | 2.026 / 1.906 | 0.743 / 0.857 | 3.17 / 2.84 | 15 / 3, 12 / 4 | -0.28 [-0.70,+0.08] / -0.40 [-1.01,+0.03] | 1.086 / 1.343 | reject: static worse (q4 +0.19 sig) |
| qv2 | Q_V_MULT=2 only | 1.929 / 0.83 | 0.648 | 3.067 | 16 / 2 | -0.38 [-0.84,-0.03] | 1.595 | passes alone; gain vanishes on top of heading prior (below); optional |
| qth2 | Q_TH_MULT=2 only | 2.144 | 0.703 | 3.425 | 14 / 6 | -0.16 [-0.42,+0.09] | 1.805 | reject |
| pixlen | pixel std x(1+0.5..) by track length (K=0.5) | 2.023 | 0.740 | 3.163 | 15 / 4 | -0.28 [-0.68,+0.07] | 1.334 | not significant, static +0.07 |
| fej1 | FEJ clone poses in Jacobians | 4.187 / 1.15 | 0.937 | 7.076 | 26 / 15 | +1.88 [+1.01,+2.87] | 1.973 | REJECT, much worse |
| fej2 | FEJ + feature re-triangulated | 4.852 / 1.21 | 1.141 | 8.151 | 36 / 15 | +2.55 [+1.31,+3.93] | 3.999 | REJECT, much worse |

### On top of the heading-aware startup prior (stack.c = startup/v2.c + texture switches; PRIOR_MODE=3)
| arm | S mean / med | static | mid | >5 / >10 | d vs submitted | val mean (mid) |
|---|---|---|---|---|---|---|
| sk_head (PRIOR_MODE=3) | 1.327 / 0.57 | 0.678 | 1.904 | 9 / 0 | -0.98 [-1.73,-0.41] | 0.631 (0.654) |
| + detbright | 1.287 / 0.60 | 0.600 | 1.897 | 7 / 0 | -1.02 [-1.76,-0.45] | 0.592 (0.658) |
| + detbright + norm1 | 1.258 / 0.60 | 0.705 | 1.749 | 6 / 1 | -1.05 | 1.035 (1.239, new >10 m) |
| + qv2 | 1.340 | 0.653 | 1.950 | 8 / 1 | -0.97 | 0.635 |
| + detbright + qv2 | 1.244 / 0.57 | 0.601 | 1.815 | 7 / 0 | -1.06 [-1.80,-0.47] | 0.629 |

Gains shrink as predicted: detbright adds -0.04 on search mean (-0.08 on static, >5 m flights 9 -> 7), within noise individually but with the
same causal direction and no new tails; qv2 adds nothing (+0.01). norm1 adds a >10 m flight and worsens val: not adopted.

## Findings
- C9: the only change with a CI excluding zero that also helps tails/static and has a clear mechanism is the brightness-scaled detection threshold
  (4 of the 8 starved/dark flights drop by 1.2-8.6 m: dark 16.6 -> 8.0, 26329 mid 10.4 -> 4.1). Normalized KLT and retry help some flights, hurt others.
  Textureless is a minor lever for the mid starts overall (as diag/NOTES said); on the heading-prior stack detbright is worth about -0.04 mean, -0.08 static.
- C7: velocity NEES in steady flight is ~3 (consistent, median) but position NEES is 4x (static) to 14x (mid) overconfident, and the mid startup transient
  has velocity NEES 87 / position 407 in 0-5 s. Doubling process noise (q2/q4) or velocity noise alone (qv2) lowers search ATE on the baseline
  (-0.28..-0.40) but static gets worse for q2/q4 and the gain disappears once the startup prior fixes the transient; so the inconsistency
  is mainly the startup, not steady state. FEJ, the textbook consistency fix, made things much worse here (probably because the Jacobians at the clone-time
  pose are poor when the pose estimates change a lot after the early corrections; no time to bisect an implementation bug, so treat as
  "not working as implemented"). Pixel-noise scaling by track length: not significant. Better consistency did not translate into ATE gains beyond the startup fix.
- No `nees` re-measurement for each arm was run (only baseline); ATE is the only after-metric.

## Recommended adopted set
Only `TEX_DETECT_BRIGHT` (detection threshold scaled by the squared mean brightness). `adopted.patch` (unified diff vs orig.c, 32 lines) and
`adopt.c` (built variant source; `texture_adopt` scores bit-identically to `texture_detbright`: S 1.914, static 0.598, mid 3.084, val 1.930, fuel 22.6 M).
Combined with heading prior: `stack.c` with `-DPRIOR_MODE=3 -DTEX_DETECT_BRIGHT=1` (S 1.287, val 0.592). The one hunk of the gate arm did not patch into stack.c (unused).
