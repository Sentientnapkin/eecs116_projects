"""Run only the predeclared RA arms sequentially on one GPU, with distinct continuation names."""
import os,sys,subprocess,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from launch import resolve
GPU=sys.argv[1]
for item in sys.argv[2:]:
 name, seed=item.split(':'); seed=int(seed)
 run,data,extra=resolve(name,None if seed==217 else seed,'codexfinish')
 out=ROOT/'results/loop'/run
 if out.exists() and json.loads((out/'manifest.json').read_text()).get('status')=='completed':continue
 cmd=[sys.executable,'-B',str(ROOT/'odometry_train.py'),'--config',str(ROOT/'configs/odometry.json'),'--data',data,'--output',str(out),*extra]
 env={**os.environ,'CUDA_VISIBLE_DEVICES':GPU,'OMP_NUM_THREADS':'4','PYTHONHASHSEED':'0'}
 print('start',run,flush=True)
 with open(str(out)+'.log','a') as log: rc=subprocess.run(cmd,env=env,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
 print('finish',run,rc,flush=True)
 if rc:sys.exit(rc)
