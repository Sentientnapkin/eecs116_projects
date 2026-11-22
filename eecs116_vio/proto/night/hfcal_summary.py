"""Summarize v3/v4a/v4b on the public server-calibrated set (night/hfcal/, written by hf_eval.sh).

Diag lines are matched to episodes by order within each chunk (episode names repeat in this set).
    python hfcal_summary.py MANIFEST.json
"""
import glob
import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
R = f"{HERE}/{sys.argv[2] if len(sys.argv) > 2 else 'hfcal'}"
man = {os.path.basename(e["file"]): e for e in json.load(open(sys.argv[1]))["episodes"]}
line_re = re.compile(r"^(\S+)\s+ATE\s+([\d.]+)\s+zeros\s+([\d.]+)")
LIBS = [("v3", "base"), ("v4a", "fl_sc_sw6"), ("v4b", "fl_sc_sw8")]

res = {}  # label -> {zip: (ate, zeros)}
for label, lib in LIBS:
    res[label] = {}
    for chunk in sorted(glob.glob(f"{R}/chunk_0*")):
        files = [os.path.basename(l.strip()) for l in open(chunk) if l.strip()]
        lines = [line_re.match(l) for l in open(f"{R}/{lib}_{os.path.basename(chunk)}.txt")]
        vals = [(float(m.group(2)), float(m.group(3))) for m in lines if m and m.group(1) != "MEAN"]
        if len(vals) != len(files):
            print(f"WARNING {lib} {chunk}: {len(vals)} results for {len(files)} files")
        res[label].update(zip(files, vals))

common = sorted(set.intersection(*(set(r) for r in res.values())))
zeros = np.array([res["v3"][f][1] for f in common])
print(f"{len(common)} episodes; doing nothing {zeros.mean():.2f} m "
      f"(manifest says {np.mean([man[f]['zero_motion_ate_m'] for f in common]):.2f})")


def groups():
    yield "all", common
    yield "starts at rest", [f for f in common if man[f]["start_offset_s"] == 0]
    yield "starts mid-flight", [f for f in common if man[f]["start_offset_s"] > 0]
    for cat in ("procthor", "hssd-train", "hssd-val"):
        yield cat, [f for f in common if man[f]["catalog"] == cat]
    yield "never-trained scenes", [f for f in common if man[f]["group"] == "clean"]


print(f"\n{'group':22s} {'n':>4s} {'nothing':>8s} " + " ".join(f"{l:>7s}" for l, _ in LIBS)
      + "   " + " ".join(f"{l + ' worse':>10s}" for l, _ in LIBS))
for name, sel in groups():
    z = np.mean([res["v3"][f][1] for f in sel])
    means = [np.mean([res[l][f][0] for f in sel]) for l, _ in LIBS]
    worse = [sum(res[l][f][0] > res[l][f][1] for f in sel) for l, _ in LIBS]
    print(f"{name:22s} {len(sel):4d} {z:8.2f} " + " ".join(f"{m:7.2f}" for m in means)
          + "   " + " ".join(f"{w:10d}" for w in worse))

print("\nmedian ATE: " + "  ".join(f"{l} {np.median([res[l][f][0] for f in common]):.2f}" for l, _ in LIBS))
a = np.array([res["v4a"][f][0] for f in common])
b = np.array([res["v4b"][f][0] for f in common])
print(f"v4a beats v4b on {np.sum(a < b)} of {len(common)} episodes")

# what a 12-flight server draw could look like
rng = np.random.default_rng(0)
idx = rng.integers(0, len(common), (20000, 12))
print("\n12-episode draws (like the server): mean ATE 5th / 50th / 95th percentile")
for l, _ in LIBS:
    v = np.array([res[l][f][0] for f in common])[idx].mean(1)
    print(f"  {l:4s} {np.percentile(v, 5):.2f} / {np.percentile(v, 50):.2f} / {np.percentile(v, 95):.2f}")
d = (a[idx] - b[idx]).mean(1)
print(f"  v4a beats v4b in {np.mean(d < 0) * 100:.0f}% of draws")

print("\nworst 8 episodes for v4a:")
for f in sorted(common, key=lambda f: -res["v4a"][f][0])[:8]:
    e = man[f]
    print(f"  {f:40s} v3 {res['v3'][f][0]:5.2f}  v4a {res['v4a'][f][0]:5.2f}  v4b {res['v4b'][f][0]:5.2f}  "
          f"nothing {res['v3'][f][1]:5.2f}  {e['catalog']:10s} start+{e['start_offset_s']:.0f}s  travel {e['travel_m']:.0f} m")
