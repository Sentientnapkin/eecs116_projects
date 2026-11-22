s = open('b16s.c').read()
a = s.index("static uint16_t lc_hs[240 * LC_W];")
b = s.index("#endif\n", s.index("static void lc_gray_int("))
new = r'''static uint16_t lc_vs[960 + 16];
/* output rows o0..o1-1: vertical 2,2,1 / 1,2,2 row taps on the raw bytes (u16 SIMD), then horizontal taps per 5-pixel group (i16 dot products) */
static void lc_gray_int(const uint8_t *rgb, uint8_t *out, int y0, int y1, int o0, int o1) {
    (void)y0; (void)y1;
    const v128_t we_lo = wasm_i16x8_make(2, 2, 2, 2, 2, 2, 1, 1), we_hi = wasm_i16x8_make(1, 0, 0, 0, 0, 0, 0, 0);
    const v128_t wo_lo = wasm_i16x8_make(0, 0, 0, 0, 0, 0, 1, 1), wo_hi = wasm_i16x8_make(1, 2, 2, 2, 2, 2, 2, 0);
    for (int i = o0; i < o1; i++) {
        const int r0 = 5 * (i >> 1) + ((i & 1) ? 2 : 0);
        const uint8_t *a = rgb + 960 * r0, *b = a + 960, *c = b + 960;
        const int odd = i & 1;
        for (int x = 0; x < 960; x += 16) {
            v128_t va = wasm_v128_load(a + x), vb = wasm_v128_load(b + x), vc = wasm_v128_load(c + x);
            v128_t al = wasm_u16x8_extend_low_u8x16(va), ah = wasm_u16x8_extend_high_u8x16(va);
            v128_t bl = wasm_u16x8_extend_low_u8x16(vb), bh = wasm_u16x8_extend_high_u8x16(vb);
            v128_t cl = wasm_u16x8_extend_low_u8x16(vc), ch = wasm_u16x8_extend_high_u8x16(vc);
            v128_t sl, sh;
            if (odd) { sl = wasm_i16x8_add(al, wasm_i16x8_shl(wasm_i16x8_add(bl, cl), 1)); sh = wasm_i16x8_add(ah, wasm_i16x8_shl(wasm_i16x8_add(bh, ch), 1)); }
            else { sl = wasm_i16x8_add(cl, wasm_i16x8_shl(wasm_i16x8_add(al, bl), 1)); sh = wasm_i16x8_add(ch, wasm_i16x8_shl(wasm_i16x8_add(ah, bh), 1)); }
            wasm_v128_store(lc_vs + x, sl); wasm_v128_store(lc_vs + x + 8, sh);
        }
        uint8_t *o = out + i * LC_W;
        const uint16_t *p = lc_vs;
        for (int m = 0; m < 64; m += 2, p += 30) {
            const v128_t l0 = wasm_v128_load(p), h0 = wasm_v128_load(p + 8), l1 = wasm_v128_load(p + 15), h1 = wasm_v128_load(p + 23);
            const v128_t E0 = wasm_i32x4_add(wasm_i32x4_dot_i16x8(l0, we_lo), wasm_i32x4_dot_i16x8(h0, we_hi));
            const v128_t O0 = wasm_i32x4_add(wasm_i32x4_dot_i16x8(l0, wo_lo), wasm_i32x4_dot_i16x8(h0, wo_hi));
            const v128_t E1 = wasm_i32x4_add(wasm_i32x4_dot_i16x8(l1, we_lo), wasm_i32x4_dot_i16x8(h1, we_hi));
            const v128_t O1 = wasm_i32x4_add(wasm_i32x4_dot_i16x8(l1, wo_lo), wasm_i32x4_dot_i16x8(h1, wo_hi));
            /* 4x4 transpose-add: lanes (E0, O0, E1, O1) totals */
            const v128_t A = wasm_i32x4_add(wasm_i32x4_shuffle(E0, O0, 0, 4, 1, 5), wasm_i32x4_shuffle(E0, O0, 2, 6, 3, 7));
            const v128_t B = wasm_i32x4_add(wasm_i32x4_shuffle(E1, O1, 0, 4, 1, 5), wasm_i32x4_shuffle(E1, O1, 2, 6, 3, 7));
            const v128_t T = wasm_i32x4_add(wasm_i32x4_shuffle(A, B, 0, 1, 4, 5), wasm_i32x4_shuffle(A, B, 2, 3, 6, 7));
            /* floor((2 T + 75) / 150) = (T * 2 + 75) * 2^k / 150 ... exact integer division per lane */
            uint32_t q[4]; wasm_v128_store(q, wasm_i32x4_add(wasm_i32x4_shl(T, 1), wasm_i32x4_splat(75)));
            o[2 * m] = (uint8_t)(q[0] / 150); o[2 * m + 1] = (uint8_t)(q[1] / 150); o[2 * m + 2] = (uint8_t)(q[2] / 150); o[2 * m + 3] = (uint8_t)(q[3] / 150);
        }
    }
}
'''
s = s[:a] + new + s[b:]
open('b16s.c', 'w').write(s)
print("ok")
