"""patch_s.py IN.c OUT.c : r1-fuelexact change 6 (R1_SBLK, default 1), applied after patch_upd.py and patch_gate.py.
The S = X Y^T lower-triangle kernels of update() and r1_hph() run na-row (na = rows left, <= 4) x 8- or 4-column blocks
that stop at the diagonal block, instead of 4 x 8 blocks that also computed (and discarded) entries above the diagonal
and padding rows. Each kept entry is the same sum in the same order (bit-identical)."""
import os, sys
NL = chr(10)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kgen import fma_block, decl_zero, loads, stores  # noqa: E402

s = open(sys.argv[1]).read()


def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (s.count(old), old[:80])
    s = s.replace(old, new)


def kern(rows, bw, listed):
    cols = bw // 2
    if listed:
        head = ['                const double *xb = xT + a0, *yb = yT + b0;',
                '                for (int i = 0; i < n; i++) {',
                '                    const double *x = xb + l[i], *yy = yb + l[i];']
    else:
        head = ['                const double *x = hpt + a0, *yy = ht + b0;',
                '                for (int q = 0; q < nnz; q++, x += ld, yy += ld) {']
    return NL.join(['                {', decl_zero('s', rows, cols)] + head + [
        loads('y', 'yy', cols),
        '                    v128_t c;',
        fma_block('s', rows, cols, lambda r: 'wasm_v128_load64_splat(x + %d)' % r, 'y'),
        '                }',
        stores('s', rows, cols, lambda r: 't[%d]' % r),
        '                }'])


def dispatch(listed):
    out = []
    first = True
    for rows in (4, 3, 2, 1):
        for bw in (8, 4):
            cond = 'na == %d && %s' % (rows, 'wide' if bw == 8 else '!wide')
            out.append(('                %s (%s)' % ('if' if first else 'else if', cond)) + NL + kern(rows, bw, listed))
            first = False
    return NL.join(out)


def block(kname, noise, listed):
    lst = '                const int *l = ql[b0 >> 3], n = nql[b0 >> 3];' + NL if listed else ''
    return ('''#if R1_SBLK
        for (int a0 = 0; a0 < KK; a0 += 4) {
            const int na = KK - a0 < 4 ? KK - a0 : 4, amax = a0 + na - 1;
            for (int b0 = 0; b0 <= amax; b0 += 8) {
''' + lst + '''                const int wide = amax - b0 >= 4; /* some column b0+4..b0+7 is on or below the diagonal */
                double t[4][8];
''' + dispatch(listed) + '''
                for (int ta = 0; ta < na; ta++) {
                    const int a = a0 + ta;
                    for (int tb = 0; tb < 8 && b0 + tb <= a; tb++) { const int b2 = b0 + tb; Sm[a * KK + b2] = Sm[b2 * KK + a] = t[ta][tb] + (a == b2 ? NOISE : 0); }
                }
            }
        }
        if (0)
#endif
''').replace('KK', kname).replace('NOISE', noise)


rep('''#ifndef R1_GATE
#define R1_GATE 1''', '''#ifndef R1_SBLK
#define R1_SBLK 1  /* r1-fuelexact change 6: S kernels stop at the diagonal block (no padding rows / above-diagonal blocks) */
#endif
#ifndef R1_GATE
#define R1_GATE 1''')
# update(): S with per-8-block q lists
rep('''        for (int a0 = 0; a0 < k; a0 += 4) {
            for (int b0 = 0; b0 < k && b0 <= a0 + 3; b0 += 8) {
                const int *l = ql[b0 >> 3], n = nql[b0 >> 3];''', block('k', 'noise', True) + '''        for (int a0 = 0; a0 < k; a0 += 4) {
            for (int b0 = 0; b0 < k && b0 <= a0 + 3; b0 += 8) {
                const int *l = ql[b0 >> 3], n = nql[b0 >> 3];''')
# r1_hph(): dense S
rep('''    for (int a0 = 0; a0 < k0; a0 += 4)
        for (int b0 = 0; b0 < k0 && b0 <= a0 + 3; b0 += 8) {''', block('k0', 'sigma2', False) + '''    for (int a0 = 0; a0 < k0; a0 += 4)
        for (int b0 = 0; b0 < k0 && b0 <= a0 + 3; b0 += 8) {''')
open(sys.argv[2], 'w').write(s)
print('patched', sys.argv[2])
