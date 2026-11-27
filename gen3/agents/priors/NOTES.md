# priors agent NOTES (plan steps 1, 2, 4: no forward-start assumption, tilt at moving starts, watchdog restart)

## SUMMARY
BEST BUILD: agents/priors/builds/F_sp10/solution.wasm = gslv_s3ft2.c (net agent's ft2 weights spliced into gslv_s3.c) with
  -DPRIOR_MODE=1 -DSTART_STD=2.0 -DSPEED_STD=1.0   (i.e. net agent's s3ft2_iso + SPEED_STD 0.5 -> 1.0). sha256 40355ed95439b443e1432b7ae1dcf240b0576df993d42e94ad3ac91269d5fbd9
- v3val 430, 3 replicates each (r0, PIXEL_STD 1.515/DMS 1010, 1.485/990), paired per-flight rep means:
  s3ft2_iso 0.913 raw / 0.881 srv-w -> F_sp10 0.828 / 0.803, d = -0.085 [-0.118,-0.050]; >3 m (sum of 3 reps) 23 -> 17; peak max 5.11M -> 5.08M.
  single r0: 0.904 -> 0.833; benchmark 0.749 -> 0.657, free-yaw 0.984 -> 0.923; hover 0.801 -> 0.715, mid 0.928 -> 0.860
  (back 0.969->0.936, side 0.766->0.754, fwd 1.045->0.898); rooms 0.454 -> 0.496 (only class that loses), warehouse 1.454 -> 1.274, forest 1.209 -> 1.033.
- v1val 210: s3ft2_iso 0.733 -> F_sp10 0.665, d -0.068 [-0.110,-0.029], rooms 0.376 -> 0.368, >3m 1 -> 2, peak 4.56M. No regression.
- SPEED_STD=2.0 equal on v3val (3-rep d -0.087) but worse on v1val (rooms 0.435) and higher peak (5.46M) -> 1.0 preferred.
WHAT DID NOT HELP (on the ft2 net): MOVE_TILT_STD 0.45 (+0.044, hurts), MOVE_VEL_STD 2.0 (neutral), START_STD 2.5 (neutral),
watchdog restart WD=1 (hard: +0.004; soft WD_SOFT=1: -0.001; triggers fire on ~5/430 flights - GSLV's NIS/speed/bias never look diverged
even in the >3 m failures). Zero-mean direction-free speed shell (PRIOR_MODE=4) bad. On the OLD v700b net: disabling the net (LC_ENABLE=0) was the big win
(-0.43 / v1val -0.28); without any net the forward-mean prior (PRIOR_MODE 3) must stay (zero-mean -> fwd starts fail); the retrained ft2 net
supersedes that (ft2+iso 0.904 vs net-off 1.01 on 430).
Switches added to gslv_s3.c (all default = reference sha eb2799cb): SPEED_STD, LC_SCALE, the 11 top defines (LV_*, TC_GAP, TC_MAXANCH, ...) overridable;
LC_START_EN (0: no startup net, periodic re-anchors on); PRIOR_MODE=4 (+START_MEAN_FWD4, START_SHELL_*); WD watchdog (WD, WD_SOFT, WD_VMAX, WD_BAMAX,
WD_BGMAX, WD_NIS, WD_STREAK, WD_UPTAU, WD_VSTD, WD_TILT, WD_KEEPV, WD_T0, WD_GAP, WD_MAXN, WD_LEVEL, WD_LVMAX, WD_DBG), ported in C from
tmp/goats/submission_stage2/vio.cpp (Vio::restart + watchdog) - reference idea only, default off, NOT recommended.

## Setup
- gslv_s3.c = copy of linejac/final/gslv_linejac_arith.c with (a) SPEED_STD and LC_SCALE made #ifndef-overridable,
  (b) WD watchdog block (WD=0 default, compiled out). No-flag build reproduces eb2799cb (verified after each edit: ref, ref2, ref3).
- mk.py NAME "DEFS" -> builds/NAME/solution.wasm (same cmake/toolchain as run_variant.build). run.sh POOL NAME "DEFS" ... = build+eval, 20 workers,
  waits while load > 170. sc.py = score.py + regime (benchmark/free-yaw) + mid-flight start split by start_fwd_speed
  (back < -0.2, side -0.2..0.5, fwd > 0.5 m/s) + >3/>5 m tails. Eval names: evals/pr_NAME__POOL.json.
- Watchdog port (from tmp/goats/submission_stage2/vio.cpp Vio::restart + watchdog; reference only, re-written in C for GSLV):
  triggers speed > WD_VMAX 6, |ba_i| > 0.4, |bg| > 0.05 (note LV_BGC clamps bg at 0.021 so this never fires), NIS streak
  (per-frame mean m2/gate over attempted features > WD_NIS: +1 else -2; > WD_STREAK). Restart: re-level R from low-passed world specific force,
  v=0 (sd WD_VSTD 2), ba=0, bg reset if > 0.04, fresh covariance, clones/tracks/edges/map cleared (as hz_recover); learned-net periodic
  re-anchors keep running.

## Pool
- v3val refreshed: 152 flights (baseline gslvlj re-run on 152: raw 1.672, median 1.237, >3m 27; hover 0.930, mid 1.847;
  benchmark 1.123, free-yaw 1.941; mid back 2.361 (n=38) / side 1.401 (43) / fwd 1.840 (42)).

## Results log
### Batch 1 (v3val 152 flights, 1 run each, paired vs gslvlj; d = mean diff, paired bootstrap 95% CI)
| name | flags | raw | srv-w | d [CI] | hover | mid | bench | free-yaw | mid back/side/fwd | >3m | peak |
| gslvlj | - | 1.672 | 1.460 | - | 0.930 | 1.847 | 1.123 | 1.941 | 2.361/1.401/1.840 | 27 | 5.10M |
| iso15 | PRIOR_MODE=1 START_STD=1.5 | 1.617 | 1.396 | -0.055 [-0.188,+0.069] | 0.930 | 1.779 | 1.052 | 1.894 | 2.174/1.459/1.751 | 24 | 4.56M |
| iso20 | PRIOR_MODE=1 START_STD=2.0 | 1.530 | 1.335 | -0.142 [-0.265,-0.042] | 0.930 | 1.672 | 1.024 | 1.778 | 1.951/1.334/1.766 | 25 | 5.38M |
| iso25 | PRIOR_MODE=1 START_STD=2.5 | 1.560 | 1.356 | -0.113 [-0.235,-0.008] | 0.930 | 1.708 | 1.037 | 1.816 | 1.967/1.393/1.797 | 24 | 5.11M |
| fwd0 | START_MEAN_FWD=0.0 | 1.576 | 1.365 | -0.096 [-0.218,+0.008] | 0.930 | 1.729 | 1.045 | 1.837 | 2.209/1.282/1.752 | 22 | 4.94M |
| pm0 | PRIOR_MODE=0 | 1.615 | 1.394 | -0.057 [-0.157,+0.046] | 0.930 | 1.777 | 1.083 | 1.876 | 2.193/1.333/1.855 | 25 | 5.61M |
| tilt30 | MOVE_TILT_STD=0.3 | 1.678 | 1.440 | +0.005 [-0.100,+0.101] | 0.930 | 1.854 | 1.094 | 1.963 | 2.246/1.392/1.972 | 28 | 4.56M |
| tilt45 | MOVE_TILT_STD=0.45 | 1.641 | 1.411 | -0.031 [-0.158,+0.080] | 0.930 | 1.808 | 1.069 | 1.921 | 2.269/1.402/1.808 | 26 | 4.42M |
| mv20 | MOVE_VEL_STD=2.0 | identical to baseline (PRIOR_MODE 3 overwrites the V block in initialize) |
| lcoff | LC_ENABLE=0 (net fully off: startup AND periodic re-anchors) | 1.247 | 1.076 | -0.425 [-0.617,-0.225] | 0.836 | 1.344 | 0.981 | 1.378 | 1.626/0.895/1.549 | 7 | 4.54M |
| sp10 | SPEED_STD=1.0 | 1.605 | 1.403 | -0.067 [-0.167,+0.024] | 0.842 | 1.785 | 1.056 | 1.874 | 2.352/1.301/1.767 | 21 | 4.91M |
=> the learned velocity net (v700b, trained at fixed FoV/no blur) HURTS on stage-3 by a lot; zero-mean isotropic start prior helps (~-0.1..-0.14);
   tilt alone neutral. Added LC_START_EN switch (0: no startup net, periodic re-anchors still on) and made the 11 top #defines (LV_*, TC_GAP, ...) overridable.
### Watchdog signal diagnosis (wddbg = WD=1 WD_DBG=2 WD_MAXN=0: logs only, never restarts; per-frame WDF lines; wdan.py)
- Per-frame NIS (mean m2/gate over attempted features) median ~0.03 in ALL flights; frames > 1.8 are 0-3 % both in good and >3 m flights
  -> the reference's NIS-streak trigger never fires on GSLV (its gate/noise scale differs; GSLV gates are loose). Max streak <= 3.
- max filter speed 1.7-4.6 m/s (never > 6); |bg| norm <= 0.036 (LV_BGC clamps per axis 0.021) -> bg trigger never fires; |ba| max 0.14-0.58
  with no separation (0.57 in a 1.06 m flight, 0.15 in a 3.85 m flight). => failures on v3val are NOT detectable by the watchdog's signals;
  expect WD to be ~inert at defaults. Tested anyway (as switch) below.
### Batch 2 (v3val 152, 1 run)
| name | flags | raw | srv-w | d [CI] | hover | mid | bench | free-yaw | mid back/side/fwd | >3m | >5m | peak |
| lsoff | LC_START_EN=0 (no startup net; periodic re-anchors on) | 1.449 | 1.270 | -0.224 [-0.404,-0.014] | 0.864 | 1.586 | 1.187 | 1.577 | 1.937/1.142/1.724 | 18 | 4 | 4.26M |
| lp0 | LV_PERIOD=0 (startup net on, no periodic) | 1.650 | 1.441 | -0.022 [-0.097,+0.056] | 1.065 | 1.789 | 1.127 | 1.907 | 2.301/1.309/1.815 | 25 | 4 | 4.77M |
| lcs3 | LC_SCALE=3.0 (net sigma x3) | 1.337 | 1.178 | -0.335 [-0.453,-0.214] | 0.829 | 1.456 | 0.893 | 1.554 | 1.870/1.056/1.492 | 17 | 1 | 4.57M |
| lcoff_iso20 | LC_ENABLE=0 PRIOR_MODE=1 START_STD=2.0 | 1.768 | 1.509 | +0.096 [-0.151,+0.376] | 0.836 | 1.988 | 1.663 | 1.820 | 2.321/1.187/2.507 | 24 | 8 | 5.11M |
| lcoff_sp10 | LC_ENABLE=0 SPEED_STD=1.0 | 1.064 | 0.930 | -0.608 [-0.778,-0.447] | 0.744 | 1.140 | 0.788 | 1.199 | 1.410/0.798/1.245 | 5 | 2 | 4.69M |
| lcoff_t45 | LC_ENABLE=0 MOVE_TILT_STD=0.45 | 1.208 | 1.040 | -0.464 [-0.656,-0.268] | 0.836 | 1.296 | 0.982 | 1.319 | 1.585/0.961/1.378 | 10 | 2 | 5.18M |
| lcoff_fwd0 | LC_ENABLE=0 START_MEAN_FWD=0.0 | 1.756 | 1.464 | +0.084 [-0.156,+0.345] | 0.836 | 1.973 | 1.860 | 1.705 | 1.926/1.178/2.830 | 25 | 8 | 5.13M |
=> INTERACTION: with the net ON, a zero-mean/isotropic start prior helps (iso20 -0.14) because the net supplies velocity/scale; with the net OFF
   the heading prior is the only early velocity information and removing its forward mean (fwd0 / iso20) is clearly worse (fwd starts 2.5-2.8 m,
   warehouse ~3 m) while backward starts do not improve -> keep the forward mean once the net is off. Weaker whole-flight SPEED_STD (1.0) helps a lot.
### v1val check of lcoff (210 flights, benchmark heading)
| gslvlj | 1.143 raw, srv-w 1.047, >3m 8, peak 5.21M, hover 0.712 mid 1.270, room 0.447 wh 1.757 fo 1.889 |
| lcoff (LC_ENABLE=0) | 0.866 raw, srv-w 0.823, d=-0.277 [-0.417,-0.162], >3m 5, peak 4.74M, hover 0.740 mid 0.903, room 0.489 wh 1.386 fo 1.095 |
=> no regression on v1 conditions either (rooms +0.04, everything else much better).
### Batch 4/5/6 (v3val 152)
| base_r1 | PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0 | 1.679 | srv-w 1.438 | d +0.007 [-0.085,+0.100] | >3m 25 | peak 4.99M |
| base_r2 | PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0 | 1.626 | 1.408 | -0.047 [-0.117,+0.023] | 27 | 4.70M |  (baseline 3-rep mean 1.659)
| lcoff_r1 | LC_ENABLE=0 + r1 | 1.224 | 1.049 | -0.448 [-0.642,-0.252] | 7 | 4.66M |
| lcoff_r2 | LC_ENABLE=0 + r2 | 1.235 | 1.059 | -0.438 [-0.632,-0.228] | 8 | 5.10M |  (lcoff 3-rep mean 1.235)
| lcoff_sp15 | LC_ENABLE=0 SPEED_STD=1.5 | 1.096 | 0.939 | -0.576 [-0.740,-0.408] | 7 | 4.41M |
| lcoff_sp20 | LC_ENABLE=0 SPEED_STD=2.0 | 1.051 | 0.933 | -0.621 [-0.799,-0.441] | 5 | 5.26M |
| A_t45 | B + MOVE_TILT_STD=0.45 (B = LC_ENABLE=0 SPEED_STD=1.0) | 1.091 | 0.938 | -0.581 [-0.743,-0.427] | 8 | 5.26M |
| A_f05 | B + START_MEAN_FWD=0.5 | 1.227 | 1.068 | -0.445 | 15 | 4.75M |  (weaker forward mean hurts all start directions)
| A_wide | B + START_STD_X=0.8 START_STD_Y=0.6 START_STD_Z=1.0 | 1.059 | 0.954 | -0.613 [-0.791,-0.440] | 6 (>5m 0) | 4.75M |
| A_wd | B + WD=1 (watchdog defaults) | 1.108 | 0.972 | -0.564 | 7 | 4.69M | fired on 4 flights, ALL worse: fo-452 1.79->4.78, fo-552 1.34->2.27, fo-588 2.94->4.64, ro-046 0.33->1.40 |
| B_m4 | B + PRIOR_MODE=4 (new: zero-mean camera-axis prior + direction-free speed shell |v|~0.9+-0.6 during START_T) | 1.600 | 1.360 | -0.073 | 22 | 4.93M | bad like fwd0 |
- A_wdb (stricter WD) and the B_m4 variants were killed: pools/v3val grew 152 -> 430 mid-run (someone refreshed), and a mis-chained
  waiter made two of my evals overlap (40 workers for ~5 min; fixed). Re-running baseline + candidates on the 430 pool.
## v3val now 430 flights. gslvlj on 430: raw 1.524, srv-w 1.390, >3m 55, peak 5.13M. lcoff_sp10 (net off, SPEED_STD 1.0) on 430: 1.011 / 0.928.
## NEW REFERENCE (coordinator): net agent's s3ft2_iso = retrained net ft2 + PRIOR_MODE=1 START_STD=2.0 (v3val 430: 0.904, srv-w 0.879, peak 4.71M).
- gslv_s3ft2.c = my gslv_s3.c with the ft2 weight block spliced from agents/net/src/s3_ft2.c (lines 1607-14788);
  mk.py ft2iso "PRIOR_MODE=1 START_STD=2.0" gslv_s3ft2.c reproduces net/builds/s3ft2_iso sha 70b4c500 (VERIFIED). F = PRIOR_MODE=1 START_STD=2.0.
| name (on ft2, vs net_s3ft2_iso, 430 flights) | flags | raw | srv-w | d [CI] | hover | mid | bench | free-yaw | back/side/fwd | >3m | peak |
| net_s3ft2_iso | F | 0.904 | 0.879 | - | 0.801 | 0.928 | 0.749 | 0.984 | 0.969/0.766/1.045 | 6 | 4.71M |
| net_s3ft2_iso_r1 | F + r1 | 0.936 | 0.899 | +0.032 [-0.005,+0.074] | 0.798 | 0.968 | 0.752 | 1.031 | 0.983/0.769/1.138 | 10 | 5.11M |
| F_sp10 | F SPEED_STD=1.0 | 0.833 | 0.812 | -0.072 [-0.113,-0.027] | 0.715 | 0.860 | 0.657 | 0.923 | 0.936/0.754/0.898 | 6 | 4.62M |
| F_sp20 | F SPEED_STD=2.0 | 0.820 | 0.803 | -0.084 [-0.123,-0.043] | 0.691 | 0.850 | 0.658 | 0.904 | 0.874/0.742/0.931 | 5 | 5.46M |
| F_t45 | F MOVE_TILT_STD=0.45 | 0.948 | 0.904 | +0.044 [+0.008,+0.084] | 0.801 | 0.982 | 0.770 | 1.040 | 1.003/0.793/1.140 | 10 | 4.53M |
| F_mv20 | F MOVE_VEL_STD=2.0 | 0.913 | 0.875 | +0.008 [-0.029,+0.049] | 0.801 | 0.938 | 0.735 | 1.004 | 0.973/0.787/1.051 | 12 | 5.32M |
| F_iso25 | PRIOR_MODE=1 START_STD=2.5 | 0.903 | 0.878 | -0.001 [-0.029,+0.025] | | | | | | 7 | 5.11M |
| F_wd | F WD=1 | 0.908 | 0.883 | +0.004 [-0.001,+0.010] | 5/430 flights changed (1 better, sum +1.55 m) | 6 | 4.71M |
| F_wds | F WD=1 WD_SOFT=1 | 0.904 | 0.878 | -0.001 [-0.002,+0.000] | 5/430 changed (4 better, sum -0.33 m) | 6 | 4.71M |
=> on the ft2 net: weaker whole-flight SPEED_STD is the only consistent winner (rooms +0.04-0.05, everything else better); tilt 0.45 hurts;
   watchdog inert (its triggers almost never fire on GSLV).
### Final replicates (ft2, 430): ft2iso_r2 (F + r2) 0.897 / srv-w 0.865; F_sp10_r1 0.836 / 0.816; F_sp10_r2 0.815 / 0.780; F_sp15 0.820 / 0.788 (d -0.084);
F_sp20_r1 0.816 / 0.801; F_sp20_r2 0.839 / 0.800. v1val: F_sp10 0.665 (d -0.068 [-0.110,-0.029]); F_sp20 0.680 (d -0.053 [-0.112,+0.004]).
Note: evalpool.py can crash at the metadata step when the generator deletes out/ep/*.json mid-glob (F_sp20_r1); re-running is cached and fine.
