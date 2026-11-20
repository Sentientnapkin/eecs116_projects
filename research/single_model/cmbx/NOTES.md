# cmbx: B8 = G+C1+FB+CMBX (research/single_model/cmbx)
b8.c = frontend/adopted_fbh.c (B6) + CMBX ported from edge/e.c (mk.py regenerates it). Switch: -DCMBX=0 -> B6 (VI_MODE=EDGE_SPD=0); CMBX=1 default.
Bit-identity: CMBX=0 per-flight ATE identical to fe2_fbh_r0 on all 171 (wasm differs from B6 only by dead code).
Run: ./rep.sh <name> "defines" (3 replicates), results research/results/single_model/<name>_r*.
(log below)
- B6 ref = fe2_fbh_r0..2 (wasm c8dc91de.. = staged fuel/publish B6; b8.c CMBX=0 builds that exact wasm sha c8dc91deb9a9).
- b8_cmbx (CMBX=1, COSMAX -0.26, SPD on) 3-rep: search 0.971 vs B6 0.931 (+0.041 [-0.014,+0.153]); mid +0.077; val 0.452 vs 0.441; >3 counts identical per rep. No gain on top of FB.
- chain.sh: variants b8_spd (SPD only), b8_vi (VI only), b8_vi50 (COSMAX -0.5).
- Search 3-rep (vs B6 0.931): spd only 0.928 (-0.003); VI only 0.974 (+0.043); VI cos -0.5 0.974; VI cos -0.7 0.974; CMBX 0.971 (+0.041 [-0.014,+0.153]). val CMBX 0.452 vs 0.441.
- Fresh 711 (ana.py): B6 0.618, CMBX 0.613, SPD-only 0.644. Regression class (17): B6 2.09, CMBX 2.04. >3/5/10: B6 21/8/0, CMBX 20/8/0, SPD 25/10/0.
  Angle 135-180 (mid, n=18) >3 m: B6 4, CMBX 2, SPD 7. But angle 0-45 >3: 5->6, speed <0.3 >3: 2->3 (CMBX).
- DECISION: not adopted (search worse, bins not all improved; gain limited to 18 reverse-start flights). Nothing published.
