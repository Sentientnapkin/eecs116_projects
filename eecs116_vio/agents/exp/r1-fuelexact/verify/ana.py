"""ana.py DIR [twin120.txt] : bitwise parity, non-finite outputs, fuel distribution, twin120 episode means."""
import glob, os, sys, numpy as np
d = sys.argv[1]; rows = []; bad = []; nonfin = []; fails = []
for f in sorted(glob.glob(d + "/*.npz")):
    z = np.load(f); n = os.path.basename(f)[:-4]
    eb, ec = z["eb"], z["ec"]
    same = eb.shape == ec.shape and np.array_equal(eb.view(np.uint64), ec.view(np.uint64))
    if not same:
        m = np.nanmax(np.abs(eb - ec)); fd = int(np.argmax((eb.view(np.uint64) != ec.view(np.uint64)).any(1)))
        bad.append((n, fd, m))
    if not np.isfinite(eb).all() or not np.isfinite(ec).all(): nonfin.append((n, int((~np.isfinite(eb)).any(1).sum()), int((~np.isfinite(ec)).any(1).sum())))
    if str(z["xb"]) or str(z["xc"]): fails.append((n, str(z["xb"]), str(z["xc"])))
    fb, fc = z["fb"], z["fc"]
    rows.append((n, fb.max(), fc.max(), fb.mean(), fc.mean(), (fc / fb).max(), float(z["ab"]), float(z["ac"]), len(eb)))
print(f"flights {len(rows)}  frames {sum(r[8] for r in rows)}  bit-identical {len(rows)-len(bad)}/{len(rows)}")
print("DIFFERENT:", bad); print("non-finite rows (base, cand):", nonfin); print("failures:", fails)
mb = np.array([r[1] for r in rows]); mc = np.array([r[2] for r in rows])
print(f"peak base {mb.max():,.0f} ({rows[int(mb.argmax())][0]})  cand {mc.max():,.0f} ({rows[int(mc.argmax())][0]})  ratio {mc.max()/mb.max():.4f}")
print(f"per-flight max: median base {np.median(mb):,.0f} cand {np.median(mc):,.0f}; p90 {np.percentile(mb,90):,.0f} {np.percentile(mc,90):,.0f}")
print(f"mean fuel ratio {sum(r[4] for r in rows)/sum(r[3] for r in rows):.4f}; max per-frame cand/base ratio {max(r[5] for r in rows):.3f}")
top = sorted(rows, key=lambda r: -r[2])[:6]; print("top cand flights:", [(r[0], int(r[2]), int(r[1])) for r in top])
print("per-class cand max:", {c: int(max(r[2] for r in rows if f"-{c}-" in r[0])) for c in ("ro", "wa", "fo") if any(f"-{c}-" in r[0] for r in rows)})
print("per-class flights:", {c: sum(f"-{c}-" in r[0] for r in rows) for c in ("ro", "wa", "fo")})
if len(sys.argv) > 2:
    ate = {r[0]: (r[6], r[7]) for r in rows}; ep = {}
    for l in open(sys.argv[2]).read().splitlines():
        if l.strip(): e, n = l.split("\t")[:2]; ep.setdefault(int(e), []).append(ate[n.strip()])
    mb_ = np.mean([np.mean([a for a, _ in v]) for v in ep.values()]); mc_ = np.mean([np.mean([b for _, b in v]) for v in ep.values()])
    print(f"twin120 (episode means) base {mb_:.4f} cand {mc_:.4f}")
