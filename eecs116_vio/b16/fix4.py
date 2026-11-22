s = open('b16s.c').read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (a[:70], s.count(a))
    s = s.replace(a, b)

# LC_SLICE == 2: the startup net runs unsliced (lands at frame ~9 as in B16); only the mid-flight re-anchor runs are sliced
rep("#define LC_PRIOR_OFF (LC_REPLACE && lc_active && ((LC_SLICE ? lc_applied : lc_frame >= LC_K) || tc_nanch > 0))",
    "#define LC_SL (LC_SLICE == 1 || (LC_SLICE == 2 && tc_nanch > 0))\n#define LC_PRIOR_OFF (LC_REPLACE && lc_active && ((LC_SL ? lc_applied : lc_frame >= LC_K) || tc_nanch > 0))")
rep("    if (lc_active) { if (LC_SLICE) { memcpy(lc_src0, frame, sizeof lc_src0); lc_q = 0; lc_trackdv = 0; } else lc_gray128(frame, lc_g0); }\n}",
    "    if (lc_active) { if (LC_SL) { memcpy(lc_src0, frame, sizeof lc_src0); lc_q = 0; lc_trackdv = 0; } else lc_gray128(frame, lc_g0); }\n}")
rep("    if (LC_SLICE) { lc_step_slice(frame, imu, n); return; }", "    if (LC_SL) { lc_step_slice(frame, imu, n); return; }")
rep("    if (LC_SLICE && part >= 100) {", "    if (part >= 100) {")
rep("    if (LC_SLICE && part == 100 + LC_PREP_PARTS) { lcp_v0 = v0; lcp_v1 = v1; return; }", "    if (part == 100 + LC_PREP_PARTS) { lcp_v0 = v0; lcp_v1 = v1; return; }")
rep("- lc_vf5[i] - (LC_SLICE && LC_DVCORR ? lc_dvupd[i] : 0);", "- lc_vf5[i] - (LC_SL && LC_DVCORR ? lc_dvupd[i] : 0);")
open('b16s.c', 'w').write(s)
print("ok")
