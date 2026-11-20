import re,glob,os,sys
rows=[]
for f in sorted(glob.glob('arm_*.txt')):
    t=open(f).read()
    if 'search all' not in t: continue
    n=f[4:-4]
    def g(tag):
        m=re.search(tag+r'\s+n=\s*\d+ mean\s+([\d.]+) \(base\s+[\d.]+\) median\s+([\d.]+) p90\s+([\d.]+) >5m\s+(\d+) >10m\s+(\d+) \| paired d=([+-][\d.]+) \[([+-][\d.]+),([+-][\d.]+)\]',t)
        return m.groups() if m else None
    a=g('search all');s=g('search static');m=g('search mid');v=g('val    all');vm=g('val    mid')
    rows.append((n,a,s,m,v,vm))
print('| arm | search mean | median | d [95% CI] | mid | static (d) | >5 / >10 m | val mean | val mid |')
print('|---|---|---|---|---|---|---|---|---|')
for n,a,s,m,v,vm in rows:
    print(f'| {n} | {a[0]} | {a[1]} | {a[5]} [{a[6]},{a[7]}] | {m[0]} | {s[0]} ({s[5]}) | {a[3]} / {a[4]} | {v[0] if v else "-"} | {vm[0] if vm else "-"} |')
