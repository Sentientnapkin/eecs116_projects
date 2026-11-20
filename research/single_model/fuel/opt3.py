# ---- 9. forward-backward specific: the backward template (extracted from the CURRENT image at the NEW track position) is bit-for-bit the
# template the next frame's forward pass extracts at the same position, so it is cached per track and level and reused (exact).
if 'forward-backward check on alternate frames' in src:
    src = src.replace('#ifndef F_EXT2\n', '#ifndef F_FBT\n#define F_FBT 1   /* reuse the backward-pass template in the next forward pass (exact) */\n#endif\n#ifndef F_EXT2\n', 1)
    _a = src.index('static int klt(int prev')
    _end = src.index('\n}\n', _a) + 3
    _old = src[_a:_end]
    _new = r'''#if F_FBT
typedef struct { unsigned long stamp; double x, y, hxx, hxy, hyy; int valid; double T[KLT_N + 4], GX[KLT_N + 4], GY[KLT_N + 4]; } Tmpl;
static Tmpl tcache[MAX_TRACKS][LEVELS];
static unsigned long pyr_stamp[2], stamp_ctr;
static double kT[KLT_N + 4], kGX[KLT_N + 4], kGY[KLT_N + 4];
static void tmpl_build(const uint8_t *I0, int w, double px, double py, double *hxx_o, double *hxy_o, double *hyy_o) {
    static double patch[(2 * KLT_R + 3) * (2 * KLT_R + 3) + 4];
    double hxx = 0, hxy = 0, hyy = 0;
    const int pw = 2 * KLT_R + 3;
    extract(I0, w, px, py, KLT_R + 1, patch);
    int n = 0;
    for (int v = 1; v < pw - 1; v++)
        for (int u = 1; u < pw - 1; u++, n++) {
            const double *q = patch + v * pw + u;
            kT[n] = q[0];
            kGX[n] = 0.5 * (q[1] - q[-1]);
            kGY[n] = 0.5 * (q[pw] - q[-pw]);
            hxx += kGX[n] * kGX[n]; hxy += kGX[n] * kGY[n]; hyy += kGY[n] * kGY[n];
        }
    *hxx_o = hxx; *hxy_o = hxy; *hyy_o = hyy;
}
/* store = 0: forward track (template from `prev` at (x0, y0): copy a cached one (3 bulk copies) if present); store = 1: backward check, the template (from the
   current image at the new position) is kept for the next frame's forward pass of the same track slot */
static int klt_t(int prev, int cur, double x0, double y0, double gx, double gy, double *ox, double *oy, int slot, int store) {
    static double cur_patch[KLT_N + 4];
    double *T = kT, *GX = kGX, *GY = kGY;
    double dx = gx - x0, dy = gy - y0, err = 1e9;
    for (int L = LEVELS - 1; L >= 0; L--) {
        double s = 1.0 / (1 << L);
        int w = IMG_W >> L, h = IMG_H >> L;
        const uint8_t *I0 = pyr[prev][L], *I1 = pyr[cur][L];
        double px = x0 * s, py = y0 * s, ddx = dx * s, ddy = dy * s;
        if (px < KLT_R + 2 || py < KLT_R + 2 || px > w - KLT_R - 3 || py > h - KLT_R - 3) {
            if (L == 0) return 0;
            continue;
        }
        double hxx, hxy, hyy;
        Tmpl *tp = &tcache[slot][L];
        if (!store && tp->valid && tp->stamp == pyr_stamp[prev] && tp->x == x0 && tp->y == y0) {
            memcpy(kT, tp->T, sizeof kT); memcpy(kGX, tp->GX, sizeof kGX); memcpy(kGY, tp->GY, sizeof kGY);
            hxx = tp->hxx; hxy = tp->hxy; hyy = tp->hyy;
        } else {
            tmpl_build(I0, w, px, py, &hxx, &hxy, &hyy);
            if (store) {
                memcpy(tp->T, kT, sizeof kT); memcpy(tp->GX, kGX, sizeof kGX); memcpy(tp->GY, kGY, sizeof kGY);
                tp->hxx = hxx; tp->hxy = hxy; tp->hyy = hyy; tp->stamp = pyr_stamp[prev]; tp->x = x0; tp->y = y0; tp->valid = 1;
            }
        }
        double det = hxx * hyy - hxy * hxy;
        double mineig = 0.5 * (hxx + hyy) - sqrt(0.25 * (hxx - hyy) * (hxx - hyy) + hxy * hxy);
        if (mineig < KLT_MIN_EIG * KLT_N || det <= 0) { /* no texture at this level */
            if (L == 0) return 0;
            dx = ddx / s; dy = ddy / s;
            continue;
        }
        for (int it = 0; it < KLT_ITERS; it++) {
            double qx = px + ddx, qy = py + ddy;
            if (qx < KLT_R + 1 || qy < KLT_R + 1 || qx > w - KLT_R - 2 || qy > h - KLT_R - 2) {
                if (L == 0) return 0;
                break;
            }
            double bx = 0, by = 0, esum = 0;
            extract(I1, w, qx, qy, KLT_R, cur_patch);
            for (int n = 0; n < KLT_N; n++) {
                double e = cur_patch[n] - T[n];
                bx += GX[n] * e; by += GY[n] * e;
                esum += fabs(e);
            }
            err = esum / KLT_N;
            double ux = (hyy * bx - hxy * by) / det, uy = (hxx * by - hxy * bx) / det;
            ddx -= ux; ddy -= uy;
            double eps = L == 0 ? KLT_EPS : KLT_EPS_COARSE;
            if (ux * ux + uy * uy < eps * eps) break;
        }
        dx = ddx / s; dy = ddy / s;
    }
    if (err > KLT_MAX_ERR) return 0;
    *ox = x0 + dx; *oy = y0 + dy;
    return 1;
}
#endif
'''
    src = src[:_a] + _new + src[_a:]
    src = src.replace('int ok = klt(prev, cur, t->x, t->y, gx, gy, &nx, &ny) &&', 'int ok = KLT_F(prev, cur, t->x, t->y, gx, gy, &nx, &ny, i, 0) &&')
    src = src.replace('if (!klt(cur, prev, nx, ny, t->x, t->y, &bx, &by) ||', 'if (!KLT_F(cur, prev, nx, ny, t->x, t->y, &bx, &by, i, 1) ||')
    src = src.replace('static void track_all(', '#if F_FBT\n#define KLT_F(p, c, a, b, g, h, o, q, sl, st) klt_t(p, c, a, b, g, h, o, q, sl, st)\n#else\n#define KLT_F(p, c, a, b, g, h, o, q, sl, st) klt(p, c, a, b, g, h, o, q)\n#endif\nstatic void track_all(', 1)
    # stamps: every new pyramid gets a fresh stamp
    src = src.replace('    build_pyramid(frame, cur);\n', '    build_pyramid(frame, cur);\n#if F_FBT\n    pyr_stamp[cur] = ++stamp_ctr;\n#endif\n', 1)
    src = src.replace('        build_pyramid(frame, cur_pyr);\n', '        build_pyramid(frame, cur_pyr);\n#if F_FBT\n        pyr_stamp[cur_pyr] = ++stamp_ctr;\n#endif\n', 1)
