"""mkprof2.py IN.c OUT.c : add sub-phase PM marks inside update(), build_rows(), line_rows() and feature_rows() of a
mkprof.py output (anchors that are not found exactly once are skipped, except the update() ones)."""
import sys
s = open(sys.argv[1]).read()
NL = '\n'
A = [('    { /* HP = H P: two rows', 60, 'upd.HP'), ('        static double HT[MAXD * (MAXK + 2)];', 61, 'upd.S'),
     ('    if (!cholesky(Sm, k)) { ST(st_cholf++); return 0; }', 62, 'upd.chol_call'),
     ('    memcpy(y, r, k * sizeof(double));' + NL + '    chol_solve(Sm, k, y);', 63, 'upd.gate'),
     ('    memcpy(y,r,k*sizeof(double));', 64, 'upd.yfwd'), ('    { /* Kt = S^-1 HP by forward', 65, 'upd.Kt'),
     ('    double dx[MAXD];' + NL + '    for (int j = 0; j < D; j += 6) {', 66, 'upd.dx'), ('        static double srow[4][MAXD + 6];', 67, 'upd.Pupd'),
     ('    inject(dx);' + NL + '    return 1;' + NL + '}' + NL, 68, 'upd.tail'),
     ('    int nclone_cols = D - CORE;' + NL + '    if (nrows > nclone_cols) {', 70, 'build_rows.QR')]
if '{ /* r1: HP = H P' in s:
    A[0] = ('    { /* r1: HP = H P', 60, 'upd.HP'); A[1] = ('    { /* r1: S = HP H^T', 61, 'upd.S')
    A[5] = ('    { /* r1: Kt = L^-1 HP', 65, 'upd.Kt'); A[7] = ('    { /* r1: P -= W^T Kt', 67, 'upd.Pupd')
B = [('    for (int a = 0; a < m; a++) for (int b = a + 1; b < m; b++) {' + NL + '        double c3[3]', 71, 'lr.dirpairs'),
     ('    for (int it = 0; it < 4; it++) {' + NL + '        double e1[3], e2[3], J[2 * MAX_OBS][4]', 72, 'lr.GN4'),
     ('        double az = fabs(L.D[2]);', 73, 'lr.vh'),
     ('        if (EDGE_MYAW && type == 2 && my_fixed) {', 74, 'lr.myaw'),
     ('    double e1[3], e2[3], Hl[2 * MAX_OBS * 4];', 75, 'lr.final_jac'),
     ('    memset(Hx, 0, nr * MAXD * sizeof(double));' + NL + '    for (int k = 0; k < m; k++) {' + NL + '        rr[2 * k]', 76, 'lr.Hx'),
     ('    const int NC = NP;', 77, 'lr.QR'),
     ('        double sigma2 = (EDGE_PIX / fx) * (EDGE_PIX / fx);' + NL + '#if R1_GATE', 78, 'lr.gate'),
     ('        double sigma2 = (EDGE_PIX / fx) * (EDGE_PIX / fx);' + NL + '#if EDGE_ASIMD', 78, 'lr.gate'),
     ('    const double hw = PIXEL_STD / EDGE_PIX;' + NL + '    for (int a = 0; a < k0; a++) {' + NL + '        for (int j = 0; j < D; j++) Hbig[(*nrows + a) * MAXD + j] = hw * H0[a * MAXD + j];' + NL + '        rbig[*nrows + a] = hw * r0[a];' + NL + '    }' + NL + '    *nrows += k0; GSD(l_rows', 79, 'lr.copy'),
     ('    double pf[3];' + NL + '    tc_att++;' + NL + '    if (!triangulate', 81, 'fr.tri'),
     ('    int m = 2 * o.n;' + NL + '    double RbcT[9];', 82, 'fr.jac'),
     ('    for (int c = 0; c < 3; c++) { /* left null space of Hf */', 83, 'fr.QR'),
     ('    int k0 = m - 3;' + NL + '    const double *H0 = Hx + 3 * MAXD', 84, 'fr.gate'),
     ('    hw *= fc_hw;', 85, 'fr.copy')]
for a, i, n in B:
    if s.count(a) == 1: A.append((a, i, n))
    elif n != 'lr.gate': print('skip anchor', n, s.count(a), file=sys.stderr)
names = []
for a, i, n in A:
    c = s.count(a); assert c >= 1, a
    s = s.replace(a, '    PM(%d);\n' % i + a, 1); names.append('%d %s' % (i, n))
open(sys.argv[2], 'w').write(s)
open(sys.argv[2] + '.ids', 'w').write(open(sys.argv[1] + '.ids').read() + '\n' + '\n'.join(names))
