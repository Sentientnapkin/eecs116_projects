s = open('b16s.c').read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (a[:70], s.count(a))
    s = s.replace(a, b)

# GRAY_G: half-res level 1 = rounded 2x2 mean of the green channel only (no luma weights)
rep("""    for (int y = 0; y < h1; y++) {
        const uint8_t *r0 = rgb + 3 * IMG_W * (2 * y), *r1 = r0 + 3 * IMG_W;
        for (int x = 0; x < w1; x += 8) {
            const uint8_t *p0 = r0 + 6 * x, *p1 = r1 + 6 * x;
            v128_t R0, G0, B0, R1, G1, B1;""",
"""#if GRAY_G
    for (int y = 0; y < h1; y++) {
        const uint8_t *r0 = rgb + 3 * IMG_W * (2 * y), *r1 = r0 + 3 * IMG_W;
        for (int x = 0; x < w1; x += 8) {
            const uint8_t *p0 = r0 + 6 * x, *p1 = r1 + 6 * x;
            v128_t G0 = wasm_i8x16_shuffle(wasm_i8x16_shuffle(wasm_v128_load(p0), wasm_v128_load(p0 + 16), 1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 0, 0, 0, 0, 0), wasm_v128_load(p0 + 32), 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 21, 24, 27, 30);
            v128_t G1 = wasm_i8x16_shuffle(wasm_i8x16_shuffle(wasm_v128_load(p1), wasm_v128_load(p1 + 16), 1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 0, 0, 0, 0, 0), wasm_v128_load(p1 + 32), 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 21, 24, 27, 30);
            v128_t gs = wasm_u16x8_shr(wasm_i16x8_add(wasm_i16x8_add(wasm_u16x8_extadd_pairwise_u8x16(G0), wasm_u16x8_extadd_pairwise_u8x16(G1)), two), 2);
            wasm_v128_store64_lane(d1 + y * w1 + x, wasm_u8x16_narrow_i16x8(gs, gs), 0);
        }
    }
    (void)c77; (void)c150; (void)c29; (void)c128;
#else
    for (int y = 0; y < h1; y++) {
        const uint8_t *r0 = rgb + 3 * IMG_W * (2 * y), *r1 = r0 + 3 * IMG_W;
        for (int x = 0; x < w1; x += 8) {
            const uint8_t *p0 = r0 + 6 * x, *p1 = r1 + 6 * x;
            v128_t R0, G0, B0, R1, G1, B1;""")
rep("""            wasm_v128_store64_lane(d1 + y * w1 + x, wasm_u8x16_narrow_i16x8(g, g), 0);
        }
    }
#undef DEINT""", """            wasm_v128_store64_lane(d1 + y * w1 + x, wasm_u8x16_narrow_i16x8(g, g), 0);
        }
    }
#endif
#undef DEINT""")
rep("#ifndef HALF_RES\n", "#ifndef GRAY_G\n#define GRAY_G 0   /* HALF_RES only: gray = green channel */\n#endif\n#ifndef HALF_RES\n")
open('b16s.c', 'w').write(s)
print("ok")
