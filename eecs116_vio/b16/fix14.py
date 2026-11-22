s = open('b16s.c').read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (a[:70], s.count(a))
    s = s.replace(a, b)
old = "#if PREP_FAST\n    const double i_f = 1.0 / f_;\n    for (int v = v_lo; v < v_hi; v++) {"
new = r'''#if PREP_SIMD
    const double i_f = 1.0 / f_;
    {
        const v128_t F = wasm_f32x4_splat((float)f_), CX = wasm_f32x4_splat((float)cx_), CY = wasm_f32x4_splat((float)cy_), ZM = wasm_f32x4_splat(1e-3f);
        const v128_t LOB = wasm_f32x4_splat(-0.5f), UW = wasm_f32x4_splat(LC_W - 0.5f), UH = wasm_f32x4_splat(LC_H - 0.5f), U0 = wasm_f32x4_make(0, 1, 2, 3);
        const v128_t S0 = wasm_f32x4_splat((float)(Rc[0] * i_f)), S1 = wasm_f32x4_splat((float)(Rc[1] * i_f)), S2 = wasm_f32x4_splat((float)(Rc[2] * i_f));
        for (int v = v_lo; v < v_hi; v++) {
            const double d1 = (v - cy_) * i_f;
            const v128_t B0 = wasm_f32x4_splat((float)(Rc[0] * (-cx_ * i_f) + Rc[3] * d1 + Rc[6])), B1 = wasm_f32x4_splat((float)(Rc[1] * (-cx_ * i_f) + Rc[4] * d1 + Rc[7])),
                         B2 = wasm_f32x4_splat((float)(Rc[2] * (-cx_ * i_f) + Rc[5] * d1 + Rc[8]));
            for (int u = 0; u < LC_W; u += 4) {
                const v128_t U = wasm_f32x4_add(U0, wasm_f32x4_splat((float)u));
                const v128_t e0 = wasm_f32x4_add(B0, wasm_f32x4_mul(S0, U)), e1 = wasm_f32x4_add(B1, wasm_f32x4_mul(S1, U)), e2 = wasm_f32x4_add(B2, wasm_f32x4_mul(S2, U));
                const v128_t iz = wasm_f32x4_div(F, wasm_f32x4_max(e2, ZM));
                const v128_t uk = wasm_f32x4_add(wasm_f32x4_mul(e0, iz), CX), vk = wasm_f32x4_add(wasm_f32x4_mul(e1, iz), CY);
                const v128_t okm = wasm_v128_and(wasm_v128_and(wasm_v128_and(wasm_f32x4_ge(uk, LOB), wasm_f32x4_le(uk, UW)), wasm_v128_and(wasm_f32x4_ge(vk, LOB), wasm_f32x4_le(vk, UH))), wasm_f32x4_gt(e2, ZM));
                const v128_t fu = wasm_f32x4_floor(uk), fv = wasm_f32x4_floor(vk);
                float au[4], av[4]; int32_t xi[4], yi[4], ok[4];
                wasm_v128_store(au, wasm_f32x4_sub(uk, fu)); wasm_v128_store(av, wasm_f32x4_sub(vk, fv));
                wasm_v128_store(xi, wasm_i32x4_trunc_sat_f32x4(fu)); wasm_v128_store(yi, wasm_i32x4_trunc_sat_f32x4(fv)); wasm_v128_store(ok, okm);
                for (int k = 0; k < 4; k++) {
                    float val = 0;
                    if (ok[k]) {
                        const int x0 = xi[k], y0 = yi[k]; const float a = au[k], b = av[k];
                        if (x0 >= 0 && y0 >= 0 && x0 + 1 < LC_W && y0 + 1 < LC_H) {
                            const uint8_t *g = lc_g5 + y0 * LC_W + x0;
                            val = ((1 - a) * (1 - b)) * g[0] + (a * (1 - b)) * g[1] + ((1 - a) * b) * g[LC_W] + (a * b) * g[LC_W + 1];
                        } else
                            for (int dy = 0; dy < 2; dy++) for (int dx = 0; dx < 2; dx++) {
                                int xx = x0 + dx, yy = y0 + dy;
                                if (xx < 0 || xx >= LC_W || yy < 0 || yy >= LC_H) continue;
                                val += ((dx ? a : 1 - a) * (dy ? b : 1 - b)) * lc_g5[yy * LC_W + xx];
                            }
                    }
                    const int p = v * LC_W + u + k;
                    lc_x1[p] = val; lc_m[p] = ok[k] ? 1.0f : 0.0f; lc_x0[p] = lc_g0[p];
                    sum0 += lc_x0[p]; sum1 += val; cnt += ok[k] != 0;
                }
            }
        }
    }
#elif PREP_FAST
    const double i_f = 1.0 / f_;
    for (int v = v_lo; v < v_hi; v++) {'''
rep(old, new)
rep("#ifndef PREP_FAST\n", "#ifndef PREP_SIMD\n#define PREP_SIMD 0   /* f32x4 derotation (rounding-level differences) */\n#endif\n#ifndef PREP_FAST\n")
open('b16s.c', 'w').write(s)
print("ok")
