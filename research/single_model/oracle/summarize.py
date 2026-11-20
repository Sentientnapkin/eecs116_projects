import re,glob,os
R='/data/backups/rganapa/Sebastian/eecs116_projects/research/results/single_model/'
def f(l):
    m=re.search(r'mean\s+([\d.]+).*?median\s+([\d.]+)',l); return m.group(1),m.group(2)
print('| arm | search all mean | static mean/med | mid mean/med | val all | val mid |')
print('|---|---|---|---|---|---|')
for p in sorted(glob.glob(R+'oracle_*/report.txt')):
    n=os.path.basename(os.path.dirname(p))[7:]; L=open(p).read().splitlines()
    g=lambda k:[l for l in L if l.startswith(k)]
    try:
        sa=f(g('search all')[0]);ss=f(g('search static')[0]);sm=f(g('search mid')[0]);va=f(g('val    all')[0]);vm=f(g('val    mid')[0])
        print(f'| {n} | {sa[0]} | {ss[0]}/{ss[1]} | {sm[0]}/{sm[1]} | {va[0]} | {vm[0]} |')
    except Exception as e: print(n,'parse fail')
