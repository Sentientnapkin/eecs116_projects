"""Detached nohup launcher with persistent exact PID records."""
import argparse,json,os,subprocess
from pathlib import Path
H=Path(__file__).resolve().parent
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--gpu');p.add_argument('--venv',default='venv-teacher');p.add_argument('cmd',nargs=argparse.REMAINDER);a=p.parse_args();cmd=a.cmd[1:] if a.cmd and a.cmd[0]=='--' else a.cmd
 e=dict(os.environ,TMPDIR='/data/backups/rganapa/Sebastian/tmp',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
 if a.gpu is not None:e['CUDA_VISIBLE_DEVICES']=a.gpu
 if cmd[0]=='python':cmd[0]=f'/data/backups/rganapa/Sebastian/{a.venv}/bin/python';cmd.insert(1,'-B')
 x=subprocess.Popen(['nohup']+cmd,env=e,stdout=open(H/f'logs/{a.name}.log','a'),stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
 path=H/'logs/jobs.json';j=json.load(open(path));j[a.name]=x.pid;path.write_text(json.dumps(j,indent=1));print(a.name,x.pid)
