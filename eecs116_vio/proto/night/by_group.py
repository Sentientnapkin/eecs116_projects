"""Per-group view of variant results (night/var_*.txt from variant.sh).

For every variant: mean ATE over all 61 flights, per flight group (night groups + the older sets), the jerky groups
together, and how many flights end up worse than "never moved".
    python by_group.py [variant names...]     (default: all, sorted by overall mean)
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NIGHT = os.path.expanduser("~/data/night")
group_of = {}
for g in sorted(os.listdir(NIGHT)):
    for f in glob.glob(f"{NIGHT}/{g}/*.zip"):
        group_of[os.path.basename(f)[:-4][:30]] = g

line_re = re.compile(r"^(\S+)\s+ATE\s+([\d.]+)\s+zeros\s+([\d.]+)")
rows = {}
for path in glob.glob(f"{HERE}/var_*.txt"):
    name = os.path.basename(path)[4:-4]
    section, flights = None, []
    for line in open(path):
        if line.startswith("=== "):
            section = line[4:].strip()
            continue
        m = line_re.match(line)
        if m and m.group(1) != "MEAN":
            key = m.group(1)[:30]
            group = group_of.get(key, "?") if section == "NIGHT" else section.lower()
            flights.append((group, float(m.group(2)), float(m.group(3))))
    if len(flights) >= 55:
        rows[name] = flights

wanted = sys.argv[1:] or sorted(rows, key=lambda n: sum(f[1] for f in rows[n]) / len(rows[n]))
groups = ["jerky", "jerky_wide", "vfast", "fov150", "fov90", "match", "match2", "medium", "hover", "agile2", "tune", "heldout"]
print(f"{'variant':16s} {'ALL':>5s} {'JERKY':>5s} {'worse':>5s} | " + " ".join(f"{g[:7]:>7s}" for g in groups))
for n in wanted:
    fl = rows[n]
    mean = lambda sel: sum(f[1] for f in sel) / max(len(sel), 1)
    jerky = [f for f in fl if f[0] in ("jerky", "jerky_wide")]
    worse = sum(f[1] > f[2] for f in fl)
    print(f"{n:16s} {mean(fl):5.2f} {mean(jerky):5.2f} {worse:5d} | "
          + " ".join(f"{mean([f for f in fl if f[0] == g]):7.2f}" for g in groups))
