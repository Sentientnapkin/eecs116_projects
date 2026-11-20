"""Build fuel/v.c from gate_base.c (gate build G): bit-exact fuel rewrites, each behind an #if switch (default 1)."""
import os
src = open(os.environ.get('IN', 'gate_base.c')).read()
def rep(old, new):
    global src
    assert src.count(old) == 1, (old[:60], src.count(old))
    src = src.replace(old, new)

# ---- switches
sw = '''
#include <wasm_simd128.h>
#ifndef F_PYR
#define F_PYR 1   /* SIMD gray + 2x2 pyramid (exact) */
#endif
#ifndef F_DET
#define F_DET 1   /* detect: integer gradient products per cell + upper-bound prune (exact) */
#endif
#ifndef F_UPD
#define F_UPD 1   /* EKF update: row-vectorised HP, Kt solves, P update (exact) */
#endif
#ifndef F_GATE
#define F_GATE 1  /* per-feature gate H0P over observing-clone blocks, SIMD (exact) */
#endif
#ifndef F_QR
#define F_QR 1    /* QR compression + null space: row-major vector form, nzc columns only (exact) */
#endif
#ifndef F_EXT
#define F_EXT 1   /* KLT bilinear extract with f64x2 (exact) */
#endif
'''
i = src.index('#define M_PI') if '#define M_PI' in src else None
# insert after last #include
import re
idx = [m.end() for m in re.finditer(r'^#include .*$', src, re.M)][-1]
src = src[:idx] + '\n' + sw + src[idx:]

# ---- 1. pyramid
old = src[src.index('static void build_pyramid'):src.index('/* (2r+1)^2 bilinear samples')]
new = '''#if F_PYR && LEVELS == 2
static void build_pyramid(const uint8_t *rgb, int which) {
    uint8_t *g = pyr[which][0];
    const v128_t c77 = wasm_i16x8_splat(77), c150 = wasm_i16x8_splat(150), c29 = wasm_i16x8_splat(29), c128 = wasm_i16x8_splat(128);
    for (int i = 0; i < IMG_W * IMG_H; i += 16) {
        const uint8_t *p = rgb + 3 * i;
        v128_t a = wasm_v128_load(p), b = wasm_v128_load(p + 16), c = wasm_v128_load(p + 32);
        v128_t r = wasm_i8x16_shuffle(wasm_i8x16_shuffle(a, b, 0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 0, 0, 0, 0, 0), c,
                                      0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 17, 20, 23, 26, 29);
        v128_t gg = wasm_i8x16_shuffle(wasm_i8x16_shuffle(a, b, 1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 0, 0, 0, 0, 0), c,
                                       0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 21, 24, 27, 30);
        v128_t bb = wasm_i8x16_shuffle(wasm_i8x16_shuffle(a, b, 2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 0, 0, 0, 0, 0, 0), c,
                                       0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 19, 22, 25, 28, 31);
        v128_t lo = wasm_i16x8_add(wasm_i16x8_add(wasm_i16x8_mul(wasm_u16x8_extend_low_u8x16(r), c77), wasm_i16x8_mul(wasm_u16x8_extend_low_u8x16(gg), c150)),
                                   wasm_i16x8_add(wasm_i16x8_mul(wasm_u16x8_extend_low_u8x16(bb), c29), c128));
        v128_t hi = wasm_i16x8_add(wasm_i16x8_add(wasm_i16x8_mul(wasm_u16x8_extend_high_u8x16(r), c77), wasm_i16x8_mul(wasm_u16x8_extend_high_u8x16(gg), c150)),
                                   wasm_i16x8_add(wasm_i16x8_mul(wasm_u16x8_extend_high_u8x16(bb), c29), c128));
        wasm_v128_store(g + i, wasm_u8x16_narrow_i16x8(wasm_u16x8_shr(lo, 8), wasm_u16x8_shr(hi, 8)));
    }
    const int w = IMG_W >> 1, h = IMG_H >> 1, ws = IMG_W;
    const uint8_t *s = pyr[which][0];
    uint8_t *d = pyr[which][1];
    const v128_t two = wasm_i16x8_splat(2);
    for (int y = 0; y < h; y++) {
        const uint8_t *r0 = s + 2 * y * ws, *r1 = r0 + ws;
        for (int x = 0; x < w; x += 8) {
            v128_t sum = wasm_i16x8_add(wasm_u16x8_extadd_pairwise_u8x16(wasm_v128_load(r0 + 2 * x)), wasm_u16x8_extadd_pairwise_u8x16(wasm_v128_load(r1 + 2 * x)));
            sum = wasm_u16x8_shr(wasm_i16x8_add(sum, two), 2);
            wasm_v128_store64_lane(d + y * w + x, wasm_u8x16_narrow_i16x8(sum, sum), 0);
        }
    }
}
#else
''' + old + '''#endif

'''
src = src.replace(old, new)

# ---- 2. detect
old = src[src.index('static void detect(int which)'):src.index('/* track every live feature')]
new = old.replace('''        double best = DETECT_MIN_SCORE;
        int bx = -1, by = -1;
        for (int y = y0 + 1; y < y0 + CELL_H; y += 2) {
            if (y < BORDER || y >= IMG_H - BORDER) continue;
            for (int x = x0 + 1; x < x0 + CELL_W; x += 2) {
                if (x < BORDER || x >= IMG_W - BORDER) continue;
                double s = corner_score(I, x, y);
                if (s > best) { best = s; bx = x; by = y; }
            }
        }
''', '''        double best = DETECT_MIN_SCORE;
        int bx = -1, by = -1;
#if F_DET
        {
            int ys0 = -1, ys1 = -1, xs0 = -1, xs1 = -1;
            for (int y = y0 + 1; y < y0 + CELL_H; y += 2) if (y >= BORDER && y < IMG_H - BORDER) { if (ys0 < 0) ys0 = y; ys1 = y; }
            for (int x = x0 + 1; x < x0 + CELL_W; x += 2) if (x >= BORDER && x < IMG_W - BORDER) { if (xs0 < 0) xs0 = x; xs1 = x; }
            if (ys0 >= 0 && xs0 >= 0) {
                static int ptr[(CELL_H + 3) * (CELL_W + 3) + 8], pxx[(CELL_H + 3) * (CELL_W + 3) + 8], pyy[(CELL_H + 3) * (CELL_W + 3) + 8], pxy[(CELL_H + 3) * (CELL_W + 3) + 8];
                const int PW = CELL_W + 3, ya = ys0 - 1, xa = xs0 - 1;
                for (int yy = ya; yy <= ys1 + 1; yy++) {
                    const uint8_t *p = I + yy * IMG_W;
                    int *o3 = ptr + (yy - ya) * PW - xa, *o0 = pxx + (yy - ya) * PW - xa, *o1 = pyy + (yy - ya) * PW - xa, *o2 = pxy + (yy - ya) * PW - xa;
                    for (int xx = xa; xx <= xs1 + 1; xx += 8) { /* 8 pixels per step; the overrun is overwritten by the next row */
                        v128_t gxv = wasm_i16x8_sub(wasm_u16x8_load8x8(p + xx + 1), wasm_u16x8_load8x8(p + xx - 1));
                        v128_t gyv = wasm_i16x8_sub(wasm_u16x8_load8x8(p + xx + IMG_W), wasm_u16x8_load8x8(p + xx - IMG_W));
                        v128_t xl = wasm_i32x4_extmul_low_i16x8(gxv, gxv), xh = wasm_i32x4_extmul_high_i16x8(gxv, gxv), yl = wasm_i32x4_extmul_low_i16x8(gyv, gyv), yh = wasm_i32x4_extmul_high_i16x8(gyv, gyv);
                        wasm_v128_store(o0 + xx, xl); wasm_v128_store(o0 + xx + 4, xh); wasm_v128_store(o3 + xx, wasm_i32x4_add(xl, yl)); wasm_v128_store(o3 + xx + 4, wasm_i32x4_add(xh, yh));
                        wasm_v128_store(o1 + xx, yl); wasm_v128_store(o1 + xx + 4, yh);
                        wasm_v128_store(o2 + xx, wasm_i32x4_extmul_low_i16x8(gxv, gyv)); wasm_v128_store(o2 + xx + 4, wasm_i32x4_extmul_high_i16x8(gxv, gyv));
                    }
                }
                for (int y = ys0; y <= ys1; y += 2) {
                    for (int x = xs0; x <= xs1; x += 2) {
                        const int o = (y - 1 - ya) * PW + (x - 1 - xa);
                        int itr = 0;
                        for (int v = 0; v < 3; v++) { const int *a3 = ptr + o + v * PW; itr += a3[0] + a3[1] + a3[2]; }
                        if (0.5 * (double)itr <= best) continue; /* score <= 0.5 (sxx + syy): cannot beat best */
                        int ixx = 0, iyy = 0, ixy = 0;
                        for (int v = 0; v < 3; v++) {
                            const int *a0 = pxx + o + v * PW, *a1 = pyy + o + v * PW, *a2 = pxy + o + v * PW;
                            ixx += a0[0] + a0[1] + a0[2]; iyy += a1[0] + a1[1] + a1[2]; ixy += a2[0] + a2[1] + a2[2];
                        }
                        double sxx = ixx, syy = iyy, sxy = ixy;
                        double half = 0.5 * (sxx + syy);
                        if (half <= best) continue; /* score <= half (sqrt >= 0): cannot beat best */
                        double s = half - sqrt(0.25 * (sxx - syy) * (sxx - syy) + sxy * sxy);
                        if (s > best) { best = s; bx = x; by = y; }
                    }
                }
            }
        }
#else
        for (int y = y0 + 1; y < y0 + CELL_H; y += 2) {
            if (y < BORDER || y >= IMG_H - BORDER) continue;
            for (int x = x0 + 1; x < x0 + CELL_W; x += 2) {
                if (x < BORDER || x >= IMG_W - BORDER) continue;
                double s = corner_score(I, x, y);
                if (s > best) { best = s; bx = x; by = y; }
            }
        }
#endif
''')
assert new != old
src = src.replace(old, new)

# ---- 3. update()
a = src.index('    for (int a = 0; a < k; a++) /* HP = H P */')
b = src.index('    for (int a = 0; a < k; a++) /* S = H P H^T + noise I */')
src = src[:a] + '''#if F_UPD
    { /* HP = H P: two rows of H at a time, six columns (three f64x2) per chunk, accumulators in registers (same per-element order) */
        const double *prow[MAXD];
        for (int q = 0; q < nnz; q++) prow[q] = Pm + nz[q] * MAXD;
        for (int a = 0; a < k; a += 2) {
            const double *h0 = H + a * MAXD, *h1 = H + (a + 1 < k ? a + 1 : a) * MAXD;
            double *o0 = HP + a * MAXD, *o1 = HP + (a + 1 < k ? a + 1 : a) * MAXD;
            for (int j = 0; j < D; j += 6) {
                v128_t a00 = wasm_f64x2_splat(0), a01 = a00, a02 = a00, a10 = a00, a11 = a00, a12 = a00;
                for (int q = 0; q < nnz; q++) {
                    const v128_t c0 = wasm_f64x2_splat(h0[nz[q]]), c1 = wasm_f64x2_splat(h1[nz[q]]);
                    const double *pr = prow[q] + j;
                    const v128_t p0 = wasm_v128_load(pr), p1 = wasm_v128_load(pr + 2), p2 = wasm_v128_load(pr + 4);
                    a00 = wasm_f64x2_add(a00, wasm_f64x2_mul(c0, p0)); a01 = wasm_f64x2_add(a01, wasm_f64x2_mul(c0, p1)); a02 = wasm_f64x2_add(a02, wasm_f64x2_mul(c0, p2));
                    a10 = wasm_f64x2_add(a10, wasm_f64x2_mul(c1, p0)); a11 = wasm_f64x2_add(a11, wasm_f64x2_mul(c1, p1)); a12 = wasm_f64x2_add(a12, wasm_f64x2_mul(c1, p2));
                }
                wasm_v128_store(o0 + j, a00); wasm_v128_store(o0 + j + 2, a01); wasm_v128_store(o0 + j + 4, a02);
                wasm_v128_store(o1 + j, a10); wasm_v128_store(o1 + j + 2, a11); wasm_v128_store(o1 + j + 4, a12);
            }
        }
    }
#else
''' + src[a:b] + '#endif\n' + src[b:]

old = src[src.index('    double col[MAXK];\n    for (int j = 0; j < D; j++) { /* Kt'):src.index('    inject(dx);\n    return 1;')]
new = '''#if F_UPD
    { /* Kt = S^-1 HP by forward then backward substitution on rows, six columns per chunk in registers (per-column arithmetic unchanged) */
        for (int i = 0; i < k; i++) {
            const double d = Sm[i * k + i];
            const v128_t dd = wasm_f64x2_splat(d);
            for (int j = 0; j < D; j += 6) {
                v128_t s0 = wasm_v128_load(HP + i * MAXD + j), s1 = wasm_v128_load(HP + i * MAXD + j + 2), s2 = wasm_v128_load(HP + i * MAXD + j + 4);
                for (int kk = 0; kk < i; kk++) {
                    const v128_t c = wasm_f64x2_splat(Sm[i * k + kk]);
                    const double *bk = Kt + kk * MAXD + j;
                    s0 = wasm_f64x2_sub(s0, wasm_f64x2_mul(c, wasm_v128_load(bk))); s1 = wasm_f64x2_sub(s1, wasm_f64x2_mul(c, wasm_v128_load(bk + 2)));
                    s2 = wasm_f64x2_sub(s2, wasm_f64x2_mul(c, wasm_v128_load(bk + 4)));
                }
                wasm_v128_store(Kt + i * MAXD + j, wasm_f64x2_div(s0, dd)); wasm_v128_store(Kt + i * MAXD + j + 2, wasm_f64x2_div(s1, dd));
                wasm_v128_store(Kt + i * MAXD + j + 4, wasm_f64x2_div(s2, dd));
            }
        }
        for (int i = k - 1; i >= 0; i--) {
            const double d = Sm[i * k + i];
            const v128_t dd = wasm_f64x2_splat(d);
            for (int j = 0; j < D; j += 6) {
                v128_t s0 = wasm_v128_load(Kt + i * MAXD + j), s1 = wasm_v128_load(Kt + i * MAXD + j + 2), s2 = wasm_v128_load(Kt + i * MAXD + j + 4);
                for (int kk = i + 1; kk < k; kk++) {
                    const v128_t c = wasm_f64x2_splat(Sm[kk * k + i]);
                    const double *bk = Kt + kk * MAXD + j;
                    s0 = wasm_f64x2_sub(s0, wasm_f64x2_mul(c, wasm_v128_load(bk))); s1 = wasm_f64x2_sub(s1, wasm_f64x2_mul(c, wasm_v128_load(bk + 2)));
                    s2 = wasm_f64x2_sub(s2, wasm_f64x2_mul(c, wasm_v128_load(bk + 4)));
                }
                wasm_v128_store(Kt + i * MAXD + j, wasm_f64x2_div(s0, dd)); wasm_v128_store(Kt + i * MAXD + j + 2, wasm_f64x2_div(s1, dd));
                wasm_v128_store(Kt + i * MAXD + j + 4, wasm_f64x2_div(s2, dd));
            }
        }
    }
    double dx[MAXD];
    for (int j = 0; j < D; j += 6) {
        v128_t s0 = wasm_f64x2_splat(0), s1 = s0, s2 = s0;
        for (int a = 0; a < k; a++) {
            const v128_t c = wasm_f64x2_splat(r[a]);
            const double *kt = Kt + a * MAXD + j;
            s0 = wasm_f64x2_add(s0, wasm_f64x2_mul(wasm_v128_load(kt), c)); s1 = wasm_f64x2_add(s1, wasm_f64x2_mul(wasm_v128_load(kt + 2), c));
            s2 = wasm_f64x2_add(s2, wasm_f64x2_mul(wasm_v128_load(kt + 4), c));
        }
        wasm_v128_store(dx + j, s0); wasm_v128_store(dx + j + 2, s1); wasm_v128_store(dx + j + 4, s2);
    }
    {
        double srow[MAXD + 6];
        for (int i = 0; i < D; i++) {
            const int j0 = i - i % 6;
            for (int j = j0; j < D; j += 6) {
                v128_t s0 = wasm_f64x2_splat(0), s1 = s0, s2 = s0;
                for (int a = 0; a < k; a++) {
                    const v128_t c = wasm_f64x2_splat(HP[a * MAXD + i]);
                    const double *kt = Kt + a * MAXD + j;
                    s0 = wasm_f64x2_add(s0, wasm_f64x2_mul(c, wasm_v128_load(kt))); s1 = wasm_f64x2_add(s1, wasm_f64x2_mul(c, wasm_v128_load(kt + 2)));
                    s2 = wasm_f64x2_add(s2, wasm_f64x2_mul(c, wasm_v128_load(kt + 4)));
                }
                wasm_v128_store(srow + j, s0); wasm_v128_store(srow + j + 2, s1); wasm_v128_store(srow + j + 4, s2);
            }
            double *pi = Pm + i * MAXD;
            for (int j = i; j < D; j++) { double v = pi[j] - srow[j]; pi[j] = v; Pm[j * MAXD + i] = v; }
        }
    }
#else
''' + old + '#endif\n'
src = src.replace(old, new)

# S block in update()
a = src.index('    for (int a = 0; a < k; a++) /* S = H P H^T + noise I */')
b = src.index('    if (!cholesky(Sm, k)) return 0;\n    double y[MAXK];')
old = src[a:b]
new = '''#if F_UPD
    {
        static double HT[MAXD * (MAXK + 2)];
        const int ld = k + (k & 1);
        for (int q = 0; q < nnz; q++) {
            for (int b2 = 0; b2 < k; b2++) HT[q * ld + b2] = H[b2 * MAXD + nz[q]];
            if (k & 1) HT[q * ld + k] = 0;
        }
        for (int a = 0; a < k; a++) {
            double hpc[MAXD];
            for (int q = 0; q < nnz; q++) hpc[q] = HP[a * MAXD + nz[q]];
            const int nv = (a + 2) / 2;
            double tmp[MAXK + 4];
            int bv = 0;
            for (; bv + 2 <= nv; bv += 2) {
                v128_t s0 = wasm_f64x2_splat(0), s1 = s0;
                for (int q = 0; q < nnz; q++) {
                    const v128_t c = wasm_f64x2_splat(hpc[q]);
                    const double *ht = HT + q * ld + 2 * bv;
                    s0 = wasm_f64x2_add(s0, wasm_f64x2_mul(c, wasm_v128_load(ht))); s1 = wasm_f64x2_add(s1, wasm_f64x2_mul(c, wasm_v128_load(ht + 2)));
                }
                wasm_v128_store(tmp + 2 * bv, s0); wasm_v128_store(tmp + 2 * bv + 2, s1);
            }
            if (bv < nv) {
                v128_t s0 = wasm_f64x2_splat(0);
                for (int q = 0; q < nnz; q++) s0 = wasm_f64x2_add(s0, wasm_f64x2_mul(wasm_f64x2_splat(hpc[q]), wasm_v128_load(HT + q * ld + 2 * bv)));
                wasm_v128_store(tmp + 2 * bv, s0);
            }
            for (int b2 = 0; b2 <= a; b2++) Sm[a * k + b2] = Sm[b2 * k + a] = tmp[b2] + (a == b2 ? noise : 0);
        }
    }
#else
''' + old + '#endif\n'
src = src.replace(old, new)

# ---- 4. extract (f64x2)
old = src[src.index('static void extract'):src.index('/* pyramidal inverse-compositional')]
new = '''#if F_EXT
static void extract(const uint8_t *I, int w, double x, double y, int r, double *out) { /* out needs 3 doubles of slack */
    int x0 = (int)x, y0 = (int)y, n = 2 * r + 1;
    double ax = x - x0, ay = y - y0;
    double w00 = (1 - ax) * (1 - ay), w01 = ax * (1 - ay), w10 = (1 - ax) * ay, w11 = ax * ay;
    const v128_t W00 = wasm_f64x2_splat(w00), W01 = wasm_f64x2_splat(w01), W10 = wasm_f64x2_splat(w10), W11 = wasm_f64x2_splat(w11);
    for (int v = 0; v < n; v++) {
        const uint8_t *p = I + (y0 - r + v) * w + x0 - r;
        double *o = out + v * n;
        for (int u = 0; u < n; u += 4) {
            v128_t l0 = wasm_u32x4_extend_low_u16x8(wasm_u16x8_load8x8(p + u));
            v128_t l1 = wasm_u32x4_extend_low_u16x8(wasm_u16x8_load8x8(p + u + 1));
            v128_t l2 = wasm_u32x4_extend_low_u16x8(wasm_u16x8_load8x8(p + u + w));
            v128_t l3 = wasm_u32x4_extend_low_u16x8(wasm_u16x8_load8x8(p + u + w + 1));
            v128_t a = wasm_f64x2_add(wasm_f64x2_add(wasm_f64x2_add(wasm_f64x2_mul(W00, wasm_f64x2_convert_low_u32x4(l0)), wasm_f64x2_mul(W01, wasm_f64x2_convert_low_u32x4(l1))),
                                                     wasm_f64x2_mul(W10, wasm_f64x2_convert_low_u32x4(l2))), wasm_f64x2_mul(W11, wasm_f64x2_convert_low_u32x4(l3)));
            l0 = wasm_i32x4_shuffle(l0, l0, 2, 3, 0, 1); l1 = wasm_i32x4_shuffle(l1, l1, 2, 3, 0, 1);
            l2 = wasm_i32x4_shuffle(l2, l2, 2, 3, 0, 1); l3 = wasm_i32x4_shuffle(l3, l3, 2, 3, 0, 1);
            v128_t b = wasm_f64x2_add(wasm_f64x2_add(wasm_f64x2_add(wasm_f64x2_mul(W00, wasm_f64x2_convert_low_u32x4(l0)), wasm_f64x2_mul(W01, wasm_f64x2_convert_low_u32x4(l1))),
                                                     wasm_f64x2_mul(W10, wasm_f64x2_convert_low_u32x4(l2))), wasm_f64x2_mul(W11, wasm_f64x2_convert_low_u32x4(l3)));
            wasm_v128_store(o + u, a); wasm_v128_store(o + u + 2, b);
        }
    }
}
#else
''' + old + '#endif\n\n'
src = src.replace(old, new)
src = src.replace('patch[(2 * KLT_R + 3) * (2 * KLT_R + 3)], cur_patch[KLT_N];', 'patch[(2 * KLT_R + 3) * (2 * KLT_R + 3) + 4], cur_patch[KLT_N + 4];')

# ---- 5. feature_rows: nzc earlier, vector null space, vector gate
a = src.index('    double sigma2 = (PIXEL_STD / fx) * (PIXEL_STD / fx);\n    int nzc[6 * MAX_OBS]')
b = src.index('    for (int a = 0; a < k0; a++)\n        for (int jj = 0; jj < nnz; jj++) {')
nzc_block = src[a:b]
gate_old_end = src.index('    if (!cholesky(Sm, k0)) return 0;')
gate_old = src[b:gate_old_end]
src = src[:a] + '#if !F_GATE\n' + nzc_block + '#endif\n' + gate_old_replaced if False else src
# move nzc computation before the null-space loop (nzc depends only on ci/o)
nz_only = nzc_block.replace('    double sigma2 = (PIXEL_STD / fx) * (PIXEL_STD / fx);\n', '')
src = src.replace(nzc_block, '    double sigma2 = (PIXEL_STD / fx) * (PIXEL_STD / fx);\n')
src = src.replace('    MARK(10,0);\n', '    MARK(10,0);\n') if False else src
anchor = '    for (int c = 0; c < 3; c++) { /* left null space of Hf */'
assert src.count(anchor) == 1
src = src.replace(anchor, nz_only + anchor)
# gate
b = src.index('    for (int a = 0; a < k0; a++)\n        for (int jj = 0; jj < nnz; jj++) {')
gate_old_end = src.index('    if (!cholesky(Sm, k0)) return 0;')
gate_old = src[b:gate_old_end]
gate_new = '''#if F_GATE
    {
        const int nb = nnz / 6;
        static double H0T[6 * MAX_OBS * (2 * MAX_OBS + 2)];
        const int ldt = k0 + (k0 & 1);
        for (int q = 0; q < nnz; q++) {
            for (int a = 0; a < k0; a++) H0T[q * ldt + a] = H0[a * MAXD + nzc[q]];
            if (k0 & 1) H0T[q * ldt + k0] = 0;
        }
        for (int a = 0; a < k0; a++) {
            const double *h0 = H0 + a * MAXD;
            for (int blk = 0; blk < nb; blk++) {
                const int base = nzc[6 * blk];
                v128_t s0 = wasm_f64x2_splat(0), s1 = s0, s2 = s0;
                for (int q = 0; q < nnz; q++) {
                    const v128_t c = wasm_f64x2_splat(h0[nzc[q]]);
                    const double *pr = Pm + nzc[q] * MAXD + base;
                    s0 = wasm_f64x2_add(s0, wasm_f64x2_mul(c, wasm_v128_load(pr)));
                    s1 = wasm_f64x2_add(s1, wasm_f64x2_mul(c, wasm_v128_load(pr + 2)));
                    s2 = wasm_f64x2_add(s2, wasm_f64x2_mul(c, wasm_v128_load(pr + 4)));
                }
                double *hp = H0P + a * MAXD + base;
                wasm_v128_store(hp, s0); wasm_v128_store(hp + 2, s1); wasm_v128_store(hp + 4, s2);
            }
        }
        for (int a = 0; a < k0; a++) {
            v128_t acc[MAX_OBS + 1];
            const int nv = (a + 2) / 2; /* lanes 0..a (b <= a) */
            for (int bv = 0; bv < nv; bv++) acc[bv] = wasm_f64x2_splat(0);
            for (int q = 0; q < nnz; q++) {
                const v128_t c = wasm_f64x2_splat(H0P[a * MAXD + nzc[q]]);
                const double *ht = H0T + q * ldt;
                for (int bv = 0; bv < nv; bv++) acc[bv] = wasm_f64x2_add(acc[bv], wasm_f64x2_mul(c, wasm_v128_load(ht + 2 * bv)));
            }
            double tmp[2 * MAX_OBS + 2];
            for (int bv = 0; bv < nv; bv++) wasm_v128_store(tmp + 2 * bv, acc[bv]);
            for (int b2 = 0; b2 <= a; b2++) Sm[a * k0 + b2] = Sm[b2 * k0 + a] = tmp[b2] + (a == b2 ? sigma2 : 0);
        }
    }
#else
''' + gate_old + '#endif\n'
src = src.replace(gate_old, gate_new)

# ---- 6. null space over nzc columns, vectorised per 6-column block; QR compression in row-major vector form
a = src.index('        for (int j = 0; j < D; j++) {\n            double s = 0;\n            for (int i = c; i < m; i++) s += v[i] * Hx[i * MAXD + j];')
b = src.index('        double s = 0;\n        for (int i = c; i < m; i++) s += v[i] * rr[i];')
old = src[a:b]
new = '''#if F_QR
        {
            const v128_t f = wasm_f64x2_splat(2 / vn);
            for (int blk = 0; blk < nnz / 6; blk++) {
                const int base = nzc[6 * blk];
                v128_t s0 = wasm_f64x2_splat(0), s1 = s0, s2 = s0;
                for (int i = c; i < m; i++) {
                    const v128_t vi = wasm_f64x2_splat(v[i]);
                    const double *row = Hx + i * MAXD + base;
                    s0 = wasm_f64x2_add(s0, wasm_f64x2_mul(vi, wasm_v128_load(row)));
                    s1 = wasm_f64x2_add(s1, wasm_f64x2_mul(vi, wasm_v128_load(row + 2)));
                    s2 = wasm_f64x2_add(s2, wasm_f64x2_mul(vi, wasm_v128_load(row + 4)));
                }
                s0 = wasm_f64x2_mul(s0, f); s1 = wasm_f64x2_mul(s1, f); s2 = wasm_f64x2_mul(s2, f);
                for (int i = c; i < m; i++) {
                    const v128_t vi = wasm_f64x2_splat(v[i]);
                    double *row = Hx + i * MAXD + base;
                    wasm_v128_store(row, wasm_f64x2_sub(wasm_v128_load(row), wasm_f64x2_mul(s0, vi)));
                    wasm_v128_store(row + 2, wasm_f64x2_sub(wasm_v128_load(row + 2), wasm_f64x2_mul(s1, vi)));
                    wasm_v128_store(row + 4, wasm_f64x2_sub(wasm_v128_load(row + 4), wasm_f64x2_mul(s2, vi)));
                }
            }
        }
#else
''' + old + '#endif\n'
src = src.replace(old, new)

a = src.index('            for (int j = c; j < D; j++) {\n                double s = 0;\n                for (int i = pr; i < nrows; i++) s += v[i] * Hbig[i * MAXD + j];')
b = src.index('            double s = 0;\n            for (int i = pr; i < nrows; i++) s += v[i] * rbig[i];')
old = src[a:b]
new = '''#if F_QR
            {
                static double sj[MAXD];
                for (int j = c; j < D; j++) sj[j] = 0;
                for (int i = pr; i < nrows; i++) {
                    const double vi = v[i];
                    const double *row = Hbig + i * MAXD;
                    for (int j = c; j < D; j++) sj[j] += vi * row[j];
                }
                const double f = 2 / vn;
                for (int j = c; j < D; j++) sj[j] *= f;
                for (int i = pr; i < nrows; i++) {
                    const double vi = v[i];
                    double *row = Hbig + i * MAXD;
                    for (int j = c; j < D; j++) row[j] -= sj[j] * vi;
                }
            }
#else
''' + old + '#endif\n'
src = src.replace(old, new)
exec(open('opt2.py').read())
import os
if not os.environ.get('NOARMS'): exec(open('arms.py').read())
open(os.environ.get('OUT', 'v.c'), 'w').write(src)
