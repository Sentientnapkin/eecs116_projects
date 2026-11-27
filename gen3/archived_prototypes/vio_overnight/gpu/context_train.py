#!/usr/bin/env python3
"""Resumable small learned temporal-context experiment on existing stage-3 caches.

Only causal frames through b=g+1 and IMU integrations ending at b are inputs.
All arms use the same held-out anchors pos>=3 and final-epoch model selection.
"""
import json, os, sys, time, random, hashlib, datetime
RUN_START=time.monotonic()
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F

ROOT=Path('/data/backups/rganapa/Sebastian/eecs116_projects')
G=ROOT.parent/'gen3'; I6=G/'research/i6'; OUT=Path(os.environ.get('CTX_OUT','/dev/shm/vio_loop3/context_replication'))
SEED=int(os.environ.get('CTX_SEED','4')); K_ONLY=int(os.environ.get('CTX_K','2')); TRAIN_LIST=os.environ.get('CTX_TRAIN_LIST','train727.txt')
sys.path.insert(0,str(I6/'src'))
import i6lib as L

torch.set_num_threads(2)
DEV='cuda'; EPOCHS=100; STEPS=400; BS=256; LR=4e-3
VARIANTS=(K_ONLY,)

def load_data():
    keep=[x.strip() for x in open(G/'agents/netv2/lists'/TRAIN_LIST) if x.strip()]
    trf=[G/f'agents/net/cache/train/{n}.npz' for n in keep if (G/f'agents/net/cache/train/{n}.npz').exists()]
    vk=[x.strip() for x in open(G/'agents/netv2/lists/val749.txt') if x.strip()]
    vaf=[G/f'agents/net/cache/val/{n}.npz' for n in sorted(vk) if (G/f'agents/net/cache/val/{n}.npz').exists()]
    tr=L.D(trf,DEV,(0,2),[1]*len(trf)); va=L.D(vaf,DEV,(0,))
    # Common causal panel: 3 prior frames available before g, then frame g+1.
    trs=torch.nonzero((tr.pos>=3)&(tr.pos+1<tr.len)).squeeze(1)
    vas=torch.nonzero((va.pos>=3)&(va.pos+1<va.len)).squeeze(1)
    w=L.lv4.weights(tr,trs,0.5,[1.0])
    return tr,va,trs,vas,w

def warp_to(Dd, ref, src):
    """Warp source image into ref's gyro-derotated camera grid; returns normalized I, mask."""
    B=len(ref); u,v=L.T.pixel_grid(DEV)
    fx,fy,cx,cy=[Dd.K[ref,i].view(B,1,1) for i in range(4)]
    ids=torch.stack([ref,src],1).cpu(); fr=Dd.frames[ids.view(-1)].to(DEV,non_blocking=True).view(B,2,L.H0,L.W0).float()
    ds=torch.stack([(u-cx)/fx,(v-cy)/fy,torch.ones(B,L.H0,L.W0,device=DEV)],-1)
    Rb=Dd.R[ref].transpose(1,2)@Dd.R[src]; Rc=Dd.Rbc.T@Rb@Dd.Rbc
    dk=torch.einsum('bji,bhwj->bhwi',Rc,ds); z=dk[...,2].clamp(min=1e-3)
    uk=fx*dk[...,0]/z+cx; vk=fy*dk[...,1]/z+cy
    gx=(uk+0.5)/L.W0*2-1; gy=(vk+0.5)/L.H0*2-1
    out=F.grid_sample(fr[:,1:2],torch.stack([gx,gy],-1),mode='bilinear',padding_mode='zeros',align_corners=False)[:,0]
    m=((gx.abs()<=1)&(gy.abs()<=1)&(dk[...,2]>1e-3)).float()
    # Identity frame avoids resampling and always-valid mask.
    same=(ref==src).view(B,1,1); out=torch.where(same,fr[:,0],out); m=torch.where(same,torch.ones_like(m),m)
    return out,m

def imu19(Dd,a,b):
    B=len(a); Rs=Dd.R[a]
    dv=torch.einsum('bji,bj->bi',Rs,Dd.V[b]-Dd.V[a])/(0.05*5*9.81)
    return torch.cat([Dd.f[a]/9.81,Dd.g[a],Dd.f[b]/9.81,Dd.g[b],dv,
      L.T.rot_vec(Rs.transpose(1,2)@Dd.R[b]),(Dd.fx[a]/100).view(B,1)],1)

def sample(Dd,g,K,train=False,mirror=None):
    B=len(g); b=g+1; first=g-(K-2); seq=[]; masks=[]
    for t in range(K):
        im,ma=warp_to(Dd,g,first+t); seq.append(im); masks.append(ma)
    X=torch.stack(seq,1); M=torch.stack(masks,1)
    # Normalize all channels jointly per sample over valid pixels.
    valid=M
    den=valid.sum((1,2,3),keepdim=True).clamp(min=1)
    mean=(X*valid).sum((1,2,3),keepdim=True)/den
    var=(((X-mean)**2)*valid).sum((1,2,3),keepdim=True)/den
    X=(X-mean)/(var.sqrt()+5.0)*valid
    if train: X=X+0.03*torch.randn_like(X)*valid
    if mirror is None: mirror=torch.zeros(B,dtype=torch.bool,device=DEV)
    mm=mirror.view(B,1,1,1)
    X=torch.where(mm,X.flip(-1),X); M=torch.where(mm,M.flip(-1),M)
    ca=torch.linspace(-1,1,L.W0,device=DEV).view(1,1,1,1,L.W0).expand(B,1,1,L.H0,L.W0)
    cb=torch.linspace(-1,1,L.H0,device=DEV).view(1,1,1,L.H0,1).expand(B,1,1,L.H0,L.W0)
    # Keep BCHW: X and M each contribute K channels; flattening here collapses
    # channels into height and makes the coordinate concatenation 3-D.
    img=torch.cat([X,M],1)
    img=F.avg_pool2d(torch.cat([img,ca[:,0],cb[:,0]],1),2)
    # Include every causal IMU interval from the history through g->b.
    vec=torch.cat([imu19(Dd,first+j,first+j+1) for j in range(K-1)],1)
    # Mirror maps body-y and pseudo-vector signs exactly as i6lib's augmentation.
    sign=torch.tensor(L.VEC19_SIGN,device=DEV).view(1,19).repeat(1,K-1)
    vec=torch.where(mirror.view(B,1),vec*sign,vec)
    tgt=torch.stack([Dd.vb[g],Dd.vb[b]],1)
    tgt=torch.where(mirror.view(B,1,1),tgt*torch.tensor(L.SV,device=DEV).view(1,1,3),tgt)
    return img,vec,tgt

@torch.no_grad()
def predict(net,Dd,starts,K,bs=512):
    net.eval(); mus=[]; lvs=[]; ys=[]
    for i in range(0,len(starts),bs):
        x,v,y=sample(Dd,starts[i:i+bs],K); mu,lv=net(x,None,v); mus.append(mu[:,1]);lvs.append(lv[:,1]);ys.append(y[:,1])
    return torch.cat(mus),torch.cat(lvs),torch.cat(ys)

def metrics(mu,lv,y):
    e=(mu-y).norm(dim=-1); sp=y.norm(dim=-1); ps=mu.norm(dim=-1)
    moving=sp>1.0; fast=sp>1.5
    angle=torch.rad2deg(torch.acos(((mu*y).sum(-1)/(ps*sp).clamp(min=1e-8)).clamp(-1,1)))
    z=(mu-y)/torch.exp(lv/2)
    return {'n':len(e),'all':float(e.mean()),'median':float(e.median()),'p90':float(torch.quantile(e,.9)),
      'fast_gt1_5':int(fast.sum()),'fast_err':float(e[fast].mean()),'speed_abs_err':float((ps-sp).abs().mean()),
      'speed_bias':float((ps-sp).mean()),'dir_deg_gt1':float(angle[moving].mean()),
      'zrms':float(z.square().mean().sqrt()),'tail_gt1':int((e>1).sum()),'tail_gt2':int((e>2).sum())}

def smoke(tr,starts):
    """Check channel counts, finite tensors/loss, unit loss, and one backward per arm."""
    g=starts[:2]
    for K in VARIANTS:
        x,v,y=sample(tr,g,K,True,torch.zeros(len(g),dtype=torch.bool,device=DEV))
        assert x.ndim==4 and x.shape[1]==2*K+2 and v.shape==(len(g),19*(K-1))
        assert y.shape==(len(g),2,3) and all(torch.isfinite(t).all() for t in (x,v,y))
        net=L.AblNet(2*K+2,19*(K-1),0).to(DEV)
        mu,lv=net(x,None,v); loss=.5*(mu-y).square().sum(-1).mean()
        assert torch.isfinite(mu).all() and torch.isfinite(lv).all() and torch.isfinite(loss)
        loss.backward()
        assert any(p.grad is not None and torch.isfinite(p.grad).all() for p in net.parameters())
        print('smoke',K,'shapes',tuple(x.shape),tuple(v.shape),tuple(y.shape),'loss',float(loss),flush=True)

def main():
    OUT.mkdir(parents=True,exist_ok=True); torch.cuda.set_device(0)
    # CUDA_VISIBLE_DEVICES=7 maps physical GPU7 to device 0.
    tr,va,trs,vas,w=load_data(); valmeta=L.lv4.val_meta()
    # Seed before smoke/model construction, then reset so smoke does not affect the run.
    torch.manual_seed(SEED); torch.cuda.manual_seed_all(SEED); np.random.seed(SEED); random.seed(SEED)
    smoke(tr,trs)
    torch.manual_seed(SEED); torch.cuda.manual_seed_all(SEED); np.random.seed(SEED); random.seed(SEED)
    manifest={'gpu':'physical 7 (CUDA_VISIBLE_DEVICES=7)','train_cache':f'existing agents/net/cache/train ({TRAIN_LIST}), phases 0+2',
      'validation_cache':'existing agents/net/cache/val (val749 list), phase 0','common_anchor_rule':'pos>=3 and pos+1<len for every K; target is b=g+1',
      'input_context':'K consecutive frames ending at b, each past frame gyro-warped into g; all K-1 IMU interval features through b; only IMU integrations, no GT input',
      'replication_of':'pilot ctx2/ctx5; pilot seed known 20261127 for sampling but set after model initialization',
      'recipe':{'epochs':EPOCHS,'steps_per_epoch':STEPS,'train_list':TRAIN_LIST,'batch':BS,'lr':LR,'loss':'i6 abl.py MSE epoch0, beta-NLL thereafter','seed':SEED,'seed_status':'explicit; set before smoke, model initialization, sampling, and training'},
      'arms':list(VARIANTS),'n_train_anchors':len(trs),'n_val_anchors':len(vas),'limits':{'wall_seconds':7200,'output_cap_bytes':4_000_000_000}}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    job_seconds=int(os.environ.get('CTX_JOB_SECONDS','10800')); remaining=max(0,datetime.datetime(2026,11,27,16,tzinfo=datetime.timezone.utc).timestamp()-time.time()); deadline=time.monotonic()+min(job_seconds,remaining)
    for K in VARIANTS:
        name=f'ctx{K}'; d=OUT/name; d.mkdir(exist_ok=True); result=d/'result.json'; ck=d/'last.pt'
        if result.exists(): continue
        cin=2*K+2; nvec=19*(K-1); net=L.AblNet(cin,nvec,0).to(DEV)
        opt=torch.optim.AdamW(net.parameters(),lr=LR,weight_decay=1e-4)
        sched=torch.optim.lr_scheduler.OneCycleLR(opt,max_lr=LR,total_steps=EPOCHS*STEPS,pct_start=.1)
        start=0
        if ck.exists():
            c=torch.load(ck,map_location=DEV,weights_only=False); net.load_state_dict(c['net']);opt.load_state_dict(c['opt']);sched.load_state_dict(c['sched']);start=c['epoch']+1
            torch.set_rng_state(c['torch_rng'].cpu());torch.cuda.set_rng_state(c['cuda_rng']);np.random.set_state(c['np_rng']);random.setstate(c['py_rng'])
            print('resume',name,'at epoch',start,flush=True)
        else: pass
        print('start',name,'parameters',sum(p.numel() for p in net.parameters()),'cin',cin,'nvec',nvec,'anchors',len(trs),len(vas),flush=True)
        for ep in range(start,EPOCHS):
            if time.monotonic()>=deadline: raise TimeoutError('per-job wall budget')
            t0=time.monotonic(); net.train(); agg=0.
            for _ in range(STEPS):
                g=trs[torch.multinomial(w,BS,replacement=True)]; mir=torch.rand(BS,device=DEV)<.5
                x,v,y=sample(tr,g,K,True,mir);mu,lv=net(x,None,v)
                if ep==0: loss=.5*(mu-y).square().sum(-1).mean(-1).mean()
                else:
                    nll=.5*((y-mu).square()*torch.exp(-lv)+lv)
                    loss=(nll*torch.exp(lv.detach()).sqrt()).sum(-1).mean(-1).mean()
                opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(net.parameters(),5.0);opt.step();sched.step();agg+=float(loss.detach())
            val=None
            if ep in (4,12,EPOCHS-1):
                mu,lv,y=predict(net,va,vas,K);val=metrics(mu,lv,y)
            state={'epoch':ep,'net':net.state_dict(),'opt':opt.state_dict(),'sched':sched.state_dict(),
                   'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state(),'np_rng':np.random.get_state(),'py_rng':random.getstate()}
            tmp=ck.with_suffix('.tmp');torch.save(state,tmp);tmp.replace(ck)
            row={'epoch':ep,'train_loss':agg/STEPS,'val':val,'seconds':time.monotonic()-t0,'total_elapsed':time.monotonic()-RUN_START}
            with (d/'epochs.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
            print(name,json.dumps(row),flush=True)
        mu,lv,y=predict(net,va,vas,K); r=metrics(mu,lv,y)
        # End-to-end feature+network wall latency, batch one, warm GPU.
        gs=vas[:128];torch.cuda.synchronize();t0=time.perf_counter()
        for ix in gs: sample(va,ix.reshape(1),K)
        torch.cuda.synchronize(); prep=(time.perf_counter()-t0)/len(gs)*1000
        xx,vv,_=sample(va,vas[:1],K); torch.cuda.synchronize();t0=time.perf_counter()
        for _ in range(1000): net(xx,None,vv)
        torch.cuda.synchronize(); infer=(time.perf_counter()-t0)/1000*1000
        torch.save(net.state_dict(),d/'model.pt')
        r.update(variant=name,K=K,cin=cin,nvec=nvec,params=sum(p.numel() for p in net.parameters()),
          prep_latency_ms_batch1=prep,network_latency_ms_batch1=infer,validation_anchor_rule='pos>=3',
          val_episode_count=len(va.names),checkpoint=str(d/'model.pt'))
        result.write_text(json.dumps(r,indent=2)+'\n')
        pred=OUT/f'{name}_val_predictions.npz';np.savez_compressed(pred,mu=mu.cpu().numpy().astype(np.float16),lv=lv.cpu().numpy().astype(np.float16),y=y.cpu().numpy().astype(np.float16),fid=va.fid[vas].cpu().numpy(),pos=va.pos[vas].cpu().numpy(),flight_names=np.asarray(va.names))
        r['model_sha256']=hashlib.sha256((d/'model.pt').read_bytes()).hexdigest()
        result.write_text(json.dumps(r,indent=2)+'\n')
        print('DONE',name,json.dumps(r),flush=True)
    (OUT/'queue.done').write_text('all context arms completed\n')

if __name__=='__main__': main()
