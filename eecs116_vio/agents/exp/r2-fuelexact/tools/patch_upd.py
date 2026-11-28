"""patch_upd.py IN.c OUT.c : r1-fuelexact change 1 (R1_UPD, default 1): faster exact kernels in update().
Kernels are generated (fixed register blocks, fully written out) so that clang keeps every accumulator in a wasm local."""
import os, sys
NL = chr(10)
s = open(sys.argv[1]).read()


def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (s.count(old), old[:80])
    s = s.replace(old, new)


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kgen import fma_block, decl_zero, loads, stores, chain  # noqa: E402
R2U = int(os.environ.get('R2U', '8'))


# ---------------- switch + helpers, before update()
rep("static int cur_rw;\nstatic int update(", r'''static int cur_rw;
#ifndef R2_CHAIN
#define R2_CHAIN 1  /* r2-fuelexact change 1: chained accumulation (partial sums stay on the wasm stack); bit-identical */
#endif
#ifndef R1_W18
#define R1_W18 1  /* r1-fuelexact change 4: 18-column register blocks in the HP and P-update kernels */
#endif
#ifndef R1_REM
#define R1_REM 1  /* r1-fuelexact change 3: row-remainder kernels (blocks of fewer than four rows) */
#endif
#ifndef R1_UPD
#define R1_UPD 1  /* r1-fuelexact: update() with larger register blocks and exact-zero skipping; bit-identical results */
#endif
#if R1_UPD
/* Exactness (all r1 kernels): every output element is the same sum of the same products in the same order as in the
 * F_UPD kernels (same start value; only the commutativity of IEEE * and + is used). Terms skipped in HP and S are h*p with
 * h == 0 exactly (an H entry), i.e. +-0 for finite p; an accumulator that starts at +0 is never -0 under round-to-nearest,
 * so adding +-0 never changes it. */
static const double r1_zrow[MAXD + 16];
static double r1_scr[4][MAXD + 16];
#endif
static int update(''')


# ---------------- HP
def hp_kernel(cols, rows=4):
    return NL.join([
        decl_zero('s', rows, cols),
        '                const double *w = hb;',
        '#if R2_CHAIN',
        '                int q = 0;',
        chain(lambda r, c: 's%d%d' % (r, c), rows, cols, R2U, 'add', 'q', 'nq', lambda m: 'w += %d' % (4 * m),
              lambda u, c: 'wasm_v128_load(pp[q + %d] + j + %d)' % (u, 2 * c), lambda u, r: 'wasm_v128_load64_splat(w + %d)' % (4 * u + r)),
        '#else',
        '                for (int q = 0; q < nq; q++, w += 4) {',
        '                    const double *pr = pp[q] + j;',
        loads('p', 'pr', cols),
        '                    v128_t c;',
        fma_block('s', rows, cols, lambda r: 'wasm_v128_load64_splat(w + %d)' % r, 'p'),
        '                }',
        '#endif',
        stores('s', rows, cols, lambda r: '(o[%d] + j)' % r)])


def hp_cols(rows):
    return ('#if R1_W18' + NL + '            for (; j + 18 <= D; j += 18) {' + NL + hp_kernel(9, rows) + NL + '            }' + NL + '#endif' + NL +
            '            for (; j + 12 <= D; j += 12) {' + NL + hp_kernel(6, rows) + NL + '            }' + NL +
            '            if (j < D) { /* D % 12 == 6 */' + NL + hp_kernel(3, rows) + NL + '            }' + NL)


rep('''#if F_UPD
    { /* HP = H P: two rows of H at a time''', '''#if R1_UPD
    { /* r1: HP = H P, four rows of H x twelve columns per pass over the q where one of the four rows is nonzero */
        static double hb[MAXD * 4]; static const double *pp[MAXD];
        for (int a = 0; a < k; a += 4) {
            const double *h[4]; double *o[4];
            for (int t = 0; t < 4; t++) { h[t] = a + t < k ? H + (a + t) * MAXD : r1_zrow; o[t] = a + t < k ? HP + (a + t) * MAXD : r1_scr[t]; }
            int nq = 0;
            for (int q = 0; q < nnz; q++) {
                const int c = nz[q];
                const double v0 = h[0][c], v1 = h[1][c], v2 = h[2][c], v3 = h[3][c];
                if (v0 != 0 || v1 != 0 || v2 != 0 || v3 != 0) { double *w = hb + 4 * nq; w[0] = v0; w[1] = v1; w[2] = v2; w[3] = v3; pp[nq++] = Pm + c * MAXD; }
            }
            int j = 0;
#if R1_REM /* r1 change 3: a block of na < 4 rows runs an na-row kernel (no padding rows) */
            const int na = k - a < 4 ? k - a : 4;
            if (na == 4) {
''' + hp_cols(4) + '''            } else if (na == 3) {
''' + hp_cols(3) + '''            } else if (na == 2) {
''' + hp_cols(2) + '''            } else {
''' + hp_cols(1) + '''            }
#else
''' + hp_cols(4) + '''#endif
        }
    }
#elif F_UPD
    { /* HP = H P: two rows of H at a time''')

# ---------------- S
s_kernel = '\n'.join([
    decl_zero('s', 4, 4),
    '                const double *xb = xT + a0, *yb = yT + b0;',
    '                for (int i = 0; i < n; i++) {',
    '                    const double *x = xb + l[i], *yy = yb + l[i];',
    loads('y', 'yy', 4),
    '                    v128_t c;',
    fma_block('s', 4, 4, lambda r: 'wasm_v128_load64_splat(x + %d)' % r, 'y'),
    '                }',
    '                double t[4][8];',
    stores('s', 4, 4, lambda r: 't[%d]' % r)])
rep('''#if F_UPD
    {
        static double HT[MAXD * (MAXK + 2)];''', '''#if R1_UPD
    { /* r1: S = HP H^T + noise I, lower triangle (b <= a) mirrored; four rows a x eight columns b per pass over the q where
         one of the eight H rows b is nonzero. Same per-element sums as the F_UPD kernel: s(a,b) = sum_q HP[a][nz_q] H[b][nz_q]. */
        static double xT[MAXD * (MAXK + 8)], yT[MAXD * (MAXK + 8)]; static int ql[(MAXK + 8) / 8][MAXD]; int nql[(MAXK + 8) / 8];
        const int ld = (k + 7) & ~7;
        for (int q = 0; q < nnz; q++) {
            double *x = xT + q * ld, *yy = yT + q * ld; const int c = nz[q];
            int b = 0;
            for (; b < k; b++) { x[b] = HP[b * MAXD + c]; yy[b] = H[b * MAXD + c]; }
            for (; b < ld; b++) { x[b] = 0; yy[b] = 0; }
        }
        for (int b0 = 0; b0 < k; b0 += 8) {
            int n = 0; int *l = ql[b0 >> 3];
            for (int q = 0; q < nnz; q++) {
                const double *yy = yT + q * ld + b0;
                if (yy[0] != 0 || yy[1] != 0 || yy[2] != 0 || yy[3] != 0 || yy[4] != 0 || yy[5] != 0 || yy[6] != 0 || yy[7] != 0) l[n++] = q * ld;
            }
            nql[b0 >> 3] = n;
        }
        for (int a0 = 0; a0 < k; a0 += 4) {
            for (int b0 = 0; b0 < k && b0 <= a0 + 3; b0 += 8) {
                const int *l = ql[b0 >> 3], n = nql[b0 >> 3];
''' + s_kernel + '''
                for (int ta = 0; ta < 4 && a0 + ta < k; ta++) {
                    const int a = a0 + ta;
                    for (int tb = 0; tb < 8 && b0 + tb <= a; tb++) { const int b2 = b0 + tb; Sm[a * k + b2] = Sm[b2 * k + a] = t[ta][tb] + (a == b2 ? noise : 0); }
                }
            }
        }
    }
#elif F_UPD
    {
        static double HT[MAXD * (MAXK + 2)];''')

# ---------------- gate solve only for a finite gate (gate == INFINITY: m2 > gate is false for every m2, NaN included)
rep('''    double y[MAXK];
    memcpy(y, r, k * sizeof(double));
    chol_solve(Sm, k, y); /* y = S^-1 r */
    double m2 = 0;
    for (int a = 0; a < k; a++) m2 += r[a] * y[a];
    if (m2 > gate) { ST(st_ugate++); return 0; }''', '''    double y[MAXK];
    if (!R1_UPD || gate != INFINITY) { /* r1: with an infinite gate the test cannot fire; y is recomputed after have_s */
    memcpy(y, r, k * sizeof(double));
    chol_solve(Sm, k, y); /* y = S^-1 r */
    double m2 = 0;
    for (int a = 0; a < k; a++) m2 += r[a] * y[a];
    if (m2 > gate) { ST(st_ugate++); return 0; }
    }''')


# ---------------- Kt (LJ_FWD: forward substitution only)
def kt_kernel(cols):
    a = ['a%d' % c for c in range(cols)]; b = ['b%d' % c for c in range(cols)]
    L = []
    L.append('                v128_t %s;' % ', '.join('a%d = wasm_v128_load(h0 + j + %d)' % (c, 2 * c) for c in range(cols)))
    L.append('                v128_t %s;' % ', '.join('b%d = wasm_v128_load(h1 + j + %d)' % (c, 2 * c) for c in range(cols)))
    L.append('                const double *bk = Kt + j;')
    L.append('#if R2_CHAIN')
    L.append('                int kk = 0;')
    L.append(chain(lambda r, c: ('a%d' if r == 0 else 'b%d') % c, 2, cols, R2U, 'sub', 'kk', 'i', lambda m: 'bk += %d * MAXD' % m,
                   lambda u, c: 'wasm_v128_load(bk + %d * MAXD + %d)' % (u, 2 * c), lambda u, r: 'wasm_v128_load64_splat(%s + kk + %d)' % ('si' if r == 0 else 'si1', u)))
    L.append('#else')
    L.append('                for (int kk = 0; kk < i; kk++, bk += MAXD) {')
    L.append('                    const v128_t %s;' % ', '.join('k%d = wasm_v128_load(bk + %d)' % (c, 2 * c) for c in range(cols)))
    L.append('                    v128_t c = wasm_v128_load64_splat(si + kk);')
    L.append('                    ' + ' '.join('a%d = wasm_f64x2_sub(a%d, wasm_f64x2_mul(c, k%d));' % (c, c, c) for c in range(cols)))
    L.append('                    c = wasm_v128_load64_splat(si1 + kk);')
    L.append('                    ' + ' '.join('b%d = wasm_f64x2_sub(b%d, wasm_f64x2_mul(c, k%d));' % (c, c, c) for c in range(cols)))
    L.append('                }')
    L.append('#endif')
    L.append('                ' + ' '.join('a%d = wasm_f64x2_div(a%d, d0);' % (c, c) for c in range(cols)))
    L.append('                ' + ' '.join('wasm_v128_store(o0 + j + %d, a%d);' % (2 * c, c) for c in range(cols)))
    L.append('                if (two) {')
    L.append('                    ' + ' '.join('b%d = wasm_f64x2_sub(b%d, wasm_f64x2_mul(cl, a%d));' % (c, c, c) for c in range(cols)))
    L.append('                    ' + ' '.join('wasm_v128_store(o1 + j + %d, wasm_f64x2_div(b%d, d1));' % (2 * c, c) for c in range(cols)))
    L.append('                }')
    return '\n'.join(L)


rep('''    { /* Kt = S^-1 HP by forward then backward substitution on rows''', '''#if R1_UPD && LJ_FWD
    { /* r1: Kt = L^-1 HP, two rows x twelve columns per pass; row i+1 takes its kk = i term once row i is final (same order) */
        for (int i = 0; i < k; i += 2) {
            const int two = i + 1 < k;
            const double *si = Sm + i * k, *si1 = Sm + (two ? i + 1 : i) * k;
            const v128_t d0 = wasm_f64x2_splat(si[i]), d1 = wasm_f64x2_splat(two ? si1[i + 1] : 1.0), cl = wasm_f64x2_splat(two ? si1[i] : 0.0);
            double *o0 = Kt + i * MAXD, *o1 = two ? Kt + (i + 1) * MAXD : r1_scr[0];
            const double *h0 = HP + i * MAXD, *h1 = two ? HP + (i + 1) * MAXD : r1_scr[1];
            int j = 0;
            for (; j + 12 <= D; j += 12) {
''' + kt_kernel(6) + '''
            }
            if (j < D) { /* D % 12 == 6 */
''' + kt_kernel(3) + '''
            }
        }
    }
    if (0)
#endif
    { /* Kt = S^-1 HP by forward then backward substitution on rows''')


# ---------------- P update
def pu_kernel(cols):
    return '\n'.join([
        decl_zero('s', 6, cols),
        '                const double *kt = Kt + j, *hp = Wk + i0;',
        '#if R2_CHAIN',
        '                int a = 0;',
        chain(lambda r, c: 's%d%d' % (r, c), 6, cols, R2U, 'add', 'a', 'k', lambda m: 'kt += %d * MAXD, hp += %d * MAXD' % (m, m),
              lambda u, c: 'wasm_v128_load(kt + %d * MAXD + %d)' % (u, 2 * c), lambda u, r: 'wasm_v128_load64_splat(hp + %d * MAXD + %d)' % (u, r)),
        '#else',
        '                for (int a = 0; a < k; a++, kt += MAXD, hp += MAXD) {',
        loads('k', 'kt', cols),
        '                    v128_t c;',
        fma_block('s', 6, cols, lambda r: 'wasm_v128_load64_splat(hp + %d)' % r, 'k'),
        '                }',
        '#endif',
        stores('s', 6, cols, lambda r: '(sr[%d] + j)' % r)])


rep('''    {
#if F_UPD2
        static double srow[4][MAXD + 6];''', '''#if R1_UPD
    { /* r1: P -= W^T Kt (W = Kt with LJ_FWD) for j >= i: six rows x twelve columns per pass over a; mirrored by 2x2 transposes */
        static double sr[6][MAXD + 18];
        const double *const Wk = LJ_FWD ? Kt : HP;
        for (int i0 = 0; i0 < D; i0 += 6) {
            int j = i0;
#if R1_W18 /* r1 change 4: eighteen columns per pass while they fit */
            for (; j + 18 <= D; j += 18) {
''' + pu_kernel(9) + '''
            }
#endif
            for (; j + 12 <= D; j += 12) {
''' + pu_kernel(6) + '''
            }
            if (j < D) { /* six columns left */
''' + pu_kernel(3) + '''
            }
            for (int t = 0; t < 6; t++) { const int i = i0 + t; double *pi = Pm + i * MAXD; for (int jj = i; jj < i0 + 6; jj++) { double v = pi[jj] - sr[t][jj]; pi[jj] = v; Pm[jj * MAXD + i] = v; } }
            for (int jj = i0 + 6; jj < D; jj += 2) {
                double *p0 = Pm + i0 * MAXD + jj, *p1 = p0 + MAXD, *p2 = p1 + MAXD, *p3 = p2 + MAXD, *p4 = p3 + MAXD, *p5 = p4 + MAXD;
                v128_t a0 = wasm_f64x2_sub(wasm_v128_load(p0), wasm_v128_load(sr[0] + jj)), a1 = wasm_f64x2_sub(wasm_v128_load(p1), wasm_v128_load(sr[1] + jj));
                v128_t a2 = wasm_f64x2_sub(wasm_v128_load(p2), wasm_v128_load(sr[2] + jj)), a3 = wasm_f64x2_sub(wasm_v128_load(p3), wasm_v128_load(sr[3] + jj));
                v128_t a4 = wasm_f64x2_sub(wasm_v128_load(p4), wasm_v128_load(sr[4] + jj)), a5 = wasm_f64x2_sub(wasm_v128_load(p5), wasm_v128_load(sr[5] + jj));
                wasm_v128_store(p0, a0); wasm_v128_store(p1, a1); wasm_v128_store(p2, a2); wasm_v128_store(p3, a3); wasm_v128_store(p4, a4); wasm_v128_store(p5, a5);
                double *q0 = Pm + jj * MAXD + i0, *q1 = q0 + MAXD;
                wasm_v128_store(q0, wasm_i64x2_shuffle(a0, a1, 0, 2)); wasm_v128_store(q1, wasm_i64x2_shuffle(a0, a1, 1, 3));
                wasm_v128_store(q0 + 2, wasm_i64x2_shuffle(a2, a3, 0, 2)); wasm_v128_store(q1 + 2, wasm_i64x2_shuffle(a2, a3, 1, 3));
                wasm_v128_store(q0 + 4, wasm_i64x2_shuffle(a4, a5, 0, 2)); wasm_v128_store(q1 + 4, wasm_i64x2_shuffle(a4, a5, 1, 3));
            }
        }
    }
    if (0)
#endif
    {
#if F_UPD2
        static double srow[4][MAXD + 6];''')
open(sys.argv[2], 'w').write(s)
print('patched', sys.argv[2])
