import json,sys,statistics as s
n,p=sys.argv[1],sys.argv[2];E='/data/backups/rganapa/Sebastian/gen3/evals/'
a={r['id']:r for r in json.load(open(E+f'cg_{n}__{p}.json'))}
b={r['id']:r for r in json.load(open(E+'cg_goats__v3val.json'))+json.load(open(E+'cg_goats__v1val.json'))}
c={r['id']:r for r in json.load(open(E+'net_auto_727_sp10__v3val.json'))+json.load(open(E+'net_auto_727_sp10__v1val.json'))}
ids=[i for i in a if a[i]['ate'] is not None]
print(n,' '.join(f"{a[i]['ate']:.2f}" for i in ids),'| mean %.3f goats %.3f gslv %.3f peak %.2fM n %d'%(s.mean(a[i]['ate'] for i in ids),s.mean(b[i]['ate'] for i in ids),s.mean(c[i]['ate'] for i in ids),max(a[i]['peak'] for i in ids)/1e6,len(ids)))
