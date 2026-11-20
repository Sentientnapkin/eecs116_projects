#!/bin/bash
# compact table of all learned_* reports
cd /data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model
for d in learned_*; do [ -f $d/report.txt ] || continue; python3 - $d <<'P'
import sys,re
d=sys.argv[1]; L=open(d+'/report.txt').read().splitlines()[1:]
o={}
for l in L:
    m=re.match(r'(\w+)\s+(\w+)\s+n=\s*\d+ mean\s+([\d.]+) .*?>5m\s+(\d+) >10m\s+(\d+) \| paired d=([+-][\d.]+) \[([+-][\d.]+),([+-][\d.]+)\]',l)
    if m: o[(m.group(1),m.group(2))]=(m.group(3),m.group(6),m.group(7),m.group(8),m.group(4),m.group(5))
f=lambda k:(f"{o[k][0]} ({o[k][1]}[{o[k][2]},{o[k][3]}])" if k in o else '-')
print(f"{d[8:]:22s} search {f(('search','all')):30s} mid {o.get(('search','mid'),['-'])[0]:6s} static {o.get(('search','static'),['-'])[0]:6s} >5m {o.get(('search','all'),['','','','','-'])[4]:>2s} | val {f(('val','all')):30s} mid {o.get(('val','mid'),['-'])[0]:6s} static {o.get(('val','static'),['-'])[0]:6s}")
P
done
