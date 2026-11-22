"""Table of eval/results/var_*.txt: mean ATE per flight group, overall, and flights worse than "never moved"."""
import glob
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
line_re = re.compile(r"^(\S+)\s+ATE\s+([\d.]+)\s+zeros\s+([\d.]+)")
rows, groups = {}, []
for path in sorted(glob.glob(f"{HERE}/results/var_*.txt")):
    name, group, flights = os.path.basename(path)[4:-4], None, []
    for line in open(path):
        if line.startswith("=== "):
            group = line[4:].strip()
            groups.append(group) if group not in groups else None
        m = line_re.match(line)
        if m and group and m.group(1) != "MEAN":
            flights.append((group, float(m.group(2)), float(m.group(3))))
    if flights:
        rows[name] = flights
mean = lambda sel: sum(f[1] for f in sel) / len(sel) if sel else float("nan")
print(f"{'variant':16s} {'flights':>7s} {'ALL':>5s} {'worse':>5s} {'zeros':>5s} | " + " ".join(f"{g[:11]:>11s}" for g in groups))
for name in sorted(rows, key=lambda n: mean(rows[n])):
    fl = rows[name]
    print(f"{name:16s} {len(fl):7d} {mean(fl):5.2f} {sum(f[1] > f[2] for f in fl):5d} {sum(f[2] for f in fl) / len(fl):5.2f} | "
          + " ".join(f"{mean([f for f in fl if f[0] == g]):11.2f}" for g in groups))
