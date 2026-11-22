"""Resumable AMP/DDP+EMA teacher or truth/KD/scale/hint student training."""
import argparse,copy,json,math,os,time,random
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import DataLoader
from models import Motion,CONFIGS,load
from data import Stream,validation,batch
from train import loss_fn
HERE=Path(__file__).resolve().parent

def evaluate(m,val,dev):
 m.eval();es=[];ev=[];zs=[];zv=[];speeds=[];sources=[]
 with torch.no_grad():
  for start in range(0,len(val[0]),128):
   b=[v[start:start+128] for v in val];im,ma,ax,y,v,tau=batch(b,dev,m.cfg['aux']==11,False)
   with torch.autocast('cuda',dtype=torch.bfloat16):o,vo,h=m(im,ma,ax,feats=True)
   es.extend((o[:,:3].float()-y[:,:3]).norm(dim=1).cpu().tolist());ev.extend((vo[:,:3].float()-v).norm(dim=1).cpu().tolist())
   zs.extend(((o[:,:3].float()-y[:,:3]).abs()/o[:,3:6].float().clamp(-6,3).exp()).cpu().tolist());zv.extend(((vo[:,:3].float()-v).abs()/vo[:,3:6].float().clamp(-6,3).exp()).cpu().tolist());speeds.extend(b[6].tolist())
 e=np.array(es);v=np.array(ev);z=np.array(zs);vz=np.array(zv);sp=np.array(speeds)
 r=dict(n=len(e),disp_error=float(e.mean()),velocity_error=float(v.mean()),laplace_z=z.mean(0).tolist(),velocity_z=vz.mean(0).tolist())
 for lo,hi in [(0,1),(1,2),(2,3),(3,4),(4,float('inf'))]:
  s=(sp>=lo)&(sp<hi)
  if s.any():r[f'speed_{lo}_{hi}']=dict(n=int(s.sum()),disp_error=float(e[s].mean()),velocity_error=float(v[s].mean()),z=z[s].mean(0).tolist())
 m.train();return r

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--name',required=True,choices=CONFIGS);ap.add_argument('--out',required=True);ap.add_argument('--hours',type=float,required=True);ap.add_argument('--reset-clock',action='store_true');ap.add_argument('--reset-best',action='store_true');ap.add_argument('--teacher');ap.add_argument('--resume');ap.add_argument('--seed',type=int,default=7301);ap.add_argument('--bs',type=int,default=64);ap.add_argument('--workers',type=int,default=4);ap.add_argument('--eval-every',type=int,default=2000);ap.add_argument('--max-steps',type=int,default=10000000);a=ap.parse_args()
 rank=int(os.environ.get('RANK',0));local=int(os.environ.get('LOCAL_RANK',0));world=int(os.environ.get('WORLD_SIZE',1));dev=f'cuda:{local}';torch.cuda.set_device(local);torch.set_num_threads(1)
 if world>1:torch.distributed.init_process_group('nccl')
 torch.manual_seed(a.seed+rank);np.random.seed(a.seed+rank);random.seed(a.seed+rank);torch.backends.cudnn.benchmark=True
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True);model=Motion(CONFIGS[a.name]).to(dev);teacher=None;proj=None
 if a.teacher:
  teacher,_=load(a.teacher);teacher.to(dev).eval()
  for p in teacher.parameters():p.requires_grad_(False)
  proj=nn.Linear(model.cfg['fc'],teacher.cfg['fc']).to(dev)
 if world>1:
  model=DDP(model,device_ids=[local]);proj=DDP(proj,device_ids=[local]) if proj is not None else None
 raw=model.module if world>1 else model;ema=copy.deepcopy(raw).eval()
 for p in ema.parameters():p.requires_grad_(False)
 opt=torch.optim.AdamW(list(model.parameters())+(list(proj.parameters()) if proj is not None else []),lr=.001,weight_decay=1e-4)
 step=0;elapsed=0.;best=float('inf')
 if a.resume:
  ck=torch.load(a.resume,map_location=dev,weights_only=False);raw.load_state_dict(ck.get('raw_model',ck['model']));ema.load_state_dict(ck['model']);opt.load_state_dict(ck['optimizer']);step=ck['step'];elapsed=ck.get('elapsed',0.)
  if proj is not None:(proj.module if world>1 else proj).load_state_dict(ck['projection'])
  best=float('inf') if a.reset_best else ck.get('best',best)
  if a.reset_clock:elapsed=0.
 val=validation(n=3072);dl=DataLoader(Stream(a.seed+rank*1000,student=bool(a.teacher)),batch_size=a.bs,num_workers=a.workers,pin_memory=True,persistent_workers=True,prefetch_factor=2)
 start=time.time();smooth=None;lr0=.001 if teacher is None else .0006
 if rank==0:print(json.dumps(dict(name=a.name,world=world,batch=a.bs*world,hours=a.hours,parameters=sum(p.numel() for p in raw.parameters()),resume_step=step)),flush=True)
 for b in dl:
  age=elapsed+time.time()-start;frac=min(age/(a.hours*3600),1.);lr=lr0*min(1.,(step+1)/1000)*(.03+.97*.5*(1+math.cos(math.pi*frac)))
  for g in opt.param_groups:g['lr']=lr
  im,ma,ax,y,v,tau=batch(b,dev,raw.cfg['aux']==11,True)
  with torch.autocast('cuda',dtype=torch.bfloat16):
   o,vo,h=model(im,ma,ax,feats=True);loss,mu,ls=loss_fn(o,y);vl=(v-vo[:,:3].float()).abs()*(-vo[:,3:6].float().clamp(-6,3)).exp()+vo[:,3:6].float().clamp(-6,3);loss=loss+.3*vl.mean()
   if teacher is not None:
    tax=torch.cat([ax,tau[:,None]],1)
    with torch.no_grad():to,tv,th=teacher(im,ma,tax,feats=True)
    tm=torch.cat([to[:,:3],to[:,6:9]],1).float();tl=torch.cat([to[:,3:6],to[:,9:12]],1).float().clamp(-6,3)
    kd=((mu-tm).abs()/(tl.exp()+.02)).mean();scale=(ls-tl).square().mean();hint=(proj(h.float())-th.float()).square().mean()/(th.float().square().mean().detach()+.01)
    loss=loss+.5*kd+.05*scale+.1*hint+.1*(vo[:,:3].float()-tv[:,:3].float()).abs().mean()
  if not torch.isfinite(loss):raise RuntimeError('nonfinite loss')
  opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5.);opt.step();step+=1
  with torch.no_grad():
   for p,q in zip(ema.parameters(),raw.parameters()):p.lerp_(q.detach(),.001)
   for p,q in zip(ema.buffers(),raw.buffers()):p.copy_(q)
  smooth=float(loss) if smooth is None else .98*smooth+.02*float(loss)
  done=age>=a.hours*3600 or step>=a.max_steps
  if rank==0 and step%200==0:print(f'step {step} loss {smooth:.5f} lr {lr:.3g} hours {age/3600:.4f}',flush=True)
  if step%a.eval_every==0 or done:
   if world>1:torch.distributed.barrier()
   if rank==0:
    r=evaluate(ema,val,dev);r.update(step=step,hours=age/3600,lr=lr,train_loss=smooth,name=a.name);score=r['disp_error']
    improve=score<best;best=min(best,score)
    ck=dict(model=ema.state_dict(),raw_model=raw.state_dict(),config=raw.cfg,name=a.name,step=step,elapsed=age,optimizer=opt.state_dict(),val=r,best=best,seed=a.seed)
    if proj is not None:ck['projection']=(proj.module if world>1 else proj).state_dict()
    tmp=out/'last.tmp.pt';torch.save(ck,tmp);tmp.replace(out/'last.pt')
    if improve:torch.save(ck,out/'best.pt')
    with (out/'curve.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
    with (HERE/'NOTES.md').open('a') as f:f.write(f"- {a.name} checkpoint step{step}, {age/3600:.2f}h: 1s error{r['disp_error']:.5f}m, velocity{r['velocity_error']:.5f}m/s, Laplace z{r['laplace_z']}; world{world}.\n")
    print('VAL '+json.dumps(r),flush=True)
   if world>1:torch.distributed.barrier()
  if done:break
 if world>1:torch.distributed.destroy_process_group()
 if rank==0:print('DONE',a.name,step,flush=True)
if __name__=='__main__':main()
