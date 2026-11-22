"""Isolated long teacher / same-cost lcJ student training, with auditable manifests."""
import argparse,json,sys,time,os
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
H=Path(__file__).resolve().parent; SM=H.parent; BASE=SM.parents[2]
sys.path[:0]=[str(SM/'learnvel'),str(SM/'learned_c'),str(SM/'learned')]
import train as T
from lv_train import Multi
from lv_eval import EvalData

def dataset_files():
    d=json.load(open(H/'tables/data_audit.json')); rows=d['train'][:]
    p=H/'gen/sl_rows.json'
    if p.exists():
        ho={tuple(x) for x in d['holdout_scenes']}; bad=set(d['forbidden_scenes'])
        import hashlib
        for n,r in json.load(open(p)).items():
            fo=int(hashlib.sha256(f"{r['catalog']}:{r['scene']}".encode()).hexdigest()[:8],16)%5
            assert fo in (0,1,2) and r['scene'] not in bad and (r['catalog'],r['scene']) not in ho
            rows.append(dict(r,cache=str(BASE/'tmp/sl_cache_train'/f'{n}.npz')))
    assert len({r['name'] for r in rows})==len(rows)
    return rows

def model(a): return T.Net(a.res,a.width,a.nf,13+6*(a.nf-1),deep=a.deep,hidden=a.hidden)

def stats(mu,lv,y):
    mu,lv,y=mu[:,1],lv[:,1],y[:,1];e=(mu-y).norm(dim=-1);sp=y.norm(dim=-1); z=(mu-y)*torch.exp(-lv/2)
    out={}
    for label,mask in [('all',sp>=0),('lt1',sp<1),('1to2',(sp>=1)&(sp<=2)),('gt2',sp>2)]:
        out[label]=dict(n=int(mask.sum()),err=float(e[mask].mean()),zrms=float(z[mask].square().mean().sqrt()),scale=float((mu[mask]*y[mask]).sum()/y[mask].square().sum().clamp(min=1e-12)))
    return out

@torch.no_grad()
def evaluate(net,D,st,a):
    mu,lv,y=T.predict(net,D,st,a.nf,a.gap,a.res,bs=256)
    return stats(mu,lv,y)

def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--nf',type=int,default=2);p.add_argument('--gap',type=int,default=1);p.add_argument('--res',type=int,default=128);p.add_argument('--width',type=float,default=2);p.add_argument('--deep',action='store_true');p.add_argument('--hidden',type=int,default=256);p.add_argument('--seed',type=int,default=0);p.add_argument('--epochs',type=int,default=120);p.add_argument('--steps',type=int,default=400);p.add_argument('--bs',type=int,default=128);p.add_argument('--lr',type=float,default=.002);p.add_argument('--teacher',default='');p.add_argument('--init',default='');p.add_argument('--kd',type=float,default=.5)
    a=p.parse_args();torch.manual_seed(a.seed);np.random.seed(a.seed);torch.backends.cudnn.benchmark=True
    rows=dataset_files(); out=H/'runs'/a.name;out.mkdir(exist_ok=True);(out/'manifest.json').write_text(json.dumps(rows,indent=1));(out/'config.json').write_text(json.dumps(vars(a),indent=1))
    import shutil;shutil.copy2(__file__,out/'train_source.py')
    print('loading',len(rows),'train flights',flush=True);D=Multi([Path(r['cache']) for r in rows],'cuda',(0,2))
    E=EvalData(sorted((BASE/'tmp/lv_cache').glob('st2*.npz')),'cuda');E3=EvalData(sorted((BASE/'tmp/sl_cache_st3').glob('*.npz')),'cuda')
    st=D.valid_starts(a.nf,a.gap);es=E.valid_starts(a.nf,a.gap);es3=E3.valid_starts(a.nf,a.gap)
    # Joint speed/texture balancing. Texture computed in chunks to bound device memory.
    tex=[]
    for chunk in D.frames.split(4096):
        x=chunk.float();tex.append(((x[:,:,2:]-x[:,:,:-2]).abs()>8).float().mean((1,2)))
    tex=torch.cat(tex);sp=D.vb.norm(dim=-1);sb=torch.bucketize(sp,torch.tensor([.3,1.,2.,3.],device='cuda'));tb=(tex>.07).long();cell=sb*2+tb;cells=cell[st+(a.nf-1)*a.gap];cnt=torch.bincount(cells,minlength=10).float().clamp(min=1);w=cnt[cells].pow(-.5)
    del tex
    net=model(a).cuda();teacher=None;ta=None
    if a.init: net.load_state_dict(torch.load(a.init,map_location='cuda',weights_only=True))
    if a.teacher:
        td=Path(a.teacher);ta=argparse.Namespace(**json.load(open(td/'config.json')));assert a.nf==2 and a.gap==1 and a.res==64 and a.width in (1,1.5) and not a.deep and a.hidden==128
        teacher=model(ta).cuda();teacher.load_state_dict(torch.load(td/'best.pt',map_location='cuda',weights_only=True));teacher.eval();teacher.requires_grad_(False)
        cal=json.load(open(td/'result.json')).get('sigma_scale',1.0)
        # Student and teacher share final frame, despite different temporal windows.
        span=(ta.nf-1)*ta.gap;st=D.valid_starts(ta.nf,ta.gap);cells=cell[st+span];cnt=torch.bincount(cells,minlength=10).float().clamp(min=1);w=cnt[cells].pow(-.5)
    print('loaded anchors',len(st),'params/macs',T.count(net,a.nf,13+6*(a.nf-1),a.res),flush=True)
    opt=torch.optim.AdamW(net.parameters(),lr=a.lr,weight_decay=1e-4);sched=torch.optim.lr_scheduler.OneCycleLR(opt,max_lr=a.lr,total_steps=a.epochs*a.steps,pct_start=.1)
    best=1e9;log=[];t0=time.time()
    for ep in range(a.epochs):
        net.train();total=0
        # Draw once per epoch: avoids repeated O(N) multinomial setup per batch.
        sampled=st[torch.multinomial(w,a.bs*a.steps,replacement=True)].view(a.steps,a.bs)
        for g in sampled:
            sg=g if teacher is None else g+(ta.nf-1)*ta.gap-1
            img,vec,y,_=T.build_batch(D,sg,a.nf,a.gap,a.res,True);fl=torch.rand(a.bs,device='cuda')<.5
            if fl.any(): img[fl],vec[fl],y[fl]=T.flip(img[fl],vec[fl],y[fl],a.nf)
            mu,lv=net(img,vec)
            loss=(T.nll(mu,lv,y)*torch.exp(lv.detach()).pow(.5)).sum(-1).mean() if ep>=1 else .5*(mu-y).square().sum(-1).mean()
            if teacher is not None:
                with torch.no_grad():
                    ti,tv,_,_=T.build_batch(D,g,ta.nf,ta.gap,ta.res,False)
                    if fl.any(): ti[fl],tv[fl],_=T.flip(ti[fl],tv[fl],torch.zeros_like(y[fl]),ta.nf)
                    mt,lt=teacher(ti,tv);lt=lt+2*np.log(cal)
                # Soft velocity + calibrated sigma, with truth supervision on both heads.
                soft_lv=torch.log(torch.exp(lt[:,1])+(mu[:,1].detach()-mt[:,1]).square()).clamp(-7,4)
                kd=.5*((mu[:,1]-mt[:,1]).square()*torch.exp(-.5*lt[:,1])).mean()+.25*(lv[:,1]-soft_lv).square().mean();loss=loss+a.kd*kd
            opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(net.parameters(),5);opt.step();sched.step();total+=float(loss.detach())
        r2=evaluate(net,E,es,a);r3=evaluate(net,E3,es3,a)
        # Pooled tuning data only, high-speed error carries additional priority.
        n2,n3=r2['all']['n'],r3['all']['n'];crit=(n2*r2['all']['err']+n3*r3['all']['err'])/(n2+n3)+.25*(r2['gt2']['err']+r3['gt2']['err'])/2
        rec=dict(epoch=ep,loss=total/a.steps,st2dev=r2,st3=r3,crit=crit,seconds=time.time()-t0);log.append(rec)
        print(a.name,ep,'loss',round(total/a.steps,4),'st2',round(r2['all']['err'],4),'st3',round(r3['all']['err'],4),'fast',round((r2['gt2']['err']+r3['gt2']['err'])/2,4),'seconds',round(time.time()-t0),flush=True)
        if ep>=3 and crit<best:
            best=crit;torch.save(net.state_dict(),out/'best.pt');sigma=((r2['all']['zrms']**2*n2+r3['all']['zrms']**2*n3)/(n2+n3))**.5
            result=dict(args=vars(a),best_epoch=ep,best_crit=best,st2dev=r2,st3=r3,sigma_scale=sigma,n_train_flights=len(rows),n_train_scenes=len({(r['catalog'],r['scene']) for r in rows}));(out/'result.json').write_text(json.dumps(result,indent=1))
        (out/'log.json').write_text(json.dumps(log,indent=1))
        torch.save(dict(epoch=ep,net=net.state_dict(),opt=opt.state_dict(),sched=sched.state_dict()),out/'last.pt')
    print('DONE',a.name,flush=True)
if __name__=='__main__':main()
