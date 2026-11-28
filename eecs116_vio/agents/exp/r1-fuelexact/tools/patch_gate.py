"""patch_gate.py IN.c OUT.c : r1-fuelexact change 2 (R1_GATE, default 1): the per-feature Mahalanobis gate of feature_rows()
and line_rows() (H0P = H0 P over the feature's clone columns, S = H0P H0^T + sigma2 I) with larger register blocks.
Same per-element sums in the same order (bit-identical)."""
import os, sys
NL = chr(10)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kgen import fma_block, decl_zero, loads, stores  # noqa: E402

s = open(sys.argv[1]).read()


def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (s.count(old), old[:80])
    s = s.replace(old, new)


def h0p_kernel(nblk, rows=4):
    cols = 3 * nblk
    ld = ['                    const v128_t %s;' % ', '.join(
        'p%d = wasm_v128_load(pr + b%d + %d)' % (3 * bi + c, bi, 2 * c) for bi in range(nblk) for c in range(3))]
    st = []
    for r in range(rows):
        st.append('                ' + ' '.join('wasm_v128_store(o[%d] + b%d + %d, s%d%d);' % (r, bi, 2 * c, r, 3 * bi + c) for bi in range(nblk) for c in range(3)))
    return '\n'.join([
        decl_zero('s', rows, cols),
        '                const double *x = ht + a0;',
        '                for (int q = 0; q < nnz; q++, x += ld) {',
        '                    const double *pr = prow[q];',
        ld[0],
        '                    v128_t c;',
        fma_block('s', rows, cols, lambda r: 'wasm_v128_load64_splat(x + %d)' % r, 'p'),
        '                }'] + st)


def h0p_blocks(rows):
    return ('        for (; blk + 2 <= nb; blk += 2) {' + NL + '            const int b0 = nzc[6 * blk], b1 = nzc[6 * blk + 6];' + NL +
            h0p_kernel(2, rows) + NL + '        }' + NL + '        if (blk < nb) {' + NL + '            const int b0 = nzc[6 * blk];' + NL +
            h0p_kernel(1, rows) + NL + '        }' + NL)


s_kernel = '\n'.join([
    decl_zero('s', 4, 4),
    '                const double *x = hpt + a0, *yy = ht + b0;',
    '                for (int q = 0; q < nnz; q++, x += ld, yy += ld) {',
    loads('y', 'yy', 4),
    '                    v128_t c;',
    fma_block('s', 4, 4, lambda r: 'wasm_v128_load64_splat(x + %d)' % r, 'y'),
    '                }',
    '                double t[4][8];',
    stores('s', 4, 4, lambda r: 't[%d]' % r)])

func = '''#ifndef R1_GATE
#define R1_GATE 1  /* r1-fuelexact: blocked H0P / S kernels for the per-feature gates (bit-identical) */
#endif
#if R1_GATE
/* H0P[a][nzc] = sum_q H0[a][nzc_q] P[nzc_q][nzc] (four rows x twelve columns per pass), then
 * S[a][b] = sum_q H0P[a][nzc_q] H0[b][nzc_q] + (a == b ? sigma2 : 0) for b <= a (four x eight per pass), mirrored.
 * Same sums, same q order and same start value (+0) as the feature_rows / line_rows kernels. nnz is a multiple of 6. */
static double r1_gscr[4][MAXD + 16];
static void r1_hph(const double *H0, const int k0, const int *nzc, const int nnz, const double sigma2) {
    static double ht[6 * MAX_OBS * (2 * MAX_OBS + 8)], hpt[6 * MAX_OBS * (2 * MAX_OBS + 8)];
    static const double *prow[6 * MAX_OBS];
    const int ld = (k0 + 7) & ~7, nb = nnz / 6;
    for (int q = 0; q < nnz; q++) {
        prow[q] = Pm + nzc[q] * MAXD;
        double *x = ht + q * ld; int a = 0;
        for (; a < k0; a++) x[a] = H0[a * MAXD + nzc[q]];
        for (; a < ld; a++) x[a] = 0;
    }
    for (int a0 = 0; a0 < k0; a0 += 4) {
        double *o[4];
        for (int t = 0; t < 4; t++) o[t] = a0 + t < k0 ? H0P + (a0 + t) * MAXD : r1_gscr[t];
        int blk = 0;
#if R1_REM
        const int na = k0 - a0 < 4 ? k0 - a0 : 4;
        if (na == 4) {
''' + h0p_blocks(4) + '''        } else if (na == 3) {
''' + h0p_blocks(3) + '''        } else if (na == 2) {
''' + h0p_blocks(2) + '''        } else {
''' + h0p_blocks(1) + '''        }
#else
''' + h0p_blocks(4) + '''#endif
    }
    for (int q = 0; q < nnz; q++) {
        double *x = hpt + q * ld; int a = 0;
        for (; a < k0; a++) x[a] = H0P[a * MAXD + nzc[q]];
        for (; a < ld; a++) x[a] = 0;
    }
    for (int a0 = 0; a0 < k0; a0 += 4)
        for (int b0 = 0; b0 < k0 && b0 <= a0 + 3; b0 += 8) {
''' + s_kernel + '''
            for (int ta = 0; ta < 4 && a0 + ta < k0; ta++) {
                const int a = a0 + ta;
                for (int tb = 0; tb < 8 && b0 + tb <= a; tb++) { const int b2 = b0 + tb; Sm[a * k0 + b2] = Sm[b2 * k0 + a] = t[ta][tb] + (a == b2 ? sigma2 : 0); }
            }
        }
}
#endif
static int line_rows(const Obs *o_in, int *nrows) {'''
rep('static int line_rows(const Obs *o_in, int *nrows) {', func)

# line_rows gate
rep('''        double sigma2 = (EDGE_PIX / fx) * (EDGE_PIX / fx);
#if EDGE_ASIMD''', '''        double sigma2 = (EDGE_PIX / fx) * (EDGE_PIX / fx);
#if R1_GATE
        r1_hph(H0, k0, nzc, nnz, sigma2);
#elif EDGE_ASIMD''')

# feature_rows gate
rep('''    double sigma2 = (PIXEL_STD / fx) * (PIXEL_STD / fx);
''', '''    double sigma2 = (PIXEL_STD / fx) * (PIXEL_STD / fx);
#if R1_GATE
    r1_hph(H0, k0, nzc, nnz, sigma2);
    if (0)
#endif
''')
open(sys.argv[2], 'w').write(s)
print('patched', sys.argv[2])
