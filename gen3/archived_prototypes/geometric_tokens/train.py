import json,time,random
from pathlib import Path
import numpy as np, torch, torch.nn as nn
OUT=Path(__file__).resolve().parent; torch.set_num_threads(2)
class DeepSet(nn.Module):
 def __init__(self):
  super().__init__(); self.phi=nn.Sequential(nn.Linear(5,64),nn.GELU(),nn.Linear(64,64),nn.GELU()); self.imu=nn.Sequential(nn.Linear(19,64),nn.GELU()); self.head=nn.Sequential(nn.Linear(64*3,128),nn.GELU(),nn.Linear(128,4))
 def forward(self,x,v):
  h=self.phi(x); z=torch.cat([h.mean(1),h.max(1).values,self.imu(v)],1); q=self.head(z); return q[:,:3],q[:,3:].clamp(-6,4)
class SetAttention(nn.Module):
 def __init__(self):
  super().__init__(); self.inp=nn.Linear(5,64); layer=nn.TransformerEncoderLayer(64,4,128,dropout=0.0,batch_first=True,norm_first=True,activation='gelu'); self.enc=nn.TransformerEncoder(layer,2,enable_nested_tensor=False); self.imu=nn.Sequential(nn.Linear(19,64),nn.GELU()); self.head=nn.Sequential(nn.Linear(192,128),nn.GELU(),nn.Linear(128,4))
 def forward(self,x,v):
  h=self.enc(self.inp(x)); q=self.head(torch.cat([h.mean(1),h.max(1).values,self.imu(v)],1)); return q[:,:3],q[:,3:].clamp(-6,4)
@torch.no_grad()
def score(net,vd,mu,std,vm,vs):
 net.eval(); X=torch.tensor(vd['x'].astype('float32'),device='cuda'); V=torch.tensor(vd['v'].astype('float32'),device='cuda'); Y=torch.tensor(vd['y'],device='cuda')
 X=(X-mu)/std; V=(V-vm)/vs; pp=[]; ll=[]
 for i in range(0,len(X),256):
  p,l=net(X[i:i+256],V[i:i+256]); pp.append(p); ll.append(l)
 p=torch.cat(pp); l=torch.cat(ll); e=p-Y; sp=Y.norm(dim=1); ps=p.norm(dim=1); moving=sp>.5; ang=torch.rad2deg(torch.acos(((p*Y).sum(1)/(ps*sp).clamp(min=1e-8)).clamp(-1,1)))
 return {'n':len(Y),'vector_norm_error_mps':float(e.norm(dim=1).mean()),'speed_abs_error_mps':float((ps-sp).abs().mean()),'direction_deg_moving':float(ang[moving].mean()),'nll_diag':float((.5*(e.square()*torch.exp(-l)+l)).sum(1).mean()),'uncertainty_z_rms':float((e.square()*torch.exp(-l)).mean().sqrt()),'predicted_std_median':float(torch.exp(.5*l).median())}
def main():
 tr=np.load(OUT/'train.npz'); va=np.load(OUT/'val.npz'); device='cuda'; results=[]
 x=torch.tensor(tr['x'].astype('float32'),device=device); v=torch.tensor(tr['v'].astype('float32'),device=device); y=torch.tensor(tr['y'],device=device)
 xm=x.mean((0,1),keepdim=True); xs=x.std((0,1),keepdim=True).clamp(min=.05); vm=v.mean(0,keepdim=True); vs=v.std(0,keepdim=True).clamp(min=.05)
 for kind,Cls in [('deepsets',DeepSet),('attention',SetAttention)]:
  for seed in (17,29):
   torch.manual_seed(seed); np.random.seed(seed); random.seed(seed); net=Cls().to(device); opt=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=1e-4); params=sum(p.numel() for p in net.parameters()); t=time.time(); best=None
   for ep in range(10):
    net.train(); order=torch.randint(len(y),(100*256,),device=device); losses=[]
    for i in range(0,len(order),256):
     ix=order[i:i+256]; xb=(x[ix]-xm)/xs; vb=(v[ix]-vm)/vs; mu,lv=net(xb,vb); err=y[ix]-mu; loss=.5*(err.square()*torch.exp(-lv)+lv).sum(1).mean(); opt.zero_grad(set_to_none=True); loss.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(),5); opt.step(); losses.append(float(loss.detach()))
    row={'epoch':ep+1,'train_nll':float(np.mean(losses))}; print('EPOCH',kind,seed,json.dumps(row),flush=True)
   metric=score(net,va,xm,xs,vm,vs); row={'model':kind,'seed':seed,'params':params,'train_anchors':len(y),'val_anchors':len(va['y']),'epochs':10,'steps_per_epoch':100,'batch':256,'val':metric,'seconds':round(time.time()-t,2)}; results.append(row); torch.save({'state_dict':net.state_dict(),'model':kind,'seed':seed,'params':params,'normalization':{'x_mean':xm.cpu(),'x_std':xs.cpu(),'imu_mean':vm.cpu(),'imu_std':vs.cpu()}},OUT/f'{kind}_seed{seed}.pt'); print('RESULT',json.dumps(row),flush=True)
 (OUT/'results.json').write_text(json.dumps({'inputs':'48 sparse derotated LK tokens (5 features each) + 19D IMU preintegration/intrinsics; targets next vb in m/s','split':'50 train flights phases0+2, 20 held-out validation flights phase0; capped 16k/4k anchors','results':results},indent=2))
if __name__=='__main__': main()
