"""cmp.py BASE_DIR CAND_DIR : bitwise parity of per-frame poses+twists (prof.py outputs) and fuel ratios per flight."""
import glob, os, sys, numpy as np
ok = True; rows = []
for f in sorted(glob.glob(sys.argv[1] + '/*.npz')):
    n = os.path.basename(f); g = os.path.join(sys.argv[2], n)
    if not os.path.exists(g): print('missing', n); ok = False; continue
    a, b = np.load(f), np.load(g)
    pa, pb = a['poses'], b['poses']
    same = pa.shape == pb.shape and np.array_equal(pa.view(np.uint64), pb.view(np.uint64))
    ok &= same
    ta, tb = a['tot'].astype(float), b['tot'].astype(float)
    rows.append((ta.max(), tb.max(), ta.mean(), tb.mean()))
    nd = '' if same else ' first diff frame %d' % int(np.argmax((pa != pb).any(1))) if pa.shape == pb.shape else ' shape'
    print(f"{n[:-4]:22s} {'IDENTICAL' if same else 'DIFFERENT'}{nd}  max {ta.max()/1e6:.3f} -> {tb.max()/1e6:.3f}M ({100*(tb.max()/ta.max()-1):+.1f}%)  mean {ta.mean()/1e6:.3f} -> {tb.mean()/1e6:.3f}M ({100*(tb.mean()/ta.mean()-1):+.1f}%)  frame-max-ratio {np.max(tb/ta):.3f}")
r = np.array(rows)
print(f"ALL {'IDENTICAL' if ok else 'NOT IDENTICAL'}: max {r[:,0].max()/1e6:.3f} -> {r[:,1].max()/1e6:.3f}M ({100*(r[:,1].max()/r[:,0].max()-1):+.1f}%), mean {100*(r[:,3].sum()/r[:,2].sum()-1):+.1f}%")
