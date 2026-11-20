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
