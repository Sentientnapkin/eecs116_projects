"""Three-replicate tuning of preselected finalists. Never reads candidate confirmation results."""
import json,os,subprocess,time
from pathlib import Path
H=Path(__file__).resolve().parent;BASE=H.parents[3];TP=BASE/'venv-teacher/bin/python';VP=BASE/'venv-viobench-9b1b079/bin/python'
def run(script,*args,venv=TP):
 print('RUN',script,*args,flush=True);subprocess.run([str(venv),'-B',str(H/script),*map(str,args)],check=True)
def note(s):
 print(s,flush=True)
 with open(H/'NOTES.md','a') as f:f.write('- '+time.strftime('%F %T UTC: ')+s+'\n')
print('Waiting for both families of r0 screens and calibrations.',flush=True)
while not (H/'tables/lcj_screen_summary.json').exists():time.sleep(15)
w=json.load(open(H/'tables/wide_screen_summary.json'));j=json.load(open(H/'tables/lcj_screen_summary.json'));allrows=sorted(w+j,key=lambda r:r['arm']);pick=[min(w,key=lambda r:r['arm']),min(j,key=lambda r:r['arm'])]
for r in allrows:
 if r['name'] not in {x['name'] for x in pick}:pick.append(r);break
note('Finalists selected using r0 tuning only: '+', '.join(r['name'] for r in pick)+'. Running replicates1/2.')
results=[]
for r in pick:
 name=r['name']
 for rep in [1,2]:
  run('replicate.py',name,'--rep',rep)
  run('evaluate.py','--name',name,'--rep',rep,'--workers','48',venv=VP)
 run('compare.py',name,'--reps','3');d=json.load(open(H/f'tables/{name}_comparison_r3.json'))[0];results.append(dict(name=name,**d))
# Resource ceiling from reference only, no candidate confirmation data consulted.
LV=H.parent/'learnvel/tables';limit=max(r['peak'] for pool in ['st2dev','st3','st2conf','fdev','fconf','st1dev','st1conf'] for rep in ['', '_r1','_r2'] for r in json.load(open(LV/f'glNP{rep}__{pool}.json')))
valid=[r for r in results if r['arm_peak']<=limit];best=min(valid or results,key=lambda r:r['arm'])
out=dict(selected=best,finalists=results,reference_peak_limit=limit,tuning_goal_pass=best['pct']<=-5 and best['ci'][1]<0 and best['arm_peak']<=limit)
(H/'tables/finalists_tune.json').write_text(json.dumps(out,indent=1));note(f'3rep tuning DONE. Selected {best["name"]}, ATE{best["arm"]:.6f}, change{best["pct"]:+.2f}%, CI{best["ci"]}, peak{best["arm_peak"]/1e6:.3f}M. Tuning goal pass={out["tuning_goal_pass"]}; confirmation and preflight pending.')
