static void extract_f32(const uint8_t *I, int w, double x, double y, int r, float *out) {
    int x0 = (int)x, y0 = (int)y, n = 2 * r + 1;
    double ax = x - x0, ay = y - y0;
    const v128_t W00 = wasm_f32x4_splat((float)((1 - ax) * (1 - ay))), W01 = wasm_f32x4_splat((float)(ax * (1 - ay)));
    const v128_t W10 = wasm_f32x4_splat((float)((1 - ax) * ay)), W11 = wasm_f32x4_splat((float)(ax * ay));
    for (int v = 0; v < n; v++) {
        const uint8_t *p = I + (y0 - r + v) * w + x0 - r;
        float *o = out + v * n;
        for (int u = 0; u < n; u += 4) {
            v128_t t0 = wasm_f32x4_convert_u32x4(wasm_u32x4_extend_low_u16x8(wasm_u16x8_load8x8(p + u)));
            v128_t t1 = wasm_f32x4_convert_u32x4(wasm_u32x4_extend_low_u16x8(wasm_u16x8_load8x8(p + u + 1)));
            v128_t t2 = wasm_f32x4_convert_u32x4(wasm_u32x4_extend_low_u16x8(wasm_u16x8_load8x8(p + u + w)));
            v128_t t3 = wasm_f32x4_convert_u32x4(wasm_u32x4_extend_low_u16x8(wasm_u16x8_load8x8(p + u + w + 1)));
            wasm_v128_store(o + u, wasm_f32x4_add(wasm_f32x4_add(wasm_f32x4_add(wasm_f32x4_mul(W00, t0), wasm_f32x4_mul(W01, t1)), wasm_f32x4_mul(W10, t2)), wasm_f32x4_mul(W11, t3)));
        }
    }
}
static inline double hsum4(v128_t v) { return (double)(wasm_f32x4_extract_lane(v, 0) + wasm_f32x4_extract_lane(v, 1) + wasm_f32x4_extract_lane(v, 2) + wasm_f32x4_extract_lane(v, 3)); }
static int klt(int prev, int cur, double x0, double y0, double gx, double gy, double *ox, double *oy) {
    static float T[KLT_N + 4], GX[KLT_N + 4], GY[KLT_N + 4], patch[(2 * KLT_R + 3) * (2 * KLT_R + 3) + 4], cur_patch[KLT_N + 4];
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
        const int pw = 2 * KLT_R + 3;
        extract_f32(I0, w, px, py, KLT_R + 1, patch);
        int n = 0;
        v128_t vxx = wasm_f32x4_splat(0), vxy = vxx, vyy = vxx;
        const v128_t half = wasm_f32x4_splat(0.5f);
        float txx = 0, txy = 0, tyy = 0;
        for (int v = 1; v < pw - 1; v++) {
            const float *q = patch + v * pw;
            int u = 1;
            for (; u + 4 <= pw - 1; u += 4, n += 4) {
                v128_t gxv = wasm_f32x4_mul(half, wasm_f32x4_sub(wasm_v128_load(q + u + 1), wasm_v128_load(q + u - 1)));
                v128_t gyv = wasm_f32x4_mul(half, wasm_f32x4_sub(wasm_v128_load(q + u + pw), wasm_v128_load(q + u - pw)));
                wasm_v128_store(T + n, wasm_v128_load(q + u)); wasm_v128_store(GX + n, gxv); wasm_v128_store(GY + n, gyv);
                vxx = wasm_f32x4_add(vxx, wasm_f32x4_mul(gxv, gxv)); vxy = wasm_f32x4_add(vxy, wasm_f32x4_mul(gxv, gyv)); vyy = wasm_f32x4_add(vyy, wasm_f32x4_mul(gyv, gyv));
            }
            for (; u < pw - 1; u++, n++) {
                float gxs = 0.5f * (q[u + 1] - q[u - 1]), gys = 0.5f * (q[u + pw] - q[u - pw]);
                T[n] = q[u]; GX[n] = gxs; GY[n] = gys; txx += gxs * gxs; txy += gxs * gys; tyy += gys * gys;
            }
        }
        double hxx = hsum4(vxx) + txx, hxy = hsum4(vxy) + txy, hyy = hsum4(vyy) + tyy;
        double det = hxx * hyy - hxy * hxy;
        double mineig = 0.5 * (hxx + hyy) - sqrt(0.25 * (hxx - hyy) * (hxx - hyy) + hxy * hxy);
        if (mineig < KLT_MIN_EIG * KLT_N || det <= 0) {
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
            extract_f32(I1, w, qx, qy, KLT_R, cur_patch);
            v128_t bxv = wasm_f32x4_splat(0), byv = bxv, esv = bxv;
            for (n = 0; n + 4 <= KLT_N; n += 4) {
                v128_t e = wasm_f32x4_sub(wasm_v128_load(cur_patch + n), wasm_v128_load(T + n));
                bxv = wasm_f32x4_add(bxv, wasm_f32x4_mul(wasm_v128_load(GX + n), e)); byv = wasm_f32x4_add(byv, wasm_f32x4_mul(wasm_v128_load(GY + n), e));
                esv = wasm_f32x4_add(esv, wasm_f32x4_abs(e));
            }
            double bx = hsum4(bxv), by = hsum4(byv), esum = hsum4(esv);
            for (; n < KLT_N; n++) { float e = cur_patch[n] - T[n]; bx += GX[n] * e; by += GY[n] * e; esum += fabsf(e); }
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
