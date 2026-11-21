# audit/ — necessity + update-rate audit and edge-case hardening of T4uB (own dir only; no git; holdout/fold-4 untouched)

Base: tier1m/t1m_T4uB.c -> audit/a.c (leading #defines wrapped in #ifndef so -D overrides work; plus default-off switches
AB_THRUST/AB_VPRIOR/AB_ZUPT (ablations), AUD_STATS (stderr event counters), HARDEN (sanitizer + watchdog)).
a.c with no defines builds byte-identical to t1m_T4uB.wasm (sha e13ccbbf...faaa2) - re-verified after every edit.
Tools: ev.sh NAME SRC "DEFS" [rep] (fresh-711, 24 workers, tables/NAME.json), runner.sh (pops jobs.txt; 2 streams = 48 workers),
cmp.py NAME [r1 r2] (paired vs T4uB/T4uBr1/T4uBr2, scene bootstrap CI, dev f0-2 / conf f3-4), prof.sh (fuel per phase, 60 search flights),
stress.py (edge-case suite, 24 fresh flights 12 static/12 mid, synthetic perturbations), stab.py (stress tables).
Run python with /data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python (system python has no numpy).

## Evaluator facts (viobench/docs/ABI.md, runner/sandbox.py, config.json)
Fresh instance per episode; step gets 320x240 RGB + IMU rows (t_prev,t], always 10 rows at 200 Hz, frame 0 gets one interval.
Failure = trap, status!=0, non-finite value or zero quaternion in out -> that frame and ALL later frames scored as identity (filled).
Limits: step fuel 20e9, 2 GiB memory, 60 s wall per step. Float->int casts compile to i32.trunc_sat (no trap on NaN).
All local episodes: same T_cam_imu, 1200 frames, 20 Hz; fx varies 133-233 (640 px).

## Fuel profile (prof/an_base.txt, 60 search flights): peak 3.99 M, p99 3.67, p95 3.27, median 1.66, mean 1.84
Median frame: update() 0.47, klt 0.34, pyramid 0.21, detect 0.18, solve_dx (2nd iteration) 0.17, gate H0P 0.06, map 0.03, propagate 0.03.
Peak frames (top 0.5%, 3.77 M): update() 1.59 + solve_dx 0.78 + klt 0.38 + gate H0P 0.25 + pyramid 0.21 + gate S 0.11 + nullspace 0.09.
=> the PEAK is set by the MSCKF update batch (EKF + 2nd iteration ~63% of the peak frame); governor budget 3.6 M + ~10% overrun.
Frame 0: detect 1.42 M (all 60 cells); net frames 7-9: net prep/head ~3.0-3.45 M.

## PART A ablations (fresh-711, 1 rep unless noted; d vs T4uB r0 0.384)
| arm | fresh | d [CI] | dev / conf | >3/5/10 | peak | verdict |
| ITER_UPD=1 (no 2nd iteration) | 0.417 | +0.034 [+0.001,+0.059] | +0.021/+0.059 | 3/0/0 | 3.72 | KEEP (area -0.16 at same budget); retune arm queued |
| MAP_MODE=0 (no map relocalization) | 0.451 | +0.067 [+0.036,+0.092] | +0.057/+0.087 | 2/1/0 | 4.04 | KEEP |
| TC_MON=0 (no pv25 net re-anchor) | 0.448 | +0.065 [+0.024,+0.102] | | 12/4/0 | 4.03 | KEEP (tails) |
| LC_ENABLE=0 (no startup net) | 0.516 | +0.132 [+0.070,+0.195] | | 16/2/1 | 4.03 | KEEP |
| INV_HOLD=0 (no hover-start hold) | 0.379 | -0.005 [-0.036,+0.014] | -0.004/-0.007 | 2/0/0 | 4.00 | candidate REMOVE (reps queued) |
| GATE_MODE=0 (no movement gate) | 0.366 | -0.018 [-0.032,-0.006] | -0.006/-0.042 | 2/1/1 | 4.00 | candidate REMOVE (31 flights change; reps queued) |
| PRIOR_MODE=0 (no heading startup prior) | 0.376 | -0.007 [-0.024,+0.008] | | 3/1/1 | 4.06 | candidate (reps queued) |
| FB_PERIOD=0 (no fwd-bwd KLT check) | 0.463 | +0.079 [+0.041,+0.113] | | 2/1/0 | 4.10 | KEEP |
(B17 switches LI_GATENET/LI_PVS: already measured T4u vs T4uB 0.391 -> 0.381 3 reps: KEEP.)

## PART C stress suite on T4uB (stress_out/base_T4uB.json; 24 flights; ATE vs identity-fallback 'ident')
All 46 cases: 0 traps, peak fuel <= 4.00 M in every case (governor holds), except NaN/Inf IMU -> NaN output -> FAILED episode (filled).
Big ATE holes: nan_imu/inf_imu (episode fails at the frame), imu_spike 1% x N(0,50 m/s^2) -> 10.3 m, speed3 (3x time-compressed
flight, synthetic IMU) 23 m (worst 118 m), const_seg (camera stall while moving -> false ZUPT) 3.1 m, black/flat/saturated whole
flight ~2.9 m (> identity 2.75), flat 30 s segment 2.1, black 20 s 1.7, light flicker 1.9, dark x0.15 1.3, mount rotations 0.7-1.2
(net + thrust model assume the fixed mount; all local + doc configs share it). hover_then_fly 68 m was a synthesis artifact
(hover IMU bias != flight bias); synthesis fixed to GT-derived bias, rerun pending.

## Session 2 (after interruption 17:58)
- Runner: runner2.sh streams at 20 workers (RW); waiter.sh starts a 2nd stream when the orphaned jobs (ab_lat0, ab_gate0_r1,
  ab_hold0_r1 run_fresh) finish. Queued reps: gate0/hold0/prior0 r1,r2 + combination ab_ghp; h1 (HARDEN=1) at the front.
- HARDEN (a.c, default off; T4uB_H = HARDEN=1):
  1. hz_filter: drops IMU rows that are non-finite, non-increasing in time, beyond 16 g / 2000 deg/s, or (window of 4-64 rows) farther than
     12 m/s^2 / 3 rad/s from the window's per-axis median (normal data max deviation 1.65 m/s^2 / 0.44 rad/s over 60 flights; max |a| 14.1, |w| 2.1).
  2. hz_watch (end of step): non-finite nominal -> restore last good nominal; |v| > 10 m/s, |p| > 1 km, |bg| > 1, |ba| > 5, P diag < 0 / NaN / > 1e6
     -> soft reset (v=0 if implausible), fresh covariance, empty window/tracks/map, net off.
  3. hz_out_guard: never return a non-finite / zero-quaternion state (last good output, zero twist).
  Spot tests (H vs base): nan_imu / inf_imu: episode FAILED (filled from frame 300) -> completes, 0.33/0.22 m; imu_spike: 6.5/9.1 -> 0.26/0.29 m;
  speed3 (unphysical 3x compression) 55-64 m -> 5-13 m with VMAX 10 (16-21 m with VMAX 20).
- speed3 is NOT a valid quadrotor flight (tilt unchanged while accel x9 -> thrust model gate fails 97% of frames); speed2 (x4 accel) is the
  more meaningful 'faster flight' probe: static starts fine (0.33 -> 0.30 avg), MID starts degrade 0.33 -> 0.88, 0.75 -> 3.35, 0.21 -> 1.97
  (startup net / heading prior trained on slow flights). Server flights are ~3x longer path than ours -> flag to coordinator (needs faster
  training flights; not fixable by hardening).
- hover_then_fly 68 m was an artifact (hover IMU bias from a 10-sample mean); with the GT-derived bias it is 0.19-0.65 m (fine).
- PART B event rates (AUD_STATS build, 24 fresh flights, stress_out/stats_base.json; per frame):
  live tracks 34.5; MSCKF batches on 62% of frames, 10.0 rows/frame, 1.49 features attempted (tri-fail 0.07, chi2-gate 0.07);
  2nd iteration actually run on 3.9% of frames (6.7% of update batches; ITER_BACK fallback never); FB check 16.6 tracks/frame,
  rejects 1.47 (9%); KLT fails 1.45; detection 7.8 cells scored -> 2.96 new tracks; map tries 0.22, accepted 0.053 (24%);
  regular vision ZUPT 0.2% of frames; thrust row accepted 99.8%; EKF Cholesky failures 0; net re-anchor fires rare.
- EXACT REWRITE F_REUSE (a.c, default off): on the 93% of update batches where the 2nd iteration is skipped, update() reuses solve_dx's
  HP and Cholesky(S) (identical arithmetic, P unchanged in between). prof/an_reuse.txt: poses bit-identical 60/60 flights;
  mean 1.84 -> 1.62 M, median 1.66 -> 1.51, p95 3.27 -> 2.66, p99 3.67 -> 3.09; PEAK unchanged 3.99 M (now set by frames where the
  2nd iteration runs: update 1.45 + solve_dx 0.68, and net frames 8-9 ~3.3-3.45 M). Per-flight peak median 3.79 -> 3.49.
  Arms queued: rf1 (F_REUSE fresh-711, exactness), ig60/ig75 (F_REUSE + IT2_GOV: 2nd iteration only when the budget allows,
  GC_ROW lowered to 60k/75k -> more rows per frame at the same 3.6 M budget).
- ab_lat0 (INV_LAT=0): 0.375 (-0.009): reps queued.
- EXACTNESS (estcmp.py: estimate.tum + twist.txt bytes, fresh-711 vs T4uB r0): rf1 (F_REUSE) 711/711 identical; h1 (HARDEN) 711/711
  identical, peak 4.004 -> 4.015 M (+0.3%, watchdog overhead ~10k/frame).
- ig60 / ig75 (F_REUSE + budget-gated 2nd iteration + GC_ROW 60k/75k): 0.380 / 0.376 but peak 5.52 / 4.28 M -> REJECT as is
  (GC_ROW must be recalibrated from measured costs; hand to fuelpush).
- GATE_MODE=0 x3 reps: 0.364 vs 0.381, d -0.017 [-0.031,-0.006], dev -0.007 / conf -0.037, 31 flights change, tails 2.0->1.0 >3 m: REMOVE.
- INV_HOLD=0 x2: -0.002 [-0.019,+0.012] neutral; no fuel saved (hold updates only in the first 1 s) -> keep (no reason to change).
- Queued: hF (HARDEN+F_REUSE, expected bit-identical), hFg (+GATE_MODE=0); stress on aud_hF (stress_out/hF.json).
