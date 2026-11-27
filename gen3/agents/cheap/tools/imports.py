"""imports.py WASM: list the import section (module.name kind) of a wasm binary."""
import sys
b = open(sys.argv[1], 'rb').read(); assert b[:4] == b'\0asm'
def leb(i):
    r = s = 0
    while True:
        x = b[i]; i += 1; r |= (x & 0x7f) << s; s += 7
        if x < 0x80: return r, i
i = 8; out = []
while i < len(b):
    sid = b[i]; n, i = leb(i + 1); end = i + n
    if sid == 2:
        cnt, i = leb(i)
        for _ in range(cnt):
            l, i = leb(i); m = b[i:i + l].decode(); i += l; l, i = leb(i); f = b[i:i + l].decode(); i += l
            k = b[i]; i += 1
            if k == 0: _, i = leb(i)
            elif k == 1: i += 1; fl, i = leb(i); _, i = leb(i); (i := leb(i)[1]) if fl & 1 else None
            elif k == 2: fl, i = leb(i); _, i = leb(i); (i := leb(i)[1]) if fl & 1 else None
            elif k == 3: i += 2
            out.append(f'{m}.{f} kind={k}')
    i = end
print(len(out), 'imports'); print('\n'.join(out))
