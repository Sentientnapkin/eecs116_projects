s = open('b16s.c').read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (a[:70], s.count(a))
    s = s.replace(a, b)
code = r'''
#ifndef LC_GRAY_INT
#define LC_GRAY_INT 0   /* 1: integer SIMD gray resample, out = floor(sum W S / 75 + 1/2) (rounding-level differences from the float version) */
#endif
#if LC_GRAY_INT
static uint16_t lc_hs[240 * LC_W];
/* source rows y0..y1-1: horizontal 2,2,1 / 1,2,2 tap sums of R+G+B per 5-pixel group; output rows o0..o1-1 from them */
static void lc_gray_int(const uint8_t *rgb, uint8_t *out, int y0, int y1, int o0, int o1) {
    const v128_t we_lo = wasm_i16x8_make(2, 2, 2, 2, 2, 2, 1, 1), we_hi = wasm_i16x8_make(1, 0, 0, 0, 0, 0, 0, 0);
    const v128_t wo_lo = wasm_i16x8_make(0, 0, 0, 0, 0, 0, 1, 1), wo_hi = wasm_i16x8_make(1, 2, 2, 2, 2, 2, 2, 0);
    for (int y = y0; y < y1; y++) {
        const uint8_t *p = rgb + 960 * y; uint16_t *h = lc_hs + y * LC_W;
        for (int m = 0; m < 63; m++, p += 15) {
            const v128_t v = wasm_v128_load(p), lo = wasm_u16x8_extend_low_u8x16(v), hi = wasm_u16x8_extend_high_u8x16(v);
            const v128_t E = wasm_i32x4_add(wasm_i32x4_dot_i16x8(lo, we_lo), wasm_i32x4_dot_i16x8(hi, we_hi));
            const v128_t O = wasm_i32x4_add(wasm_i32x4_dot_i16x8(lo, wo_lo), wasm_i32x4_dot_i16x8(hi, wo_hi));
            const v128_t X = wasm_i32x4_add(wasm_i32x4_shuffle(E, O, 0, 4, 1, 5), wasm_i32x4_shuffle(E, O, 2, 6, 3, 7));
            const v128_t Y = wasm_i32x4_add(X, wasm_i32x4_shuffle(X, X, 2, 3, 0, 1));
            h[2 * m] = (uint16_t)wasm_i32x4_extract_lane(Y, 0); h[2 * m + 1] = (uint16_t)wasm_i32x4_extract_lane(Y, 1);
        }
        int S0 = p[0] + p[1] + p[2], S1 = p[3] + p[4] + p[5], S2 = p[6] + p[7] + p[8], S3 = p[9] + p[10] + p[11], S4 = p[12] + p[13] + p[14];
        h[126] = (uint16_t)(2 * S0 + 2 * S1 + S2); h[127] = (uint16_t)(S2 + 2 * S3 + 2 * S4);
    }
    const v128_t c75 = wasm_i32x4_splat(75);
    for (int i = o0; i < o1; i++) {
        const uint16_t *r0 = lc_hs + (5 * (i >> 1)) * LC_W; uint8_t *o = out + i * LC_W;
        const uint16_t *a = (i & 1) ? r0 + 2 * LC_W : r0, *b = a + LC_W, *c = b + LC_W;
        const int wa = (i & 1) ? 1 : 2, wc = (i & 1) ? 2 : 1;
        for (int x = 0; x < LC_W; x += 4) {
            v128_t va = wasm_u32x4_load16x4(a + x), vb = wasm_u32x4_load16x4(b + x), vc = wasm_u32x4_load16x4(c + x);
            v128_t sum = wasm_i32x4_add(wasm_i32x4_add(wasm_i32x4_mul(va, wasm_i32x4_splat(wa)), wasm_i32x4_shl(vb, 1)), wasm_i32x4_mul(vc, wasm_i32x4_splat(wc)));
            v128_t t2 = wasm_i32x4_add(wasm_i32x4_shl(sum, 1), c75);
            uint32_t q[4]; wasm_v128_store(q, t2);
            for (int k = 0; k < 4; k++) { uint32_t v = q[k] / 150; o[x + k] = (uint8_t)(v > 255 ? 255 : v); }
        }
    }
}
#endif
'''
rep("static void lc_gray128(const uint8_t *rgb, uint8_t *out) {\n    const float k3 = 1.0f / 3.0f;\n",
    code + "static void lc_gray128(const uint8_t *rgb, uint8_t *out) {\n#if LC_GRAY_INT\n    lc_gray_int(rgb, out, 0, 240, 0, LC_H); return;\n#endif\n    const float k3 = 1.0f / 3.0f;\n")
rep("    const int OR = LC_H / lc_gb, SR = OR * 5 / 2;\n",
    "    const int OR = LC_H / lc_gb, SR = OR * 5 / 2;\n#if LC_GRAY_INT\n    lc_gray_int(rgb, out, SR * b, SR * b + SR, OR * b, OR * b + OR); return;\n#endif\n")
open('b16s.c', 'w').write(s)
print("ok")
