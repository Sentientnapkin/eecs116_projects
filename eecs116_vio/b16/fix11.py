s = open('b16s.c').read()
def rep(a, b, cnt=1):
    global s
    assert s.count(a) == cnt, (a[:70], s.count(a))
    s = s.replace(a, b)
# hold the vision updates (MSCKF + map) until the (sliced) net has landed: the delayed velocity measurement then stays consistent
rep("static void msckf_update(Obs *batch, int nbatch) {\n    if (UPD_ROWCAP > 0) {",
    "static void msckf_update(Obs *batch, int nbatch) {\n    if (LC_HOLDING) return;\n    if (UPD_ROWCAP > 0) {")
rep("static void map_relocalize(int budget) {\n    double Rwc[9], pwc[3];",
    "static void map_relocalize(int budget) {\n    if (LC_HOLDING) return;\n    double Rwc[9], pwc[3];")
rep("static int lc_have_row, lc_frame, lc_next, lc_ready, lc_applied, lc_active;\n",
    "static int lc_have_row, lc_frame, lc_next, lc_ready, lc_applied, lc_active;\n#ifndef LC_HOLD\n#define LC_HOLD 0   /* 1: no MSCKF/map updates until the startup net has landed; 2: also during re-anchor runs */\n#endif\n#define LC_HOLDING (LC_HOLD && lc_active && !lc_applied && (LC_HOLD == 2 || tc_nanch == 0))\n")
open('b16s.c', 'w').write(s)
print("ok")
