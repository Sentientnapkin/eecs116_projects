import pickle,sys,json,glob,numpy as np
from pathlib import Path
sys.path.insert(0,'.')
from research.single_model.run_variant import ate_rows
r=pickle.load(open('research/results/single_model/texture_dbg/perflight.pkl','rb'))
sel=[e for e,d in r.items() if d['slice']=='search' and (np.mean(d['c']['long'][:40])<6 or np.mean(d['c']['bright'])<60 or (d['start']=='static' and d['ate']>1.2))]
print('flight (start, flat, bright): base | arms')
A={n:ate_rows(Path(glob.glob(f'research/results/single_model/texture_{n}/eval/*/scores.json')[0])) for n in sys.argv[1:]}
for e in sel:
    d=r[e]; print(e[-14:],d['start'],round(d['flat'],2),round(float(np.mean(d['c']['bright']))),f"{d['ate']:.2f} |",' '.join(f"{n}:{A[n][e]:.2f}" for n in A))
