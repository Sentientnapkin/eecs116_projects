/* ===================================================================================================================
 * Learned startup-velocity net (research/single_model/learned_c). Inference of train2.py's Net (nf=2, 64x48, width 1) in plain C.
 * Inputs: frame 0 and frame LC_K (=5), gyro-derotated into frame 0's orientation with the raw-gyro integral between them (own integration,
 * independent of the filter's biased state), per-frame normalisation, validity mask, coordinate channels; 19 IMU features
 * (window means of specific force/gyro at both frames, integral of R a dt, relative rotation vector, fx).
 * Output: body-frame velocity at frame 5 (head K) + per-axis log-variance. The forward pass can be spread over frames (LC_SPREAD).
 * Static memory only. Needs from the host file: fx, cx, cy, R_bc (camera -> body), update(), Hs, R, vel, MAXD, V.
 * =================================================================================================================== */
#ifndef LC_K
#define LC_K 5
#endif
#ifndef LC_SPREAD
#define LC_SPREAD 0          /* 0: whole net in frame LC_K; 1: stages over frames K..K+4; 2: over K..K+5 */
#endif
#ifndef LC_SCALE
#define LC_SCALE 1.0         /* multiplier on the predicted sigma */
#endif
#ifndef LC_FLOOR
#define LC_FLOOR 0.05        /* m/s, floor of the sigma used by the filter */
#endif
#ifndef LC_REPLACE
#define LC_REPLACE 1         /* 1: once the net has been applied, the heading prior's startup role ends */
#endif
#ifndef LC_SLOW_V
#define LC_SLOW_V 0.0       /* predicted speed below this: sigma floor LC_SLOW_FLOOR instead (hover-like starts) */
#endif
#ifndef LC_SLOW_FLOOR
#define LC_SLOW_FLOOR LC_FLOOR
#endif
#ifndef LC_SPD_K
#define LC_SPD_K 0.0         /* sigma *= 1 + K*predicted speed (calibration for fast starts) */
#endif
#ifndef LC_ENABLE
#define LC_ENABLE 1
#endif
#ifndef LC_EXTRA_SD
#define LC_EXTRA_SD 0.0      /* m/s added in quadrature (delay of the measurement) */
#endif
#define LC_W 128
#define LC_H 96
#define LC_PW 64
#define LC_PH 48
#include "lc_weights.h"

static uint8_t lc_g0[LC_H * LC_W], lc_g5[LC_H * LC_W];
static float lc_tmp[240 * LC_W];                      /* gray resampling scratch */
static float lc_x0[LC_H * LC_W], lc_x1[LC_H * LC_W], lc_m[LC_H * LC_W]; /* normalisation scratch */
static float lc_in[LC_PH * LC_PW * 5];
static float lc_a0[24 * 32 * LC_C0], lc_a1[12 * 16 * LC_C1], lc_a2[6 * 8 * LC_C2], lc_a3[3 * 4 * LC_C3];
static float lc_vec[19], lc_out[12];
static double lc_Rc[9], lc_Vi[3], lc_Rs[9], lc_Vs[3], lc_R5[9], lc_V5[3], lc_fm[2][3], lc_gm[2][3], lc_tprev, lc_Rf5[9], lc_vf5[3];
static int lc_have_row, lc_frame, lc_next, lc_ready, lc_applied, lc_active;
static const signed char lc_at_tab[4][6] = {{0, 0, 0, 0, 0, 0}, {0, 1, 2, 3, 3, 4}, {0, 1, 2, 3, 4, 5}, {0, 1, 1, 1, 1, 1}};

static void lc_exp(const double *w, double *r) { /* Rodrigues, same as prep.py exp_rot (first order below 1e-9) */
    double th = sqrt(w[0] * w[0] + w[1] * w[1] + w[2] * w[2]);
    if (th > 1e-9) {
        double a[3] = {w[0] / th, w[1] / th, w[2] / th}, s = sin(th), c = cos(th), k = 1 - c;
        r[0] = c + k * a[0] * a[0]; r[1] = k * a[0] * a[1] - s * a[2]; r[2] = k * a[0] * a[2] + s * a[1];
        r[3] = k * a[0] * a[1] + s * a[2]; r[4] = c + k * a[1] * a[1]; r[5] = k * a[1] * a[2] - s * a[0];
        r[6] = k * a[0] * a[2] - s * a[1]; r[7] = k * a[1] * a[2] + s * a[0]; r[8] = c + k * a[2] * a[2];
    } else {
        r[0] = 1; r[1] = -w[2]; r[2] = w[1]; r[3] = w[2]; r[4] = 1; r[5] = -w[0]; r[6] = -w[1]; r[7] = w[0]; r[8] = 1;
    }
}

/* raw-gyro orientation and integral of R a dt over this step's IMU rows (+ window means) */
static void lc_rows(const double *imu, int n, double *fm, double *gm) {
    double fs[3] = {0, 0, 0}, gs[3] = {0, 0, 0};
    for (int r = 0; r < n; r++) {
        const double *row = imu + 7 * r;
        double dt = lc_have_row ? row[0] - lc_tprev : 0.005, w[3] = {row[4] * dt, row[5] * dt, row[6] * dt}, dR[9], Rn[9];
        lc_have_row = 1; lc_tprev = row[0];
        lc_exp(w, dR); m3mul(lc_Rc, dR, Rn); memcpy(lc_Rc, Rn, sizeof Rn);
        for (int i = 0; i < 3; i++) {
            lc_Vi[i] += (lc_Rc[3 * i] * row[1] + lc_Rc[3 * i + 1] * row[2] + lc_Rc[3 * i + 2] * row[3]) * dt;
            fs[i] += row[1 + i]; gs[i] += row[4 + i];
        }
    }
    for (int i = 0; i < 3; i++) { fm[i] = n ? fs[i] / n : 0; gm[i] = n ? gs[i] / n : 0; }
}

/* 320x240 RGB -> gray (mean of channels, float) -> exact area resampling by 2.5 -> 128x96 uint8 (rounded). The 2.5 ratio makes the taps periodic
 * (5 source pixels -> 2 outputs with weights {1,1,.5} and {.5,1,1}); same float operations in the same order as the generic version -> bit-identical, ~3x cheaper. */
static void lc_gray128(const uint8_t *rgb, uint8_t *out) {
    const float k3 = 1.0f / 3.0f;
    for (int y = 0; y < 240; y++) {
        const uint8_t *p = rgb + 960 * y; float *t = lc_tmp + y * LC_W;
        for (int m = 0; m < 64; m++, p += 15) {
            float g0 = (float)(p[0] + p[1] + p[2]) * k3, g1 = (float)(p[3] + p[4] + p[5]) * k3, g2 = (float)(p[6] + p[7] + p[8]) * k3,
                  g3 = (float)(p[9] + p[10] + p[11]) * k3, g4 = (float)(p[12] + p[13] + p[14]) * k3;
            t[2 * m] = ((g0 + g1) + 0.5f * g2) * 0.4f; t[2 * m + 1] = ((0.5f * g2 + g3) + g4) * 0.4f;
        }
    }
    for (int i = 0; i < LC_H; i++) {
        const float *r0 = lc_tmp + (5 * (i >> 1)) * LC_W; uint8_t *o = out + i * LC_W;
        if (i & 1) {
            const float *a = r0 + 2 * LC_W, *b = r0 + 3 * LC_W, *c = r0 + 4 * LC_W;
            for (int x = 0; x < LC_W; x++) { float v = ((0.5f * a[x] + b[x]) + c[x]) * 0.4f + 0.5f; o[x] = (uint8_t)(v < 0 ? 0 : v > 255 ? 255 : (int)v); }
        } else {
            const float *a = r0, *b = r0 + LC_W, *c = r0 + 2 * LC_W;
            for (int x = 0; x < LC_W; x++) { float v = ((a[x] + b[x]) + 0.5f * c[x]) * 0.4f + 0.5f; o[x] = (uint8_t)(v < 0 ? 0 : v > 255 ? 255 : (int)v); }
        }
    }
}

/* 1 once the frame-K step has been reached: the heading prior's startup role ends (the zero-mean speed prior takes over until the net lands) */
#define LC_PRIOR_OFF (LC_REPLACE && lc_active && lc_frame >= LC_K)
static void lc_begin(const uint8_t *frame, const double *imu, int n) { /* frame 0 (init step) */
    memset(lc_Rc, 0, sizeof lc_Rc); lc_Rc[0] = lc_Rc[4] = lc_Rc[8] = 1; memset(lc_Vi, 0, sizeof lc_Vi);
    lc_have_row = 0; lc_frame = 0; lc_next = 0; lc_ready = 0; lc_applied = 0; lc_active = LC_ENABLE;
    lc_rows(imu, n, lc_fm[0], lc_gm[0]);
    memcpy(lc_Rs, lc_Rc, sizeof lc_Rs); memcpy(lc_Vs, lc_Vi, sizeof lc_Vs);
    if (lc_active) lc_gray128(frame, lc_g0);
}

/* stage 0: derotate frame K into frame 0, normalise, pool, vector features */
static void lc_stage_prep(void) {
    double Rb[9], T[9], Rc[9], s = 128.0 / 320.0, f_ = fx * s, cx_ = (cx + 0.5) * s - 0.5, cy_ = (cy + 0.5) * s - 0.5;
    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) { double a = 0; for (int k = 0; k < 3; k++) a += lc_Rs[3 * k + i] * lc_R5[3 * k + j]; Rb[3 * i + j] = a; }
    m3tmul(R_bc, Rb, T); m3mul(T, R_bc, Rc);              /* Rc = Rbc^T Rb Rbc */
    double sum0 = 0, sum1 = 0, cnt = 0;
    for (int v = 0; v < LC_H; v++)
        for (int u = 0; u < LC_W; u++) {
            double d[3] = {(u - cx_) / f_, (v - cy_) / f_, 1.0}, dk[3];
            for (int i = 0; i < 3; i++) dk[i] = Rc[i] * d[0] + Rc[3 + i] * d[1] + Rc[6 + i] * d[2]; /* Rc^T d */
            double z = dk[2] > 1e-3 ? dk[2] : 1e-3, uk = f_ * dk[0] / z + cx_, vk = f_ * dk[1] / z + cy_;
            int ok = uk >= -0.5 && uk <= LC_W - 0.5 && vk >= -0.5 && vk <= LC_H - 0.5 && dk[2] > 1e-3;
            float val = 0;
            if (ok) {
                double fu = floor(uk), fv = floor(vk), au = uk - fu, av = vk - fv;
                int x0 = (int)fu, y0 = (int)fv;
                for (int dy = 0; dy < 2; dy++) for (int dx = 0; dx < 2; dx++) {
                    int xx = x0 + dx, yy = y0 + dy;
                    if (xx < 0 || xx >= LC_W || yy < 0 || yy >= LC_H) continue;
                    val += (float)((dx ? au : 1 - au) * (dy ? av : 1 - av)) * lc_g5[yy * LC_W + xx];
                }
            }
            int p = v * LC_W + u;
            lc_x1[p] = val; lc_m[p] = (float)ok; lc_x0[p] = lc_g0[p];
            sum0 += lc_x0[p]; sum1 += val; cnt += ok;
        }
    double n0 = LC_H * LC_W, m0 = sum0 / n0, m1 = sum1 / (cnt > 1 ? cnt : 1), v0 = 0, v1 = 0;
    for (int p = 0; p < LC_H * LC_W; p++) { double a = lc_x0[p] - m0, b = (lc_x1[p] - m1) * lc_m[p]; v0 += a * a; v1 += b * b; }
    float i0 = (float)(1.0 / (sqrt(v0 / n0) + 5.0)), i1 = (float)(1.0 / (sqrt(v1 / (cnt > 1 ? cnt : 1)) + 5.0)), fm0 = (float)m0, fm1 = (float)m1;
    for (int v = 0; v < LC_PH; v++)
        for (int u = 0; u < LC_PW; u++) {
            float a0 = 0, a1 = 0, am = 0;
            for (int dy = 0; dy < 2; dy++) for (int dx = 0; dx < 2; dx++) {
                int p = (2 * v + dy) * LC_W + 2 * u + dx;
                a0 += (lc_x0[p] - fm0) * i0; a1 += (lc_x1[p] - fm1) * i1 * lc_m[p]; am += lc_m[p];
            }
            float *o = lc_in + (v * LC_PW + u) * 5;
            o[0] = a0 * 0.25f; o[1] = a1 * 0.25f; o[2] = am * 0.25f;
            o[3] = (float)(-1.0 + (2 * u + 0.5) * (2.0 / 127.0)); o[4] = (float)(-1.0 + (2 * v + 0.5) * (2.0 / 95.0));
        }
    /* vector features */
    for (int i = 0; i < 3; i++) {
        lc_vec[i] = (float)(lc_fm[0][i] / 9.81); lc_vec[3 + i] = (float)lc_gm[0][i];
        lc_vec[6 + i] = (float)(lc_fm[1][i] / 9.81); lc_vec[9 + i] = (float)lc_gm[1][i];
        double dv = lc_Rs[i] * (lc_V5[0] - lc_Vs[0]) + lc_Rs[3 + i] * (lc_V5[1] - lc_Vs[1]) + lc_Rs[6 + i] * (lc_V5[2] - lc_Vs[2]);
        lc_vec[12 + i] = (float)(dv / (0.05 * 5 * 1 * 1 * 9.81));
    }
    double tr = (Rb[0] + Rb[4] + Rb[8] - 1) / 2;
    tr = tr < -1 + 1e-6 ? -1 + 1e-6 : tr > 1 - 1e-6 ? 1 - 1e-6 : tr;
    double th = acos(tr), w[3] = {Rb[7] - Rb[5], Rb[2] - Rb[6], Rb[3] - Rb[1]}, k = th / (2 * sin(th) + 1e-6);
    for (int i = 0; i < 3; i++) lc_vec[15 + i] = (float)(w[i] * k);
    lc_vec[18] = (float)(fx / 100.0);
}

#define LC_CONV(NAME, CI, CO, IH, IW, WT, BT) \
static void NAME(const float *in, float *out) { \
    const int OH = (IH) / 2, OW = (IW) / 2; \
    for (int oy = 0; oy < OH; oy++) for (int ox = 0; ox < OW; ox++) { \
        float acc[CO]; for (int c = 0; c < (CO); c++) acc[c] = (BT)[c]; \
        for (int ky = 0; ky < 3; ky++) { int iy = oy * 2 - 1 + ky; if (iy < 0 || iy >= (IH)) continue; \
            for (int kx = 0; kx < 3; kx++) { int ix = ox * 2 - 1 + kx; if (ix < 0 || ix >= (IW)) continue; \
                const float *ip = in + (iy * (IW) + ix) * (CI); const float *wp = (WT) + (ky * 3 + kx) * (CI) * (CO); \
                for (int ci = 0; ci < (CI); ci++) { float a = ip[ci]; const float *w = wp + ci * (CO); for (int c = 0; c < (CO); c++) acc[c] += a * w[c]; } } } \
        float *op = out + (oy * OW + ox) * (CO); for (int c = 0; c < (CO); c++) op[c] = acc[c] > 0 ? acc[c] : 0; } }
LC_CONV(lc_conv0, 5, LC_C0, LC_PH, LC_PW, LC_W0, LC_B0)
LC_CONV(lc_conv1, LC_C0, LC_C1, 24, 32, LC_W1, LC_B1)
LC_CONV(lc_conv2, LC_C1, LC_C2, 12, 16, LC_W2, LC_B2)
LC_CONV(lc_conv3, LC_C2, LC_C3, 6, 8, LC_W3, LC_B3)

static void lc_head(void) {
    float emb[32], h[128];
    for (int j = 0; j < 32; j++) emb[j] = LC_FB0[j];
    for (int i = 0; i < 19; i++) for (int j = 0; j < 32; j++) emb[j] += lc_vec[i] * LC_FW0[i * 32 + j];
    for (int j = 0; j < 32; j++) emb[j] = emb[j] > 0 ? emb[j] : 0;
    for (int j = 0; j < 128; j++) h[j] = LC_H1B[j];
    for (int i = 0; i < 12 * LC_C3; i++) { float a = lc_a3[i]; const float *w = LC_H1W + i * 128; for (int j = 0; j < 128; j++) h[j] += a * w[j]; }
    for (int i = 0; i < 32; i++) { float a = emb[i]; const float *w = LC_H1W + (12 * LC_C3 + i) * 128; for (int j = 0; j < 128; j++) h[j] += a * w[j]; }
    for (int j = 0; j < 128; j++) h[j] = h[j] > 0 ? h[j] : 0;
    for (int j = 0; j < 12; j++) lc_out[j] = LC_H2B[j];
    for (int i = 0; i < 128; i++) { float a = h[i]; const float *w = LC_H2W + i * 12; for (int j = 0; j < 12; j++) lc_out[j] += a * w[j]; }
}

/* the filter measurement: body-frame velocity at frame K, expressed as the world innovation at frame K applied to the current state */
static void lc_apply(void) {
    double sd[3], mu[3], dw[3], r[3];
    double spd = sqrt(lc_out[6] * lc_out[6] + lc_out[7] * lc_out[7] + lc_out[8] * lc_out[8]), fl = spd < LC_SLOW_V ? LC_SLOW_FLOOR : LC_FLOOR;
    for (int i = 0; i < 3; i++) {
        double lv = lc_out[9 + i]; lv = lv < -7 ? -7 : lv > 4 ? 4 : lv;
        double s = LC_SCALE * exp(0.5 * lv) * (1.0 + LC_SPD_K * spd); s = sqrt(s * s + LC_EXTRA_SD * LC_EXTRA_SD);
        sd[i] = s < fl ? fl : s; mu[i] = lc_out[6 + i];
    }
    for (int i = 0; i < 3; i++) dw[i] = lc_Rf5[3 * i] * mu[0] + lc_Rf5[3 * i + 1] * mu[1] + lc_Rf5[3 * i + 2] * mu[2] - lc_vf5[i];
    memset(Hs, 0, sizeof Hs);
    for (int i = 0; i < 3; i++) {
        r[i] = (R[i] * dw[0] + R[3 + i] * dw[1] + R[6 + i] * dw[2]) / sd[i];
        for (int j = 0; j < 3; j++) Hs[i * MAXD + V + j] = R[3 * j + i] / sd[i];
    }
#ifdef LC_DEBUG
    fprintf(stderr, "LC apply frame %d mu %.3f %.3f %.3f sd %.3f %.3f %.3f | innov_b %.3f %.3f %.3f (x sd) vel_w %.3f %.3f %.3f\n", lc_frame, mu[0], mu[1], mu[2], sd[0], sd[1], sd[2], r[0], r[1], r[2], vel[0], vel[1], vel[2]);
#endif
    update(r, Hs, 3, 1.0, INFINITY);
#ifdef LC_DEBUG
    fprintf(stderr, "LC after vel_w %.3f %.3f %.3f\n", vel[0], vel[1], vel[2]);
#endif
    lc_applied = 1;
}

/* called once per step after the IMU part (frames >= 1) */
static void lc_step(const uint8_t *frame, const double *imu, int n) {
    if (!lc_active || lc_applied) return;
    lc_frame++;
    if (lc_frame <= LC_K) {
        double fm[3], gm[3];
        lc_rows(imu, n, fm, gm);
        if (lc_frame == LC_K) {
            memcpy(lc_fm[1], fm, sizeof fm); memcpy(lc_gm[1], gm, sizeof gm);
            memcpy(lc_R5, lc_Rc, sizeof lc_R5); memcpy(lc_V5, lc_Vi, sizeof lc_V5);
            memcpy(lc_Rf5, R, sizeof lc_Rf5); memcpy(lc_vf5, vel, sizeof lc_vf5);
            lc_gray128(frame, lc_g5);
        }
    }
    if (lc_frame < LC_K) return;
    const signed char *at = lc_at_tab[LC_SPREAD];
    while (lc_next < 6 && lc_frame >= LC_K + at[lc_next]) {
        switch (lc_next) {
        case 0: lc_stage_prep(); break;
        case 1: lc_conv0(lc_in, lc_a0); break;
        case 2: lc_conv1(lc_a0, lc_a1); break;
        case 3: lc_conv2(lc_a1, lc_a2); break;
        case 4: lc_conv3(lc_a2, lc_a3); break;
        case 5: lc_head(); lc_apply(); break;
        }
        lc_next++;
        if (lc_next < 6 && at[lc_next] > at[lc_next - 1]) break; /* one scheduled frame per step */
    }
}
