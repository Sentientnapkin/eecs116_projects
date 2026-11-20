"""Create prof.c: fgt.c with host-import fuel marks (profiling only; never submitted).
MARK(id): "phase id begins here"; the fuel until the next MARK is attributed to id."""
import re,sys
src=open(sys.argv[1] if len(sys.argv)>1 else '../final/fgt.c').read()
def rep(old,new,count=1):
    global src
    assert src.count(old)==count,(old,src.count(old))
    src=src.replace(old,new)
hdr='''
#ifdef PROF
__attribute__((import_module("env"), import_name("mark"))) void mark(int id, int val);
#define MARK(i,v) mark(i,v)
#else
#define MARK(i,v) ((void)0)
#endif
'''
idx=[m.end() for m in re.finditer(r'^#include .*$',src,re.M)][-1]
src=src[:idx]+'\n'+hdr+src[idx:]
# step
rep('    for (int r = 0; r < imu_count; r++) propagate(imu + 7 * r);\n    if (imu_count) imu_measurements(imu, imu_count);\n    vision(frame);\n    write_state(out);',
    '    MARK(1,0);\n    for (int r = 0; r < imu_count; r++) propagate(imu + 7 * r);\n    MARK(2,0);\n    if (imu_count) imu_measurements(imu, imu_count);\n    MARK(25,0);\n    vision(frame);\n    MARK(23,0);\n    write_state(out);\n    MARK(24,0);')
if 'update_tex_scale(cur);\n    double Rwc_now' in src:
    rep('    build_pyramid(frame, cur);\n    update_tex_scale(cur);\n    double Rwc_now[9];\n    m3mul(R, R_bc, Rwc_now);\n    track_all(prev, cur, Rwc_now);',
        '    MARK(3,0);\n    build_pyramid(frame, cur);\n    MARK(4,0);\n    update_tex_scale(cur);\n    MARK(5,0);\n    double Rwc_now[9];\n    m3mul(R, R_bc, Rwc_now);\n    track_all(prev, cur, Rwc_now);\n    MARK(6,0);')
else:
    rep('    build_pyramid(frame, cur);\n    double Rwc_now[9];\n    m3mul(R, R_bc, Rwc_now);\n    track_all(prev, cur, Rwc_now);',
        '    MARK(3,0);\n    build_pyramid(frame, cur);\n    MARK(5,0);\n    double Rwc_now[9];\n    m3mul(R, R_bc, Rwc_now);\n    track_all(prev, cur, Rwc_now);\n    MARK(6,0);')
# feature_rows
rep('static int feature_rows(const Obs *o_in, int *nrows) {\n    Obs o = {0};','static int feature_rows(const Obs *o_in, int *nrows) {\n    MARK(7,0);\n    Obs o = {0};')
rep('    double pf[3];\n    if (!triangulate(&o, ci, pf)) return 0;\n    int m = 2 * o.n;','    double pf[3];\n    MARK(8,0);\n    if (!triangulate(&o, ci, pf)) return 0;\n    MARK(9,0);\n    int m = 2 * o.n;')
rep('    for (int c = 0; c < 3; c++) { /* left null space of Hf */','    MARK(10,0);\n    for (int c = 0; c < 3; c++) { /* left null space of Hf */')
rep('    int k0 = m - 3;\n    const double *H0','    MARK(11,0);\n    int k0 = m - 3;\n    const double *H0')
rep('    if (*nrows + k0 > MAX_ROWS) return 0;\n    for (int a = 0; a < k0; a++) {','    MARK(12,0);\n    if (*nrows + k0 > MAX_ROWS) return 0;\n    for (int a = 0; a < k0; a++) {')
rep('    *nrows += k0;\n    return 1;\n}','    *nrows += k0;\n    MARK(28,0);\n    return 1;\n}')
# msckf_update
rep('    int nrows = 0;\n    for (int b = 0; b < nbatch; b++) feature_rows(&batch[b], &nrows);\n    if (!nrows) return;',
    '    int nrows = 0;\n    MARK(26,nbatch);\n    for (int b = 0; b < nbatch; b++) feature_rows(&batch[b], &nrows);\n    MARK(13,nrows);\n    if (!nrows) { MARK(21,0); return; }')
rep('        nrows = nclone_cols;\n    }\n    update(rbig','        nrows = nclone_cols;\n    }\n    MARK(14,nrows);\n    update(rbig')
rep('(PIXEL_STD / fx) * (PIXEL_STD / fx), INFINITY);\n}','(PIXEL_STD / fx) * (PIXEL_STD / fx), INFINITY);\n    MARK(21,0);\n}')
# update() internals
V='#if F_UPD' in src
rep('    int nz[MAXD], nnz = 0;\n    for (int i = 0; i < D; i++) {\n        int any = 0;','    int nz[MAXD], nnz = 0;\n    MARK(14,k);\n    for (int i = 0; i < D; i++) {\n        int any = 0;')
if V:
    rep('#if F_UPD\n    { /* HP = H P:','    MARK(15,nnz);\n#if F_UPD\n    { /* HP = H P:')
else:
    rep('    for (int a = 0; a < k; a++) /* HP = H P */','    MARK(15,nnz);\n    for (int a = 0; a < k; a++) /* HP = H P */')
if V: rep('#if F_UPD\n    {\n        static double HT','    MARK(16,0);\n#if F_UPD\n    {\n        static double HT')
else: rep('    for (int a = 0; a < k; a++) /* S = H P H^T + noise I */','    MARK(16,0);\n    for (int a = 0; a < k; a++) /* S = H P H^T + noise I */')
rep('    if (!cholesky(Sm, k)) return 0;\n    double y[MAXK];','    MARK(17,0);\n    if (!cholesky(Sm, k)) return 0;\n    double y[MAXK];')
if V:
    rep('#if F_UPD\n    { /* Kt = S^-1 HP','    MARK(18,0);\n#if F_UPD\n    { /* Kt = S^-1 HP')
    if '    {\n#if F_UPD2' in src: rep('    {\n#if F_UPD2','    MARK(19,0);\n    {\n#if F_UPD2')
    else: rep('    {\n        double srow[MAXD + 6];','    MARK(19,0);\n    {\n        double srow[MAXD + 6];')
else:
    rep('    double col[MAXK];\n    for (int j = 0; j < D; j++) { /* Kt','    double col[MAXK];\n    MARK(18,0);\n    for (int j = 0; j < D; j++) { /* Kt')
    rep('    for (int i = 0; i < D; i++)\n        for (int j = i; j < D; j++) {\n            double s = 0;\n            for (int a = 0; a < k; a++) s += HP','    MARK(19,0);\n    for (int i = 0; i < D; i++)\n        for (int j = i; j < D; j++) {\n            double s = 0;\n            for (int a = 0; a < k; a++) s += HP')
rep('    inject(dx);\n    return 1;','    MARK(20,0);\n    inject(dx);\n    return 1;')
# vision pieces
rep('    if (++frames_since_clone >= clone_every) {','    MARK(22,0);\n    if (++frames_since_clone >= clone_every) {')
rep('    detect(cur);\n    cur_pyr = cur;','    MARK(27,0);\n    detect(cur);\n    MARK(23,0);\n    cur_pyr = cur;')
def rep_any(old,new,count=0):
    global src
    assert old in src, old
    src=src.replace(old,new)
# klt internals
rep_any('        extract(I0, w, px, py, KLT_R + 1, patch);\n        int n = 0;','        MARK(29,0);\n        extract(I0, w, px, py, KLT_R + 1, patch);\n        MARK(30,0);\n        int n = 0;')
rep_any('        double det = hxx * hyy - hxy * hxy;\n        double mineig','        MARK(5,0);\n        double det = hxx * hyy - hxy * hxy;\n        double mineig',2)
rep_any('            extract(I1, w, qx, qy, KLT_R, cur_patch);\n            for (n = 0; n < KLT_N; n++) {','            MARK(31,0);\n            extract(I1, w, qx, qy, KLT_R, cur_patch);\n            MARK(32,0);\n            for (n = 0; n < KLT_N; n++) {')
rep_any('            err = esum / KLT_N;','            MARK(5,0);\n            err = esum / KLT_N;')
open('prof.c','w').write(src)
