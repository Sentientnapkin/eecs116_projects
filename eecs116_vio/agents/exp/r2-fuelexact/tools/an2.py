"""an2.py OUTDIR : per-call inclusive cost of update()/feature_rows/line_rows on each flight's top frames, and a fit of
update cost vs (k, D)."""
import glob, sys, os, numpy as np
T = ['update', 'feature_rows', 'line_rows', 'edge_rows', 'build_rows']
allev = []
for f in sorted(glob.glob(sys.argv[1] + '/*.npz')):
    z = np.load(f); tot, ev = z['tot'], z['ev']; allev.append(ev)
    print(os.path.basename(f)[:-4])
    for fr in np.argsort(-tot)[:3]:
        e = ev[ev[:, 0] == fr]
        print(f"  frame {fr} tot {tot[fr]/1e3:.0f}k:", ' '.join(f"{T[t][:4]}(k{k},D{d})={c/1e3:.0f}k" for _, t, k, d, c in e if t == 0 or c > 3e4))
ev = np.concatenate(allev); u = ev[ev[:, 1] == 0]
print('\nupdate calls by k (all frames): k  n  mean-cost  mean-D')
for k in np.unique(u[:, 2]):
    m = u[u[:, 2] == k]
    if len(m) > 20 or k > 20: print(f"  k={k:3d} n={len(m):6d} cost {m[:,4].mean()/1e3:7.1f}k  D {m[:,3].mean():.1f}")
print('total update fuel by k class: small (k<=3) %.1f%%' % (100 * u[u[:, 2] <= 3, 4].sum() / u[:, 4].sum()))
