import json,glob,numpy as np,sys
sys.path.insert(0,'.')
R='research/results/single_model/'
def L(n): return {r['episode']:r for r in json.load(open(glob.glob(R+n+'/eval/*/scores.json')[0]))['rows']}
for n in ('fgt_merged','fgt_merged_b','final_f0','preflight_gate_a','tails_adopted'):
    D=L(n); pk=[r['peak_fuel_per_frame'] for r in D.values()]; p95=[r['p95_fuel_per_frame'] for r in D.values()]
    print(n,'n',len(D),'filled_full!=0',sum(bool(r['filled_full']) for r in D.values()),'incomplete',sum(not r['completed'] for r in D.values()),'failure',sum(bool(r['failure']) for r in D.values()),'peak fuel %.2fM (%.3f%% of 2e10)'%(max(pk)/1e6,100*max(pk)/2e10),'worst p95 %.2fM'%(max(p95)/1e6),'median p95 %.2fM'%(np.median(p95)/1e6),'mean ate %.3f'%np.mean([r['ate_full'] for r in D.values()]))
