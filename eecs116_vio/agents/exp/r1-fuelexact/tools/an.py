"""an.py OUTDIR IDS [topN] : per-phase self fuel: mean over all frames, mean over each flight's top-N frames, and the
breakdown of each flight's peak frame. Also counts and PV values (gov_used k = vals[43], rows = vals[45])."""
import glob, sys, os, numpy as np
d, idf = sys.argv[1], sys.argv[2]; top = int(sys.argv[3]) if len(sys.argv) > 3 else 10
nm = {0: 'step(other)'}
for l in open(idf): i, n = l.split(); nm[int(i)] = n
S, P, C = [], [], []
for f in sorted(glob.glob(d + '/*.npz')):
    z = np.load(f); seg, tot, cnt, vals = z['seg'], z['tot'], z['cnt'], z['vals']
    S.append(seg); o = np.argsort(-tot)[:top]; P.append(seg[o]); C.append(cnt[o])
    k = o[0]; s = seg[k]
    print(f"{os.path.basename(f)[:-4]}: max {tot.max()/1e6:.3f}M p99 {np.percentile(tot,99)/1e6:.2f} med {np.median(tot)/1e6:.2f} | peak frame {k} gov_used {vals[k,43]}k rows {vals[k,45]} nb {vals[k,39]} units {vals[k,17]} cells {vals[k,16]} map {vals[k,18]}")
    print('   ', ', '.join(f"{nm.get(i,i)} {s[i]/1e3:.0f}k({cnt[k,i]})" for i in np.argsort(-s)[:12] if s[i] > 2e4))
    print('    top frames:', ' '.join(f"{i}:{tot[i]/1e6:.2f}" for i in sorted(o)))
S = np.concatenate(S); P = np.concatenate(P); C = np.concatenate(C)
ms, mp = S.mean(0), P.mean(0)
print(f"\nphase                 mean/frame   share | top-{top} frames mean  share  calls")
for i in np.argsort(-mp)[:30]:
    print(f"{nm.get(i,i):22s} {ms[i]/1e3:9.0f}k {100*ms[i]/ms.sum():5.1f}% | {mp[i]/1e3:9.0f}k {100*mp[i]/mp.sum():5.1f}% {C[:,i].mean():7.1f}")
print(f"{'TOTAL':22s} {ms.sum()/1e3:9.0f}k        | {mp.sum()/1e3:9.0f}k")
