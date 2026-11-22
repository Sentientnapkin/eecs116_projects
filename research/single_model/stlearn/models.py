import torch
from torch import nn
from model import Teacher

CONFIGS={
 'teacher':dict(enc=[(2,48,2),(48,48,1),(48,96,2),(96,96,1),(96,128,2),(128,128,1),(128,128,1),(128,128,1)],head=192,fc=384,h2=96,aux=11),
 'S100':dict(enc=[(2,16,2),(16,16,1),(16,32,2),(32,32,1),(32,48,2),(48,48,1)],head=64,fc=128,h2=32,aux=10),
 'S25':dict(enc=[(2,8,2),(8,8,1),(8,16,2),(16,16,1),(16,24,2),(24,24,1)],head=32,fc=64,h2=16,aux=10),
 'S6':dict(enc=[(2,4,2),(4,4,1),(4,8,2),(8,8,1),(8,8,2),(8,8,1)],head=8,fc=32,h2=8,aux=10),
 'S2':dict(enc=[(2,4,4),(4,4,1),(4,4,2),(4,4,1)],head=8,fc=24,h2=4,aux=10)}
class Motion(Teacher):
 def __init__(self,cfg):
  super().__init__(enc=cfg['enc'],head=cfg['head'],fc=cfg['fc'],h2=cfg['h2'])
  self.cfg=cfg
  if cfg['aux']!=10:self.fc1=nn.Linear(cfg['h2']*6*8+cfg['aux'],cfg['fc'])
  self.vhead=nn.Linear(cfg['fc'],6)
  with torch.no_grad():self.vhead.weight.mul_(.1);self.vhead.bias.zero_();self.vhead.bias[3:]=-1
 def all_outputs(self,img,mask,aux):
  out,h=super().forward(img,mask,aux,feats=True);return out,self.vhead(h),h
 def forward(self,img,mask,aux,feats=False):
  out,h=super().forward(img,mask,aux,feats=True)
  return (out,self.vhead(h),h) if feats else out

def load(path):
 d=torch.load(path,map_location='cpu',weights_only=False);m=Motion(d['config']);m.load_state_dict(d['model']);m.eval();return m,d

def macs(name):
 m=Motion(CONFIGS[name]).eval();count=[0]
 def hook(mod,ins,out):
  if isinstance(mod,nn.Conv2d):count[0]+=out.numel()*mod.in_channels*mod.kernel_size[0]*mod.kernel_size[1]
  elif isinstance(mod,nn.Linear):count[0]+=out.numel()*mod.in_features
 hooks=[v.register_forward_hook(hook) for v in m.modules() if isinstance(v,(nn.Conv2d,nn.Linear))]
 with torch.no_grad():m(torch.zeros(1,3,96,128),torch.ones(1,3,96,128),torch.zeros(1,CONFIGS[name]['aux']),feats=True)
 for h in hooks:h.remove()
 count[0]+=2*49*12*16*CONFIGS[name]['enc'][-1][1]
 return dict(model=name,macs=count[0],parameters=sum(p.numel() for p in m.parameters()))
