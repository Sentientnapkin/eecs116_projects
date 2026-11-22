s = open('b16s.c').read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (a[:70], s.count(a))
    s = s.replace(a, b)

old = """    for (int v = v_lo; v < v_hi; v++)
        for (int u = 0; u < LC_W; u++) {
            double d[3] = {(u - cx_) / f_, (v - cy_) / f_, 1.0}, dk[3];
            for (int i = 0; i < 3; i++) dk[i] = Rc[i] * d[0] + Rc[3 + i] * d[1] + Rc[6 + i] * d[2]; /* Rc^T d */
            double z = dk[2] > 1e-3 ? dk[2] : 1e-3, uk = f_ * dk[0] / z + cx_, vk = f_ * dk[1] / z + cy_;
            int ok = uk >= -0.5 && uk <= LC_W - 0.5 && vk >= -0.5 && vk <= LC_H - 0.5 && dk[2] > 1e-3;
            float val = 0;
            if (ok) {
                double fu = floor(uk), fv = floor(vk), au = uk - fu, av = vk - fv;
                int x0 = (int)fu, y0 = (int)fv;
                for (int dy = 0; dy < 2; dy++) for (int dx = 0; dx < 2; dx++) {
                    int xx = x0 + dx, yy = y0 + dy;
                    if (xx < 0 || xx >= LC_W || yy < 0 || yy >= LC_H) continue;
                    val += (float)((dx ? au : 1 - au) * (dy ? av : 1 - av)) * lc_g5[yy * LC_W + xx];
                }
            }
            int p = v * LC_W + u;
            lc_x1[p] = val; lc_m[p] = (float)ok; lc_x0[p] = lc_g0[p];
            sum0 += lc_x0[p]; sum1 += val; cnt += ok;
        }"""
new = """#if PREP_FAST
    const double i_f = 1.0 / f_;
    for (int v = v_lo; v < v_hi; v++) {
        const double d1 = (v - cy_) * i_f;
        double dk[3];
        for (int i = 0; i < 3; i++) dk[i] = Rc[i] * (-cx_ * i_f) + Rc[3 + i] * d1 + Rc[6 + i]; /* Rc^T d at u = 0 */
        const double s0 = Rc[0] * i_f, s1 = Rc[1] * i_f, s2 = Rc[2] * i_f;    /* d(dk)/du */
        for (int u = 0; u < LC_W; u++, dk[0] += s0, dk[1] += s1, dk[2] += s2) {
            double z = dk[2] > 1e-3 ? dk[2] : 1e-3, iz = f_ / z, uk = dk[0] * iz + cx_, vk = dk[1] * iz + cy_;
            int ok = uk >= -0.5 && uk <= LC_W - 0.5 && vk >= -0.5 && vk <= LC_H - 0.5 && dk[2] > 1e-3;
            float val = 0;
            if (ok) {
                double fu = floor(uk), fv = floor(vk), au = uk - fu, av = vk - fv;
                int x0 = (int)fu, y0 = (int)fv;
                if (x0 >= 0 && y0 >= 0 && x0 + 1 < LC_W && y0 + 1 < LC_H) {
                    const uint8_t *g = lc_g5 + y0 * LC_W + x0;
                    val = (float)((1 - au) * (1 - av)) * g[0] + (float)(au * (1 - av)) * g[1] + (float)((1 - au) * av) * g[LC_W] + (float)(au * av) * g[LC_W + 1];
                } else
                    for (int dy = 0; dy < 2; dy++) for (int dx = 0; dx < 2; dx++) {
                        int xx = x0 + dx, yy = y0 + dy;
                        if (xx < 0 || xx >= LC_W || yy < 0 || yy >= LC_H) continue;
                        val += (float)((dx ? au : 1 - au) * (dy ? av : 1 - av)) * lc_g5[yy * LC_W + xx];
                    }
            }
            int p = v * LC_W + u;
            lc_x1[p] = val; lc_m[p] = (float)ok; lc_x0[p] = lc_g0[p];
            sum0 += lc_x0[p]; sum1 += val; cnt += ok;
        }
    }
#else
""" + old + "\n#endif"
rep(old, new)
rep("#ifndef LC_PREP_SPLIT\n", "#ifndef PREP_FAST\n#define PREP_FAST 0   /* incremental derotation + fast bilinear path (rounding-level differences) */\n#endif\n#ifndef LC_PREP_SPLIT\n")
open('b16s.c', 'w').write(s)
print("ok")
