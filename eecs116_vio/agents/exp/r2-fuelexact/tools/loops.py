"""loops.py FILE.s FUNC : innermost loops of FUNC in a wasm .s: line, instruction count, f64x2/f64 mul counts, local ops."""
import re, sys
L = open(sys.argv[1]).read().split('\n')
st = next(i for i, l in enumerate(L) if l.startswith(sys.argv[2] + ':'))
en = next(i for i in range(st + 1, len(L)) if L[i].strip().startswith('end_function'))
body = L[st:en]; stack = []
def ins(l):
    t = l.split('#')[0].strip()
    return t if t and not t.endswith(':') and not t.startswith('.') else None
for i, l in enumerate(body):
    t = ins(l)
    if t is None: continue
    if t.startswith('loop'): stack.append([i, False])
    elif t.startswith('end_loop'):
        s, nested = stack.pop()
        if stack: stack[-1][1] = True
        if nested: continue
        seg = [ins(x) for x in body[s + 1:i]]; seg = [x for x in seg if x and x.split()[0] not in ('block', 'end_block', 'nop', 'drop', 'end_if', 'else', 'end_loop')]
        op = [x.split()[0] for x in seg]
        print(f"line {st+s+1}: n={len(op)} mul2={op.count('f64x2.mul')} add/sub2={op.count('f64x2.add')+op.count('f64x2.sub')} mul={op.count('f64.mul')} "
              f"get={op.count('local.get')} set={op.count('local.set')+op.count('local.tee')} load={sum('load' in o for o in op)} store={sum('store' in o for o in op)}")
