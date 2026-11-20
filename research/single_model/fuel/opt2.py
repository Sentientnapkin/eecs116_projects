# ---- 8. second-round exact rewrites (exec'd by mkv.py after the first round; uses `src`)
src = src.replace('#ifndef F_EXT\n', '#ifndef F_EXT2\n#define F_EXT2 1  /* KLT patch: convert each source row to f64 once, reuse for the 4 taps (exact) */\n#endif\n#ifndef F_GATE2\n#define F_GATE2 1 /* gate H0P: three rows of H0 per pass over P (exact) */\n#endif\n#ifndef F_UPD2\n#define F_UPD2 1  /* P update: four rows of P per pass over Kt (exact) */\n#endif\n#ifndef F_EXT\n', 1)

# (a) extract with row conversion
_a = src.index('#if F_EXT\nstatic void extract')
_b = src.index('#else', _a)
_new = r'''#if F_EXT && F_EXT2
static void extract(const uint8_t *I, int w, double x, double y, int r, double *out) { /* out needs 3 doubles of slack */
    int x0 = (int)x, y0 = (int)y, n = 2 * r + 1;
    double ax = x - x0, ay = y - y0;
    double w00 = (1 - ax) * (1 - ay), w01 = ax * (1 - ay), w10 = (1 - ax) * ay, w11 = ax * ay;
    const v128_t W00 = wasm_f64x2_splat(w00), W01 = wasm_f64x2_splat(w01), W10 = wasm_f64x2_splat(w10), W11 = wasm_f64x2_splat(w11);
    enum { SA = 16 };
    static double A[(2 * (KLT_R + 1) + 2) * SA];
    for (int v = 0; v <= n; v++) { /* n + 1 source rows, converted once */
        const uint8_t *p = I + (y0 - r + v) * w + x0 - r;
        double *o = A + v * SA;
        for (int u = 0; u <= n; u += 4) {
            v128_t l = wasm_u32x4_extend_low_u16x8(wasm_u16x8_load8x8(p + u));
            wasm_v128_store(o + u, wasm_f64x2_convert_low_u32x4(l));
            wasm_v128_store(o + u + 2, wasm_f64x2_convert_low_u32x4(wasm_i32x4_shuffle(l, l, 2, 3, 0, 1)));
        }
    }
    for (int v = 0; v < n; v++) {
        const double *a0 = A + v * SA, *a1 = a0 + SA;
        double *o = out + v * n;
        for (int u = 0; u < n; u += 2)
            wasm_v128_store(o + u, wasm_f64x2_add(wasm_f64x2_add(wasm_f64x2_add(wasm_f64x2_mul(W00, wasm_v128_load(a0 + u)), wasm_f64x2_mul(W01, wasm_v128_load(a0 + u + 1))),
                                                                  wasm_f64x2_mul(W10, wasm_v128_load(a1 + u))), wasm_f64x2_mul(W11, wasm_v128_load(a1 + u + 1))));
    }
}
'''
src = src[:_a] + _new + src[_b:].replace('#if F_EXT\nstatic', '#if F_EXT\nstatic', 1)

# (b) gate: H0P three rows at a time
_a = src.index('        for (int a = 0; a < k0; a++) {\n            const double *h0 = H0 + a * MAXD;')
_b = src.index('        for (int a = 0; a < k0; a++) {\n            v128_t acc[MAX_OBS + 1];')
_old = src[_a:_b]
_new = r'''#if F_GATE2
        for (int a = 0; a < k0; a += 3) {
            const int a1 = a + 1 < k0 ? a + 1 : a, a2 = a + 2 < k0 ? a + 2 : a1; /* padding rows repeat the last row (same values written twice) */
            const double *h0 = H0 + a * MAXD, *h1 = H0 + a1 * MAXD, *h2 = H0 + a2 * MAXD;
            for (int blk = 0; blk < nb; blk++) {
                const int base = nzc[6 * blk];
                v128_t s00 = wasm_f64x2_splat(0), s01 = s00, s02 = s00, s10 = s00, s11 = s00, s12 = s00, s20 = s00, s21 = s00, s22 = s00;
                for (int q = 0; q < nnz; q++) {
                    const int col = nzc[q];
                    const double *pr = Pm + col * MAXD + base;
                    const v128_t p0 = wasm_v128_load(pr), p1 = wasm_v128_load(pr + 2), p2 = wasm_v128_load(pr + 4);
                    const v128_t c0 = wasm_f64x2_splat(h0[col]), c1 = wasm_f64x2_splat(h1[col]), c2 = wasm_f64x2_splat(h2[col]);
                    s00 = wasm_f64x2_add(s00, wasm_f64x2_mul(c0, p0)); s01 = wasm_f64x2_add(s01, wasm_f64x2_mul(c0, p1)); s02 = wasm_f64x2_add(s02, wasm_f64x2_mul(c0, p2));
                    s10 = wasm_f64x2_add(s10, wasm_f64x2_mul(c1, p0)); s11 = wasm_f64x2_add(s11, wasm_f64x2_mul(c1, p1)); s12 = wasm_f64x2_add(s12, wasm_f64x2_mul(c1, p2));
                    s20 = wasm_f64x2_add(s20, wasm_f64x2_mul(c2, p0)); s21 = wasm_f64x2_add(s21, wasm_f64x2_mul(c2, p1)); s22 = wasm_f64x2_add(s22, wasm_f64x2_mul(c2, p2));
                }
                double *o0 = H0P + a * MAXD + base, *o1 = H0P + a1 * MAXD + base, *o2 = H0P + a2 * MAXD + base;
                wasm_v128_store(o0, s00); wasm_v128_store(o0 + 2, s01); wasm_v128_store(o0 + 4, s02);
                wasm_v128_store(o1, s10); wasm_v128_store(o1 + 2, s11); wasm_v128_store(o1 + 4, s12);
                wasm_v128_store(o2, s20); wasm_v128_store(o2 + 2, s21); wasm_v128_store(o2 + 4, s22);
            }
        }
#else
''' + _old + '#endif\n'
src = src[:_a] + _new + src[_b:]

# (c) P update: four rows of P per pass over Kt
_a = src.index('        double srow[MAXD + 6];\n        for (int i = 0; i < D; i++) {')
_b = src.index('    }\n#else', _a)
_old = src[_a:_b]
_new = r'''#if F_UPD2
        static double srow[4][MAXD + 6];
        for (int i0 = 0; i0 < D; i0 += 4) {
            const int r1 = i0 + 1 < D ? i0 + 1 : D - 1, r2 = i0 + 2 < D ? i0 + 2 : D - 1, r3 = i0 + 3 < D ? i0 + 3 : D - 1;
            const int j0 = i0 - i0 % 6;
            for (int j = j0; j < D; j += 6) {
                v128_t s00 = wasm_f64x2_splat(0), s01 = s00, s02 = s00, s10 = s00, s11 = s00, s12 = s00, s20 = s00, s21 = s00, s22 = s00, s30 = s00, s31 = s00, s32 = s00;
                for (int a = 0; a < k; a++) {
                    const double *kt = Kt + a * MAXD + j, *hpa = HP + a * MAXD;
                    const v128_t k0v = wasm_v128_load(kt), k1v = wasm_v128_load(kt + 2), k2v = wasm_v128_load(kt + 4);
                    const v128_t c0 = wasm_f64x2_splat(hpa[i0]), c1 = wasm_f64x2_splat(hpa[r1]), c2 = wasm_f64x2_splat(hpa[r2]), c3 = wasm_f64x2_splat(hpa[r3]);
                    s00 = wasm_f64x2_add(s00, wasm_f64x2_mul(c0, k0v)); s01 = wasm_f64x2_add(s01, wasm_f64x2_mul(c0, k1v)); s02 = wasm_f64x2_add(s02, wasm_f64x2_mul(c0, k2v));
                    s10 = wasm_f64x2_add(s10, wasm_f64x2_mul(c1, k0v)); s11 = wasm_f64x2_add(s11, wasm_f64x2_mul(c1, k1v)); s12 = wasm_f64x2_add(s12, wasm_f64x2_mul(c1, k2v));
                    s20 = wasm_f64x2_add(s20, wasm_f64x2_mul(c2, k0v)); s21 = wasm_f64x2_add(s21, wasm_f64x2_mul(c2, k1v)); s22 = wasm_f64x2_add(s22, wasm_f64x2_mul(c2, k2v));
                    s30 = wasm_f64x2_add(s30, wasm_f64x2_mul(c3, k0v)); s31 = wasm_f64x2_add(s31, wasm_f64x2_mul(c3, k1v)); s32 = wasm_f64x2_add(s32, wasm_f64x2_mul(c3, k2v));
                }
                wasm_v128_store(srow[0] + j, s00); wasm_v128_store(srow[0] + j + 2, s01); wasm_v128_store(srow[0] + j + 4, s02);
                wasm_v128_store(srow[1] + j, s10); wasm_v128_store(srow[1] + j + 2, s11); wasm_v128_store(srow[1] + j + 4, s12);
                wasm_v128_store(srow[2] + j, s20); wasm_v128_store(srow[2] + j + 2, s21); wasm_v128_store(srow[2] + j + 4, s22);
                wasm_v128_store(srow[3] + j, s30); wasm_v128_store(srow[3] + j + 2, s31); wasm_v128_store(srow[3] + j + 4, s32);
            }
            for (int t = 0; t < 4 && i0 + t < D; t++) {
                const int i = i0 + t;
                double *pi = Pm + i * MAXD;
                for (int j = i; j < D; j++) { double v = pi[j] - srow[t][j]; pi[j] = v; Pm[j * MAXD + i] = v; }
            }
        }
#else
''' + _old + '#endif\n'
src = src[:_a] + _new + src[_b:]
