from pathlib import Path
import sys
import numpy as np
w=Path(__file__).resolve().parent
tag=sys.argv[1] if len(sys.argv)>1 else 'base_detail'
fs=sorted((w/('prof/'+tag)).glob('*.npz'))
a=np.concatenate([np.load(f)['seg'] for f in fs]); t=np.concatenate([np.load(f)['tot'] for f in fs])
groups={'line tracking/detection':[60], 'line GN fit':[61], 'line update Jacobians':[62], 'line null-space/gating/row output':[59], 'velocity net':[3,20,21,22,23,24,25,26,27], 'rest MSCKF update':[11,12,13,14,15,28,29,31,32,33,34,35,36,37,48,49,50,51,52,53,54,55,56,57]}
rows=['| phase | peak frame M | mean of top 1% frames M |','|---|---:|---:|']
i=t.argmax(); top=t>=np.percentile(t,99); covered=np.zeros_like(t,dtype=float)
for name,ids in groups.items():
 v=a[:,ids].sum(axis=1);covered+=v;rows.append(f'| {name} | {v[i]/1e6:.3f} | {v[top].mean()/1e6:.3f} |')
v=t-covered;rows.append(f'| other | {v[i]/1e6:.3f} | {v[top].mean()/1e6:.3f} |');rows.append(f'| total | {t[i]/1e6:.3f} | {t[top].mean()/1e6:.3f} |')
s=f'\n## Refined profile: {tag}\n{len(fs)} st2dev flights, {len(t)} frames; p99 {np.percentile(t,99)/1e6:.3f} M. Host-marker build (small instrumentation overhead).\n'+'\n'.join(rows)+'\n'
print(s);(w/('prof/table_'+tag+'.md')).write_text(s)
if len(fs)==60:
 p=w/'NOTES.md';p.write_text(p.read_text()+s)
