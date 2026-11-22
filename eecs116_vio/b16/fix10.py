s = open('b16s.c').read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (a[:70], s.count(a))
    s = s.replace(a, b)

# runtime slice sizes: startup run (fast, bigger slices) vs re-anchor runs (small slices)
rep("static void lc_gray128_band(const uint8_t *rgb, uint8_t *out, int b) {\n    const float k3 = 1.0f / 3.0f;\n    const int OR = LC_H / LC_GB, SR = OR * 5 / 2;",
    "static int lc_gb = LC_GB, lc_pp = LC_PREP_PARTS, lc_c0r = LC_C0R, lc_c1r = LC_C1R;\nstatic void lc_gray128_band(const uint8_t *rgb, uint8_t *out, int b) {\n    const float k3 = 1.0f / 3.0f;\n    const int OR = LC_H / lc_gb, SR = OR * 5 / 2;")
rep("    if (part >= 100) { int q = part - 100; v_lo = q < LC_PREP_PARTS ? q * LC_H / LC_PREP_PARTS : LC_H; v_hi = q < LC_PREP_PARTS ? (q + 1) * LC_H / LC_PREP_PARTS : LC_H; }",
    "    if (part >= 100) { int q = part - 100; v_lo = q < lc_pp ? q * LC_H / lc_pp : LC_H; v_hi = q < lc_pp ? (q + 1) * LC_H / lc_pp : LC_H; }")
rep("    if (part == 0 || (part >= 100 && part < 100 + LC_PREP_PARTS)) return;", "    if (part == 0 || (part >= 100 && part < 100 + lc_pp)) return;")
rep("    if (part != 101 + LC_PREP_PARTS) for", "    if (part != 101 + lc_pp) for")
rep("    if (part == 100 + LC_PREP_PARTS) { lcp_v0 = v0; lcp_v1 = v1; return; }", "    if (part == 100 + lc_pp) { lcp_v0 = v0; lcp_v1 = v1; return; }")
rep("""    const int G1 = LC_GB, P0 = 2 * LC_GB, PF = P0 + LC_PREP_PARTS, C0 = PF + 2, N0 = 24 / LC_C0R, N1 = 12 / LC_C1R;""",
    """    if (lc_q == 0) { int re = tc_nanch > 0; lc_gb = re ? LC_GB_RE : LC_GB; lc_pp = re ? LC_PP_RE : LC_PREP_PARTS; lc_c0r = re ? LC_C0R_RE : LC_C0R; lc_c1r = re ? LC_C1R_RE : LC_C1R; }
    const int G1 = lc_gb, P0 = 2 * lc_gb, PF = P0 + lc_pp, C0 = PF + 2, N0 = 24 / lc_c0r, N1 = 12 / lc_c1r;""")
rep("    else if (q == PF) lc_stage_prep(100 + LC_PREP_PARTS);\n    else if (q == PF + 1) lc_stage_prep(101 + LC_PREP_PARTS);",
    "    else if (q == PF) lc_stage_prep(100 + lc_pp);\n    else if (q == PF + 1) lc_stage_prep(101 + lc_pp);")
rep("    else if (q < C0 + N0) lc_conv0_rows(lc_in, lc_a0, LC_C0R * (q - C0), LC_C0R * (q - C0) + LC_C0R);\n    else if (q < C0 + N0 + N1) lc_conv1_rows(lc_a0, lc_a1, LC_C1R * (q - C0 - N0), LC_C1R * (q - C0 - N0) + LC_C1R);",
    "    else if (q < C0 + N0) lc_conv0_rows(lc_in, lc_a0, lc_c0r * (q - C0), lc_c0r * (q - C0) + lc_c0r);\n    else if (q < C0 + N0 + N1) lc_conv1_rows(lc_a0, lc_a1, lc_c1r * (q - C0 - N0), lc_c1r * (q - C0 - N0) + lc_c1r);")
rep("#ifndef LC_C1R\n", "#ifndef LC_GB_RE\n#define LC_GB_RE LC_GB\n#endif\n#ifndef LC_PP_RE\n#define LC_PP_RE LC_PREP_PARTS\n#endif\n#ifndef LC_C0R_RE\n#define LC_C0R_RE LC_C0R\n#endif\n#ifndef LC_C1R_RE\n#define LC_C1R_RE LC_C1R\n#endif\n#ifndef LC_C1R\n")
open('b16s.c', 'w').write(s)
print("ok")
