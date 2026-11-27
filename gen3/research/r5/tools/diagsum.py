import sys,glob,re,collections as C
name=sys.argv[1];pool=sys.argv[2] if len(sys.argv)>2 else 'mid40'
S=C.Counter();n=0
for f in glob.glob(f'/data/backups/rganapa/Sebastian/gen3/evals/{name}/{pool}/*/*/report/logs/*/stderr.txt'):
    L=[l for l in open(f) if l.startswith('R5 ')]
    if not L: continue
    n+=1
    for k,v in re.findall(r'(\w+)=(-?\d+)',L[-1]): S[k]+=int(v)
print(name,'flights',n,{k:round(v/n,1) for k,v in S.items() if k!='f'})
