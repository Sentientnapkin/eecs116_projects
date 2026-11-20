import json,glob,numpy as np
R='research/results/single_model/'
a=json.load(open(glob.glob(R+'final_f0/eval/*/scores.json')[0]));b=json.load(open(glob.glob(R+'preflight_f0/eval/*/scores.json')[0]))
A={r['episode']:r for r in a['rows']};B={r['episode']:r for r in b['rows']}
print(len(A),len(B),set(A)==set(B))
print('ate_full bit-identical on',sum(A[e]['ate_full']==B[e]['ate_full'] for e in A),'of',len(A),'max abs diff',max(abs(A[e]['ate_full']-B[e]['ate_full']) for e in A))
print('guest sha',a['guest']['sha256'],b['guest']['sha256'])
for n,D in (('final',A),('pre',B)):
  print(n,'filled_full!=0',[e for e,r in D.items() if r['filled_full']],'incomplete',[e for e,r in D.items() if not r['completed']],'failure',[e for e,r in D.items() if r['failure']],'err',[e for e,r in D.items() if 'error' in r],'frames_attempted',set(r['frames_attempted'] for r in D.values()),'frames',set(r['frames'] for r in D.values()))
print([k for k in A[next(iter(A))] if 'fuel' in k])
for n,D in (('final',A),('pre',B)):
  mx=max(r['peak_fuel_per_frame'] for r in D.values()); p95=max(r['p95_fuel_per_frame'] for r in D.values()); print(n,'max per-frame fuel',mx,'worst-flight p95',p95, 'limit frac',mx/2e10)
  e=max(D,key=lambda e:D[e]['peak_fuel_per_frame']);print(' worst',e)
