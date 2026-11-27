"""mkor.py SRC OUT.c : insert the i3 oracle harness (tools/or_block.c) + hooks into a copy of the baseline. OR=0 -> baseline code."""
import sys
src, out = sys.argv[1], sys.argv[2]
s = open(src).read(); B = open('/data/backups/rganapa/Sebastian/gen3/research/i3/tools/or_block.c').read()
def rep(a, b, cnt=1, within=None):
    global s
    if within:
        i = s.index(within); j = s.index('\n}\n', i); seg = s[i:j]
        assert seg.count(a) == cnt, (a, seg.count(a)); s = s[:i] + seg.replace(a, b) + s[j:]
    else:
        assert s.count(a) == cnt, (a, s.count(a)); s = s.replace(a, b)
D = {'OR': 0, 'OR_TAB': '"/data/backups/rganapa/Sebastian/gen3/research/i3/data/or_tab.bin"', 'OR_NK': 1.0, 'OR_NT': 0, 'OR_TAU': 2.0,
     'OR_OUTP': 0.05, 'OR_OUTK': 10.0, 'OR_SCALE': 0.0, 'OR_SEED': 1, 'OR_GATE': 0, 'OR_NONET': 0,
     'OR_VEL': 0, 'OR_VEL_EV': 10, 'OR_VEL_T0': 0, 'OR_VEL_T1': '(1 << 30)', 'OR_VEL_LAT': 0, 'OR_VEL_MODE': 0,
     'OR_GRAV': 0, 'OR_GRAV_EV': 1, 'OR_GRAV_T1': 0, 'OR_BG': 0, 'OR_BG_EV': 1, 'OR_BG_T1': 0, 'OR_BA': 0, 'OR_BA_EV': 1, 'OR_BA_T1': 0,
     'OR_ROT': 0, 'OR_ROT_EV': 1, 'OR_ROT_T1': '(1 << 30)', 'OR_ROT_MODE': 0,
     'OR_RT': 0, 'OR_RT_ABS': 0.002, 'OR_RT_EV': 10, 'OR_RT_SPAN': 10, 'OR_DZ': 0, 'OR_ALT': 0, 'OR_ALT_EV': 10, 'OR_POS': 0, 'OR_POS_EV': 10,
     'OR_DEP': 0, 'OR_DEP_REJ': 2.0, 'OR_COR': 0, 'OR_COR_PX': 0.0, 'OR_COR_REJ': 3.0}
for k in ('VEL','GRAV','BG','BA','ROT','RT','DZ','ALT','POS','DEP'): D['OR_%s_ON'%k]=0
top = ''.join('#ifndef %s\n#define %s %s\n#endif\n' % (k, k, v) for k, v in D.items())
top += '#define OR_XR ((OR && OR_DEP_ON) ? 2 : 0)\n#if OR\nstatic int or_k = -1, or_i = -1, or_cfr[1024];\n#endif\n'
rep('#include <wasm_simd128.h>\n', '#include <wasm_simd128.h>\n' + top)
rep('    clones[nclones].id = clone_counter++;\n', '    clones[nclones].id = clone_counter++;\n#if OR\n    or_cfr[clones[nclones].id & 1023] = or_k;\n#endif\n')
rep('        update(r, Hs, 3, 1.0, INFINITY);\n#ifdef LC_DEBUG\n        fprintf(stderr, "LC after', '        if (!OR_NONET) update(r, Hs, 3, 1.0, INFINITY);\n#ifdef LC_DEBUG\n        fprintf(stderr, "LC after')
FR = 'static int feature_rows(const Obs *o_in, int *nrows) {'
rep(FR, B + FR)
rep('    if (!triangulate(&o, ci, pf)) { tc_tri++; return 0; }\n', '    if (!triangulate(&o, ci, pf)) { tc_tri++; return 0; }\n#if OR && (OR_DEP_ON || OR_COR)\n    double or_dz = 0; int or_drow = or_feat(&o, ci, pf, &or_dz); if (or_drow < 0) return 0; (void)or_drow;\n#endif\n', within=FR)
DEP = '''#if OR && OR_DEP_ON
    if (or_drow == 1) {
        const Clone *c = &clones[ci[0]]; double Rwc[9], pwc[3], dpt[3], pc[3], u[3], sku[9], tmp[3], w = (PIXEL_STD / fx) / or_dsd;
        camera_pose(c, Rwc, pwc); for (int i = 0; i < 3; i++) dpt[i] = pf[i] - pwc[i]; m3tvec(Rwc, dpt, pc);
        for (int i = 0; i < 3; i++) tmp[i] = pf[i] - c->p[i]; m3tvec(c->R, tmp, u); skew(u, sku);
        memset(Hx + m * MAXD, 0, MAXD * sizeof(double));
        int off = CORE + 6 * ci[0];
        rr[m] = w * (or_dz - pc[2]);
        for (int cc = 0; cc < 3; cc++) {
            double s_th = 0, s_p = 0;
            for (int t = 0; t < 3; t++) { s_th += R_bc[3 * t + 2] * sku[3 * t + cc]; s_p += R_bc[3 * t + 2] * c->R[3 * cc + t]; }
            Hx[m * MAXD + off + cc] = w * s_th; Hx[m * MAXD + off + 3 + cc] = -w * s_p; Hf[m * 3 + cc] = w * s_p;
        }
        m++;
    }
#endif
'''
rep('    int nzc[6 * MAX_OBS], nnz = 0, seen[MAX_CLONES + 1] = {0};\n', DEP + '    int nzc[6 * MAX_OBS], nnz = 0, seen[MAX_CLONES + 1] = {0};\n', within=FR)
rep('static double Hx[2 * MAX_OBS * MAXD], rr[2 * MAX_OBS], Hf[2 * MAX_OBS * 3];', 'static double Hx[(2 * MAX_OBS + OR_XR) * MAXD], rr[2 * MAX_OBS + OR_XR], Hf[(2 * MAX_OBS + OR_XR) * 3];')
rep('static double H0P[(2 * MAX_OBS) * MAXD];', 'static double H0P[(2 * MAX_OBS + OR_XR) * MAXD];')
rep('double norm = 0, v[2 * MAX_OBS];', 'double norm = 0, v[2 * MAX_OBS + OR_XR];', 3)
rep('double y[2 * MAX_OBS], ry[2 * MAX_OBS];', 'double y[2 * MAX_OBS + OR_XR], ry[2 * MAX_OBS + OR_XR];', 3)
ST = 'int32_t step(double t, const uint8_t *frame, const double *imu, int32_t imu_count, double *out) {'
rep('        initialize(imu, imu_count, t);\n', '        initialize(imu, imu_count, t);\n#if OR\n        or_init(imu);\n#endif\n', within=ST)
rep('        write_state(out);\n#if HARDEN\n        hz_out_guard(out);\n#endif\n        return VIOBENCH_STATUS_OK;\n    }\n',
    '#if OR\n        or_step();\n#endif\n        write_state(out);\n#if HARDEN\n        hz_out_guard(out);\n#endif\n        return VIOBENCH_STATUS_OK;\n    }\n', within=ST)
rep('    for (int r = 0; r < imu_count; r++) propagate(imu + 7 * r);\n', '#if OR\n    or_k++; or_pre();\n#endif\n    for (int r = 0; r < imu_count; r++) propagate(imu + 7 * r);\n#if OR\n    or_postprop();\n#endif\n', within=ST)
rep('    write_state(out);\n#if HARDEN\n    hz_out_guard(out);\n#endif\n    if (GATE_DEBUG', '#if OR\n    or_step();\n#endif\n    write_state(out);\n#if HARDEN\n    hz_out_guard(out);\n#endif\n    if (GATE_DEBUG', within=ST)
open(out, 'w').write(s)
