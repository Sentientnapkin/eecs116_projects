import os,json,time,subprocess,sys,signal
from pathlib import Path
from multiprocessing import Pool
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[2];BASE=ROOT.parent;RAW=BASE/'gen/raw-stlearn';PY=BASE/'venv-sim/bin/python'
sys.path.insert(0,str(HERE));import cache
children=[]
def stop(sig,frm):
 for p in children:
  try:os.killpg(p.pid,signal.SIGTERM)
  except ProcessLookupError:pass
 raise SystemExit(128+sig)
for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,stop)
def main():
 for d in ['logs','cfg','bench','partial']:(RAW/d).mkdir(parents=True,exist_ok=True)
 roster=json.load(open(HERE/'gen/roster.json'))['flights'];donefile=HERE/'work/generated_records.json';done=json.load(open(donefile)) if donefile.exists() else {};roster=[f for f in roster if f['id'] not in done]
 for start in range(0,len(roster),32):
  c=cache.refresh()
  if c['roles'].get('train',0)>=5000:print('DATA TARGET REACHED',c,flush=True);break
  while float(Path('/proc/loadavg').read_text().split()[0])>145:time.sleep(30)
  chunk=roster[start:start+32];rp=RAW/'cfg/batch.json';rp.write_text(json.dumps({'flights':chunk}));children.clear();print('GENERATE',start,len(chunk),'GPUs6,7',flush=True)
  for i in range(16):
   env=dict(os.environ,CUDA_VISIBLE_DEVICES=str([6,7][i%2]),CUDAARCHS='90',HYPERLUX_BACKEND='OPTIX',HYPERLUX_CACHE_DIR=str(BASE/'tmp/stlearn_optix'),VIOBENCH_CACHE=str(BASE/'tmp/stlearn_gen_viobench'),TMPDIR=str(BASE/'tmp'),CONTA_CACHE=str(BASE/'gen/conta'),VIOBENCH_SPOOL=str(BASE/'tmp/stlearn_spool'),XDG_CACHE_HOME=str(BASE/'tmp/stlearn_xdg'),PATH=str(BASE/'venv-sim/bin')+':/usr/local/cuda/bin:'+os.environ['PATH'])
   cmd=[str(PY),'native_campaign.py','generate','--gen-roster',str(rp),'--gen-raw',str(RAW),'--worker',str(i),'--workers','16']
   children.append(subprocess.Popen(cmd,cwd=ROOT/'research',env=env,stdout=open(RAW/f'logs/worker{i}.log','a'),stderr=subprocess.STDOUT,start_new_session=True))
  for p in children:
   rc=p.wait()
   if rc:print('worker returned',rc,flush=True)
  children.clear();rs=[]
  for f in chunk:
   if (RAW/'bench'/(f['id']+'.zip')).exists():rs.append(dict(f,name=f['id'],dir=str(RAW/'bench'),kind='raw',file=__import__('hashlib').sha256(('raw:'+f['id']).encode()).hexdigest()+'_raw.npz'))
  with Pool(8) as pool:
   for r,status in pool.map(cache.safe_one,rs):
    if not status.startswith('ERR'):
     done[r['name']]=r;(RAW/'bench'/(r['name']+'.zip')).unlink(missing_ok=True)
    else:print(r['name'],status,flush=True)
  donefile.write_text(json.dumps(done));c=cache.refresh();print('CACHED',c,flush=True)
  with (HERE/'NOTES.md').open('a') as f:f.write(f'- Generated/cache batch {start//32}: {len(done)} accepted own flights; total cache {c}. Own zips deleted only after cache success.\n')
 print('DONE',cache.refresh(),flush=True)
if __name__=='__main__':main()
