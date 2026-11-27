/* ---------------- generic part (agents/cheap/tools/net_tmpl_tail.c) ---------------- */
#if NET_NL == 1
#define LC_AL lc_a0
#define LC_CL LC_C0
#elif NET_NL == 2
#define LC_AL lc_a1
#define LC_CL LC_C1
#elif NET_NL == 3
#define LC_AL lc_a2
#define LC_CL LC_C2
#elif NET_NL == 4
#define LC_AL lc_a3
#define LC_CL LC_C3
#else
#define LC_AL lc_a4
#define LC_CL LC_C4
#endif
#define NET_FH (LC_PH >> NET_NL)
#define NET_FW (LC_PW >> NET_NL)
#define NET_FIN (NET_FH * NET_FW * LC_CL)
LC_CONVR(ns_conv0, 5, LC_C0, LC_PH, LC_PW, LC_W0, LC_B0)
#if NET_NL > 1
LC_CONVR(ns_conv1, LC_C0, LC_C1, LC_PH >> 1, LC_PW >> 1, LC_W1, LC_B1)
#endif
#if NET_NL > 2
LC_CONVR(ns_conv2, LC_C1, LC_C2, LC_PH >> 2, LC_PW >> 2, LC_W2, LC_B2)
#endif
#if NET_NL > 3
LC_CONVR(ns_conv3, LC_C2, LC_C3, LC_PH >> 3, LC_PW >> 3, LC_W3, LC_B3)
#endif
#if NET_NL > 4
LC_CONVR(ns_conv4, LC_C3, LC_C4, LC_PH >> 4, LC_PW >> 4, LC_W4, LC_B4)
#endif
static void ns_conv(int L, int a, int b, int x0, int x1) {
    switch (L) {
    case 0: ns_conv0(lc_in, lc_a0, a, b, x0, x1); break;
#if NET_NL > 1
    case 1: ns_conv1(lc_a0, lc_a1, a, b, x0, x1); break;
#endif
#if NET_NL > 2
    case 2: ns_conv2(lc_a1, lc_a2, a, b, x0, x1); break;
#endif
#if NET_NL > 3
    case 3: ns_conv3(lc_a2, lc_a3, a, b, x0, x1); break;
#endif
#if NET_NL > 4
    case 4: ns_conv4(lc_a3, lc_a4, a, b, x0, x1); break;
#endif
    }
}
/* head rows [r0, r1) of the first linear layer (input = flattened (h, w, c) features of the last conv, then the 32-d IMU embedding) */
static void ns_head_part(int r0, int r1, int first, int last) {
    if (first) {
        for (int j = 0; j < 32; j++) ns_emb[j] = LC_FB0[j];
        for (int i = 0; i < 19; i++) for (int j = 0; j < 32; j++) ns_emb[j] += lc_vec[i] * LC_FW0[i * 32 + j];
        for (int j = 0; j < 32; j++) ns_emb[j] = ns_emb[j] > 0 ? ns_emb[j] : 0;
        for (int j = 0; j < LC_HID; j++) ns_h[j] = LC_H1B[j];
    }
    for (int i = r0; i < r1; i++) { float a = i < NET_FIN ? LC_AL[i] : ns_emb[i - NET_FIN]; const float *w = LC_H1W + i * LC_HID; for (int j = 0; j < LC_HID; j++) ns_h[j] += a * w[j]; }
    if (last) {
        for (int j = 0; j < LC_HID; j++) ns_h[j] = ns_h[j] > 0 ? ns_h[j] : 0;
        for (int j = 0; j < 12; j++) lc_out[j] = LC_H2B[j];
        for (int i = 0; i < LC_HID; i++) { float a = ns_h[i]; const float *w = LC_H2W + i * 12; for (int j = 0; j < 12; j++) lc_out[j] += a * w[j]; }
    }
}
/* generic gray: RGB 320x240 -> mean of channels -> area resampling to LC_W x LC_H (float weights) -> uint8 rounded */
static void lc_gray_rows_g(const uint8_t *rgb, uint8_t *out, int y0, int y1) {
    const double r = 320.0 / LC_W;
    static float row[LC_W];
    for (int y = y0; y < y1; y++) {
        double sy0 = y * r, sy1 = (y + 1) * r;
        for (int x = 0; x < LC_W; x++) row[x] = 0;
        for (int sy = (int)sy0; sy < sy1 && sy < 240; sy++) {
            float wy = (float)((sy + 1 < sy1 ? sy + 1 : sy1) - (sy > sy0 ? sy : sy0));
            const uint8_t *p = rgb + 960 * sy;
            for (int x = 0; x < LC_W; x++) {
                double sx0 = x * r, sx1 = (x + 1) * r; float acc = 0;
                for (int sx = (int)sx0; sx < sx1 && sx < 320; sx++) {
                    float wx = (float)((sx + 1 < sx1 ? sx + 1 : sx1) - (sx > sx0 ? sx : sx0));
                    acc += wx * (float)(p[3 * sx] + p[3 * sx + 1] + p[3 * sx + 2]);
                }
                row[x] += wy * acc;
            }
        }
        float k = (float)(1.0 / (3.0 * r * r));
        for (int x = 0; x < LC_W; x++) { float v = row[x] * k + 0.5f; out[y * LC_W + x] = (uint8_t)(v < 0 ? 0 : v > 255 ? 255 : (int)v); }
    }
}
/* ---- micro-step schedule (built once from the shapes) */
#define NS_MAX 512
enum { T_G0, T_G5, T_PREP, T_VAR, T_POOL, T_CONV, T_HEAD };
static unsigned char ns_t[NS_MAX]; static short ns_l[NS_MAX], ns_a[NS_MAX], ns_b[NS_MAX], ns_x0[NS_MAX], ns_x1[NS_MAX]; static float ns_c[NS_MAX];
static int ns_n = 0;
static void ns_addx(int t, int l, int a, int b, int x0, int x1, double c) { if (ns_n < NS_MAX) { ns_t[ns_n] = t; ns_l[ns_n] = l; ns_a[ns_n] = a; ns_b[ns_n] = b; ns_x0[ns_n] = x0; ns_x1[ns_n] = x1; ns_c[ns_n] = (float)c; ns_n++; } }
static void ns_add(int t, int l, int a, int b, double c) { ns_addx(t, l, a, b, 0, 0, c); }
#ifndef NET_VB
#define NET_VB 55296   /* MACs per conv micro-step (reference conv1 row) */
#endif
#ifndef NET_HB
#define NET_HB 40000   /* MACs per head micro-step */
#endif
static void ns_build(void) {
    ns_n = 0;
    for (int f = 0; f < 2; f++) {
        if (LC_W == 128) { for (int k = 0; k < 16; k++) ns_add(f ? T_G5 : T_G0, 0, 3 * k, 3 * k + 3, 46e3); }
        else { double r = 320.0 / LC_W; int g = (int)(45e3 / (r * 320 * 14)); if (g < 1) g = 1;
               for (int y = 0; y < LC_H; y += g) ns_add(f ? T_G5 : T_G0, 0, y, y + g < LC_H ? y + g : LC_H, g * r * 320 * 14 + 3e3); }
    }
    { int g = 4 * 128 / LC_W; if (g < 1) g = 1; for (int y = 0; y < LC_H; y += g) ns_add(T_PREP, 0, y, y + g < LC_H ? y + g : LC_H, 70e3 * g * LC_W / 512.0 + 3e3); }
    for (int k = 0; k < 4; k++) ns_add(T_VAR, 0, k * (LC_H * LC_W / 4), (k + 1) * (LC_H * LC_W / 4), 60e3 * LC_W * LC_H / 12288.0 + 2e3);
    ns_add(T_POOL, 0, 0, LC_PH / 2, 120e3 * LC_W * LC_H / 12288.0 + 2e3); ns_add(T_POOL, 0, LC_PH / 2, LC_PH, 120e3 * LC_W * LC_H / 12288.0 + 2e3);
    static const int CO[5] = {LC_C0,
#if NET_NL > 1
        LC_C1,
#else
        0,
#endif
#if NET_NL > 2
        LC_C2,
#else
        0,
#endif
#if NET_NL > 3
        LC_C3,
#else
        0,
#endif
#if NET_NL > 4
        LC_C4
#else
        0
#endif
    };
    int ci = 5, ih = LC_PH, iw = LC_PW;
    for (int L = 0; L < NET_NL; L++) {
        int oh = (ih + 1) / 2, ow = (iw + 1) / 2; double mr = (double)ow * CO[L] * ci * 9;
        int g = (int)(NET_VB / mr);
        if (g >= 1) { for (int y = 0; y < oh; y += g) { int e = y + g < oh ? y + g : oh; ns_addx(T_CONV, L, y, e, 0, ow, mr * (e - y) * 2.8 + 5e3); } }
        else { /* a row exceeds the step: split it by output columns */
            int gx = (int)(NET_VB / (mr / ow)); if (gx < 1) gx = 1;
            for (int y = 0; y < oh; y++) for (int x = 0; x < ow; x += gx) { int e = x + gx < ow ? x + gx : ow; ns_addx(T_CONV, L, y, y + 1, x, e, mr / ow * (e - x) * 2.8 + 5e3); }
        }
        ci = CO[L]; ih = oh; iw = ow;
    }
    int nin = NET_FIN + 32, g = (int)(NET_HB / LC_HID); if (g < 1) g = 1;
    for (int r = 0; r < nin; r += g) { int e = r + g < nin ? r + g : nin; ns_add(T_HEAD, r == 0, r, e, (e - r) * LC_HID * 3.0 + (e == nin ? LC_HID * 12 * 3.0 : 0) + (r == 0 ? 19 * 32 * 3 : 0) + 5e3); }
}
#ifndef NET_K
#define NET_K 5
#endif
static int nt_frame, nt_pos;
static int ns_do(int k) {
    int a = ns_a[k], b = ns_b[k];
    switch (ns_t[k]) {
    case T_G0:
    case T_G5: {
        const uint8_t *src = ns_t[k] == T_G0 ? ns_rgb0 : ns_rgb5; uint8_t *dst = ns_t[k] == T_G0 ? lc_g0 : lc_g5;
        if (ns_t[k] == T_G5 && !ns_have5) return 0;
#if LC_W == 128
        for (int pr = a; pr < b; pr++) lc_gray_pair_i(src, dst, pr);
#else
        lc_gray_rows_g(src, dst, a, b);
#endif
        return 1; }
    case T_PREP: if (a == 0) ns_prep_init(); ns_prep_rows(a, b); return 1;
    case T_VAR: ns_var(a, b); return 1;
    case T_POOL: ns_pool(a, b); return 1;
    case T_CONV: ns_conv(ns_l[k], a, b, ns_x0[k], ns_x1[k]); return 1;
    case T_HEAD: ns_head_part(a, b, ns_l[k], b == NET_FIN + 32); return 1;
    }
    return 1;
}
/* ---- API (net.h) */
void net_cam(double fx_, double cx_, double cy_, const double *Rbc) { fx = fx_; cx = cx_; cy = cy_; memcpy(R_bc, Rbc, sizeof R_bc); if (!ns_n) ns_build(); }
void net_begin(const uint8_t *frame, const double *imu, int n) {
    memset(lc_Rc, 0, sizeof lc_Rc); lc_Rc[0] = lc_Rc[4] = lc_Rc[8] = 1; memset(lc_Vi, 0, sizeof lc_Vi);
    lc_have_row = 0; nt_frame = 0; nt_pos = 0; ns_have5 = 0;
    lc_rows(imu, n, lc_fm[0], lc_gm[0]);
    memcpy(lc_Rs, lc_Rc, sizeof lc_Rs); memcpy(lc_Vs, lc_Vi, sizeof lc_Vs);
    memcpy(ns_rgb0, frame, sizeof ns_rgb0);
}
int net_feed(const uint8_t *frame, const double *imu, int n) {
    if (nt_frame >= NET_K) return 0;
    nt_frame++;
    double fm[3], gm[3];
    lc_rows(imu, n, fm, gm);
    if (nt_frame == NET_K) {
        memcpy(lc_fm[1], fm, sizeof fm); memcpy(lc_gm[1], gm, sizeof gm);
        memcpy(lc_R5, lc_Rc, sizeof lc_R5); memcpy(lc_V5, lc_Vi, sizeof lc_V5);
        memcpy(ns_rgb5, frame, sizeof ns_rgb5); ns_have5 = 1;
        return 1;
    }
    return 0;
}
int net_nsteps(void) { return ns_n; }
double net_cost(int k) { return k < ns_n ? ns_c[k] : 0; }
double net_total(void) { double s = 0; for (int k = 0; k < ns_n; k++) s += ns_c[k]; return s; }
int net_pos(void) { return nt_pos; }
int net_done(void) { return nt_pos >= ns_n; }
int net_tick(void) { if (nt_pos >= ns_n) return 0; if (!ns_do(nt_pos)) return 0; nt_pos++; return 1; }
void net_out(double *mu, double *lv) { for (int i = 0; i < 3; i++) { mu[i] = lc_out[6 + i]; lv[i] = lc_out[9 + i]; } }
