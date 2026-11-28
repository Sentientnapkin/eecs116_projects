"""vpar2.py OUTDIR MODE CACHEDIR ZIP... : like vpar.py but reuses cached base outputs (eb,fb,xb,ab) from CACHEDIR and runs only r2."""
import os, sys, numpy as np
sys.argv = [sys.argv[0], sys.argv[1], sys.argv[2]] + sys.argv[3:]
cache = sys.argv.pop(3)
src = open("/mnt/c/Users/alexa/AppData/Local/Temp/claude/24df673cbfed4a36/7259d14f-b38a-4306-96ea-dba8960ce8af/scratchpad/par/vpar.py").read()
src = src.replace("r1-fuelexact/r1-fuelexact.wasm", "r2-fuelexact/r2-fuelexact.wasm")
head, loop = src.split("for p in sys.argv[3:]:")
exec(head)
for p in sys.argv[3:]:
    n = os.path.basename(p)[:-4]
    z = np.load(os.path.join(cache, n + ".npz"))
    eb, fb, xb, ab = z["eb"], z["fb"], str(z["xb"]), float(z["ab"])
    ec, fc, xc, ac = run(CAND, p, f"/tmp/vpar2_{os.getpid()}_c")
    np.savez(os.path.join(out, n + ".npz"), eb=eb, ec=ec, fb=fb, fc=fc, xb=xb, xc=xc, ab=ab, ac=ac)
    same = eb.shape == ec.shape and np.array_equal(eb.view(np.uint64), ec.view(np.uint64))
    print(n, "IDENTICAL" if same else "DIFFERENT", f"ate {ab:.4f} {ac:.4f} fmax {fb.max():.0f} {fc.max():.0f} fail[{xb}][{xc}]", flush=True)
