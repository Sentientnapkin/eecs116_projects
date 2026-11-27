# n3 REPORT: IMU ESKF + small velocity net + gyro-compensated patch epipolar gyro-bias aid
Labels: MEASURED (real wasm / native sim), NEW EXPERIMENT, HYPOTHESIS.
## Result (MEASURED, real wasm, wasmtime fuel)
- Build builds/q8/solution.wasm sha256 e9569545066350e1c4865d106d7c8d95696862eef5a9e8eed6006ced5ddcb5b0, flags `NET_SIG=0.44 PB=8` (defaults NP=6 patches, 7x7 samples at stride 2, 320 px), source src/ins_P2.c (= n2 ins.c + net C_lo32_kd1 + src/ext_patch_v2.inc), 0 imports.
- v3val (258 existing flights; 100 of the 358 were removed from disk): mean 4.073 m, median 3.60 (room 2.62 / warehouse 5.32 / forest 4.67), peak fuel 194,774, gain 2.50.  v1val (61): 3.494 m, peak 190,763, gain 3.22.
- Reference n2 plain IMU+net (c3, same net, no patches): v3val 4.704 / v1val 4.077 at 150,661 (gain 1.89 / 2.57). Patch aid: -0.63 m v3val, -0.58 m v1val, +44k peak fuel; gain +0.6. Not competitive: break-even (8.23) at ~195k needs ~1.2 m.
- d40 dev subset (43 flights, every 6th of v3val): no patches 4.331; q8 3.843. 15 single-run variants (PB 6/8/12/1/4, PPX, SIGV, VMIN, NP 4/6/8/12, PUSEATT, NET_SIG 0.6, PMINTR, stride 3) all 3.82-4.16 (all below 4.33, differences between them within chaos noise). Second full-v3val run (VMIN=0.3) 4.035.
- Uploaded: HF SentientNapkin/gslv-stage3 ins_patch_C_lo32_kd1.wasm and .c.
## Design
Up to NP=6 fixed-grid patches (texture-tested, re-seeded on loss), gyro-predicted location + last residual flow, 1-iteration LK against a reference template held for PB=8 frames (0.4 s baseline). At each ref->cur pair: epipolar residual e = (b1 x R_gyro b2).t_hat with t_hat = net/filter velocity direction (skipped below 0.5 m/s), Jacobian wrt gyro-bias error H = dt J^T Rc Rbc^T, noise = pixel term + leak term rm/f * (SIGV/|v|) (translational residual flow rm, so distant patches weigh most), scalar EKF updates on the 21-state filter (bg only; PUSEATT=0). Per frame patch work ~45k fuel.
## Diagnostics (NEW EXPERIMENT, native sim with GT-velocity stub net noise 0.35, 20 flights; sim.py, src/stub_net.h)
- Sign confirmed (PSGN=+1 improves, -1 diverges). Bug found: intrinsics from host are already at the requested width (do not halve).
- Per-patch SNR is the limit: predicted bias signal rms 3e-4 rad per 0.05 s pair vs measurement noise 3-5e-3 (0.4-0.6 px) dominated by translational leak from velocity-direction error; regression slope of e on predicted signal 0.1-0.9 (noisy). Final gyro-bias error only 0.0097 -> 0.0076-0.0090 rad/s (n2's sim assumed 0.01 rad/s measurement noise every 4 frames, not reached). Longer baselines raise signal but leak grows equally.
- Joint (rotation, translation-direction) estimation per window (ext_patch_v3.inc): delta uncertainty ~0.07 rad vs signal 0.002 rad; useless (ATE worse). Abandoned.
- Stub-net native ATE: 3.18 no aid -> 2.1-2.4 with aid; real net: 4.33 -> 3.84 (d40).
## Failure modes / HYPOTHESES
- Rooms/forest/warehouse have near depth so few distant patches; hover (<0.5 m/s) gives no aid. HYPOTHESIS: 640 px width (2x angular resolution, same patch fuel but net cost changes) or sky/far-wall patch selection could help; not tried. Even perfect bias gives ~1.9 m in n2's sim, so this family cannot reach the 1.2 m break-even.
- Local pessimistic vs server (about 0.85-0.9 local per 0.586 server for the full MSCKF); no server calibration for this family.
## Files
src/ext_patch_v2.inc (final), src/ext_patch.inc (same), v1/v3 variants, src/ins_P2.c (final C), src/ins_N.c + stub_net.h + sim.py (native dev loop), mk.py/ev.py/runq.sh/runb.sh, res/summary.tsv, res/n3_*.json.
Reproduce: `python3 mk.py q8 "NET_SIG=0.44 PB=8" src/ins_P2.c; ../../../venv-teacher/bin/python ev.py n3_q8 builds/q8/solution.wasm pools/v3val 8`.
