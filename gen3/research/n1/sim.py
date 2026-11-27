import sys,glob,json,numpy as np
from concurrent.futures import ProcessPoolExecutor
g=np.array([0,0,-9.81])
def sk(a): return np.array([[0,-a[2],a[1]],[a[2],0,-a[0]],[-a[1],a[0],0]])
def expm(w):
    th=np.linalg.norm(w)
    if th<1e-9: return np.eye(3)+sk(w)
    K=sk(w/th);return np.eye(3)+np.sin(th)*K+(1-np.cos(th))*K@K
def run(args):
    f,sig,P,model,lat,opts=args
    d=np.load(f);t=d['t'];gy=d['gyro'];ac=d['acc'];Rt=d['R'];vt=d['v'];pt=d['p'];N=len(t)
    rng=np.random.default_rng(abs(hash(f))%2**31)
    # initial attitude from accel (tilt), yaw 0
    a0=ac[:10].mean(0);a0/=np.linalg.norm(a0);z=np.array([0,0,1.]);ax=np.cross(a0,z);s=np.linalg.norm(ax);c=a0@z
    R=expm(ax/s*np.arctan2(s,c)) if s>1e-9 else np.eye(3)
    v=np.zeros(3);p=np.zeros(3);bg=np.zeros(3);ba=np.zeros(3)
    P0=np.diag([0.05**2]*2+[0.001**2]+[2.0**2]*3+[1e-6]*3+[0.02**2]*3+[0.2**2]*3)
    P0[2,2]=1e-6
    if opts.get('orbg'): bg=np.mean(gy-d['wgt'],0);P0[9:12,9:12]=np.eye(3)*1e-8
    sg,sa=0.07,0.28;rg,ra=opts.get('rg',6e-4),opts.get('ra',1e-3)
    Pm=P0.copy();x=np.zeros(15)  # error mean main block (zeroed after inject)
    clones=[] # dict(Rk,vk,idx)
    # measurement noise process (in body frame; noise relative to true body velocity)
    sc=rng.normal()*opts.get('scale',0.0); nz=np.zeros(3);dtf=0.05
    sched=[(k*P+opts.get('phase',0),k*P+opts.get('phase',0)+lat) for k in range(1,N//10//P+1)]
    fr=0;pend=[]
    traj=np.zeros((N//10+1,3));
    nclone_max=0
    Phi=np.eye(15);Qa=np.zeros((15,15));ipos=0
    Ec=np.zeros(0)  # clone mean
    Pfull=Pm  # covariance with clones appended
    meas_queue={} # frame -> list of (clone creation frame)
    snaps={}
    R0=R.copy();nxt=0
    for i in range(1,N):
        dt=t[i]-t[i-1]
        w=gy[i]-bg;a=ac[i]-ba
        Ra=R@a
        # F
        F=np.zeros((15,15));F[0:3,9:12]=-R;F[3:6,0:3]=-sk(Ra);F[3:6,12:15]=-R;F[6:9,3:6]=np.eye(3)
        Fd=np.eye(15)+F*dt
        Qd=np.zeros((15,15));Qd[0:3,0:3]=np.eye(3)*(sg*dt)**2;Qd[3:6,3:6]=np.eye(3)*(sa*dt)**2
        Qd[9:12,9:12]=np.eye(3)*rg**2*dt;Qd[12:15,12:15]=np.eye(3)*ra**2*dt
        p=p+v*dt+0.5*(Ra+g)*dt*dt;v=v+(Ra+g)*dt;R=R@expm(w*dt)
        Phi=Fd@Phi;Qa=Fd@Qa@Fd.T+Qd
        if i%10: continue
        k=i//10  # frame index
        n=Pfull.shape[0]
        Pfull[:15,:]=Phi@Pfull[:15,:];Pfull[:,:15]=Pfull[:,:15]@Phi.T;Pfull[:15,:15]+=Qa
        Pfull=0.5*(Pfull+Pfull.T)
        Phi=np.eye(15);Qa=np.zeros((15,15))
        traj[k]=R0.T@p
        # clone creation at frame time of net input
        if k%P==0 and k>0:
            m=Pfull.shape[0]
            Pn=np.zeros((m+6,m+6));Pn[:m,:m]=Pfull
            Pn[m:,:m]=Pfull[3:6,:] if False else np.vstack([Pfull[0:3,:],Pfull[3:6,:]]) if False else 0
            # clone of (theta,v) = rows 0:3 and 3:6 of main block
            sel=np.r_[0:6]
            T=np.zeros((m+6,m));T[:m,:m]=np.eye(m);T[m:m+6,sel]=np.eye(6)
            Pfull=T@Pfull@T.T
            clones.append(dict(Rk=R.copy(),vk=v.copy(),due=k+lat,idx=m,tr=k,ztrue=None))
            # measurement realised now (net sees frames now): noisy body vel at the time
            vb=Rt[i].T@vt[i]
            if model=='white': nz=rng.normal(size=3)*sig
            elif model.startswith('ar'):
                tau=float(model[2:]);al=np.exp(-dtf*P/tau);nz=al*nz+np.sqrt(1-al*al)*rng.normal(size=3)*sig
            elif model=='scale': nz=rng.normal(size=3)*sig*0.5+sc*vb*opts.get('sc_k',1.0)
            clones[-1]['z']=vb+nz
            clones[-1]['xm']=np.zeros(6)
        # keep clone means in x vector: handled via stored xm
        # process due
        done=[c for c in clones if c['due']<=k]
        if 'noupd' in opts: done=[]
        for c in done:
            m=Pfull.shape[0];ci=c['idx']
            Rk=c['Rk'];vk=c['vk']
            Hm=np.zeros((3,m));Hm[:,ci:ci+3]=Rk.T@sk(vk);Hm[:,ci+3:ci+6]=Rk.T
            Rm=np.eye(3)*(sig*opts.get('inf',1.0))**2
            xc=np.concatenate([x[:15],np.zeros(0)])
            # clone means stored in c['xm']
            xm=np.concatenate([x[:15]*0]) 
            # residual: z - h(nom) - H xhat_clone (clone mean)
            y=c['z']-Rk.T@vk-Hm[:,ci:ci+6]@c['xm']
            S=Hm@Pfull@Hm.T+Rm
            Kg=Pfull@Hm.T@np.linalg.inv(S)
            dx=Kg@y  # increments to all means
            # update means
            for cc in clones:
                if cc is c: continue
                cc['xm']=cc['xm']+dx[cc['idx']:cc['idx']+6]
            Pfull=(np.eye(m)-Kg@Hm)@Pfull;Pfull=0.5*(Pfull+Pfull.T)
            # inject main error
            dm=dx[:15]
            R=expm(dm[0:3])@R;v=v+dm[3:6];p=p+dm[6:9];bg=bg+dm[9:12];ba=ba+dm[12:15]
            # clones' mean relative to their nominal unchanged (true error est stays), but main-state reset affects cross terms: ignore (small)
            # remove clone c
            keep=np.r_[0:ci,ci+6:m];Pfull=Pfull[np.ix_(keep,keep)]
            for cc in clones:
                if cc is c: continue
                if cc['idx']>ci: cc['idx']-=6
            clones.remove(c)
            R0=R0
        nclone_max=max(nclone_max,len(clones))
    # score: GT position in start-body frame
    Rt0=Rt[0];ptb=(pt-pt[0])@Rt0
    ik=np.arange(0,N,10)[:len(traj)-1+1][:len(traj)]
    ik=np.clip(ik,0,N-1)
    err=np.linalg.norm(traj[:len(ik)]-ptb[ik],axis=1)[1:]
    # heading err: yaw of R_est vs R_true^ (relative to start) at end
    Rrel_est=R0.T@R; Rrel_tr=Rt0.T@Rt[-1]
    Dr=Rrel_est@Rrel_tr.T;hd=np.degrees(np.arccos(np.clip((np.trace(Dr)-1)/2,-1,1)))
    bgtrue=np.mean(gy-d['wgt'],0)
    return dict(f=f,ate=float(err.mean()),end=float(err[-1]),hd=float(hd),bgerr=float(np.linalg.norm(bg-bgtrue)),bgn=float(np.linalg.norm(bgtrue)))
if __name__=='__main__':
    cfgs=json.load(open(sys.argv[1]));out=sys.argv[2];fl=sorted(glob.glob('cache/*.npz'))
    done=set()
    try: done={json.loads(l)['name'] for l in open(out)}
    except: pass
    ex=ProcessPoolExecutor(8)
    for c in cfgs:
        if c['name'] in done: continue
        r=list(ex.map(run,[(f,c['sig'],c['P'],c['model'],c['lat'],c.get('opts',{})) for f in fl]))
        a=np.array([x['ate'] for x in r])
        rec=dict(name=c['name'],cfg=c,ate=float(a.mean()),med=float(np.median(a)),hd=float(np.mean([x['hd'] for x in r])),hdmed=float(np.median([x['hd'] for x in r])),bgerr=float(np.mean([x['bgerr'] for x in r])),bgn=float(np.mean([x['bgn'] for x in r])),per=[x['ate'] for x in r])
        open(out,'a').write(json.dumps(rec)+'\n')
