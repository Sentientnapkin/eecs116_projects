"""Overlap wider-student r0 screening with later lcJ training; max48 eval workers."""
import json,os,subprocess,time,hashlib,sys
from pathlib import Path
H=Path(__file__).resolve().parent;BASE=H.parents[3];TP=BASE/'venv-teacher/bin/python';VP=BASE/'venv-viobench-9b1b079/bin/python'
REF='5e4d2a0d40333b3f5152d60de84a688abc5d0eec8c1c73fa402dc9907839d196'
env=dict(os.environ,CUDA_VISIBLE_DEVICES='4',CUDA_CACHE_PATH=str(BASE/'tmp/stlong_cuda_cache'))
def run(script,*args,venv=TP):
 print('RUN',script,*args,flush=True);subprocess.run([str(venv),'-B',str(H/script),*map(str,args)],env=env,check=True)
def note(s):
 print(s,flush=True)
 with open(H/'NOTES.md','a') as f:f.write('- '+time.strftime('%F %T UTC: ')+s+'\n')
print('Waiting for all three width1.5 student runs to complete.',flush=True)
while True:
 if all((H/f'logs/wide{s}.log').exists() and f'DONE wide{s}' in (H/f'logs/wide{s}.log').read_text() for s in range(3)):break
 time.sleep(15)
# Generation and the width1.5 stage have finished; GPU4 is now free for direct evaluations.
results=[]
for s in range(3):
 name=f'wide{s}';r=H/'runs'/name
 run('direct.py','--run',r,'--out',name)
 run('calibrate.py',name)
 run('build.py','--name',name,'--run',r)
 run('build.py','--name',name+'_off','--run',r,'--off')
 assert hashlib.sha256((H/'builds'/f'{name}_off/solution.wasm').read_bytes()).hexdigest()==REF
 run('evaluate.py','--name',name,'--workers','48',venv=VP)
 run('compare.py',name,'--reps','1')
 d=json.load(open(H/f'tables/{name}_comparison_r1.json'))[0];results.append(dict(name=name,**d));note(f'{name} r0 pooled ATE{d["arm"]:.6f}, vs GSLV{d["pct"]:+.2f}%, peak{d["arm_peak"]/1e6:.3f}M. Switch-off exact.')
best=min(results,key=lambda d:d['arm']);name=best['name'];r=H/'runs'/name
cal=json.load(open(H/f'tables/{name}_calibration.json'));pred=json.load(open(H/f'tables/{name}_direct.json'));n=sum(x['all']['n'] for x in pred.values());sigma=(sum(x['all']['n']*x['all']['zrms']**2 for x in pred.values())/n)**.5
for tag,k,ss in [('sig',0,sigma),('cal',cal['best']['speedk'],cal['best']['sigma_scale'])]:
 if tag=='cal' and k==0:continue
 variant=name+'_'+tag
 run('build.py','--name',variant,'--run',r,'--sigscale',ss,'--speedk',k)
 run('evaluate.py','--name',variant,'--workers','48',venv=VP)
 run('compare.py',variant,'--reps','1');d=json.load(open(H/f'tables/{variant}_comparison_r1.json'))[0];results.append(dict(name=variant,**d))
(H/'tables/wide_screen_summary.json').write_text(json.dumps(results,indent=1));note('Wider-model r0 screens and calibration screens DONE. Finalist3rep selection pending.')
