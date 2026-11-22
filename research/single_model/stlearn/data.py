import json,math,time
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import IterableDataset
from cache import CACHE,paths
from train import Flights,exp_so3,Kmat,prepare
HERE=Path(__file__).resolve().parent

def sample(fl,i,rng,lag=1.,augment=True):
 m=fl.meta(i);tall=m['times'];dt=float(np.median(np.diff(tall)));scale=float(rng.uniform(.8,1.4)) if augment and rng.random()<.12 else 1.
 L=max(1,round(lag*scale/dt));half=L//2
 if L+2>=len(tall):return None
 for attempt in range(20):
  t=int(rng.integers(L,min(len(tall),L+max(2,round(1/dt))))) if augment and rng.random()<.2 else int(rng.integers(L,len(tall)));ix=[t,t-half,t-L];Rc=[m['R'][k].astype(float)@m['T_bc'][:3,:3] for k in ix]
  angle=math.acos(np.clip((np.trace(Rc[0].T@Rc[2])-1)*.5,-1,1))
  if angle<math.radians(45):break
 else:return None
 K=Kmat(float(m['fxw'][t]));Ki=np.linalg.inv(K);Hs=[]
 for j in (1,2):
  rot=Rc[0].T@Rc[j];rot=exp_so3(rng.normal(0,math.radians(.4)*(j/2)**.5,3))@rot;Hs.append(K@rot.T@Ki)
 P,W=m['P'],m['W'];physical=tall[t]-tall[t-L];tau=physical/scale;tm=(tall[t]-tall[t-half])/scale
 df=Rc[0].T@(P[t]-P[t-L]);dm=Rc[0].T@(P[t]-P[t-half]);af=Rc[0].T@(P[t]-P[t-L]-W[t-L]*physical);am=Rc[0].T@(P[t]-P[t-half]-W[t-half]*(tall[t]-tall[t-half]))
 tn=math.radians(float(rng.choice([.5,1,1,2])));g=exp_so3(rng.normal(0,tn,3))@(Rc[0].T@np.array([0.,0.,-1.]));bias=rng.normal(0,9.81*tn,3)+rng.normal(0,.05,3)
 af+=.5*bias*tau*tau+rng.normal(0,.012*tau**1.5,3);am+=.5*bias*tm*tm+rng.normal(0,.012*tm**1.5,3)
 aux=np.r_[g,m['fxw'][t],af,am].astype('f');vel=(Rc[0].T@W[t]*scale).astype('f');speed=float(np.linalg.norm(vel))
 return np.stack([fl.img(i)[k] for k in ix]),np.stack(Hs).astype('f'),aux,np.r_[df,dm].astype('f'),vel,np.float32(tau),np.float32(speed),np.int64(i)
class Stream(IterableDataset):
 def __init__(self,seed,student=False):self.seed=seed;self.student=student
 def __iter__(self):
  wi=torch.utils.data.get_worker_info();rng=np.random.default_rng([self.seed,wi.id if wi else 0]);rows=json.load(open(HERE/'work/train_records.json'));assert rows and all(r['role']=='train' for r in rows);fl=Flights(CACHE,rows)
  while True:
   i=int(rng.integers(len(fl.items)));lag=1. if self.student else float(rng.choice([.25,.5,1,1,1,2]))
   s=sample(fl,i,rng,lag)
   if s is not None:yield s

def validation(n=3072,seed=7300):
 rows=json.load(open(HERE/'work/val_records.json'));assert rows and all(r['role']=='val' for r in rows);fl=Flights(CACHE,rows);rng=np.random.default_rng(seed);out=[]
 while len(out)<n:
  s=sample(fl,int(rng.integers(len(fl.items))),rng,lag=1.,augment=False)
  if s is not None:out.append(s)
 return [torch.from_numpy(np.stack([v[k] for v in out])) for k in range(8)]

def batch(b,dev,teacher,aug):
 ims,Hs,ax,tgt,v,tau,sp,ix=b;v=v.to(dev);tau=tau.to(dev)
 # Original mirror draws are internal; apply our own coherent flip to both labels.
 if aug:
  # prepare(False) below then add consistent image/aux/label augmentation here.
  pass
 img,mask,aux,tgt=prepare(ims,Hs,ax,tgt,dev,False)
 if aug:
  B=len(img);gain=torch.empty(B,1,1,1,device=dev).uniform_(.6,1.4);contrast=torch.empty_like(gain).uniform_(.6,1.4);mean=(img*mask).sum((2,3),keepdim=True)/mask.sum((2,3),keepdim=True).clamp_min(1)
  img=((img-mean)*contrast+mean)*gain+torch.randn_like(img)*.01;img=img.clamp(0,1)*mask
  dark=torch.rand(B,3,1,1,device=dev)<.02;img=torch.where(dark,torch.zeros_like(img),img)
  if torch.rand((),device=dev)<.2:img=torch.nn.functional.avg_pool2d(img,3,stride=1,padding=1)*mask
  flip=torch.rand(B,device=dev)<.5;img=torch.where(flip[:,None,None,None],img.flip(3),img);mask=torch.where(flip[:,None,None,None],mask.flip(3),mask);sx=torch.where(flip,-1.,1.)
  aux=aux.clone();aux[:,[0,4,7]]*=sx[:,None];tgt=tgt.clone();tgt[:,[0,3]]*=sx[:,None];v=v.clone();v[:,0]*=sx
 if teacher:aux=torch.cat([aux,tau[:,None]],1)
 return img,mask,aux,tgt,v,tau
