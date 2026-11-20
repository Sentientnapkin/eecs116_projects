# b6fix: mechanism analysis and targeted fixes for B6 (frontend/adopted_fbh.c)  -- WORK LOG (updated as I go)

## Tools
- diag.c = adopted_fbh.c + per-frame stderr counters (mkdiag.py; behaviour unchanged: search 0.950, val 0.442, fresh 0.6184 reproduce B6). FB_ON=0 = G+C1 front end.
- runs: results/single_model/b6f_diag (171), fresh_b6f_diag (711), b6f_diag0 (no-FB, 171), b6f_reg0 (no-FB on 60 fresh flights).
- mech.py (per-flight: error onset (first >3 m), err@2/5/10 s, attitude error, live/live3 tracks, accepted features, FB drop fraction, tri/gate fractions), classify.py (rule tree), mech_table.json.
- fx.c = adopted_fbh.c + switchable fixes (mkfx.py + block.h); all FX_* default to 0 => B6.

## 1. Mechanism table (B6 flights > 3 m; fresh 21, selected search/val 12 (11 distinct rows incl. 66104 trio))
Rule tree (classify.py): live tracks median < 5 = textureless; < 25 = starved coasting; else onset(err>3 m) < 6 s -> startup (wrong direction: mid, angle>90 deg, speed>0.5; fast: start speed>1.8; lock-out: accepted-feature rate ~0 before onset; else runaway); onset >= 6 s -> late drift (attitude error at onset >8 deg = tilt, else scale/bias).
| mechanism | fresh n (mean ATE) | selected n (mean ATE) |
|---|---|---|
| starved coasting (live tracks <25 for whole flight; 6 of 9 are FB-regressions) | 9 (4.86) | 1 (4.65) |
| textureless (tracks dead, 1 live track: scene 66104_174226329 flat) | 0 | 4 (4.29) |
| startup wrong direction (>90 deg) | 6 (4.06) | 2 (6.97) |
| startup fast (>1.8 m/s) | 3 (5.52) | 1 (3.22) |
| startup other (runaway, slow/ambiguous) | 3 (4.02) | 0 |
| startup lock-out (no accepted features) | 0 | 1 (4.68) |
| late tilt/attitude drift | 0 | 1 (3.40) |
| late scale/bias drift | 0 | 2 (3.29) |
Per-flight rows: mech_table.json. Pooled evidence: bad flights have median live3 tracks 14 vs 22 and 1.0 vs 1.9 accepted features per frame (good); 20-frame lock-out windows (live3>=8, nothing accepted) are rare (2.5% of frames in bad vs 0.3% in good): the dominant failure signature is track starvation, not a covariance lock-out.
Wrong-direction / fast starts: onset < 2.5 s (err 3-5 m at 2 s), accepted features ~0 in the 100 frames before onset, est/true speed ratio at 2 s 3-20: startup runaway.

## 1b. FB-induced starvation (the 33 flights worse than G+C1 by >0.5 m on fresh)
Re-ran the 33 (plus the >3 m set) with FB off (diag0). Mean over the 33 (FB vs no FB): live tracks 41.4 vs 47.7, live tracks with >=3 obs 16.3 vs 22.3 (-27%), accepted features/frame 1.28 vs 1.43, chi2-gate rejection 9.5% vs 18.4%, FB drop 10.4% of checked tracks. So FB removes ~13% of live tracks and ~27% of long tracks. The biggest regressions are exactly the low-track flights: static 166-05 (live 35 -> 17, ATE 1.37 -> 5.72), 166-00 (40 -> 18), 176-06, 64-00, 57-00, 85-01 (live 11-24 under FB); 8 of the 33 flipped from <3 m to >3 m. About 12 of the 33 (live 55-60 in both runs, e.g. 97643-00, 82-01, 191-00) are NOT starvation: same track counts, earlier-onset startup divergence (chaotic: err@2 s 0.5 -> 3.8): FB perturbs the startup transient. Dropped tracks are ~half low-texture / fast-flow ones, so FB is mostly an outlier removal that costs 1 long track in 4 when texture is scarce.

## 3. Fix arms (selected = 171 visible, 3 replicates r0/r1/r2; ref = fe2_fbh 3-rep: search 0.931, val 0.441)
- A1 adaptive FB (FX_FBMIN=30: FB only while >=30 of 60 grid tracks alive; rationale: FB trades tracks for outlier robustness, only affordable when tracks are plentiful; assumption: the chi2 gate handles outliers when scarce): search 3-rep 0.944 (d +0.014 [-0.077,+0.105], reps 1.008/0.925/0.901), static 0.474 vs 0.466, val 0.438 vs 0.441, >5 m 4/4/3, >10 m 1/0/0; fuel peak 22.6 M. Selected set: no effect (noise). Fresh: pending below.
  A1 fresh (711): 0.652 vs B6 0.618 (d +0.034 [-0.017,+0.086]); dev +0.046, confirm +0.008; >3 21->18, >5 8->9 => REJECTED (FB is worth its tracks even when starved; chaos-level on the flights it was meant for).
- A2 brightness-adaptive detection + KLT min-eigenvalue (FX_DETB=2; from texture/ detbright; rationale: gradient scores scale with exposure^2; assumption: noise is exposure-independent): fresh 0.627 (d +0.009 [-0.024,+0.049]); dev +0.006, confirm +0.014; >3 21->24, >10 0->1 => REJECTED (no gain; the fresh/selected failures are not dark-frame failures).
- A3 starvation-adaptive chi2 gate (FX_GATEZ=2.5 while nothing accepted for 20 frames with >=8 long tracks, moving; rationale: covariance-based gate locks out when state error exceeds sigma; assumption: outliers are rarer than state-error rejections): fresh 0.632 (d +0.014 [-0.001,+0.035]); dev +0.007, confirm +0.027; >5 8->10, >10 0->1 => REJECTED (lock-out windows are rare: 2.5% of frames in bad flights).
- A4 startup forward sd from the C6 flight-envelope rms (START_STD_Z=0.96 vs 0.6; rationale: prior should cover the true forward-speed spread, assumption: server speed distribution = pool): fresh 0.655 (d +0.037 [-0.003,+0.080]); dev +0.021, confirm +0.069; >3 21->28 => REJECTED (widening hurts the majority of starts more than it helps fast ones).
- A5 lock-out covariance inflation (FX_INFL=0.3 m/s on Pv, 0.03 rad on Pth every 20 frames while starved): fresh 0.615 (d -0.003 [-0.022,+0.016]); dev 0.000, confirm -0.010; >3 21->20, >5 8->8 => no effect, REJECTED (below the 0.03 bar).
- A6 no FB during the first 40 frames (FX_FBT0=40; rationale: FB perturbs the startup transient): fresh 0.638 (d +0.019); dev +0.002, confirm +0.055 => REJECTED.
Selected-set 3-rep runs were done only for A1 (the single arm that targeted a diagnosed mechanism and was not already clearly rejected on fresh); the other arms failed the dev bar on the single 711-flight fresh run (noise 0.02-0.04) so were not replicated.

## DECISION: nothing adopted. B6 stays as is.
adopted.patch is empty; adopted.c is a copy of frontend/adopted_fbh.c (no change). Preflight not applicable. Holdout set not scored.
Finding: failure mass is startup divergence (wrong direction / fast: 12 of 33 flights, err 3-5 m by t=2 s, no accepted features before onset) and track starvation in low-texture scenes (static 166-05, 85-01, 166-00 etc.; FB removes ~27% of long tracks); adaptive FB does not recover them on average, i.e. the effect is chaotic startup sensitivity rather than a clean starvation mechanism.
