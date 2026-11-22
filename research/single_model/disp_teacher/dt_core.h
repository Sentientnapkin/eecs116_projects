/* dt_core.h: displacement-teacher network + MSCKF relative-displacement update, inlined into a B16-family source.
 * Requires dt_weights.h (export_c.py) included before this file. Plain C, float32 inference.
 *
 * Measurement (training target, model.py): d_c = R_c(t)^T (p(t) - p(t-L)), L = 20 frames = 5 clones; the past frames
 * t-10 and t-20 are warped into frame t's orientation with the filter's relative rotation (same inverse bilinear warp,
 * zero padding, align_corners=True pixel centres as model.warp). In body axes z_b = R_bc d_c = R_b^T (p_b - p_a).
 * Jacobian (right-perturbed orientations): d z_b / d theta_b = [z_b]x, d/d p_b = R_b^T, d/d p_a = -R_b^T.
 */
#ifndef DT_ON
#define DT_ON 1
#endif
#ifndef DT_EVERY
#define DT_EVERY 1          /* apply at every DT_EVERY-th eligible clone (1 = every clone, overlapping 1 s windows) */
#endif
#ifndef DT_INFL
#define DT_INFL 2.0         /* sigma = DT_INFL * sqrt(2) * laplace_scale (overlap + model-error inflation) */
#endif
#ifndef DT_SIGMIN
#define DT_SIGMIN 0.02      /* m, per-axis floor */
#endif
#ifndef DT_GATE
#define DT_GATE 16.27       /* chi2(3) 99.9 % */
#endif
#ifndef DT_T0
#define DT_T0 1.0           /* s, first use */
#endif
#ifndef DT_LAG
#define DT_LAG 20
#endif
#ifndef DT_MINNIS
#define DT_MINNIS 0         /* >0: disagreement trigger, apply only when the update's NIS (or its EMA) exceeds this */
#endif
#ifndef DT_NIS_A
#define DT_NIS_A 0.0        /* EMA weight of the NIS trigger (0 = instantaneous) */
#endif
#define DT_W 128
#define DT_H 96
#define DT_RING (DT_LAG + 1)

static uint8_t dt_gray[DT_RING][DT_W * DT_H];
static double dt_dv[DT_RING][3], dt_dp[DT_RING][3], dt_tau[DT_RING]; /* per-frame IMU-only increments (world, v0 = 0) */
static double dt_pdv[3], dt_pdp[3], dt_ptau;                           /* pending: the current step's interval */
static double dt_Rwb[DT_RING][9];
static int dt_frame[DT_RING];
static int dt_count;            /* frames pushed since init */
static int dt_eligible, dt_used, dt_rej, dt_skip;
static double dt_nis_ema = -1;
static double dt_last[12], dt_lastaux[10];
static float dt_tmpf[240 * DT_W];

/* OpenCV COLOR_RGB2GRAY (fixed point, 8U) then INTER_AREA 320x240 -> 128x96 (2.5x: taps .4 .4 .2 / .2 .4 .4) */
static void dt_gray128(const uint8_t *rgb, uint8_t *out) {
    for (int y = 0; y < 240; y++) {
        const uint8_t *p = rgb + 960 * y; float *t = dt_tmpf + y * DT_W;
        float g[5];
        for (int m = 0; m < 64; m++, p += 15) {
            for (int k = 0; k < 5; k++) g[k] = (float)((p[3 * k] * 4899 + p[3 * k + 1] * 9617 + p[3 * k + 2] * 1868 + 8192) >> 14);
            t[2 * m] = (g[0] + g[1]) * 0.4f + g[2] * 0.2f; t[2 * m + 1] = g[2] * 0.2f + (g[3] + g[4]) * 0.4f;
        }
    }
    for (int i = 0; i < DT_H; i++) {
        const float *r0 = dt_tmpf + (5 * (i >> 1)) * DT_W; uint8_t *o = out + i * DT_W;
        const float *a, *b, *c; float wa, wb, wc;
        if (i & 1) { a = r0 + 2 * DT_W; b = r0 + 3 * DT_W; c = r0 + 4 * DT_W; wa = .2f; wb = .4f; wc = .4f; }
        else { a = r0; b = r0 + DT_W; c = r0 + 2 * DT_W; wa = .4f; wb = .4f; wc = .2f; }
        for (int x = 0; x < DT_W; x++) { float v = a[x] * wa + b[x] * wb + c[x] * wc; int q = (int)lrintf(v); o[x] = (uint8_t)(q < 0 ? 0 : q > 255 ? 255 : q); }
    }
}

/* ---------------- network ---------------- */
static float dt_buf0[96 * 48 * 64 * 3], dt_buf1[96 * 48 * 64 * 3];
static float dt_feat[3][DT_ENC_C * 24 * 32];
static float dt_cat[(3 * DT_ENC_C + 2 * 49) * 12 * 16];
static float dt_in[3][2 * DT_H * DT_W];

#include <wasm_simd128.h>
static float dt_col[32 * 9 * 3072]; /* max ci*9*HW over layers (enc layer 2); head 386*9*192 is smaller */
/* conv3x3 via im2col + 4x8 register-blocked SIMD GEMM; co % 4 == 0 and (ho*wo) % 8 == 0 (true for this net) */
static void dt_conv(const float *in, int ci, int h, int w, const float *wt, const float *bias, int co, int s, float *out) {
    const int ho = (h + s - 1) / s, wo = (w + s - 1) / s, HW = ho * wo, K = ci * 9;
    for (int c = 0; c < ci; c++) for (int ky = 0; ky < 3; ky++) for (int kx = 0; kx < 3; kx++) {
        float *col = dt_col + (c * 9 + ky * 3 + kx) * HW; const float *ip = in + c * h * w;
        for (int y = 0; y < ho; y++) {
            int iy = y * s + ky - 1; float *cr = col + y * wo;
            if (iy < 0 || iy >= h) { for (int x = 0; x < wo; x++) cr[x] = 0; continue; }
            const float *row = ip + iy * w;
            for (int x = 0; x < wo; x++) { int ix = x * s + kx - 1; cr[x] = (ix >= 0 && ix < w) ? row[ix] : 0.0f; }
        }
    }
    for (int o = 0; o < co; o += 4) {
        const float *w0 = wt + o * K, *w1 = w0 + K, *w2 = w1 + K, *w3 = w2 + K;
        for (int p = 0; p < HW; p += 8) {
            v128_t a00 = wasm_f32x4_splat(bias[o]), a01 = a00, a10 = wasm_f32x4_splat(bias[o + 1]), a11 = a10,
                   a20 = wasm_f32x4_splat(bias[o + 2]), a21 = a20, a30 = wasm_f32x4_splat(bias[o + 3]), a31 = a30;
            const float *cp = dt_col + p;
            for (int k = 0; k < K; k++, cp += HW) {
                const v128_t c0 = wasm_v128_load(cp), c1 = wasm_v128_load(cp + 4);
                v128_t b;
                b = wasm_f32x4_splat(w0[k]); a00 = wasm_f32x4_add(a00, wasm_f32x4_mul(b, c0)); a01 = wasm_f32x4_add(a01, wasm_f32x4_mul(b, c1));
                b = wasm_f32x4_splat(w1[k]); a10 = wasm_f32x4_add(a10, wasm_f32x4_mul(b, c0)); a11 = wasm_f32x4_add(a11, wasm_f32x4_mul(b, c1));
                b = wasm_f32x4_splat(w2[k]); a20 = wasm_f32x4_add(a20, wasm_f32x4_mul(b, c0)); a21 = wasm_f32x4_add(a21, wasm_f32x4_mul(b, c1));
                b = wasm_f32x4_splat(w3[k]); a30 = wasm_f32x4_add(a30, wasm_f32x4_mul(b, c0)); a31 = wasm_f32x4_add(a31, wasm_f32x4_mul(b, c1));
            }
            const v128_t z = wasm_f32x4_splat(0);
            float *op = out + o * HW + p;
            wasm_v128_store(op, wasm_f32x4_max(a00, z)); wasm_v128_store(op + 4, wasm_f32x4_max(a01, z));
            wasm_v128_store(op + HW, wasm_f32x4_max(a10, z)); wasm_v128_store(op + HW + 4, wasm_f32x4_max(a11, z));
            wasm_v128_store(op + 2 * HW, wasm_f32x4_max(a20, z)); wasm_v128_store(op + 2 * HW + 4, wasm_f32x4_max(a21, z));
            wasm_v128_store(op + 3 * HW, wasm_f32x4_max(a30, z)); wasm_v128_store(op + 3 * HW + 4, wasm_f32x4_max(a31, z));
        }
    }
}

/* reference scalar conv (kept for checks) */
static void dt_conv_ref(const float *in, int ci, int h, int w, const float *wt, const float *bias, int co, int s, float *out) {
    const int ho = (h + s - 1) / s, wo = (w + s - 1) / s;
    for (int o = 0; o < co; o++) {
        float *op = out + o * ho * wo;
        for (int i = 0; i < ho * wo; i++) op[i] = bias[o];
        for (int c = 0; c < ci; c++) {
            const float *ip = in + c * h * w; const float *k = wt + (o * ci + c) * 9;
            for (int ky = 0; ky < 3; ky++) {
                for (int y = 0; y < ho; y++) {
                    int iy = y * s + ky - 1; if (iy < 0 || iy >= h) continue;
                    const float *row = ip + iy * w; float *orow = op + y * wo;
                    for (int kx = 0; kx < 3; kx++) {
                        const float kv = k[ky * 3 + kx];
                        int x0 = 0, x1 = wo;
                        while (x0 < wo && x0 * s + kx - 1 < 0) x0++;
                        while (x1 > x0 && (x1 - 1) * s + kx - 1 >= w) x1--;
                        if (s == 1) { const float *r = row + kx - 1; for (int x = x0; x < x1; x++) orow[x] += kv * r[x]; }
                        else { for (int x = x0; x < x1; x++) orow[x] += kv * row[x * s + kx - 1]; }
                    }
                }
            }
        }
        for (int i = 0; i < ho * wo; i++) if (op[i] < 0) op[i] = 0;
    }
}

static void dt_linear(const float *in, int ni, const float *wt, const float *b, int no, float *out, int relu) {
    for (int o = 0; o < no; o++) {
        float s = b[o]; const float *k = wt + o * ni;
        for (int i = 0; i < ni; i++) s += k[i] * in[i];
        out[o] = relu && s < 0 ? 0 : s;
    }
}

static void dt_encode(const float *in2, float *feat) {
    int c = 2, h = DT_H, w = DT_W; const float *src = in2; float *dst = dt_buf0;
    for (int l = 0; l < DT_ENC_N; l++) {
        dt_conv(src, c, h, w, dt_enc_w[l], dt_enc_b[l], dt_enc_co[l], dt_enc_s[l], l == DT_ENC_N - 1 ? feat : dst);
        h = (h + dt_enc_s[l] - 1) / dt_enc_s[l]; w = (w + dt_enc_s[l] - 1) / dt_enc_s[l]; c = dt_enc_co[l];
        src = dst; dst = dst == dt_buf0 ? dt_buf1 : dt_buf0;
    }
}

static void dt_corr_g(const float *a, const float *b, int C, int H, int W, int r, float *out) { /* (2r+1)^2 channels, mean over C */
    const int n = 2 * r + 1;
    for (int dy = -r; dy <= r; dy++) for (int dx = -r; dx <= r; dx++) {
        float *o = out + ((dy + r) * n + dx + r) * H * W;
        for (int i = 0; i < H * W; i++) o[i] = 0;
        for (int c = 0; c < C; c++) {
            const float *ap = a + c * H * W, *bp = b + c * H * W;
            for (int y = 0; y < H; y++) { int yy = y + dy; if (yy < 0 || yy >= H) continue;
                for (int x = 0; x < W; x++) { int xx = x + dx; if (xx < 0 || xx >= W) continue; o[y * W + x] += ap[y * W + x] * bp[yy * W + xx]; } }
        }
        for (int i = 0; i < H * W; i++) o[i] *= 1.0f / C;
    }
}

static void dt_corr(const float *a, const float *b, int C, float *out) { dt_corr_g(a, b, C, 12, 16, 3, out); }
#ifdef DT_V3
static float dt_cat3[(3 * DT_ENC_C + 2 * 81) * 24 * 32];
static void dt_forward(const float *aux, float *out12) {
    for (int j = 0; j < 3; j++) {  /* per-frame brightness normalisation over valid pixels */
        float *im = dt_in[j], *mk = dt_in[j] + DT_H * DT_W; double s = 0, n = 0;
        for (int i = 0; i < DT_H * DT_W; i++) { s += im[i] * mk[i]; n += mk[i]; }
        float mean = (float)(s / (n < 1 ? 1 : n));
        for (int i = 0; i < DT_H * DT_W; i++) im[i] = (im[i] - mean) * mk[i];
    }
    for (int j = 0; j < 3; j++) dt_encode(dt_in[j], dt_feat[j]);
    const int HW = 24 * 32, C = DT_ENC_C;
    for (int j = 0; j < 3; j++) memcpy(dt_cat3 + j * C * HW, dt_feat[j], sizeof(float) * C * HW);
    dt_corr_g(dt_feat[0], dt_feat[1], C, 24, 32, 4, dt_cat3 + 3 * C * HW);
    dt_corr_g(dt_feat[0], dt_feat[2], C, 24, 32, 4, dt_cat3 + (3 * C + 81) * HW);
    dt_conv(dt_cat3, 3 * C + 162, 24, 32, dt_h_w[0], dt_h_b[0], dt_h_co[0], 2, dt_buf0);
    dt_conv(dt_buf0, dt_h_co[0], 12, 16, dt_h_w[1], dt_h_b[1], dt_h_co[1], 1, dt_buf1);
    dt_conv(dt_buf1, dt_h_co[1], 12, 16, dt_h_w[2], dt_h_b[2], dt_h_co[2], 2, dt_buf0);
    dt_conv(dt_buf0, dt_h_co[2], 6, 8, dt_h_w[3], dt_h_b[3], dt_h_co[3], 1, dt_buf1);
    static float v[DT_H2C * 48 + 10], h1[DT_FC], h2[DT_FC];
    memcpy(v, dt_buf1, sizeof(float) * DT_H2C * 48); memcpy(v + DT_H2C * 48, aux, 10 * sizeof(float));
    dt_linear(v, DT_H2C * 48 + 10, dt_fc1_w, dt_fc1_b, DT_FC, h1, 1);
    dt_linear(h1, DT_FC, dt_fc2_w, dt_fc2_b, DT_FC, h2, 1);
    dt_linear(h2, DT_FC, dt_out_w, dt_out_b, 12, out12, 0);
}
#else
static void dt_forward(const float *aux, float *out12) {
    for (int j = 0; j < 3; j++) dt_encode(dt_in[j], dt_feat[j]);
    const int HW = 12 * 16, C = DT_ENC_C;
    for (int j = 0; j < 3; j++) memcpy(dt_cat + j * C * HW, dt_feat[j], sizeof(float) * C * HW);
    dt_corr(dt_feat[0], dt_feat[1], C, dt_cat + 3 * C * HW);
    dt_corr(dt_feat[0], dt_feat[2], C, dt_cat + (3 * C + 49) * HW);
    dt_conv(dt_cat, 3 * C + 98, 12, 16, dt_h_w[0], dt_h_b[0], dt_h_co[0], 1, dt_buf0);
    dt_conv(dt_buf0, dt_h_co[0], 12, 16, dt_h_w[1], dt_h_b[1], dt_h_co[1], 2, dt_buf1);
    dt_conv(dt_buf1, dt_h_co[1], 6, 8, dt_h_w[2], dt_h_b[2], dt_h_co[2], 1, dt_buf0);
    static float v[DT_H2C * 48 + 10], h1[DT_FC], h2[DT_FC];
    memcpy(v, dt_buf0, sizeof(float) * DT_H2C * 48); memcpy(v + DT_H2C * 48, aux, 10 * sizeof(float));
    dt_linear(v, DT_H2C * 48 + 10, dt_fc1_w, dt_fc1_b, DT_FC, h1, 1);
    dt_linear(h1, DT_FC, dt_fc2_w, dt_fc2_b, DT_FC, h2, 1);
    dt_linear(h2, DT_FC, dt_out_w, dt_out_b, 12, out12, 0);
}
#endif

/* inverse bilinear warp (align_corners=True semantics, zero padding); Hinv maps dst pixel -> src pixel.
   writes image (/255) and mask channels into dst2 = [img][mask] */
static void dt_warp(const uint8_t *src, const double *Hinv, float *dst2) {
    float *im = dst2, *mk = dst2 + DT_H * DT_W;
    for (int v = 0; v < DT_H; v++) for (int u = 0; u < DT_W; u++) {
        double sx = Hinv[0] * u + Hinv[1] * v + Hinv[2], sy = Hinv[3] * u + Hinv[4] * v + Hinv[5], sz = Hinv[6] * u + Hinv[7] * v + Hinv[8];
        float val = 0, m = 0;
        if (sz > 0) {
            if (sz < 1e-9) sz = 1e-9;
            float x = (float)(sx / sz), y = (float)(sy / sz);
            if (x > -2 && x < DT_W + 1 && y > -2 && y < DT_H + 1) {
                int x0 = (int)floorf(x), y0 = (int)floorf(y); float fx = x - x0, fy = y - y0;
                float wsum = 0, acc = 0;
                for (int j = 0; j < 2; j++) for (int i = 0; i < 2; i++) {
                    int xx = x0 + i, yy = y0 + j; float wgt = (i ? fx : 1 - fx) * (j ? fy : 1 - fy);
                    if (xx >= 0 && xx < DT_W && yy >= 0 && yy < DT_H) { acc += wgt * src[yy * DT_W + xx]; wsum += wgt; }
                }
                val = acc / 255.0f; m = wsum > 0.999f ? 1.0f : 0.0f;
            }
        }
        mk[v * DT_W + u] = m; im[v * DT_W + u] = val * m;
    }
}

#ifndef DT_NET_ONLY
/* call BEFORE propagation: preintegrate this step's IMU rows with the filter's rotation/biases (mirrors propagate()) */
static void dt_preint(const double *imu, int n) {
    double Rk[9], tl = last_t; memcpy(Rk, R, sizeof Rk);
    for (int i = 0; i < 3; i++) dt_pdv[i] = dt_pdp[i] = 0;
    dt_ptau = 0;
    for (int r = 0; r < n; r++) {
        const double *row = imu + 7 * r; double dt = row[0] - tl;
        if (dt <= 0) continue;
        tl = row[0];
        double w[3], a[3], wdt[3], dR[9], Ra[3], Rn[9];
        for (int i = 0; i < 3; i++) { w[i] = row[4 + i] - bg[i]; a[i] = row[1 + i] - ba[i]; wdt[i] = w[i] * dt; }
        m3vec(Rk, a, Ra); Ra[2] -= GRAVITY;
        for (int i = 0; i < 3; i++) { dt_pdp[i] += dt_pdv[i] * dt + 0.5 * Ra[i] * dt * dt; dt_pdv[i] += Ra[i] * dt; }
        dt_ptau += dt;
        exp_so3(wdt, dR); m3mul(Rk, dR, Rn); memcpy(Rk, Rn, sizeof Rk);
    }
}
/* acceleration-only displacement over the last nf frame intervals ending at the current step (pending included), world */
static void dt_accdisp(int nf, double *out) {
    double v[3] = {0, 0, 0}, p[3] = {0, 0, 0};
    for (int j = nf - 1; j >= 1; j--) {            /* ring frames dt_count-j (oldest first) */
        int k = (dt_count - j) % DT_RING;
        for (int i = 0; i < 3; i++) { p[i] += v[i] * dt_tau[k] + dt_dp[k][i]; v[i] += dt_dv[k][i]; }
    }
    for (int i = 0; i < 3; i++) p[i] += v[i] * dt_ptau + dt_pdp[i];
    memcpy(out, p, sizeof p);
}
static void dt_reset(void) { dt_count = 0; dt_eligible = dt_used = dt_rej = dt_skip = 0; dt_nis_ema = -1; }

/* call once per step AFTER the filter update, with the step's frame */
static void dt_push(const uint8_t *rgb) {
    int k = dt_count % DT_RING;
    dt_gray128(rgb, dt_gray[k]);
    memcpy(dt_Rwb[k], R, sizeof R);
    dt_frame[k] = frame_no;
    memcpy(dt_dv[k], dt_pdv, sizeof dt_pdv); memcpy(dt_dp[k], dt_pdp, sizeof dt_pdp); dt_tau[k] = dt_ptau;
    for (int i = 0; i < 3; i++) dt_pdv[i] = dt_pdp[i] = 0;
    dt_ptau = 0;
    dt_count++;
#ifdef DT_LOG
    if (frame_no % 300 == 299) fprintf(stderr, "dt f%d skip %d used %d rej %d last %.2f %.2f %.2f s %.2f %.2f %.2f\n", frame_no, dt_skip, dt_used, dt_rej,
                                        dt_last[0], dt_last[1], dt_last[2], exp(dt_last[3]), exp(dt_last[4]), exp(dt_last[5]));
#endif
}

/* the newest clone was just added at this frame (frames_since_clone == 0); clones[nclones-1] is it. */
static void dt_update(const uint8_t *rgb) {
#if DT_ON
    if (!initialized || nclones < 6 || dt_count < DT_LAG || last_t - t_start < DT_T0) return;
    if (frames_since_clone != 0) return;
    const Clone *cb = &clones[nclones - 1], *ca = &clones[nclones - 6];
    if (cb->id - ca->id != 5) return;
    if ((dt_eligible++ % DT_EVERY) != 0) return;
    /* current frame gray (not yet pushed) */
    static uint8_t cur[DT_W * DT_H];
    dt_gray128(rgb, cur);
    const int km = (dt_count - DT_LAG / 2) % DT_RING, kf = (dt_count - DT_LAG) % DT_RING;
    if (dt_frame[kf] != frame_no - DT_LAG || dt_frame[km] != frame_no - DT_LAG / 2) return;
    /* intrinsics at 128x96 (Inputs: (c + .5) * s - .5) */
    const double s = DT_W / 320.0, Kfx = fx * s, Kfy = fy * s, Kcx = (cx + .5) * s - .5, Kcy = (cy + .5) * s - .5;
    double Rwc_t[9], Rwc_j[9], Rcc[9], tmp[9];
    m3mul(cb->R, R_bc, Rwc_t);
    for (int q = 0; q < 2; q++) {
        const double *Rb = q == 0 ? dt_Rwb[km] : ca->R;   /* far frame uses the clone itself (same frame) */
        m3mul(Rb, R_bc, Rwc_j);
        m3tmul(Rwc_t, Rwc_j, Rcc);                        /* prev cam -> cur cam */
        /* Hinv = K Rcc^T K^-1 */
        double Ki[9] = {1 / Kfx, 0, -Kcx / Kfx, 0, 1 / Kfy, -Kcy / Kfy, 0, 0, 1}, K[9] = {Kfx, 0, Kcx, 0, Kfy, Kcy, 0, 0, 1}, A[9], Hinv[9];
        double RccT[9]; for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) RccT[3 * i + j] = Rcc[3 * j + i];
        m3mul(RccT, Ki, A); m3mul(K, A, Hinv);
        dt_warp(dt_gray[q == 0 ? km : kf], Hinv, dt_in[q + 1]);
    }
    for (int i = 0; i < DT_W * DT_H; i++) { dt_in[0][i] = cur[i] / 255.0f; dt_in[0][DT_W * DT_H + i] = 1.0f; }
    (void)tmp;
    float aux[10], o[12];
    { double gw[3] = {0, 0, -1}, gc[3]; m3tvec(Rwc_t, gw, gc); for (int i = 0; i < 3; i++) aux[i] = (float)gc[i]; aux[3] = (float)(Kfx / DT_W); }
    { double aw[3], ac[3];   /* intervals (t-L, t] and (t-L/2, t]: the far window spans DT_LAG frame intervals */
      dt_accdisp(DT_LAG, aw); m3tvec(Rwc_t, aw, ac); for (int i = 0; i < 3; i++) aux[4 + i] = (float)ac[i];
      dt_accdisp(DT_LAG / 2, aw); m3tvec(Rwc_t, aw, ac); for (int i = 0; i < 3; i++) aux[7 + i] = (float)ac[i]; }
    dt_forward(aux, o);
    for (int i = 0; i < 12; i++) dt_last[i] = o[i];
    for (int i = 0; i < 10; i++) dt_lastaux[i] = aux[i];
#ifdef DT_LOGAUX
    fprintf(stderr, "aux f%d %.4f %.4f %.4f | %.4f %.4f %.4f | %.4f %.4f %.4f | z %.4f %.4f %.4f\n", frame_no, aux[0], aux[1], aux[2],
            aux[4], aux[5], aux[6], aux[7], aux[8], aux[9], o[0], o[1], o[2]);
#endif
    /* residual and Jacobian in camera axes, whitened */
    double dpw[3], hb[3], hc[3], zc[3] = {o[0], o[1], o[2]}, sig[3];
    for (int i = 0; i < 3; i++) dpw[i] = cb->p[i] - ca->p[i];
    m3tvec(cb->R, dpw, hb);                     /* R_b^T (p_b - p_a) */
    m3tvec(R_bc, hb, hc);                       /* camera axes */
    for (int i = 0; i < 3; i++) {
        double ls = o[3 + i]; if (ls < -6) ls = -6; if (ls > 3) ls = 3;
        sig[i] = DT_INFL * 1.41421356 * exp(ls); if (sig[i] < DT_SIGMIN) sig[i] = DT_SIGMIN;
    }
    static double Hm[3 * MAXD]; double r[3];
    memset(Hm, 0, sizeof Hm);
    const int ob = CORE + 6 * (nclones - 1), oa = CORE + 6 * (nclones - 6);
    double Sk[9], RbT[9], Jth[9], Jp[9];
    skew(hb, Sk);                                 /* d hb / d theta_b = [hb]x */
    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) RbT[3 * i + j] = cb->R[3 * j + i];
    /* camera-axis rows: R_bc^T * (body rows) */
    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) {
        double a = 0, b = 0;
        for (int k = 0; k < 3; k++) { a += R_bc[3 * k + i] * Sk[3 * k + j]; b += R_bc[3 * k + i] * RbT[3 * k + j]; }
        Jth[3 * i + j] = a; Jp[3 * i + j] = b;
    }
    for (int i = 0; i < 3; i++) {
        r[i] = (zc[i] - hc[i]) / sig[i];
        for (int j = 0; j < 3; j++) {
            Hm[i * MAXD + ob + j] = Jth[3 * i + j] / sig[i];
            Hm[i * MAXD + ob + 3 + j] = Jp[3 * i + j] / sig[i];
            Hm[i * MAXD + oa + 3 + j] = -Jp[3 * i + j] / sig[i];
        }
    }
#if DT_MINNIS > 0
    { /* disagreement trigger: NIS = r^T (H P H^T + I)^-1 r over the 9 nonzero columns; apply only when B16 likely wrong */
        int cols[9]; for (int j = 0; j < 3; j++) { cols[j] = ob + j; cols[3 + j] = ob + 3 + j; cols[6 + j] = oa + 3 + j; }
        double S[9];
        for (int i = 0; i < 3; i++) for (int k = 0; k < 3; k++) {
            double s = i == k ? 1.0 : 0.0;
            for (int u = 0; u < 9; u++) { double hu = Hm[i * MAXD + cols[u]]; if (hu == 0) continue;
                for (int w = 0; w < 9; w++) s += hu * Pm[cols[u] * MAXD + cols[w]] * Hm[k * MAXD + cols[w]]; }
            S[3 * i + k] = s;
        }
        double x[3];
        if (!solve3(S, r, x)) return;
        double nis = r[0] * x[0] + r[1] * x[1] + r[2] * x[2];
        dt_nis_ema = dt_nis_ema < 0 ? nis : (1 - DT_NIS_A) * dt_nis_ema + DT_NIS_A * nis;
        if ((DT_NIS_A > 0 ? dt_nis_ema : nis) < DT_MINNIS) { dt_skip++; return; }
    }
#endif
    if (update(r, Hm, 3, 1.0, DT_GATE)) dt_used++; else dt_rej++;
#else
    (void)rgb;
#endif
}
#endif /* DT_NET_ONLY */
