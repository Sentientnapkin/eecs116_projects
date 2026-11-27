# n2 REPORT: IMU + small learned velocity net, real wasm (stage 1); stage 2 sim
Labels: MEASURED / NEW EXPERIMENT / MATH / HYPOTHESIS / UNKNOWN.
## Stage 1 (MEASURED, real wasm, wasmtime fuel)
- Build: src/ins.c + gen.sh (net C_lo32_kd1 spliced, gray at epoch only, windows chained so inference runs every 5 frames, micro-steps spread over 4 following frames; 21-state float ESKF = n1 sim port with one stochastic clone; 0 imports; abi 320 px). Final src/ins_C.c, builds/c3/solution.wasm sha256 d35cff2fe10b3225b02886934932c1c9d962e251168592a88d0434691d8cd11c, flags none (defaults NET_SIG=0.44).
- v3val (258 flights) mean 4.704 m, med 3.93 (room 2.65 / warehouse 6.49 / forest 5.51); v1val (61) 4.077 m; peak fuel 150,661 (epoch frame: low-res gray = 129k, measured; other frames ~100k); gain 1.89 (v3val), baseline 8.23. NOT competitive (needs <1.25 m).
- Fuel per unit (MEASURED, mbn.py): gray 129k, net steps 49/10/47/35/44k, head 114k, one frame memcpy of 230 KB ~320k (so double-buffering the frame is worse). First version 210k peak (all in epoch+head frames).
- Tuning on s40 (40 flights): fixed sigma 0.3/0.44/0.6/0.9, net log-variance, gating, V0STD, bias clamps/RW: all 4.3-5.3 m, no real gain (sweep runs partly dropped flights, "no report", so only roughly comparable; lv-based sigma 4.42 vs fixed 0.44 4.29 on s40).
- Bigger nets (A2_Lkd/E_Lkd, 1.4 M fuel) not built: at P=5 that is >290k/frame, break-even would be ~1.0 m while the small net gives 4.7; HYPOTHESIS they cannot close the gap since heading is the bottleneck.
- Real result (4.7 m) is worse than n1's sim (white 3.6, scale-bias 2.3): real net errors are correlated/worse than assumed.
- Uploaded to HF SentientNapkin/gslv-stage3: ins_C_lo32_kd1_P5.wasm, ins_C_lo32_kd1_P5.c, README line.
## Stage 2 (NEW EXPERIMENT, python sim2.py, n1 flights, C32 P5 sigma .44, lat 4)
Direct gyro-bias measurement (proxy for gyro-compensated patch tracks) with sigma_b rad/s every 4 or 20 frames (res_sim.jsonl):
no aid 3.58 m (heading err 48 deg); sigma_b 0.02..0.0003 every 4 frames: 1.87 -> 1.86 m (heading 5.7-7 deg); every 20 frames 2.14 -> 1.98.
Scale-bias noise model: no aid 2.28, with bias aid 1.09 m.
Even a perfect bias gives 1.86 m (white-noise net model) > break-even ~1.25 m @160k; only the optimistic scale-bias model reaches 1.09 (gain ~ break-even), and the real net behaves worse than either model. Patch cost (e1: ~4.4k/patch/frame, 8 patches ~36k) would bring peak to ~190k. Parallax contamination of patch rotation not modelled (HYPOTHESIS: makes the aid weaker). No stage-2 wasm built; n3 does the real patch-heading work.
