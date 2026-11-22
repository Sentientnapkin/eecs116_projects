import sys, glob, numpy as np
for f in sorted(glob.glob(sys.argv[1] + '/*.npz'))[:4]:
    z = np.load(f); seg, vals, cnt = z['seg'], z['vals'], z['cnt']; tot = seg.sum(1)
    top = np.argsort(-tot)[:6]
    print(f.split('/')[-1][:30], 'median', round(np.median(tot)/1e6, 2))
    for i in sorted(top):
        comp = {k: seg[i, k]/1e6 for k in (13, 12, 11, 33, 14, 8, 5, 30, 9, 3, 20, 27, 21, 22, 23, 24) if seg[i, k] > 1e5}
        print(f"  frame {i:4d} (mod4={i%4}) tot {tot[i]/1e6:.2f}M nbatch {int(vals[i,40])} rows {int(vals[i,41])} upd-calls {int(cnt[i,13])}", {k: round(v, 2) for k, v in comp.items()})
