"""Score variants on the HF server-calibrated set (outputs of hf_var.sh).

Scenes are split in two by a hash of the scene name: TUNE (choose settings here) and CHECK (never tuned on).
    python hf_sum.py NAME --line          one summary line (used by hf_var.sh)
    python hf_sum.py [NAME ...]           table, default all variants sorted by TUNE mean
    python hf_sum.py A B --flights        per-flight comparison of two variants
"""
import glob
import json
import os
import re
import sys
import zlib

import numpy as np

H = os.path.dirname(os.path.abspath(__file__))
MANIFEST = "/mnt/c/Users/alexa/AppData/Local/Temp/claude/c501a6732310c193/cf501e9a-f739-4dcf-b5ae-aa78f93c24f1/scratchpad/hfcal/manifest.json"
if not os.path.exists(MANIFEST):
    MANIFEST = f"{H}/manifest.json"
man = {os.path.basename(e["file"]): e for e in json.load(open(MANIFEST))["episodes"]}
line_re = re.compile(r"^(\S+)\s+ATE\s+([\d.]+)\s+zeros\s+([\d.]+)")
chunks = sorted(glob.glob(f"{H}/chunks/c*"))


def load(name):
    res = {}
    for c in chunks:
        files = [os.path.basename(l.strip()) for l in open(c) if l.strip()]
        out = f"{H}/out/{name}_{os.path.basename(c)}.txt"
        if not os.path.exists(out):
            return None
        vals = [(float(m.group(2)), float(m.group(3))) for m in map(line_re.match, open(out)) if m and m.group(1) != "MEAN"]
        if len(vals) != len(files):
            return None
        res.update(zip(files, vals))
    return res


def is_tune(f):
    return zlib.crc32(man[f]["scene"].encode()) % 2 == 0


def stats(res):
    fl = sorted(res)
    a = lambda sel: np.mean([res[f][0] for f in sel]) if sel else float("nan")
    tune = [f for f in fl if is_tune(f)]
    check = [f for f in fl if not is_tune(f)]
    return dict(all=a(fl), tune=a(tune), check=a(check), nothing=np.mean([res[f][1] for f in fl]),
                worse=sum(res[f][0] > res[f][1] for f in fl),
                rest=a([f for f in fl if man[f]["start_offset_s"] == 0]),
                mid=a([f for f in fl if man[f]["start_offset_s"] > 0]),
                procthor=a([f for f in fl if man[f]["catalog"] == "procthor"]),
                hssd=a([f for f in fl if man[f]["catalog"] != "procthor"]),
                median=np.median([res[f][0] for f in fl]), n=len(fl), ntune=len(tune))


COLS = ["tune", "check", "all", "median", "worse", "rest", "mid", "procthor", "hssd"]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--line" in sys.argv:
        s = stats(load(args[0]))
        print(f"{args[0]:22s} " + " ".join(f"{k} {s[k]:.3f}" if k != "worse" else f"worse {s[k]}" for k in COLS))
        return
    if "--flights" in sys.argv:
        A, B = load(args[0]), load(args[1])
        for f in sorted(A, key=lambda f: B[f][0] - A[f][0]):
            e = man[f]
            print(f"{f:42s} {args[0]} {A[f][0]:5.2f}  {args[1]} {B[f][0]:5.2f}  nothing {A[f][1]:5.2f}  {e['catalog']:10s} "
                  f"start+{e['start_offset_s']:4.1f}s travel {e['travel_m']:3.0f} m  {'TUNE' if is_tune(f) else 'check'}")
        return
    names = args or [os.path.basename(p)[:-8] for p in glob.glob(f"{H}/out/*_c00.txt")]
    rows = [(n, stats(r)) for n in names if (r := load(n))]
    if not args:
        rows.sort(key=lambda x: x[1]["tune"])
    first = rows[0][1]
    print(f"{first['n']} flights ({first['ntune']} tune / {first['n'] - first['ntune']} check), doing nothing {first['nothing']:.2f} m")
    print(f"{'variant':22s} " + " ".join(f"{c:>8s}" for c in COLS))
    for n, s in rows:
        print(f"{n:22s} " + " ".join(f"{s[c]:8d}" if c == "worse" else f"{s[c]:8.3f}" for c in COLS))


if __name__ == "__main__":
    main()
