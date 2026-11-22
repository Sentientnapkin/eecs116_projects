from pathlib import Path
import sys
import numpy as np
w=Path(__file__).resolve().parent
name=sys.argv[1] if len(sys.argv)>1 else 'check'
vals={}
for f in (w.parents[1]/('results/single_model/lj_'+name+'/check12')).glob('**/stderr.txt'):
 for l in f.read_text().splitlines():
  if l.startswith('AJ '):
   _,k,r,a=l.split(); vals.setdefault(int(k),[]).append((float(r),float(a)))
s=[]
for k,vs in sorted(vals.items()):
 a=np.array(vs);s.append(f'kind {k}: n={len(a)}, relative max={a[:,0].max():.3g}, p99={np.percentile(a[:,0],99):.3g}, absolute max={a[:,1].max():.3g}')
t='\n'.join(s);print(t);(w/('tables/'+name+'.txt')).write_text(t+'\n')
