- 2026-11-20 09:19:27 loop start/resume: phase=init spent=0.00h of 5.0h, cfg={'budget_h': 5.0, 'reserve_min': 25.0, 'reps': 3, 'workers': 24, 'concurrent': 2, 'load_max': 140.0, 'a_frac': 0.4, 'b_frac': 0.7, 'topk': 12, 'seed': 20261120, 'keep_best': 20, 'step0': 0.3, 'step_min': 0.07, 'mu': 4, 'lam': 6}
- 2026-11-20 09:19:27 INIT: evaluating default vector (reproduction check) and fresh-A reference
- 2026-11-20 09:21:45 loop start/resume: phase=init spent=0.00h of 5.0h, cfg={'budget_h': 5.0, 'reserve_min': 25.0, 'reps': 3, 'workers': 24, 'concurrent': 2, 'load_max': 140.0, 'a_frac': 0.4, 'b_frac': 0.7, 'topk': 12, 'seed': 20261120, 'keep_best': 20, 'step0': 0.3, 'step_min': 0.07, 'mu': 4, 'lam': 6}
- 2026-11-20 09:21:45 INIT: evaluating default vector (reproduction check) and fresh-A reference
- 2026-11-20 09:22:09 loop start/resume: phase=init spent=0.00h of 5.0h, cfg={'budget_h': 5.0, 'reserve_min': 25.0, 'reps': 3, 'workers': 24, 'concurrent': 2, 'load_max': 140.0, 'a_frac': 0.4, 'b_frac': 0.7, 'topk': 12, 'seed': 20261120, 'keep_best': 20, 'step0': 0.3, 'step_min': 0.07, 'mu': 4, 'lam': 6}
- 2026-11-20 09:22:09 INIT: evaluating default vector (reproduction check) and fresh-A reference
- 2026-11-20 09:25:14 reproduction: wasm sha == gate.wasm True; visible flights identical to preflight_gate_a: 144/144
- 2026-11-20 09:25:14 fresh-A default vs fresh/table_gate.json: 475/475 identical
- 2026-11-20 09:25:14 phase -> A
- 2026-11-20 09:25:14 PHASE A: one-at-a-time sensitivity sweeps (38 params x 0.5/0.8/1.25/2.0, replicate-averaged), cap 40% of budget
- 2026-11-20 10:02:02 PHASE A done; top parameters by effect: GYRO_NOISE(-0.09/0.16), ACCEL_NOISE(-0.06/0.07), INIT_TILT_STD(-0.03/0.03), INIT_VELOCITY_STD(-0.03/0.02), MOVE_TILT_STD(+0.05/0.10), DET_FORCE(+0.00/0.04), ACCEL_BIAS_WALK(+0.02/0.04), GYRO_BIAS_WALK(+0.02/0.03), START_T(+0.02/0.03), GATE_PAIRS(+0.00/0.00), GATE_DISP(+0.00/0.00), DET_GYRO(+0.00/0.00)
- 2026-11-20 10:02:02 phase -> B
- 2026-11-20 10:02:02 FINAL: top-3 on held-out fresh-B and summary
- 2026-11-20 10:02:02 summary written to SUMMARY.md; finalist sources in best/
- 2026-11-20 10:02:02 phase -> stopped
- 2026-11-20 10:02:02 loop finished

## REBASE 2026-11-20 (coordinator): base gate.c (G) -> inventive/adopted.c (G + C1: INV_HOLD, INV_VZ 0.3, INV_LAT 0.5)
G-based run was stopped gracefully after 0.66 h (27 vectors, phase A pass 1 partial; no promotion; archive: ledger_G_base.jsonl, archive_G_base/). Its sensitivity findings
(replicate-mean search delta vs G default 1.181; 13 of 38 parameters probed at 0.8x/1.25x):
  GYRO_NOISE 0.056 -0.086 (0.0875 +0.070; fuel +0.2M), ACCEL_NOISE 0.224 -0.058, INIT_TILT_STD 0.0625 -0.034, INIT_VELOCITY_STD 1.25 -0.030 (val worse +0.09),
  MOVE_TILT_STD both directions worse (+0.05/+0.16), ACCEL_BIAS_WALK, GYRO_BIAS_WALK, START_T, DET_FORCE all worse or flat (+0.00..+0.06);
  FLAT (|delta| < 0.02, skipped in the rebased phase A): DET_GYRO, GATE_DISP, GATE_PAIRS, GATE_PAIRS_MAX. Noise level (gyro/accel noise) was the only clear lever; none was promoted
  (screen needs >= 0.03 AND fresh-A, which had not been reached). Rebased registry: 44 parameters (adds HOLD_T, HOLD_T0, HOLD_GN, HOLD_TAU, INV_VZ, INV_LAT). Remaining budget set to 4 h.
- 2026-11-20 10:03:41 loop start/resume: phase=init spent=0.00h of 4.0h, cfg={'budget_h': 4.0, 'reserve_min': 25.0, 'reps': 3, 'workers': 24, 'concurrent': 2, 'load_max': 140.0, 'a_frac': 0.4, 'b_frac': 0.7, 'topk': 12, 'seed': 20261120, 'keep_best': 20, 'step0': 0.3, 'step_min': 0.07, 'mu': 4, 'lam': 6}
- 2026-11-20 10:03:41 INIT: evaluating default vector (reproduction check) and fresh-A reference
- 2026-11-20 10:07:44 reproduction: wasm sha == inv_adopted.wasm True; visible flights identical to preflight_gate_a: 144/144
- 2026-11-20 10:07:44 fresh-A default vs inventive/fresh_table_c1.json: 475/475 identical
- 2026-11-20 10:07:44 phase -> A
- 2026-11-20 10:07:44 PHASE A: one-at-a-time sensitivity sweeps (38 params x 0.5/0.8/1.25/2.0, replicate-averaged), cap 40% of budget
- 2026-11-20 10:07:44 phase A skips parameters measured flat on the G-based run: DET_GYRO, GATE_DISP, GATE_PAIRS, GATE_PAIRS_MAX
- 2026-11-20 11:40:42 PHASE A done; top parameters by effect: GYRO_NOISE(-0.10/0.14), KLT_MIN_EIG(-0.06/0.12), INV_VZ(-0.05/0.07), START_STD_X(-0.05/0.05), MIN_DEPTH(-0.04/0.05), HOLD_T(-0.04/0.03), ZUPT_DISPARITY(-0.04/0.02), INV_LAT(-0.03/0.05), INIT_VELOCITY_STD(-0.03/0.04), MIN_OBS(+0.01/0.15), ZUPT_STD(-0.03/0.02), START_MEAN_FWD(+0.05/0.15)
- 2026-11-20 11:46:23 A-decision: screen-pass a46db7875c48 d_search=+0.095 val 0.497 delta={'GYRO_NOISE': 0.056} | fresh-A 0.761 (ref 0.721) n5 8/6 n10 2/0 -> reject
- 2026-11-20 11:46:23 A-decision: screen-pass b9a6228e370d d_search=+0.055 val 0.576 delta={'KLT_MIN_EIG': 2.5} | fresh-A 0.700 (ref 0.721) n5 4/6 n10 0/0 -> PROMOTE
- 2026-11-20 11:46:24 PROMOTED b9a6228e370d: replicate-mean search 1.079 -> 1.024, val 0.537 -> 0.576, paired bootstrap (cand-ref, scene) {'search': [-0.055, -0.214, 0.108], 'val': [0.039, -0.032, 0.131]}, fresh-A 0.700, fuel 21.56M; changed vs default: {'KLT_MIN_EIG': 2.5}
- 2026-11-20 11:46:24 phase -> B
- 2026-11-20 11:46:24 PHASE B: coordinate descent on top 12 parameters with step halving (step 0.300)
- 2026-11-20 12:16:29 B step 0.300: screen-pass ba7c9bb8d93e d_search=+0.071 val 0.587 delta={'INIT_VELOCITY_STD': 0.769231, 'ZUPT_DISPARITY': 0.52, 'MIN_DEPTH': 0.26, 'KLT_MIN_EIG': 2.5} | fresh-A 0.688 (ref 0.700) n5 4/4 n10 0/0 -> PROMOTE
- 2026-11-20 12:16:29 PROMOTED ba7c9bb8d93e: replicate-mean search 1.024 -> 0.953, val 0.576 -> 0.587, paired bootstrap (cand-ref, scene) {'search': [-0.071, -0.133, -0.019], 'val': [0.011, -0.063, 0.067]}, fresh-A 0.688, fuel 21.61M; changed vs default: {'INIT_VELOCITY_STD': 0.769231, 'ZUPT_DISPARITY': 0.52, 'MIN_DEPTH': 0.26, 'KLT_MIN_EIG': 2.5}
- 2026-11-20 12:40:24 B: no promotion at step 0.300; halving to 0.150
- 2026-11-20 12:53:29 phase -> C
- 2026-11-20 12:53:29 PHASE C: (4,6) evolution strategy around the best vectors for the remaining budget
- 2026-11-20 13:24:21 C gen 4: screen-pass 25579ce5fe59 d_search=+0.045 val 0.585 delta={'ACCEL_NOISE': 0.252967, 'INIT_VELOCITY_STD': 0.591716, 'START_STD_X': 0.532307, 'SPEED_STD': 0.48286, 'CHI2_Z': 1.72031, 'ZUPT_DISPARITY': 0.52, 'MIN_DEPTH': 0.168341, 'KLT_MIN_EIG': 2.5, 'INV_LAT': 0.533664} | fresh-A 0.755 (ref 0.688) n5 6/4 n10 0/0 -> reject
- 2026-11-20 13:32:46 C gen 5: screen-pass 509d9bc35289 d_search=+0.030 val 0.608 delta={'ACCEL_NOISE': 0.23265, 'INIT_VELOCITY_STD': 0.591716, 'ZUPT_DISPARITY': 0.52, 'ZUPT_STD': 0.0181035, 'MIN_DEPTH': 0.338, 'KLT_MIN_EIG': 2.5} | fresh-A 0.692 (ref 0.688) n5 6/4 n10 0/0 -> reject
- 2026-11-20 13:40:18 phase -> final
- 2026-11-20 13:40:18 FINAL: top-3 on held-out fresh-B and summary
- 2026-11-20 13:51:47 summary written to SUMMARY.md; finalist sources in best/
- 2026-11-20 13:51:47 phase -> done
- 2026-11-20 13:51:47 loop finished
