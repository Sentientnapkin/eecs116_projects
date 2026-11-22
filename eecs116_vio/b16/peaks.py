import sys, glob, numpy as np, os
d = os.path.expanduser(f"~/ws_m/report_{sys.argv[1]}")
for f in sorted(glob.glob(f"{d}/**/fuel*.npy", recursive=True)):
    a = np.load(f); a = a.ravel()
    top = np.argsort(a)[::-1][:8]
    print(os.path.relpath(f, d)[:40], f"max {a.max()/1e6:.2f}M med {np.median(a)/1e6:.2f}M", " ".join(f"{i}:{a[i]/1e6:.1f}" for i in sorted(top)))
