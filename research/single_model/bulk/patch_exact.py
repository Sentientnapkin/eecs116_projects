"""b13x.c = learned_c/lc_b11.c (B7 exact + net) + F code (ITER / MAP) taken from b6bulk.c. All F switches default OFF/ON as in b6bulk (off)."""
import re
base = open('../learned_c/lc_b11.c').read()
src = open('b6bulk.c').read()
def cut(a, b, s=src, incl_b=False):
    i = s.index(a); j = s.index(b, i); return s[i:j + (len(b) if incl_b else 0)]
def rep(a, b, cnt=1):
    global base
    assert base.count(a) == cnt, (a[:60], base.count(a)); base = base.replace(a, b)
# 1 params
params = cut("#ifndef ITER_BACK", "/* MSCKF */\n")
mapparams = cut("#ifndef MAP_MODE", "/* MSCKF */\n")
params = cut("#ifndef ITER_BACK", "#ifndef ITER_UPD") + cut("#ifndef ITER_TH", "#ifndef ITER_UPD") if False else None
iterp = "#ifndef ITER_MAXF\n#define ITER_MAXF 0\n#endif\n#ifndef ITER_BACK\n#define ITER_BACK 0.0\n#endif\n#ifndef ITER_TH\n#define ITER_TH 0.0\n#endif\n#ifndef ITER_UPD\n#define ITER_UPD 1\n#endif\n"
rep("/* MSCKF */\n", iterp + mapparams + "/* MSCKF */\n")
# 2 Obs / tid
rep("typedef struct { int n; int cid[MAX_OBS]; double x[MAX_OBS], y[MAX_OBS]; } Obs;", "typedef struct { int n; int cid[MAX_OBS]; double x[MAX_OBS], y[MAX_OBS]; int tid; double px, py; } Obs;")
rep("lost[nlost++] = t->obs;", "{ lost[nlost] = t->obs; lost[nlost].tid = -1; nlost++; }")
rep("batch[(*nb)++] = *o;", "int ti = (int)(((const char *)o - (const char *)&tracks[0].obs) / sizeof(Track));\n    batch[*nb] = *o; batch[*nb].tid = ti; batch[*nb].px = tracks[ti].x; batch[*nb].py = tracks[ti].y;\n    (*nb)++;")
# 3 map code + g_dx
mapcode = cut("#if MAP_MODE\n#define MAP_PS", "static const double *g_dx;")
rep("#define MAX_ROWS (MAX_BATCH * (2 * MAX_OBS - 3))\n", "#define MAX_ROWS (MAX_BATCH * (2 * MAX_OBS - 3))\n" + mapcode + "static const double *g_dx;\n")
# 4 gate + hook
rep("""    double y[2 * MAX_OBS];
    memcpy(y, r0, k0 * sizeof(double));
    chol_solve(Sm, k0, y);
    double m2 = 0;
    for (int a = 0; a < k0; a++) m2 += r0[a] * y[a];""", """    double y[2 * MAX_OBS], ry[2 * MAX_OBS];
    for (int a = 0; a < k0; a++) {
        ry[a] = r0[a];
        if (g_dx) { double q = 0; for (int jj = 0; jj < nnz; jj++) q += H0[a * MAXD + nzc[jj]] * g_dx[nzc[jj]]; ry[a] += q; }
    }
    memcpy(y, ry, k0 * sizeof(double));
    chol_solve(Sm, k0, y);
    double m2 = 0;
    for (int a = 0; a < k0; a++) m2 += ry[a] * y[a];""")
rep("    *nrows += k0;\n    return 1;", "    *nrows += k0;\n#if MAP_MODE\n    if (o_in->tid >= 0 && o.n >= MAP_MIN_OBS) map_add(pf, o_in->px, o_in->py);\n#endif\n    return 1;")
# 5 msckf split
i = base.index("static void msckf_update(Obs *batch, int nbatch) {"); j = base.index("/* =====", i)
body = base[i:j]
body = body.replace("static void msckf_update(Obs *batch, int nbatch) {\n    int nrows = 0;\n    for (int b = 0; b < nbatch; b++) feature_rows(&batch[b], &nrows);\n    if (!nrows) return;", "static int build_rows(Obs *batch, int nbatch) {\n    int nrows = 0;\n    for (int b = 0; b < nbatch; b++) feature_rows(&batch[b], &nrows);\n    if (!nrows) return 0;")
assert "static int build_rows" in body
body = body.replace("    update(rbig, Hbig, nrows, (PIXEL_STD / fx) * (PIXEL_STD / fx), INFINITY);\n}", "    return nrows;\n}\n")
assert "return nrows;" in body
iterblk = cut("#if ITER_UPD > 1\nstatic Clone sv_clones", "/* =====", src)
iterblk = iterblk.rstrip()
base = base[:i] + body + "\n" + iterblk.replace('CLONE_CAP', 'MAX_CLONES') + "\n\n" + base[j:]
# 6 vision hooks
rep("    build_pyramid(frame, cur);\n    double Rwc_now[9];", "    build_pyramid(frame, cur);\n#if MAP_MODE\n    map_img = cur;\n#endif\n    double Rwc_now[9];")
rep("        frames_since_clone = 0;\n        add_clone();", "        frames_since_clone = 0;\n#if MAP_MODE\n        mp_adds = 0;\n#endif\n        add_clone();")
rep("""        } else {
            msckf_update(batch, nb);
        }
    } else {""", """        } else {
            msckf_update(batch, nb);
        }
#if MAP_MODE
        map_relocalize();
#endif
    } else {""")
rep("        memset(tracks, 0, sizeof tracks);\n", "        memset(tracks, 0, sizeof tracks);\n#if MAP_MODE\n        memset(mp, 0, sizeof mp); mp_next = 0; mp_cursor = 0; mp_adds = 0; mp_tries = mp_match = mp_acc = 0;\n#endif\n")
open('exact/b13x.c', 'w').write(base)
print('ok')
