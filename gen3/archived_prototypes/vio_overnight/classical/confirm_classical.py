#!/usr/bin/env python3
"""Independent 48-flight confirmation for the screen-promising 30M capacity arm."""
import json,statistics,sys
from collections import defaultdict
from pathlib import Path
W=Path('/tmp/vio_overnight/classical'); O=Path('/dev/shm/vio_overnight/classical')
sys.path.insert(0,str(W)); import run_classical as q
def per_scene(rows):
 d=defaultdict(list)
 for r in rows:d[r['scene']].append(r['ate_full'])
 return {k:{'n':len(v),'mean':statistics.mean(v),'median':statistics.median(v),'worst':max(v)} for k,v in sorted(d.items())}
def main():
 ctrl=q.evalone('control_g30_c8','confirm48',O/'builds/control_g30_c8/solution.wasm')
 cand=q.evalone('capacity_g30_c12_o14','confirm48',O/'builds/capacity_g30_c12_o14/solution.wasm')
 paired=q.stats(cand,ctrl)
 vals=[]
 for r in cand['rows']:
  vals.append(r)
 result={'candidate':cand['candidate'],'control':ctrl['candidate'],'n_candidate':cand['n'],'n_control':ctrl['n'],'candidate_mean_ate':cand['mean_ate'],'control_mean_ate':ctrl['mean_ate'],'candidate_median_ate':cand['median_ate'],'control_median_ate':ctrl['median_ate'],'candidate_worst_ate':cand['worst_ate'],'control_worst_ate':ctrl['worst_ate'],'candidate_max_peak_fuel':cand['peak_fuel'],'control_max_peak_fuel':ctrl['peak_fuel'],'candidate_max_p95_fuel':cand['p95_fuel'],'control_max_p95_fuel':ctrl['p95_fuel'],'paired':paired,'candidate_per_scene':per_scene(cand['rows']),'control_per_scene':per_scene(ctrl['rows']),'candidate_rows':cand['rows'],'control_rows':ctrl['rows']}
 (W/'confirm_capacity_g30_c12_o14.json').write_text(json.dumps(result,indent=2)+'\n')
 q.log('CONFIRM capacity_g30_c12_o14 '+json.dumps({k:result[k] for k in ('n_candidate','candidate_mean_ate','control_mean_ate','candidate_max_peak_fuel','candidate_max_p95_fuel','paired')}))
if __name__=='__main__':
 try:main()
 except BaseException as e:q.log('CONFIRM_ERROR '+repr(e));raise
