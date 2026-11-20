import json,glob,sys
sys.path.insert(0,'.')
from research.single_model.run_variant import tags,fold
R='research/results/single_model/'
def L(n): return {r['episode']:r for r in json.load(open(glob.glob(R+n+'/eval/*/scores.json')[0]))['rows']}
G=L('inv_gbase_r0');C=L('preflight_c1_a');H=L('inv_hold');V=L('inv_vzlat')
au=json.load(open('research/single_model/final/preflight_c1/hold_audit_flights_preflight_c1_dbg.json'))
tg=tags();n4=0
print('flight start fold | G | hold-only | vz+lat-only | C1 | hold active frames | attribution (hold-only dG, vz+lat-only dG vs C1 dG)')
for e in sorted(G):
    if abs(C[e]['ate_full']-G[e]['ate_full'])<=0.3: continue
    if fold(tg[e])==4: n4+=1; continue
    g,c,h,v=G[e]['ate_full'],C[e]['ate_full'],H[e]['ate_full'],V[e]['ate_full']
    a=au[e]; 
    why='mid: hold inactive (detector moving); change from vz/lat priors (chaotic vision path)' if a['moving'] else ('hold never ran (gyro>0.12 at frame 8); change from vz/lat' if a['n_active']==0 else 'hold ran 13 frames')
    print(f"{e} {tg[e]['start']} f{fold(tg[e])} | G {g:.2f} | hold {h:.2f} ({h-g:+.2f}) | vzlat {v:.2f} ({v-g:+.2f}) | C1 {c:.2f} ({c-g:+.2f}) | act {a['n_active']} | {why}")
print('fold-4 flights >0.3 (not listed):',n4)
