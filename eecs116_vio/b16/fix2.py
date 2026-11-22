s = open('b16s.c').read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (a[:70], s.count(a))
    s = s.replace(a, b)

rep("#define LC_PREP_PARTS 8\n", """#ifndef LC_PREP_PARTS
#define LC_PREP_PARTS 16
#endif
#ifndef LC_GB
#define LC_GB 12          /* gray bands per frame copy (96 / LC_GB output rows, 2.5x as many source rows) */
#endif
#ifndef LC_C0R
#define LC_C0R 4          /* conv0 output rows per slice (24 rows) */
#endif
#ifndef LC_C1R
#define LC_C1R 3          /* conv1 output rows per slice (12 rows) */
#endif
""")
rep("""static void lc_gray128_band(const uint8_t *rgb, uint8_t *out, int b) {
    const float k3 = 1.0f / 3.0f;
    for (int y = 40 * b; y < 40 * b + 40; y++) {""",
"""static void lc_gray128_band(const uint8_t *rgb, uint8_t *out, int b) {
    const float k3 = 1.0f / 3.0f;
    const int OR = LC_H / LC_GB, SR = OR * 5 / 2;
    for (int y = SR * b; y < SR * b + SR; y++) {""")
rep("    for (int i = 16 * b; i < 16 * b + 16; i++) {\n        const float *r0 = lc_tmp + (5 * (i >> 1)) * LC_W; uint8_t *o = out + i * LC_W;\n        if (i & 1) {\n            const float *a = r0 + 2 * LC_W, *bb",
    "    for (int i = OR * b; i < OR * b + OR; i++) {\n        const float *r0 = lc_tmp + (5 * (i >> 1)) * LC_W; uint8_t *o = out + i * LC_W;\n        if (i & 1) {\n            const float *a = r0 + 2 * LC_W, *bb")
rep("""    const int P0 = 12, PF = P0 + LC_PREP_PARTS, C0 = PF + 1;
    int q = lc_q;
    if (q < 6) lc_gray128_band(lc_src0, lc_g0, q);
    else if (q < 12) { if (lc_frame <= LC_K) return; lc_gray128_band(lc_src5, lc_g5, q - 6); }
    else if (q < PF) lc_stage_prep(100 + q - P0);
    else if (q == PF) lc_stage_prep(100 + LC_PREP_PARTS);
    else if (q < C0 + 3) lc_conv0_rows(lc_in, lc_a0, 8 * (q - C0), 8 * (q - C0) + 8);
    else if (q < C0 + 5) lc_conv1_rows(lc_a0, lc_a1, 6 * (q - C0 - 3), 6 * (q - C0 - 3) + 6);
    else if (q == C0 + 5) lc_conv2(lc_a1, lc_a2);
    else if (q == C0 + 6) lc_conv3(lc_a2, lc_a3);
    else { lc_head(); lc_apply(); lc_next = 6; }""",
"""    const int G1 = LC_GB, P0 = 2 * LC_GB, PF = P0 + LC_PREP_PARTS, C0 = PF + 1, N0 = 24 / LC_C0R, N1 = 12 / LC_C1R;
    int q = lc_q;
    if (q < G1) lc_gray128_band(lc_src0, lc_g0, q);
    else if (q < P0) { if (lc_frame <= LC_K) return; lc_gray128_band(lc_src5, lc_g5, q - G1); }
    else if (q < PF) lc_stage_prep(100 + q - P0);
    else if (q == PF) lc_stage_prep(100 + LC_PREP_PARTS);
    else if (q < C0 + N0) lc_conv0_rows(lc_in, lc_a0, LC_C0R * (q - C0), LC_C0R * (q - C0) + LC_C0R);
    else if (q < C0 + N0 + N1) lc_conv1_rows(lc_a0, lc_a1, LC_C1R * (q - C0 - N0), LC_C1R * (q - C0 - N0) + LC_C1R);
    else if (q == C0 + N0 + N1) lc_conv2(lc_a1, lc_a2);
    else if (q == C0 + N0 + N1 + 1) lc_conv3(lc_a2, lc_a3);
    else { lc_head(); lc_apply(); lc_next = 6; }""")
open('b16s.c', 'w').write(s)
print("ok")
s = open('b16s.c').read()
a = "    for (int p = 0; p < LC_H * LC_W; p++) { double a = lc_x0[p] - m0, b = (lc_x1[p] - m1) * lc_m[p]; v0 += a * a; v1 += b * b; }\n"
assert s.count(a) == 1
s = s.replace(a, """    static double lcp_v0, lcp_v1;
    if (part != 101 + LC_PREP_PARTS) for (int p = 0; p < LC_H * LC_W; p++) { double a = lc_x0[p] - m0, b = (lc_x1[p] - m1) * lc_m[p]; v0 += a * a; v1 += b * b; }
    else { v0 = lcp_v0; v1 = lcp_v1; }
    if (LC_SLICE && part == 100 + LC_PREP_PARTS) { lcp_v0 = v0; lcp_v1 = v1; return; }
""")
a = "    else if (q == PF) lc_stage_prep(100 + LC_PREP_PARTS);\n    else if (q < C0 + N0)"
assert s.count(a) == 1
s = s.replace(a, "    else if (q == PF) lc_stage_prep(100 + LC_PREP_PARTS);\n    else if (q == PF + 1) lc_stage_prep(101 + LC_PREP_PARTS);\n    else if (q < C0 + 1 + N0)")
s = s.replace("PF = P0 + LC_PREP_PARTS, C0 = PF + 1,", "PF = P0 + LC_PREP_PARTS, C0 = PF + 2,", 1)
s = s.replace("    else if (q < C0 + 1 + N0)", "    else if (q < C0 + N0)", 1)
open('b16s.c', 'w').write(s)
print("ok2")
