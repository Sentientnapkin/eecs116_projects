import sys, json, numpy as np
sys.path.insert(0,'/data/backups/rganapa/Sebastian/eecs116_projects')
from research.single_model import run_variant as RV
H='/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/'
ref={r['episode']:r for r in json.load(open(H+'fresh/table_gate.json'))}
for n in sys.argv[1:]:
    t={r['episode']:r for r in json.load(open(H+f'fuel/fresh_table_{n}.json'))}
    ks=sorted(ref); x=[ref[k]['ate'] for k in ks]; y=[t[k]['ate'] for k in ks]
    d,lo,hi=RV.paired(x,y,[ref[k]['scene'] for k in ks])
    pk=max(r['peak_fuel'] for r in t.values())/1e6
    print(f"{n:9s} fresh n={len(ks)} gate {np.mean(x):.4f} arm {np.mean(y):.4f} | d {d:+.4f} [{lo:+.4f},{hi:+.4f}] | >5m {sum(v>5 for v in x)}->{sum(v>5 for v in y)} >10m {sum(v>10 for v in x)}->{sum(v>10 for v in y)} | max {max(x):.1f}->{max(y):.1f} | peak {pk:.2f}M")
    for st in ('static','mid'):
        s=[k for k in ks if ref[k]['start']==st]; print('    ',st,len(s),'gate %.3f arm %.3f'%(np.mean([ref[k]['ate'] for k in s]),np.mean([t[k]['ate'] for k in s])))
