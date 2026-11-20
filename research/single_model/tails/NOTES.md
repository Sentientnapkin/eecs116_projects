# Tails of f0 (gp_msckf + heading-aware startup prior): mechanisms and fixes  (FINAL)

Slices: search = folds 0-2 (n=119), val = fold 3 (n=25). Fold 4 / sealed files never opened. f0 reference = research/results/single_model/final_f0
(per-flight rows read through report.json rows_visible; diag build t0.c reproduces f0 exactly: search 1.033 / val 0.524).
f0 on search: mean 1.033, median 0.54, static 0.678, mid 1.348; val: 0.524 (no flight above 3 m in val).

## 1. Flights above 3 m (search; val has none; fold 4 untouched)
f0 ATE; "persistent" = bad in all 3 chaos replicates (PIXEL_STD/DETECT_MIN_SCORE 1% nudges, tails_ref_r0..2).
| flight | start | f0 | mechanism (from saved estimate/twist vs truth + diag counters t0.c) |
|---|---|---|---|
| fastmid-106366104_174226329-00 | mid | 8.50 | scene 26329 is flat (mean abs gradient 0.6 vs median 2.9, gray 94): live tracks 0-4 for all 60 s, no vision, pure IMU, yaw drifts to 50 deg. Persistent. |
| fast-106366104_174226329-00 | static | 8.04 | same flat scene, hover start fine to 3 s, error appears when it starts flying (2.4 m/s at 5 s) with no tracks. Persistent. |
| fastmid-106366104_174226329-02 | mid | 5.85 | same flat scene |
| fastmid-106366104_174226329-01 | mid | 4.90 | same flat scene |
| fastmid-108294897_176710602-01 | mid | 5.37 | wrong-direction startup (true start v 1.35 lateral/-0.7 back at 1.9 m/s, camera axis 114 deg from travel) then lock-out. Persistent (5.4/5.9/11.2). |
| fastmid-ProcTHOR-Train-123-00 | mid | 4.14 | same: heading 142 deg off. Velocity estimate has the OPPOSITE sign at 1 s (est (-1.1,-.5,.7), true (1.3,0,-1.0)); every triangulation then fails with the feature behind the camera (tri fails 58/58 per s, used 0 for 5 s). Persistent. |
| fastmid-102344457-01 | mid | 3.82 | same, heading 148 deg off. Persistent. |
| fastmid-ProcTHOR-Train-178-01 | mid | 3.39 | same, heading 140 deg, 2.2 m/s lateral. First vision update (t=0.84, 3 rows, one feature) kicks dv 1.65 m/s, dtheta 10 deg the wrong way. |
| fastmid-ProcTHOR-Train-143-01 | mid | 3.61 | forward start (20 deg) but runaway at 3-6 s (est 2 vs true 0.6 m/s), cheirality flood; chaotic (3.6/5.3/7.2). |
| fastmid-ProcTHOR-Train-100-02 | mid | 4.37 | dark (gray 27, grad 0.5); chaotic (4.4/13.1/8.1). |
Not >3 m but in the 2.5-3 band: 151-00 (2.88, chaotic to 10.9), 158-07 (2.75, grad 0.59).
Summary: 4 of 10 are one textureless scene (front-end starvation, not startup); 4-5 are startup flights whose travel direction is >90 deg from the camera axis, where the heading prior (0.9 m/s forward) has the wrong sign and the filter locks out (negative-depth triangulation flood, no vision updates for 2-5 s). The oracle (vx_0.3) takes these to 0.5-1.9 m, so velocity direction at start is the lever. Static start: only the flat-scene flight (no motion-detector problem). Bias is not a factor (|dba| < 0.15 m/s^2, error is 5-10 m in seconds).
Not the mechanism: single big first update (a trust-region cap on early dv made it worse), IMU bias, gyro bias.

## 2. Findings that drive the fixes (verified on search+val flights, truth only for the check)
- De-rotated feature flow between the first and the 3rd/4th clone (0.4-0.6 s) gives the camera translation DIRECTION with median error 10 deg, p90 18 deg (63 moving flights), including the flights flying backwards; the heading prior has median 19 deg, p75 51 deg off. Speed from flow magnitude x typical depth 2 m: log corr 0.87, median abs error 0.16 m/s (const 0.97: 0.42). Velocity from flow therefore meets the oracle spec (sigma ~0.3, direction within 30 deg).
- Applying the flow velocity everywhere HURTS the flights where the heading prior is already right (<75 deg: f0 0.69 vs 0.93 mean on 48 flights) and helps hugely where it is wrong (>75 deg: 2.0 -> 0.7 on 10 flights). So: replace the prior only when flow direction disagrees (cos(flow dir, camera axis) < 0.26).
- Flat scene: Shi-Tomasi threshold 1000 and KLT min-eigenvalue 2.0 reject the faint floor texture. Scaling both by clamp((mean abs gradient / 0.8)^2, 0.05, 1), with the gradient averaged slowly (EMA 0.05/frame), fixes the 4 flat flights (8.0->2.4 static; 8.5->3.3; 5.9->1.8; 4.9->3.2) without touching normal scenes. Without the EMA, a plain wall in view lowers thresholds and val static flights regress (160-02: 0.4 -> 6.7 m).

## 3. Arms (search = folds 0-2, mean vs f0 1.033 single run; chaos-averaged = mean of 3 replicates vs f0 replicates 1.033/1.227/1.297 = 1.186)
| arm | change | search mean (static/mid) | >3 / >5 / >10 | paired d vs f0 [95% CI] | val | verdict |
|---|---|---|---|---|---|---|
| a1 | contrast-adaptive detect+KLT, G0 1.2, no EMA | 0.996 (0.602/1.347) | 10/3/0 | -0.036 [-0.32,+0.16] | n/a | flat flights fixed, chaos elsewhere |
| a2 / reps ag08 | same, G0 0.8 | 1.000 (0.577/1.376); reps 1.00/1.144/1.16 | 8/3/0 | -0.03; reps -0.084 [-0.32,+0.07] | val static +0.28 (160-02 6.7 m) | REJECT as is (val static regression) |
| a3 | detect threshold only (no KLT scale) | 1.086 | 10/5/1 | +0.054 | | reject |
| ae08 | G0 0.8 + EMA 0.05 | reps 0.947/1.022/1.186 | 9-11 | reps -0.134 [-0.42,+0.045]; static -0.100 [-0.31,+0.01] | +0.002 | OK, adopted as part A |
| ae10 | G0 1.0 + EMA | reps 0.907/1.139/1.162 | | reps -0.116 | +0.016 | same as ae08 |
| b1 | cheirality-flood trigger (>=12 neg-depth failures/10 frames, <=2 features used, speed>1) -> v:=0, sigma 1 | 1.052 | 8/6/0 | +0.019 [-0.08,+0.13] | = | no effect (fixes 3, breaks 3) |
| b2 | b1 + drop all clones | 1.160 | 10/6/1 | +0.127 | | worse |
| b3/b4 | b1 with v:=-v / -0.5 v | 1.042/1.044 | 9/5/0 | +0.01 | | no effect |
| b5 | b1 with sigma 0.5 | 1.219 | 11/7/1 | +0.186 [+0.04,+0.37] | | worse |
| c1/c2/c3 | trust-region cap on early vision updates (dv<=0.4/0.8 m/s, 3 or 6 s) | 1.295/1.129/1.314 | 10/8/2 | +0.26/+0.10/+0.28 | | worse |
| d1 | flow velocity at 3rd clone, always | 1.083 | 10/5/1 | +0.051 | | regressions on forward starts |
| d3/d4 | flow velocity at 4th clone, always | 0.957 | 7/4/0 | -0.076 [-0.22,+0.05] | | regressions on forward starts |
| d2 | d1 + position reset | 1.045 | 6/3/0 | +0.012 | | median worse |
| d5 / reps vi | flow velocity at 4th clone only if cos(flow,optical axis)<0.26 | 0.917 (0.678/1.130); reps 0.917/1.123/1.09 | 6/3/0 | -0.116 [-0.236,-0.026]; reps -0.142 [-0.295,-0.029] | identical to f0 (never triggers on val) | adopted, part B |
| d6 / d7 | same at 3rd clone / + position reset | 0.956/0.960 | 7/4,3/0 | -0.076/-0.073 | | slightly worse than d5 |
| comb2 = adopted.c | A + B | **0.831 (static 0.586 / mid 1.049)**; reps 0.831/0.918/0.980 | 5/1/0 (reps 5-8 >3) | single -0.202 [-0.513,+0.027]; reps -0.276 [-0.580,-0.038]; static -0.100 [-0.310,+0.013] | 0.539 vs 0.524 (static 0.654 vs 0.607, n=12, noise; no >3) | ADOPT (see caveats) |

## 4. Adopted patch
`adopted.c` (built source, defaults baked in) and `adopted.patch` (unified diff vs research/single_model/final/f0.c). Score: research/results/single_model/tails_adopted (search 0.831, val 0.539; peak fuel 23.0 M vs 22.5 M f0, nothing incomplete).
Blocks (all switchable, defaults on):
- TAILS_DET/TAILS_KLT/TAILS_G0=0.8/TAILS_SMIN=0.05/TAILS_EMA=0.05: contrast-adaptive Shi-Tomasi threshold and KLT min-eigenvalue; update_tex_scale() computes the mean abs central gradient (stride 3) per frame, EMA-smooths it.
- VI_MODE=1, VI_CLONES=4, VI_TMAX=1 s, VI_NMIN=8, VI_Z0=2.0, VI_COSMAX=0.26: flow_dir() (LS over de-rotated flow between oldest and newest clone, common inverse depth) and vi_reset(): at the 4th clone of a moving start, if >=8 features and the flow direction is >75 deg from the optical axis, velocity := speed*direction (speed = |a|/dt*Z0, in [0.05,3]), covariance sigma_par = max(0.15, 0.3 speed), sigma_perp = max(0.15, 0.2 speed), cross-covariances zeroed, startup heading prior switched off for the rest of START_T.
Caveats: the single-run CI is [-0.51,+0.03]; it excludes zero only when averaged over the 3 chaos replicates (every replicate is lower than its f0 counterpart: 0.831/0.918/0.980 vs 1.033/1.227/1.297). The evidence for B is 10 search flights (5-6 backward/lateral starts), none in val (val unchanged by construction); the evidence for A is one flat scene (4 flights, one scene cluster) plus the dark flight. Replicate 1 has 151-00 at 10.9 m (f0's own replicates have it at 10.9/9.4): the chaotic flights remain (151-00, 143-01, 100-02, 158-07). Remaining tail after the patch (single run): 100-02 5.4, 158-07 4.3, 143-01 3.4, 26329-00 3.3, 26329-01 3.2.

## 5. Not done / ideas
- Direction/speed from flow could also initialise the tilt (acceleration from two flow velocities gives the thrust direction), but the accuracy (0.3 m/s over 0.4 s -> 6 deg) is no better than the current 7 deg; a longer window (1 s) with the closed-form alignment is the C4 route.
- The chaotic flights (143-01, 151-00, 100-02, 158-07) depend on small perturbations after 3 s; no mechanism found beyond starvation (100-02, 158-07 are low-contrast scenes) and runaway after hover.

## 6. Reproduce
`run.sh <name> <src.c> "<defines>"` (35 s), `rep.sh` (3 chaos replicates, name_r0..2), `cmp.py arm` (paired bootstrap vs f0, search+val), `cmprep.py tails_ref arm` (replicate-averaged), `flights.py arm [thr]`. Diagnostics: t0.c (f0 + per-frame counters, flow-direction log; behaviour identical), a.c/b.c/c.c/d.c (arms), scripts in the scratchpad only. Run names: tails_ref_r*, tails_comb2_r*, tails_adopted, tails_t*, tails_a*, tails_b*, tails_c*, tails_d*. Note: run_variant reuses an existing eval folder if the name already exists with the same digest; use a fresh name per source change.
