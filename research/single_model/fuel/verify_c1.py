"""usage: verify_c1.py RUN [REF=inv_adopted]  -- visible (search+val) byte identity of estimate.tum vs REF run + fuel stats; fold 4 never read."""
import sys,glob,json,numpy as np; sys.path.insert(0,'.')
from research.single_model import run_variant as RV
run=sys.argv[1]; ref=sys.argv[2] if len(sys.argv)>2 else 'inv_adopted'
tg=RV.tags(); R='research/results/single_model/'
vis=[e for e in tg if RV.slice_of(RV.fold(tg[e]))!='sealed']
def p(r,e):
    g=glob.glob(R+f'{r}/eval/*/{e}/report/logs/*/estimate.tum'); return g[0] if g else None
n=same=0
for e in vis:
    a,b=p(ref,e),p(run,e)
    if a and b: n+=1; same+=open(a,'rb').read()==open(b,'rb').read()
print(f'{run} vs {ref}: visible flights {n}, estimate.tum byte-identical {same}')
S=set(vis)
for r in (ref,run):
    d=[x for x in json.load(open(glob.glob(R+r+'/eval/*/scores.json')[0]))['rows'] if x['episode'] in S]
    print(f'  {r:12s} search+val n={len(d)} peak {max(x["peak_fuel_per_frame"] for x in d)/1e6:.2f}M median-of-peaks {np.median([x["peak_fuel_per_frame"] for x in d])/1e6:.2f} mean p95 {np.mean([x["p95_fuel_per_frame"] for x in d])/1e6:.2f} mean median {np.mean([x["median_fuel_per_frame"] for x in d])/1e6:.2f}')
