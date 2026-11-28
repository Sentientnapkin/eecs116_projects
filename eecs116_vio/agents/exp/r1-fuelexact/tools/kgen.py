"""kgen.py: C text generators for the fixed-size SIMD register-block kernels (used by the patch_*.py scripts)."""


def fma_block(acc, rows, cols, cname, vname, op='add'):
    """acc{r}{c} = acc{r}{c} op (c_r * v_c); c_r splat lines are given by cname(r)."""
    out = []
    for r in range(rows):
        out.append('                    c = %s;' % cname(r))
        out.append('                    ' + ' '.join('%s%d%d = wasm_f64x2_%s(%s%d%d, wasm_f64x2_mul(c, %s%d));' % (acc, r, c, op, acc, r, c, vname, c) for c in range(cols)))
    return '\n'.join(out)


def decl_zero(acc, rows, cols):
    names = ['%s%d%d' % (acc, r, c) for r in range(rows) for c in range(cols)]
    return '                v128_t %s = wasm_f64x2_splat(0), %s;' % (names[0], ', '.join('%s = %s' % (n, names[0]) for n in names[1:]))


def loads(vname, ptr, cols):
    return '                    const v128_t %s;' % ', '.join('%s%d = wasm_v128_load(%s + %d)' % (vname, c, ptr, 2 * c) for c in range(cols))


def stores(acc, rows, cols, dst):
    return '\n'.join('                ' + ' '.join('wasm_v128_store(%s + %d, %s%d%d);' % (dst(r), 2 * c, acc, r, c) for c in range(cols)) for r in range(rows))
