import os, sys, json, time, traceback
os.environ['OMP_NUM_THREADS']='1'; os.environ['OPENBLAS_NUM_THREADS']='1'
sys.path.insert(0, '/data/backups/rganapa/Sebastian/gen3/research/r6/tools')
import numpy as np
from pathlib import Path
# Import the r6 storage module without viobench's unrelated runner/wasmtime startup.
import types
_vb='/dev/shm/sebastian-vio/viobench/viobench'
for _name,_path in [('viobench',_vb),('viobench.tools',_vb+'/tools'),('viobench.tools.datasets',_vb+'/tools/datasets')]:
    _m=types.ModuleType(_name); _m.__path__=[_path]; sys.modules[_name]=_m
import fl, solve

ROOT=Path('/tmp/vio_loop3/scale_init'); OUT=ROOT/'out'; OUT.mkdir(parents=True,exist_ok=True)
LIST=[Path('/tmp/vio_loop2/shared/screen24')/(x+'.zip') for x in ('s3v3va-fo-9300479','s3v3va-ro-9300065','s3v3va-wa-9300338')]

def fit(obs, pi, pbc, ranges, lam_mode, prior=True):
    # observations hold anchor and target bearing, target frame, pseudo-range.
    # Projected residual Q(dk) [dt*w + lambda*de - rhohat*da] = 0.
    n=4 if lam_mode=='free' else 3; H=np.zeros((n,n)); b=np.zeros(n)
    for item in obs:
        a,k,da,dk,rho=item
        dt=pi['dt'][k]-pi['dt'][a]
        de=(pi['al'][k]+pi['R'][k]@pbc)-(pi['al'][a]+pi['R'][a]@pbc)
        Q=np.eye(3)-np.outer(dk,dk)
        A=np.zeros((3,n)); A[:,:3]=dt*np.eye(3)
        if n==4: A[:,3]=de
        y=Q@(rho*da - de) if n==3 else Q@(rho*da)
        if n==3: A=Q@A
        else:
            A=Q@A; y=Q@y
        wt=1.0/max(rho*rho,1e-6) # relative range noise, plus robust-ish near-depth stability
        H += wt*A.T@A; b += wt*A.T@y
    if n==4 and prior:
        H[3,3]+=25.0; b[3]+=25.0 # lambda ~ N(1,.2^2)
    ev=np.linalg.eigvalsh(H); cond=float(ev[-1]/max(ev[0],1e-30))
    if ev[0] <= 1e-10*max(ev[-1],1e-30) or not np.isfinite(cond): return None,cond
    x=np.linalg.solve(H,b)
    if n==4:
        lam=float(x[3]); lamc=float(np.clip(lam,.25,4.0)); v=x[:3]/lamc
    else: lamc=1.0; v=x
    return {'v0':v.tolist(),'lambda_raw':float(x[3]) if n==4 else 1.0,'lambda':lamc,'condition':cond,'normal_eigen_min':float(ev[0])},cond

def synthetic_check():
    rng=np.random.default_rng(1776); N=20; dt=np.linspace(0,3,N); g=np.array([0.,0.,-9.81]); v=np.array([2.2,-.6,.3]); lam=1.2
    # Nonconstant IMU alpha and lever-arm motion make the shared scale observable.
    al=np.stack([.08*np.sin(dt*1.7),.04*dt**2,.03*np.cos(dt*1.3)],1); R=np.array([fl.expm(np.array([.05*t,.02*np.sin(t),.03*t])) for t in dt]); pbc=np.array([.12,-.04,.08])
    C=dt[:,None]*v+.5*dt[:,None]**2*g+al+np.einsum('nij,j->ni',R,pbc)
    pi={'dt':dt,'al':al+.5*dt[:,None]**2*g,'R':R}
    # Construct exact rays from fixed points, and exact pseudo-ranges in the shared scale model.
    tracks=[]
    for _ in range(40):
        P=np.array([rng.uniform(-2,2),rng.uniform(-2,2),rng.uniform(8,15)])
        rays=P[None,:]-C; rays/=np.linalg.norm(rays,axis=1,keepdims=True)
        a=0
        for k in range(1,N): tracks.append((a,k,rays[a],rays[k],lam*np.linalg.norm(P-C[a])))
    got,cond=fit(tracks,pi,pbc,None,'free',False)
    err=np.linalg.norm(np.array(got['v0'])-v) if got else 999
    # Pure constant velocity, zero lever arm and no alpha variation has no lambda column.
    Cv=dt[:,None]*v; piv={'dt':dt,'al':np.zeros_like(Cv),'R':np.repeat(np.eye(3)[None],N,axis=0)}; deg=[]
    for _ in range(20):
        P=np.array([rng.uniform(-2,2),rng.uniform(-2,2),rng.uniform(8,15)]); rays=P[None,:]-Cv; rays/=np.linalg.norm(rays,axis=1,keepdims=True)
        for k in range(1,N): deg.append((0,k,rays[0],rays[k],lam*np.linalg.norm(P-Cv[0])))
    dgot,dcond=fit(deg,piv,np.zeros(3),None,'free',False)
    return {'recovered_lambda':got['lambda_raw'] if got else None,'v0_error':float(err),'condition':cond,'pass':bool(got and abs(got['lambda_raw']-lam)<1e-6 and err<1e-6 and dgot is None),'constant_velocity_lambda_unobservable':bool(dgot is None),'constant_velocity_condition':dcond}

def angle(a,b): return float(np.degrees(np.arccos(np.clip(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)),-1,1))))
def run(z):
    fid=z.stem; started=time.time(); F=fl.Flight(str(z),nframes=41,frames=True)
    ba,bg,bas,bgs=F.oracle_biases(20.0); pi=F.preint(bg=bg,ba_lin=ba); gt=F.gt_init()
    tr=fl.tracks(F,Rrel=pi['R'],maxc=150,minc=100); obs=solve.bearings(F,tr,pi,40)
    # Truth triangulation from tracked image rays and GT camera centres, never rendered depth.
    Cgt=gt['p']+np.einsum('nij,j->ni',gt['Rrel'],F.p_bc)
    rng=np.random.default_rng(sum(fid.encode()))
    eligible=[]; rejected=0
    for ks,D in obs:
        P,ev=solve._tri(ks,D,Cgt)
        if P is None: rejected+=1; continue
        a=int(ks[0]); rho=float(np.dot(P-Cgt[a],D[0]))
        if rho<=0 or not np.isfinite(rho) or ev[0]/ev[-1]<1e-5: rejected+=1; continue
        eligible.append((ks,D,a,rho))
    results=[]
    # Shared 10/20% scale shifts and independent 10% range noise, reused across gravity/window methods.
    rawnoise=np.array([rng.normal() for _ in eligible])
    for gmode in ('true_g','perturbed_g_1deg'):
      g=gt['g'].copy()
      if gmode!='true_g':
        ax=np.cross(g,np.array([1.,0.,0.])); ax/=np.linalg.norm(ax); g=fl.expm(ax*np.deg2rad(1.0))@g
      for W in (10,20,40):
        for shared in (.10,.20):
          for noise_pct in (.10,):
            ranges=(1+shared)*np.array([r[3] for r in eligible]+[0.]) # shared vector deterministic
            ranges=ranges[:-1]*(1+noise_pct*rawnoise)
            for nfr in (W,):
              fitobs=[]; tracks_window=0
              for j,(ks,D,a,rho) in enumerate(eligible):
                keep=np.where(ks<nfr)[0]
                if len(keep)<2: continue
                tracks_window+=1
                anc=int(ks[keep[0]]); da=D[keep[0]]
                for ix in keep[1:]:
                  k=int(ks[ix]); fitobs.append((anc,k,da,D[ix],float(ranges[j])))
              # Model uses oracle-bias preintegration; explicit gravity term added to alpha.
              pi_g=dict(pi); pi_g['al']=pi['al']+.5*pi['dt'][:,None]**2*g
              if not fitobs: continue
              for mode in ('fixed_lambda1','free_lambda_prior'):
                got,cond=fit(fitobs,pi_g,F.p_bc,ranges,'fixed' if mode=='fixed_lambda1' else 'free',mode!='fixed_lambda1')
                if got:
                  vv=np.array(got['v0']); truev=gt['v0']; got.update({'v0_error_mps':float(np.linalg.norm(vv-truev)),'direction_error_deg':angle(vv,truev),'speed_mps':float(np.linalg.norm(vv)),'used_tracks':tracks_window,'equations':len(fitobs),'window_duration_s':float(pi['dt'][nfr-1]-pi['dt'][0])})
                results.append({'gravity':gmode,'window_frames':W,'shared_scale_bias':shared,'independent_range_noise_fraction':noise_pct,'method':mode,'result':got,'condition':cond,'rejected_tracks_total':rejected,'eligible_gt_triangulated_tracks':len(eligible)})
    return {'id':fid,'oracle_bias_20s_nondeployable':{'ba':ba.tolist(),'bg':bg.tolist(),'ba_std':bas.tolist(),'bg_std':bgs.tolist()},'frames':F.N,'tracked_tracks':len(obs),'gt_triangulated_coverage_fraction':len(eligible)/max(len(obs),1),'rejected_bad_gt_triangulations':rejected,'synthetic_unit_check':synthetic_check(),'results':results,'seconds':time.time()-started}

if __name__=='__main__':
    print('synthetic',json.dumps(synthetic_check()),flush=True)
    for z in LIST:
      p=OUT/(z.stem+'.json')
      try:
        rr=run(z); p.write_text(json.dumps(rr,indent=2)+'\n'); print(z.stem,rr['tracked_tracks'],rr['seconds'],flush=True)
      except Exception: traceback.print_exc(); raise
