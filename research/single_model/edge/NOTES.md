# edge: server-12 edge cases, proxy set, mitigations (see research_notes/GP MSCKF micro optimizations and edge cases/server12_edge_cases.md for the full write-up)

Base: final/fgt.c with TAILS_DET/TAILS_KLT/VI_MODE defaults 0 = bit-identical to the server G wasm (ac825145; search 1.028, val 0.543). Fold 4 / sealed never read; private episodes never touched.
Files: stats.py audit.py sig.py (per-flight truth stats, sidecar audit, server-style metrics for base/f0/G/T/M), analysis.py classes.py proxy.py (draws), run.sh fresh.sh run_fresh_e.py rep_chain*.sh (runners), e.c + edge.patch (code), outputs proxy_out.md classes.txt signature.txt flightstats.json audit.json sig.json ftable_*.json, logs log_*.txt. Runs: research/results/single_model/edge_* and edge_fresh_*.

## Key tables
## Whole pool (non-fold-4, n=726: sel 144, fresh 582)
| cand | mean all | static | mid | >3 | >5 | >10 | fresh mean | sel mean |
|--|--|--|--|--|--|--|--|--|
| base | 1.395 | 0.611 | 2.179 | 79 | 43 | 11 | 1.181 | 2.259 |
| f0 | 0.841 | 0.604 | 1.077 | 37 | 18 | 1 | 0.815 | 0.944 |
| G | 0.842 | 0.605 | 1.080 | 38 | 19 | 1 | 0.817 | 0.944 |
| T | 0.824 | 0.592 | 1.056 | 32 | 18 | 2 | 0.835 | 0.780 |
| M | 0.828 | 0.592 | 1.064 | 34 | 19 | 2 | 0.836 | 0.795 |
| edge_spd1 | 0.823 | 0.605 | 1.040 | 37 | 16 | 0 | 0.793 | 0.941 |
| edge_vb | 0.818 | 0.605 | 1.031 | 34 | 18 | 1 | 0.804 | 0.875 |
| edge_cmbx | 0.786 | 0.605 | 0.968 | 32 | 15 | 0 | 0.765 | 0.872 |
| edge_g_r1 | 0.902 | 0.685 | 1.120 | 36 | 21 | 4 | 0.851 | 1.110 |
| edge_g_r2 | 0.905 | 0.621 | 1.189 | 42 | 19 | 3 | 0.842 | 1.159 |
| edge_vb_r1 | 0.879 | 0.685 | 1.073 | 32 | 21 | 4 | 0.839 | 1.040 |
| edge_vb_r2 | 0.865 | 0.621 | 1.109 | 38 | 16 | 3 | 0.822 | 1.037 |
| edge_cmbx_r1 | 0.862 | 0.685 | 1.040 | 31 | 20 | 4 | 0.820 | 1.035 |

## Arms (search n=119 / val / pool n=726 non-fold-4)
| arm | change | search | pool mean (>3/>5/>10) | paired vs G |
|--|--|--|--|--|
| g0=G | defaults | 1.028 | 0.842 (38/19/1) | = |
| spd1 | EDGE_SPD=1 | 1.027 | 0.823 (37/16/0) | -0.020 [-0.054,+0.013] |
| spd2 | EDGE_SPD=1 ratio 1.4 abs 0.15 | 1.054 | 0.830 (38/16/0) | -0.013 |
| gd3 | GATE_DISP 3.0 | 1.033 | 0.907 (43/22/3) | +0.065 [+0.016,+0.126] REJECT |
| st1 | START_T 1.0 | 1.255 | not run | REJECT |
| ta | TAILS_DET=1 TAILS_KLT=1 | 0.960 | 0.858 (39/19/2) | +0.016 |
| vb | VI_MODE=1 VI_COSMAX=-0.26 | 0.945 | 0.818 (34/18/1) | -0.024 [-0.046,-0.006] |
| cmbx | EDGE_SPD=1 VI_MODE=1 VI_COSMAX=-0.26 | 0.944 (reps 1.133/1.153) | 0.786 (32/15/0); reps 0.862/0.841 | -0.056 [-0.090,-0.026]; vs G 3-replicate mean -0.053 [-0.081,-0.028] |

cmb (first combined run) had a guard bug (sp_cap blocked when vi_ok==2) and is identical to vb; superseded by cmbx. No arm lowers P(any 12-draw episode > 5 m) below T (0.23-0.36); cmbx 0.40-0.51 vs G 0.43-0.54. Not preflighted; not adopted.

## Patch vs final/fgt.c (edge.patch)
```diff
--- ../final/fgt.c	2026-11-20 07:21:00.706237000 +0000
+++ e.c	2026-11-20 10:28:26.856668000 +0000
@@ -172,10 +172,10 @@
 /* tails: contrast-adaptive front end (flat / low-contrast scenes). TAILS_DET: 1 scales the Shi-Tomasi threshold by
    clamp((meangrad/TAILS_G0)^2, TAILS_SMIN, 1); TAILS_KLT: also scales the KLT min-eigenvalue test. */
 #ifndef TAILS_DET
-#define TAILS_DET 1 
+#define TAILS_DET 0 
 #endif
 #ifndef TAILS_KLT
-#define TAILS_KLT 1 
+#define TAILS_KLT 0 
 #endif
 #ifndef TAILS_G0
 #define TAILS_G0 0.8 
@@ -195,7 +195,7 @@
    inverse depth) and, through a typical depth VI_Z0, the speed; the velocity is reset to that with covariance
    (sigma_par along, sigma_perp across), and the startup heading prior is switched off for the rest of START_T. */
 #ifndef VI_MODE
-#define VI_MODE 1 
+#define VI_MODE 0 
 #endif
 #ifndef VI_CLONES
 #define VI_CLONES 4 
@@ -333,6 +333,27 @@
 static uint8_t pyr[2][LEVELS][IMG_W * IMG_H];
 static int cur_pyr;
 static double tex_scale = 1.0, g_ema;
+/* ---- EDGE (research/single_model/edge): speed-consistency check of the startup heading prior ----
+   EDGE_SPD 1: at the VI_CLONES-th clone of a moving start (retried until EDGE_SP_TMAX), the flow speed (|de-rotated flow| / dt * VI_Z0, same estimator as
+   the tails flow reset) is compared with the filter speed; if |v| > EDGE_SP_RATIO * v_flow + EDGE_SP_ABS the velocity is scaled to the flow speed
+   (direction of the estimate kept, V rows/cols of P scaled, sigma floor EDGE_SP_SIG) and the heading prior is switched off for the rest of START_T.
+   Target: slow mid starts where the 0.9 m/s forward prior over-states the speed (scale < 0.5 failures, e.g. e7aa signature). */
+#ifndef EDGE_SPD
+#define EDGE_SPD 0
+#endif
+#ifndef EDGE_SP_RATIO
+#define EDGE_SP_RATIO 1.8
+#endif
+#ifndef EDGE_SP_ABS
+#define EDGE_SP_ABS 0.25
+#endif
+#ifndef EDGE_SP_TMAX
+#define EDGE_SP_TMAX 1.0
+#endif
+#ifndef EDGE_SP_SIG
+#define EDGE_SP_SIG 0.2
+#endif
+static int sp_ok;
 static int g_have; /* g_ema initialised (reset at every re-init) */
 static double Rwc_prev[9]; /* camera orientation at the previous frame (gyro prediction for KLT) */
 
@@ -654,7 +675,7 @@
     update(r, Hs, 2, ACCEL_NOISE * ACCEL_NOISE / n + THRUST_MODEL_STD * THRUST_MODEL_STD, THRUST_GATE);
     double scale = sqrt(SPEED_TAU / FRAME_DT);
     int startup = moving && PRIOR_MODE && !gate_released && last_t - t_start < START_T;
-    if (VI_MODE && vi_ok == 1 && startup) return; /* flow-based velocity replaces the heading prior */
+    if ((VI_MODE && vi_ok == 1 && startup) || (EDGE_SPD && sp_ok == 1 && startup)) return; /* flow-based velocity replaces the heading prior */
     if (PRIOR_MODE == 3 && startup) { /* whitened camera-axis prior with nonzero mean */
         double Rwc[9], mu[3] = {START_MEAN_X, START_MEAN_Y, START_MEAN_FWD}, sd[3] = {START_STD_X, START_STD_Y, START_STD_Z}, vc[3];
         if (GATE_MODE == 2) { double k = GATE_SOFT_MIN + (1 - GATE_SOFT_MIN) * gate_w; for (int i = 0; i < 3; i++) { mu[i] *= gate_w; sd[i] *= k; } }
@@ -1255,6 +1276,26 @@
     }
 }
 
+static void sp_cap(void) {
+    double d[3], sc;
+    int n = flow_dir(d, &sc);
+    if (n < VI_NMIN) return;
+    sp_ok = 2;
+    const Clone *c0 = &clones[0], *c1 = &clones[nclones - 1];
+    double dt = (c1->id - c0->id) * CLONE_EVERY * FRAME_DT;
+    double sf = sc / dt * VI_Z0;
+    if (sf > 3.0) sf = 3.0;
+    double ve = sqrt(vel[0] * vel[0] + vel[1] * vel[1] + vel[2] * vel[2]);
+    if (ve > EDGE_SP_RATIO * sf + EDGE_SP_ABS) {
+        double k = sf / ve;
+        sp_ok = 1;
+        for (int i = 0; i < 3; i++) vel[i] *= k;
+        for (int j = 0; j < D; j++)
+            for (int i = V; i < V + 3; i++) { Pm[i * MAXD + j] *= k; Pm[j * MAXD + i] *= k; }
+        for (int i = V; i < V + 3; i++) Pm[i * MAXD + i] += EDGE_SP_SIG * EDGE_SP_SIG;
+    }
+}
+
 static void update_tex_scale(int which) { /* mean abs gradient of the level-0 gray image, stride 3 */
     if (!(TAILS_DET || TAILS_KLT)) return;
     const uint8_t *I = pyr[which][0];
@@ -1303,6 +1344,7 @@
         if (VI_MODE && moving && !vi_ok && nclones >= VI_CLONES && last_t - t_start < VI_TMAX &&
             !(FGT_GUARD && GATE_MODE == 1 && (gate_released || (gate_pairs >= 1 && gate_pairs <= GATE_PAIRS_MAX && gate_max < GATE_DISP))))
             vi_reset();
+        if (EDGE_SPD && moving && !sp_ok && vi_ok != 1 && nclones >= VI_CLONES && last_t - t_start < EDGE_SP_TMAX && !gate_released) sp_cap();
         vision_zupt();
         int nb = 0;
         for (int i = 0; i < nlost && nb < MAX_BATCH; i++) batch[nb++] = lost[i];
@@ -1434,7 +1476,7 @@
         }
         initialize(imu, imu_count, t);
         gate_pairs = 0; gate_released = 0; gate_force_zupt = 0; gate_max = 0; gate_sum = 0; gate_w = 1.0; gate_last = -1.0;
-        vi_ok = 0; vi_done = 0; g_have = 0; g_ema = 0; tex_scale = 1.0; frame_no = 0; clone_every = CLONE_EVERY; min_obs = MIN_OBS; tri_min_eig = TRI_MIN_EIG;
+        vi_ok = 0; vi_done = 0; sp_ok = 0; g_have = 0; g_ema = 0; tex_scale = 1.0; frame_no = 0; clone_every = CLONE_EVERY; min_obs = MIN_OBS; tri_min_eig = TRI_MIN_EIG;
         nclones = 0; clone_counter = 0; frames_since_clone = 0; nlost = 0; detect_cursor = 0;
         memset(tracks, 0, sizeof tracks);
         cur_pyr = 0;
```
