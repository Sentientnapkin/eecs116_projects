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


def chain(accn, rows, cols, U, op, var, n, step, vexpr, cexpr, ind='                '):
    """r2 (R2_CHAIN): the same accumulation, U iterations per pass with each accumulator update written as one expression
    acc = op(op(acc, c0*v0), c1*v1) ... so the partial sums stay on the wasm operand stack (one local.get/local.set per U
    multiply-adds instead of per one). The order of the operations on every accumulator is unchanged.
    accn(r, c): accumulator name; vexpr(u, c) / cexpr(u, r): vector and splat operands of sub-iteration u;
    step(m): C expression list that advances the pointers by m iterations ('' if none)."""
    def body(uu):
        L = []
        L.append(ind + '    const v128_t %s;' % ', '.join('vv%d_%d = %s' % (u, c, vexpr(u, c)) for u in range(uu) for c in range(cols)))
        L.append(ind + '    const v128_t %s;' % ', '.join('cc%d_%d = %s' % (u, r, cexpr(u, r)) for u in range(uu) for r in range(rows)))
        for r in range(rows):
            parts = []
            for c in range(cols):
                e = accn(r, c)
                for u in range(uu):
                    e = 'wasm_f64x2_%s(%s, wasm_f64x2_mul(cc%d_%d, vv%d_%d))' % (op, e, u, r, u, c)
                parts.append('%s = %s;' % (accn(r, c), e))
            L.append(ind + '    ' + ' '.join(parts))
        return L
    st = lambda m: (', ' + step(m)) if step(m) else ''
    L = [ind + 'for (; %s + %d <= %s; %s += %d%s) {' % (var, U, n, var, U, st(U))] + body(U) + [ind + '}']
    L += [ind + 'for (; %s < %s; %s++%s) {' % (var, n, var, st(1))] + body(1) + [ind + '}']
    return '\n'.join(L)
