static uint8_t lc_g0[LC_H * LC_W], lc_g5[LC_H * LC_W];
static float lc_x0[LC_H * LC_W], lc_x1[LC_H * LC_W], lc_m[LC_H * LC_W]; /* normalisation scratch */
static float lc_in[LC_PH * LC_PW * 5];
static float lc_a0[(LC_PH >> 1) * (LC_PW >> 1) * LC_C0];
#if NET_NL > 1
static float lc_a1[(LC_PH >> 2) * (LC_PW >> 2) * LC_C1];
#endif
#if NET_NL > 2
static float lc_a2[(LC_PH >> 3) * (LC_PW >> 3) * LC_C2];
#endif
#if NET_NL > 3
static float lc_a3[(LC_PH >> 4) * (LC_PW >> 4) * LC_C3];
#endif
#if NET_NL > 4
static float lc_a4[(LC_PH >> 5) * (LC_PW >> 5) * LC_C4];
#endif
static float lc_vec[19], lc_out[12];
static double lc_Rc[9], lc_Vi[3], lc_Rs[9], lc_Vs[3], lc_R5[9], lc_V5[3], lc_fm[2][3], lc_gm[2][3], lc_tprev, lc_Rf5[9], lc_vf5[3];
static int lc_have_row;
static uint8_t ns_rgb0[IMG_W * IMG_H * 3], ns_rgb5[IMG_W * IMG_H * 3];
static int ns_have5;
static double ns_Rb[9], ns_Rc[9], ns_f, ns_cx, ns_cy, ns_sum0, ns_sum1, ns_cnt, ns_v0, ns_v1, ns_m0, ns_m1;
static float ns_h[LC_HID], ns_emb[32];
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

static void lc_gray_pair_i(const uint8_t *rgb, uint8_t *out, int pr) {
    static uint16_t G[5][IMG_W + 16];
    for (int yy = 0; yy < 5; yy++) {
        const uint8_t *p = rgb + 960 * (5 * pr + yy); uint16_t *g = G[yy];
        for (int i = 0; i < IMG_W; i += 16, p += 48) {
            v128_t a = wasm_v128_load(p), b = wasm_v128_load(p + 16), c = wasm_v128_load(p + 32);
            v128_t r = wasm_i8x16_shuffle(wasm_i8x16_shuffle(a, b, 0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 0, 0, 0, 0, 0), c, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 17, 20, 23, 26, 29);
            v128_t gg = wasm_i8x16_shuffle(wasm_i8x16_shuffle(a, b, 1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 0, 0, 0, 0, 0), c, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 21, 24, 27, 30);
            v128_t bb = wasm_i8x16_shuffle(wasm_i8x16_shuffle(a, b, 2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 0, 0, 0, 0, 0, 0), c, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 19, 22, 25, 28, 31);
            wasm_v128_store(g + i, wasm_i16x8_add(wasm_i16x8_add(wasm_u16x8_extend_low_u8x16(r), wasm_u16x8_extend_low_u8x16(gg)), wasm_u16x8_extend_low_u8x16(bb)));
            wasm_v128_store(g + i + 8, wasm_i16x8_add(wasm_i16x8_add(wasm_u16x8_extend_high_u8x16(r), wasm_u16x8_extend_high_u8x16(gg)), wasm_u16x8_extend_high_u8x16(bb)));
        }
    }
    static uint16_t VE[IMG_W + 16], VO[IMG_W + 16];
    for (int i = 0; i < IMG_W; i += 8) {
        v128_t g0 = wasm_v128_load(G[0] + i), g1 = wasm_v128_load(G[1] + i), g2 = wasm_v128_load(G[2] + i), g3 = wasm_v128_load(G[3] + i), g4 = wasm_v128_load(G[4] + i);
        wasm_v128_store(VE + i, wasm_i16x8_add(wasm_i16x8_shl(wasm_i16x8_add(g0, g1), 1), g2));
        wasm_v128_store(VO + i, wasm_i16x8_add(wasm_i16x8_shl(wasm_i16x8_add(g3, g4), 1), g2));
    }
    uint8_t *oe = out + (2 * pr) * LC_W, *oo = oe + LC_W;
    for (int m = 0; m < 64; m++) {
        const uint16_t *e = VE + 5 * m, *o = VO + 5 * m;
        unsigned he0 = 2u * (e[0] + e[1]) + e[2], he1 = e[2] + 2u * (e[3] + e[4]), ho0 = 2u * (o[0] + o[1]) + o[2], ho1 = o[2] + 2u * (o[3] + o[4]);
        oe[2 * m] = (uint8_t)((2 * he0 + 75) / 150); oe[2 * m + 1] = (uint8_t)((2 * he1 + 75) / 150);
        oo[2 * m] = (uint8_t)((2 * ho0 + 75) / 150); oo[2 * m + 1] = (uint8_t)((2 * ho1 + 75) / 150);
    }
}

static void ns_prep_init(void) {
    double T[9], s_ = ((double)LC_W / 320.0);
    ns_f = fx * s_; ns_cx = (cx + 0.5) * s_ - 0.5; ns_cy = (cy + 0.5) * s_ - 0.5;
    for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) { double a = 0; for (int k = 0; k < 3; k++) a += lc_Rs[3 * k + i] * lc_R5[3 * k + j]; ns_Rb[3 * i + j] = a; }
    m3tmul(R_bc, ns_Rb, T); m3mul(T, R_bc, ns_Rc);
    ns_sum0 = 0; ns_sum1 = 0; ns_cnt = 0;
}
static void ns_prep_rows_v(int v0, int v1) {
    const float f_ = (float)ns_f, cx_ = (float)ns_cx, cy_ = (float)ns_cy, ifv = 1.0f / f_;
    const float r0 = (float)ns_Rc[0], r1 = (float)ns_Rc[1], r2 = (float)ns_Rc[2], r3 = (float)ns_Rc[3], r4 = (float)ns_Rc[4], r5 = (float)ns_Rc[5], r6 = (float)ns_Rc[6], r7 = (float)ns_Rc[7], r8 = (float)ns_Rc[8];
    const v128_t fv = wasm_f32x4_splat(f_), cxv = wasm_f32x4_splat(cx_), cyv = wasm_f32x4_splat(cy_), eps = wasm_f32x4_splat(1e-3f), lo = wasm_f32x4_splat(-0.5f),
                 hiu = wasm_f32x4_splat(LC_W - 0.5f), hiv = wasm_f32x4_splat(LC_H - 0.5f), one = wasm_f32x4_splat(1.0f), zero = wasm_f32x4_splat(0.0f);
    const v128_t du0 = wasm_f32x4_make((0 - cx_) * ifv, (1 - cx_) * ifv, (2 - cx_) * ifv, (3 - cx_) * ifv), dstep = wasm_f32x4_splat(4 * ifv);
    double s0 = 0, s1 = 0, sc = 0;
    for (int v = v0; v < v1; v++) {
        const float dv = (v - cy_) * ifv;
        const v128_t a0 = wasm_f32x4_splat(r3 * dv + r6), a1 = wasm_f32x4_splat(r4 * dv + r7), a2 = wasm_f32x4_splat(r5 * dv + r8);
        const v128_t R0 = wasm_f32x4_splat(r0), R1 = wasm_f32x4_splat(r1), R2 = wasm_f32x4_splat(r2);
        v128_t du = du0;
        float *ox1 = lc_x1 + v * LC_W, *om = lc_m + v * LC_W, *ox0 = lc_x0 + v * LC_W;
        const uint8_t *g0 = lc_g0 + v * LC_W;
        v128_t acc1 = zero, accm = zero;
        for (int u = 0; u < LC_W; u += 4, du = wasm_f32x4_add(du, dstep)) {
            v128_t k0 = wasm_f32x4_add(wasm_f32x4_mul(R0, du), a0), k1 = wasm_f32x4_add(wasm_f32x4_mul(R1, du), a1), k2 = wasm_f32x4_add(wasm_f32x4_mul(R2, du), a2);
            v128_t z = wasm_f32x4_max(k2, eps), iz = wasm_f32x4_div(fv, z);
            v128_t uk = wasm_f32x4_add(wasm_f32x4_mul(k0, iz), cxv), vk = wasm_f32x4_add(wasm_f32x4_mul(k1, iz), cyv);
            v128_t ok = wasm_v128_and(wasm_v128_and(wasm_f32x4_ge(uk, lo), wasm_f32x4_le(uk, hiu)), wasm_v128_and(wasm_v128_and(wasm_f32x4_ge(vk, lo), wasm_f32x4_le(vk, hiv)), wasm_f32x4_gt(k2, eps)));
            v128_t mf = wasm_v128_and(ok, one);
            float U[4], Vv[4], val[4]; int okl[4];
            wasm_v128_store(U, uk); wasm_v128_store(Vv, vk); wasm_v128_store(okl, ok);
            for (int l = 0; l < 4; l++) {
                float vl = 0;
                if (okl[l]) {
                    int x0 = (int)(U[l] + 1.0f) - 1, y0 = (int)(Vv[l] + 1.0f) - 1;
                    float au = U[l] - x0, av = Vv[l] - y0;
                    if (x0 >= 0 && y0 >= 0 && x0 < LC_W - 1 && y0 < LC_H - 1) {
                        const uint8_t *q = lc_g5 + y0 * LC_W + x0;
                        float t0 = q[0] + au * (q[1] - q[0]), t1 = q[LC_W] + au * (q[LC_W + 1] - q[LC_W]);
                        vl = t0 + av * (t1 - t0);
                    } else
                        for (int dy = 0; dy < 2; dy++) for (int dx = 0; dx < 2; dx++) {
                            int xx = x0 + dx, yy = y0 + dy;
                            if (xx < 0 || xx >= LC_W || yy < 0 || yy >= LC_H) continue;
                            vl += (dx ? au : 1 - au) * (dy ? av : 1 - av) * lc_g5[yy * LC_W + xx];
                        }
                }
                val[l] = vl;
            }
            v128_t vv = wasm_v128_load(val);
            wasm_v128_store(ox1 + u, vv); wasm_v128_store(om + u, mf);
            wasm_v128_store(ox0 + u, wasm_f32x4_convert_u32x4(wasm_u32x4_extend_low_u16x8(wasm_u16x8_load8x8(g0 + u))));
            acc1 = wasm_f32x4_add(acc1, vv); accm = wasm_f32x4_add(accm, mf);
        }
        int gs = 0; for (int u = 0; u < LC_W; u++) gs += g0[u];
        float a1v[4], amv[4]; wasm_v128_store(a1v, acc1); wasm_v128_store(amv, accm);
        s0 += gs; s1 += (double)a1v[0] + a1v[1] + a1v[2] + a1v[3]; sc += (double)amv[0] + amv[1] + amv[2] + amv[3];
    }
    ns_sum0 += s0; ns_sum1 += s1; ns_cnt += sc;
}
#define ns_prep_rows ns_prep_rows_v
static void ns_var(int p0, int p1) {
    if (p0 == 0) { double n0 = LC_H * LC_W; ns_m0 = ns_sum0 / n0; ns_m1 = ns_sum1 / (ns_cnt > 1 ? ns_cnt : 1); ns_v0 = 0; ns_v1 = 0; }
    for (int p = p0; p < p1; p++) { double a = lc_x0[p] - ns_m0, b = (lc_x1[p] - ns_m1) * lc_m[p]; ns_v0 += a * a; ns_v1 += b * b; }
}
static void ns_pool(int v0, int v1) {
    double n0 = LC_H * LC_W, cnt = ns_cnt;
    float i0 = (float)(1.0 / (sqrt(ns_v0 / n0) + 5.0)), i1 = (float)(1.0 / (sqrt(ns_v1 / (cnt > 1 ? cnt : 1)) + 5.0)), fm0 = (float)ns_m0, fm1 = (float)ns_m1;
    for (int v = v0; v < v1; v++)
        for (int u = 0; u < LC_PW; u++) {
            float a0 = 0, a1 = 0, am = 0;
            for (int dy = 0; dy < 2; dy++) for (int dx = 0; dx < 2; dx++) {
                int p = (2 * v + dy) * LC_W + 2 * u + dx;
                a0 += (lc_x0[p] - fm0) * i0; a1 += (lc_x1[p] - fm1) * i1 * lc_m[p]; am += lc_m[p];
            }
            float *o = lc_in + (v * LC_PW + u) * 5;
            o[0] = a0 * 0.25f; o[1] = a1 * 0.25f; o[2] = am * 0.25f;
            o[3] = (float)(-1.0 + (2 * u + 0.5) * (2.0 / (LC_W - 1))); o[4] = (float)(-1.0 + (2 * v + 0.5) * (2.0 / (LC_H - 1)));
        }
    if (v1 < LC_PH) return;
    const double *Rb = ns_Rb;
    for (int i = 0; i < 3; i++) {
        lc_vec[i] = (float)(lc_fm[0][i] / 9.81); lc_vec[3 + i] = (float)lc_gm[0][i];
        lc_vec[6 + i] = (float)(lc_fm[1][i] / 9.81); lc_vec[9 + i] = (float)lc_gm[1][i];
        double dv = lc_Rs[i] * (lc_V5[0] - lc_Vs[0]) + lc_Rs[3 + i] * (lc_V5[1] - lc_Vs[1]) + lc_Rs[6 + i] * (lc_V5[2] - lc_Vs[2]);
        lc_vec[12 + i] = (float)(dv / (0.05 * NET_K * 9.81));
    }
    double tr = (Rb[0] + Rb[4] + Rb[8] - 1) / 2;
    tr = tr < -1 + 1e-6 ? -1 + 1e-6 : tr > 1 - 1e-6 ? 1 - 1e-6 : tr;
    double th = acos(tr), w[3] = {Rb[7] - Rb[5], Rb[2] - Rb[6], Rb[3] - Rb[1]}, k = th / (2 * sin(th) + 1e-6);
    for (int i = 0; i < 3; i++) lc_vec[15 + i] = (float)(w[i] * k);
    lc_vec[18] = (float)(fx / 100.0);
}
#define LC_CONVR(NAME, CI, CO, IH, IW, WT, BT) \
static void NAME(const float *in, float *out, int oy0, int oy1, int ox0, int ox1) { \
    const v128_t zero = wasm_f32x4_splat(0.0f); \
    for (int oy = oy0; oy < oy1; oy++) for (int ox = ox0; ox < ox1; ox++) { \
        v128_t acc[(CO) / 4]; for (int q = 0; q < (CO) / 4; q++) acc[q] = wasm_v128_load((BT) + 4 * q); \
        for (int ky = 0; ky < 3; ky++) { int iy = oy * 2 - 1 + ky; if (iy < 0 || iy >= (IH)) continue; \
            for (int kx = 0; kx < 3; kx++) { int ix = ox * 2 - 1 + kx; if (ix < 0 || ix >= (IW)) continue; \
                const float *ip = in + (iy * (IW) + ix) * (CI); const float *wp = (WT) + (ky * 3 + kx) * (CI) * (CO); \
                for (int ci = 0; ci < (CI); ci++) { const v128_t a = wasm_f32x4_splat(ip[ci]); const float *w = wp + ci * (CO); \
                    for (int q = 0; q < (CO) / 4; q++) acc[q] = wasm_f32x4_add(acc[q], wasm_f32x4_mul(a, wasm_v128_load(w + 4 * q))); } } } \
        float *op = out + (oy * (((IW) + 1) / 2) + ox) * (CO); for (int q = 0; q < (CO) / 4; q++) wasm_v128_store(op + 4 * q, wasm_v128_bitselect(acc[q], zero, wasm_f32x4_gt(acc[q], zero))); } }
