s = open('b16s.c').read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (a[:70], s.count(a))
    s = s.replace(a, b)

old = """    for (int pass = 0; pass < 2; pass++) { /* pass 0: rows (F P), pass 1: columns ((F P) F^T) */
        int rs = pass == 0 ? MAXD : 1, cs = pass == 0 ? 1 : MAXD;
        for (int c = 0; c < D; c++) {"""
new = """#if PROP_FAST
    { /* pass 0 (rows of the moving block) two columns at a time; pass 1 for rows outside the block = the transposed pass-0 values
         (P is stored symmetric, same arithmetic), so the column pass runs on the 15 x 15 block only: bit-identical */
        const v128_t vdt = wasm_f64x2_splat(dt);
        v128_t cR[9], cM[9], cD[9];
        for (int i = 0; i < 9; i++) { cR[i] = wasm_f64x2_splat(R[i]); cM[i] = wasm_f64x2_splat(Ms[i]); cD[i] = wasm_f64x2_splat(dRt[i]); }
        for (int c = 0; c < D; c += 2) {
            v128_t th[3], v[3], p[3], gb[3], ab[3];
            for (int i = 0; i < 3; i++) {
                th[i] = wasm_v128_load(Pm + (TH + i) * MAXD + c); v[i] = wasm_v128_load(Pm + (V + i) * MAXD + c); p[i] = wasm_v128_load(Pm + (P + i) * MAXD + c);
                gb[i] = wasm_v128_load(Pm + (BG + i) * MAXD + c); ab[i] = wasm_v128_load(Pm + (BA + i) * MAXD + c);
            }
            for (int i = 0; i < 3; i++) {
                v128_t t = wasm_f64x2_add(wasm_f64x2_add(wasm_f64x2_mul(cD[3 * i], th[0]), wasm_f64x2_mul(cD[3 * i + 1], th[1])), wasm_f64x2_mul(cD[3 * i + 2], th[2]));
                wasm_v128_store(Pm + (TH + i) * MAXD + c, wasm_f64x2_sub(t, wasm_f64x2_mul(vdt, gb[i])));
                v128_t u = wasm_f64x2_add(wasm_f64x2_add(wasm_f64x2_add(v[i], wasm_f64x2_mul(cM[3 * i], th[0])), wasm_f64x2_mul(cM[3 * i + 1], th[1])), wasm_f64x2_mul(cM[3 * i + 2], th[2]));
                v128_t rb = wasm_f64x2_add(wasm_f64x2_add(wasm_f64x2_mul(cR[3 * i], ab[0]), wasm_f64x2_mul(cR[3 * i + 1], ab[1])), wasm_f64x2_mul(cR[3 * i + 2], ab[2]));
                wasm_v128_store(Pm + (V + i) * MAXD + c, wasm_f64x2_sub(u, wasm_f64x2_mul(vdt, rb)));
                wasm_v128_store(Pm + (P + i) * MAXD + c, wasm_f64x2_add(p[i], wasm_f64x2_mul(vdt, v[i])));
            }
        }
        for (int x = 15; x < D; x++) for (int r = 0; r < 15; r++) Pm[x * MAXD + r] = Pm[r * MAXD + x];
    }
    for (int pass = 1; pass < 2; pass++) {
        int rs = 1, cs = MAXD;
        for (int c = 0; c < 15; c++) {
#else
""" + old + "\n#endif"
rep(old, new)
rep("static void propagate(const double *row) {", "#ifndef PROP_FAST\n#define PROP_FAST 0\n#endif\nstatic void propagate(const double *row) {")
open('b16s.c', 'w').write(s)
print("ok")
