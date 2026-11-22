/* ===================================================================================================================
 * learnvel: learned GRAVITY-DIRECTION measurement (LV_GRAV). One gray128 frame (+ IMU window means) -> unit gravity in body frame.
 * Micro-steps run on the governor's leftover units (after the velocity net). Delayed measurement: the prediction refers to the
 * capture frame k; residual vs h_k = R_k^T (0,0,-1), Jacobian on the current body-frame tilt error: [h_k]x (R_k^T R).
 * =================================================================================================================== */
#ifndef LV_GPER
#define LV_GPER 10          /* min frames between captures */
#endif
#ifndef LV_GT0
#define LV_GT0 1.0          /* s: first capture */
#endif
#ifndef LV_GSC
#define LV_GSC 1.0          /* sigma scale */
#endif
#ifndef LV_GFLOOR
#define LV_GFLOOR 0.02      /* per-axis sigma floor (unit vector components ~ rad) */
#endif
#ifndef LV_GGATE
#define LV_GGATE 0          /* chi2 gate (int, 0 = none) */
#endif
#ifndef LV_GRESET
#define LV_GRESET 0         /* disagreement reset: chi2 > LV_GRCHI -> TH variance += LV_GRQ * angle^2, BG variance += LV_GRBG^2 */
#endif
#ifndef LV_GRCHI
#define LV_GRCHI 9.0
#endif
#ifndef LV_GRQ
#define LV_GRQ 1.0
#endif
#ifndef LV_GRBG
#define LV_GRBG 0.0
#endif
#ifndef LV_GLIVE
#define LV_GLIVE 100000     /* capture only while live tracks < this */
#endif
static uint8_t gr_rgb[IMG_W * IMG_H * 3], gr_g[LC_H * LC_W];
static float gr_in[LC_PH * LC_PW * 3], gr_a0[24 * 32 * GR_C0], gr_a1[12 * 16 * GR_C1], gr_a2[6 * 8 * GR_C2], gr_a3[3 * 4 * GR_C3], gr_emb[32], gr_h[128], gr_out[12];
static double gr_Rk[9], gr_vec[7], gr_m, gr_is;
static int gr_pos = -1, gr_last = -100000, gr_frame, gr_n;
static void gr_reset(void) { gr_pos = -1; gr_last = -100000; gr_frame = 0; gr_n = 0; }
static void gr_conv(const float *in, float *out, int CI, int CO, int IH, int IW, const float *WT, const float *BT, int oy0, int oy1) {
    const int OW = IW / 2; const v128_t zero = wasm_f32x4_splat(0.0f);
    for (int oy = oy0; oy < oy1; oy++) for (int ox = 0; ox < OW; ox++) {
        v128_t acc[12]; for (int q = 0; q < CO / 4; q++) acc[q] = wasm_v128_load(BT + 4 * q);
        for (int ky = 0; ky < 3; ky++) { int iy = oy * 2 - 1 + ky; if (iy < 0 || iy >= IH) continue;
            for (int kx = 0; kx < 3; kx++) { int ix = ox * 2 - 1 + kx; if (ix < 0 || ix >= IW) continue;
                const float *ip = in + (iy * IW + ix) * CI; const float *wp = WT + (ky * 3 + kx) * CI * CO;
                for (int ci = 0; ci < CI; ci++) { const v128_t a = wasm_f32x4_splat(ip[ci]); const float *w = wp + ci * CO;
                    for (int q = 0; q < CO / 4; q++) acc[q] = wasm_f32x4_add(acc[q], wasm_f32x4_mul(a, wasm_v128_load(w + 4 * q))); } } }
        float *op = out + (oy * OW + ox) * CO; for (int q = 0; q < CO / 4; q++) wasm_v128_store(op + 4 * q, wasm_v128_bitselect(acc[q], zero, wasm_f32x4_gt(acc[q], zero))); }
}
static void gr_apply(void) {
    double mu[3], sd[3], nrm = 0, h[3], e[3] = {0, 0, -1}, dR[9], K[9], H3[9], r[3];
    for (int i = 0; i < 3; i++) { mu[i] = gr_out[i]; nrm += mu[i] * mu[i]; }
    nrm = sqrt(nrm); if (!(nrm > 0.5 && nrm < 2.0)) return;
    for (int i = 0; i < 3; i++) { mu[i] /= nrm; double lv = gr_out[3 + i]; lv = lv < -12 ? -12 : lv > 2 ? 2 : lv; double s = LV_GSC * exp(0.5 * lv); sd[i] = s < LV_GFLOOR ? LV_GFLOOR : s; }
    m3tvec(gr_Rk, e, h);                 /* predicted gravity direction in body axes at capture */
    m3tmul(gr_Rk, R, dR);                /* R_k^T R_now */
    skew(h, K); m3mul(K, dR, H3);        /* d h_k / d theta_now */
    memset(Hs, 0, sizeof Hs);
    for (int i = 0; i < 3; i++) { r[i] = (mu[i] - h[i]) / sd[i]; for (int j = 0; j < 3; j++) Hs[i * MAXD + TH + j] = H3[3 * i + j] / sd[i]; }
#if LV_GRESET
    {
        double S3[9], HP3[9];
        for (int i = 0; i < 3; i++) for (int l = 0; l < 3; l++) { double a = 0; for (int j = 0; j < 3; j++) a += Hs[i * MAXD + TH + j] * Pm[(TH + j) * MAXD + TH + l]; HP3[3 * i + l] = a; }
        for (int i = 0; i < 3; i++) for (int k = 0; k < 3; k++) { double a = i == k; for (int l = 0; l < 3; l++) a += HP3[3 * i + l] * Hs[k * MAXD + TH + l]; S3[3 * i + k] = a; }
        double c0 = S3[4] * S3[8] - S3[5] * S3[7], c1 = S3[5] * S3[6] - S3[3] * S3[8], c2 = S3[3] * S3[7] - S3[4] * S3[6], det = S3[0] * c0 + S3[1] * c1 + S3[2] * c2;
        double Si[9] = {c0, S3[2] * S3[7] - S3[1] * S3[8], S3[1] * S3[5] - S3[2] * S3[4], c1, S3[0] * S3[8] - S3[2] * S3[6], S3[2] * S3[3] - S3[0] * S3[5], c2, S3[1] * S3[6] - S3[0] * S3[7], S3[0] * S3[4] - S3[1] * S3[3]};
        double m2 = 0; for (int i = 0; i < 3; i++) for (int k = 0; k < 3; k++) m2 += r[i] * Si[3 * i + k] * r[k];
        m2 /= det;
        if (m2 > LV_GRCHI) {
            double d = 0; for (int i = 0; i < 3; i++) d += (mu[i] - h[i]) * (mu[i] - h[i]);
            for (int i = 0; i < 3; i++) { Pm[(TH + i) * MAXD + TH + i] += LV_GRQ * d; Pm[(BG + i) * MAXD + BG + i] += LV_GRBG * LV_GRBG; }
        }
    }
#endif
    update(r, Hs, 3, 1.0, LV_GGATE > 0 ? (double)LV_GGATE : INFINITY);
    gr_n++;
#ifdef LV_DBG
    fprintf(stderr, "G apply frame %d cap %d mu %.4f %.4f %.4f h %.4f %.4f %.4f sd %.4f %.4f %.4f\n", gr_frame, gr_last, mu[0], mu[1], mu[2], h[0], h[1], h[2], sd[0], sd[1], sd[2]);
#endif
}
/* micro-steps (fuel measured with LV_GBENCH, 1 unit = GC_UNIT 160 k): 0-15 gray (47 k), 16 stats (163 k), 17 pool (105 k), 18-41 conv0 one output row
 * each (~110 k), 42-53 conv1 rows (~330 k), 54-59 conv2 rows (~295 k), 60-62 conv3 rows (~250 k), 63-64 head (~190 k), 65 output + update */
#define GR_STEPS 66
static int gr_cu(int k) { return k < 16 ? 1 : k < 18 ? 2 : k < 42 ? 1 : k < 54 ? 3 : k < 63 ? 2 : k < 65 ? 2 : 1; }
static void gr_do(int k) {
    if (k < 16) { for (int pr = 3 * k; pr < 3 * k + 3; pr++) lc_gray_pair(gr_rgb, gr_g, pr); return; }
    if (k == 16) { double s = 0, s2 = 0; for (int p = 0; p < LC_H * LC_W; p++) { double x = gr_g[p]; s += x; s2 += x * x; }
        double n = LC_H * LC_W; gr_m = s / n; double var = (s2 - s * s / n) / (n - 1); gr_is = 1.0 / (sqrt(var > 0 ? var : 0) + 5.0); return; }
    if (k == 17) { float m = (float)gr_m, is = (float)gr_is;
        for (int v = 0; v < LC_PH; v++) for (int u = 0; u < LC_PW; u++) {
            const uint8_t *a = gr_g + (2 * v) * LC_W + 2 * u; float x = ((float)a[0] + a[1] + a[LC_W] + a[LC_W + 1]) * 0.25f;
            float *o = gr_in + (v * LC_PW + u) * 3; o[0] = (x - m) * is;
            o[1] = (float)(-1.0 + (2 * u + 0.5) * (2.0 / 127.0)); o[2] = (float)(-1.0 + (2 * v + 0.5) * (2.0 / 95.0)); }
        return; }
    if (k < 42) { int s = k - 18; gr_conv(gr_in, gr_a0, 3, GR_C0, LC_PH, LC_PW, GR_W0, GR_B0, s, s + 1); return; }
    if (k < 54) { int s = k - 42; gr_conv(gr_a0, gr_a1, GR_C0, GR_C1, 24, 32, GR_W1, GR_B1, s, s + 1); return; }
    if (k < 60) { int s = k - 54; gr_conv(gr_a1, gr_a2, GR_C1, GR_C2, 12, 16, GR_W2, GR_B2, s, s + 1); return; }
    if (k < 63) { int s = k - 60; gr_conv(gr_a2, gr_a3, GR_C2, GR_C3, 6, 8, GR_W3, GR_B3, s, s + 1); return; }
    if (k == 63) {
        for (int j = 0; j < 32; j++) { float a = GR_FB0[j]; for (int i = 0; i < 7; i++) a += (float)gr_vec[i] * GR_FW0[i * 32 + j]; gr_emb[j] = a > 0 ? a : 0; }
        for (int j = 0; j < 128; j++) gr_h[j] = GR_H1B[j];
        for (int i = 0; i < 6 * GR_C3; i++) { float a = gr_a3[i]; const float *w = GR_H1W + i * 128; for (int j = 0; j < 128; j++) gr_h[j] += a * w[j]; }
        return; }
    if (k == 64) {
        for (int i = 6 * GR_C3; i < 12 * GR_C3; i++) { float a = gr_a3[i]; const float *w = GR_H1W + i * 128; for (int j = 0; j < 128; j++) gr_h[j] += a * w[j]; }
        for (int i = 0; i < 32; i++) { float a = gr_emb[i]; const float *w = GR_H1W + (12 * GR_C3 + i) * 128; for (int j = 0; j < 128; j++) gr_h[j] += a * w[j]; }
        for (int j = 0; j < 128; j++) gr_h[j] = gr_h[j] > 0 ? gr_h[j] : 0;
        return; }
    for (int j = 0; j < 12; j++) gr_out[j] = GR_H2B[j];
    for (int i = 0; i < 128; i++) { float a = gr_h[i]; const float *w = GR_H2W + i * 12; for (int j = 0; j < 12; j++) gr_out[j] += a * w[j]; }
    gr_apply();
}
/* per step after vision: capture (stash) + micro-steps with the leftover governor units */
static void gr_tick(const uint8_t *frame, const double *imu, int n, int units, int live) {
    gr_frame++;
    double tt = last_t - t_start;
    if (gr_pos < 0) {
        if (tt >= LV_GT0 && gr_frame - gr_last >= LV_GPER && live < LV_GLIVE && n > 0 && units >= 3) {
            memcpy(gr_rgb, frame, sizeof gr_rgb); memcpy(gr_Rk, R, sizeof gr_Rk); units -= 2;
            double f[3] = {0, 0, 0}, g[3] = {0, 0, 0};
            for (int r = 0; r < n; r++) for (int i = 0; i < 3; i++) { f[i] += imu[7 * r + 1 + i]; g[i] += imu[7 * r + 4 + i]; }
            for (int i = 0; i < 3; i++) { gr_vec[i] = f[i] / n / 9.81; gr_vec[3 + i] = g[i] / n; }
            gr_vec[6] = fx * 0.4 / 100.0;
            gr_pos = 0; gr_last = gr_frame;
        } else return;
    }
    while (gr_pos >= 0 && units >= gr_cu(gr_pos)) { units -= gr_cu(gr_pos); gr_do(gr_pos); if (++gr_pos >= GR_STEPS) gr_pos = -1; }
}
