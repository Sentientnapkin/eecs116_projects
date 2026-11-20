"""usage: cmp.py name [name...]  (tables table_fd_<name>.json); compares to B7 (store) on pool_stress: starved31, dev/confirm, ext pool"""
import json,sys,numpy as np
D='research/single_model/flatdark/'
R={r['ep']:r for r in json.load(open(D+'stress_all.json'))}
eps=json.load(open(D+'stress_ext_eps.json'))
def row(tab,sel,lab):
    a=np.array([tab[e] for e in sel if tab.get(e) is not None]); 
    return f"{lab}: n{len(a)} mean {a.mean():.2f} >3:{(a>3).sum()} >5:{(a>5).sum()} >10:{(a>10).sum()}"
sets={'starved31':[e for e in eps if R[e]['live']<25],
      'starved dev':[e for e in eps if R[e]['live']<25 and R[e]['fold']<=2],
      'starved conf':[e for e in eps if R[e]['live']<25 and R[e]['fold']>=3],
      'ext dev':[e for e in eps if R[e]['fold']<=2],'ext conf':[e for e in eps if R[e]['fold']>=3],
      'nonstarved ext':[e for e in eps if R[e]['live']>=25]}
tabs={'B7':{e:R[e]['B7'] for e in eps}}
for n in sys.argv[1:]: tabs[n]=json.load(open(D+f'table_fd_{n}.json'))
for sn,sel in sets.items():
    print('==',sn)
    for n,t in tabs.items(): print('  ',n.ljust(14),row(t,sel,''))
if len(sys.argv)>1:
    for n in sys.argv[1:]:
        ch=[e for e in eps if abs(tabs[n][e]-tabs['B7'][e])>1e-9]
        print(n,'flights changed vs B7:',len(ch),'of',len(eps))
