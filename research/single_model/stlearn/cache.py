"""Own DT-format caches from audited HF shards, legacy caches, or own raw flights."""
import os,json,hashlib,sys,collections
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[3]
CACHE=Path('/data/backups/rganapa/Sebastian/tmp/stlearn_cache');CACHE.mkdir(parents=True,exist_ok=True)

def paths(r):
 k=r['file'][:20];return CACHE/(k+'.img.npy'),CACHE/(k+'.meta.npz')
def one(r):
 pi,pm=paths(r)
 if pi.exists() and pm.exists():return r,'cached'
 if r['kind']=='hf':
  from huggingface_hub import hf_hub_download
  src=hf_hub_download('SentientNapkin/viobench-teacher-data',r['repo_file'],repo_type='dataset',cache_dir='/data/backups/rganapa/Sebastian/tmp/stlearn_hf/hub')
  assert hashlib.sha256(Path(src).read_bytes()).hexdigest()==r['sha256']
  with np.load(src,allow_pickle=False) as z:
   img=np.ascontiguousarray(z['images'][:,0]);R=z['R'].astype(float);W=np.einsum('nij,nj->ni',R,z['v']);t=z['times'].astype(float);fxw=z['imu'][:,14].astype('f');T=z['T_bc'];g=np.array([0,0,-1.])
  P=np.r_[np.zeros((1,3)),np.cumsum(.5*(W[1:]+W[:-1])*np.diff(t)[:,None],axis=0)]
 elif r['kind']=='legacy':
  with np.load(r['cache'],allow_pickle=False) as z:
   img=z['frames0'];R=z['Rcum0'].astype(float);v=z['vb0'];t=np.arange(len(img))*.25;fxw=np.full(len(img),z['K'][0]/128,dtype='f');T=z['Tbc'];f=z['fmean0'][0].astype(float)
  f/=np.linalg.norm(f);axis=np.cross(f,[0,0,1.]);ss=np.linalg.norm(axis);cc=f[2]
  if ss>1e-9:
   a=axis/ss;K=np.array([[0,-a[2],a[1]],[a[2],0,-a[0]],[-a[1],a[0],0]]);A=np.eye(3)+K*ss+(K@K)*(1-cc)
  else:A=np.eye(3)
  R=np.einsum('ij,njk->nik',A,R);W=np.einsum('nij,nj->ni',R,v);P=np.r_[np.zeros((1,3)),np.cumsum(.5*(W[1:]+W[:-1])*.25,axis=0)];g=np.array([0,0,-1.])
 else:
  sys.path.insert(0,'/dev/shm/sebastian-vio/viobench');import cv2
  from viobench.tools.datasets.storage import read_episode
  from viobench.tools.geometry import interpolate_poses,poses_to_matrices
  ep=read_episode(str(Path(r['dir'])/(r['name']+'.zip')),frames='lazy');t=ep.frame_times
  assert t[-1]-t[0]>58,'crashed/short episode'
  gt=ep.ground_truth;M=poses_to_matrices(interpolate_poses(gt[:,0],gt[:,1:8],t));R=M[:,:3,:3];P=M[:,:3,3];Md=poses_to_matrices(gt[:,1:8]);v=np.gradient(Md[:,:3,3],gt[:,0],axis=0);W=np.stack([np.interp(t,gt[:,0],v[:,i]) for i in range(3)],1)
  T=ep.T_body_camera;fxw=np.full(len(t),ep.config['camera']['fx']/ep.resolution[0],dtype='f')
  img=np.stack([cv2.resize(cv2.cvtColor(cv2.resize(np.asarray(fr),(320,240),interpolation=cv2.INTER_AREA),cv2.COLOR_RGB2GRAY),(128,96),interpolation=cv2.INTER_AREA) for fr in ep.frames]);g=np.array([0,0,-1.])
 assert np.isfinite(R).all() and np.isfinite(P).all() and len(img)>10
 tmp=str(pi)+'.tmp.npy';np.save(tmp,img);os.replace(tmp,pi)
 tmp=str(pm)+'.tmp.npz';np.savez(tmp,R=R.astype('f'),P=P,W=W,fxw=fxw,T_bc=T,times=t,gravity=g,source=r['kind']);os.replace(tmp,pm)
 return r,'ok'
def safe_one(r):
 try:return one(r)
 except Exception as e:return r,'ERR '+repr(e)[:240]
def refresh():
 sources=json.load(open(HERE/'work/source_records.json'));p=HERE/'work/generated_records.json'
 if p.exists():sources+=list(json.load(open(p)).values())
 ready=[r for r in sources if all(p.exists() for p in paths(r))]
 for fn,rs in [('train_records.json',[r for r in ready if r['role']=='train']),('val_records.json',[r for r in ready if r['role']=='val']),('all_records.json',ready)]:
  p=HERE/'work'/fn;t=p.with_suffix('.tmp');t.write_text(json.dumps(rs));t.replace(p)
 repro={r['file'] for r in json.load(open(HERE/'work/repro_sources.json'))};rep=[r for r in ready if r['file'] in repro]
 p=HERE/'work/repro_records.json';p.write_text(json.dumps(rep))
 out=dict(total=len(ready),roles=dict(collections.Counter(r['role'] for r in ready)),kinds=dict(collections.Counter(r['kind'] for r in ready)),repro=len(rep))
 (HERE/'tables/cache_counts.json').write_text(json.dumps(out,indent=2));return out
if __name__=='__main__':
 from multiprocessing import Pool
 rows=json.load(open(HERE/'work/source_records.json'));repro={r['file'] for r in json.load(open(HERE/'work/repro_sources.json'))};rows.sort(key=lambda r:(r['file'] not in repro,r['kind']!='hf'))
 with Pool(8) as p:
  for i,(r,s) in enumerate(p.imap_unordered(safe_one,rows),1):
   if s.startswith('ERR'):print(r['name'],s,flush=True)
   if i%32==0 or i==len(rows):
    c=refresh();print(i,c,flush=True)
    with (HERE/'NOTES.md').open('a') as f:f.write(f'- Cache milestone {i}/{len(rows)}: {c}.\n')
