import sys, json, time, random
from pathlib import Path
import numpy as np, torch
ROOT=Path('/data/backups/rganapa/Sebastian/gen3'); SRC=ROOT/'research/i6/src'; sys.path.insert(0,str(SRC))
import i6lib as L
OUT=Path(__file__).resolve().parent
random.seed(3411); np.random.seed(3411); torch.set_num_threads(2)
train_names=[x.strip() for x in open(ROOT/'agents/netv2/lists/train727.txt') if x.strip()]
val_names=[x.strip() for x in open(ROOT/'agents/netv2/lists/val749.txt') if x.strip()]
random.shuffle(train_names); train_names=train_names[:50]
random.shuffle(val_names); val_names=val_names[:20]
(OUT/'splits.json').write_text(json.dumps({'seed':3411,'train_flights':train_names,'val_flights':val_names,'source':'gen3 agents/net cache; i6 L.sample tracks_imu; phases train 0+2, val 0'},indent=2))
def load(names,part,phases):
 d=ROOT/'agents/net/cache'/part
 return [d/f'{n}.npz' for n in names if (d/f'{n}.npz').exists()]
@torch.no_grad()
def collect(names,part,phases,cap,outfile):
 files=load(names,part,phases); assert len(files)==len(names),(part,len(files),len(names))
 d=L.D(files,'cuda',phases,[1]*len(files)); st=L.starts3(d)
 g=torch.Generator(device=st.device).manual_seed(9527 if part=='train' else 9528)
 if len(st)>cap: st=st[torch.randperm(len(st),generator=g,device=st.device)[:cap]]
 xs=[]; vs=[]; ys=[]; fids=[]
 for j in range(0,len(st),64):
  q=st[j:j+64]; _,pts,vec,tgt=L.sample(d,q,'tracks_imu',False)
  xs.append(pts.cpu().half().numpy()); vs.append(vec.cpu().half().numpy()); ys.append(tgt[:,1].cpu().float().numpy()); fids.append(d.fid[q].cpu().numpy())
 z={'x':np.concatenate(xs).astype('float16'),'v':np.concatenate(vs).astype('float16'),'y':np.concatenate(ys).astype('float32'),'flight':np.concatenate(fids).astype('int16'),'flight_names':np.array(names)}
 np.savez_compressed(OUT/outfile,**z)
 print('CACHE',part,'flights',len(files),'available',int(len(L.starts3(d))),'selected',len(st),'shape',z['x'].shape,'file_mb',(OUT/outfile).stat().st_size/1e6,flush=True)
 return z
if __name__=='__main__':
 t=time.time(); a=collect(train_names,'train',(0,2),16000,'train.npz'); b=collect(val_names,'val',(0,),4000,'val.npz')
 # validation: units, finite values, input/target separation; input changes do not alter labels by construction
 for name,z in [('train',a),('val',b)]:
  assert np.isfinite(z['x']).all() and np.isfinite(z['v']).all() and np.isfinite(z['y']).all()
  assert z['x'].shape[1:]==(48,5) and z['v'].shape[1]==19 and z['y'].shape[1]==3
  assert float(np.median(np.linalg.norm(z['y'],axis=1))) < 30, 'target should be m/s'
 print('SMOKE_CACHE_OK',round(time.time()-t,1),'sec; target median speed',float(np.median(np.linalg.norm(a['y'],axis=1))),flush=True)
