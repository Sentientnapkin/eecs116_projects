import os,sys,json,time,traceback
os.environ['OMP_NUM_THREADS']='1'; os.environ['OPENBLAS_NUM_THREADS']='1'
sys.path.insert(0,'/data/backups/rganapa/Sebastian/gen3/research/r6/tools')
import numpy as np
from pathlib import Path
import fl,solve
ROOT=Path('/tmp/vio_loop2/geometry/init_compare'); OUT=ROOT/'out'; OUT.mkdir(exist_ok=True)
LIST=[Path('/tmp/vio_loop2/shared/screen24')/(x+'.zip') for x in ('s3v3va-fo-9300479','s3v3va-ro-9300065','s3v3va-wa-9300338')]

def angle(a,b):
 a=np.asarray(a);b=np.asarray(b);return float(np.degrees(np.arccos(np.clip(a@b/(np.linalg.norm(a)*np.linalg.norm(b)),-1,1))))
def run(z):
 fid=z.stem; dst=OUT/(fid+'.json')
 if dst.exists(): return json.load(open(dst))
 st=time.time(); F=fl.Flight(str(z),nframes=41,frames=True)
 ba,bg,ba_std,bg_std=F.oracle_biases(20.0)
 pi=F.preint(bg=bg,ba_lin=ba)
 gt=F.gt_init(); tr=fl.tracks(F,Rrel=pi['R'],maxc=150,minc=100)
 obs=solve.bearings(F,tr,pi,40)
 # Zero-residual geometry control: oracle corrected preintegration + zero residual ba reproduces GT body position plus camera lever arm.
 M0=solve.Model(pi,free=(),fixed={'v0':gt['v0'],'g':gt['g'],'ba':np.zeros(3)},p_bc=F.p_bc)
 pred=M0.centres(np.empty(0)); truth=gt['p']+np.einsum('nij,j->ni',gt['Rrel'],F.p_bc)
 geom_max=float(np.max(np.linalg.norm(pred-truth,axis=1)))
 # Finite camera displacement direction/control, evaluated from poses at each interval, not instantaneous velocity.
 finite=[]
 for k in (5,8,10,13,15,20,30,40):
  dc=truth[k]-truth[0]; finite.append({'k':k,'dt':float(F.ft[k]-F.ft[0]),'disp':float(np.linalg.norm(dc)),'direction':(dc/max(np.linalg.norm(dc),1e-12)).tolist()})
 results=[]
 gprior=gt['g']; prior_mu=np.zeros(6);prior_mu[3:]=gprior
 prior_I=np.zeros((6,6));prior_I[3:,3:]=np.eye(3)/(9.81*.15)**2
 for gmode in ('fixed_gt','free_gt_direction_prior'):
  free=('v0',) if gmode=='fixed_gt' else ('v0','g')
  fixed={'g':gt['g'],'ba':np.zeros(3)}
  M=solve.Model(pi,free=free,fixed=fixed,p_bc=F.p_bc)
  prior=None if gmode=='fixed_gt' else (prior_mu,prior_I)
  x0=np.zeros(M.n)
  for kind in ('dir','pw','mv'):
   got=solve.solve(M,obs,kind=kind,iters=5,prior=prior,gnorm=(gmode!='fixed_gt'))
   if got is None: results.append({'gravity':gmode,'kind':kind,'failure':'singular'});continue
   x,info=got; un=M.unpack(x); v=un['v0']; ve=float(np.linalg.norm(v-gt['v0']))
   H=info[0]; dh=np.sqrt(np.maximum(np.diag(H),1e-30)); Hn=H/dh[:,None]/dh[None,:]
   results.append({'gravity':gmode,'kind':kind,'v0_m_per_s':v.tolist(),'v0_error_m_per_s':ve,'v0_sign_dot':float(v@gt['v0']/(np.linalg.norm(v)*np.linalg.norm(gt['v0'])+1e-12)), 'gravity_m_per_s2_norm':float(np.linalg.norm(un['g'])),'v0_direction_unit_norm':float(np.linalg.norm(v)/max(np.linalg.norm(v),1e-12)), 'normal_condition_raw_unit_dependent_includes_prior':float(np.linalg.cond(H)),'normal_condition_diagonal_normalized_includes_prior':float(np.linalg.cond(Hn)),'landmarks':int(info[3]),'used_tracks':len(obs),'chi':float(info[1])})
 out={'id':fid,'source':'screen24','units':{'v0':'m/s','gravity':'m/s^2','finite_displacement':'m','dt':'s','v0_error':'m/s','raw_normal_condition':'unit-dependent; prior included','diagonal_normalized_normal_condition':'dimensionless; prior included'},'oracle_bias_gt_derived_20s_nondeployable':{'ba_m_per_s2':ba.tolist(),'bg_rad_per_s':bg.tolist(),'ba_std_m_per_s2':ba_std.tolist(),'bg_std_rad_per_s':bg_std.tolist()},'frames':F.N,'tracks':len(tr),'observations':len(obs),'track_obs':int(sum(len(ks) for ks,D in obs)),'geometry_max_center_error_m':geom_max,'finite_camera_intervals':finite,'results':results,'seconds':time.time()-st}
 dst.write_text(json.dumps(out,indent=2)+'\n');return out
if __name__=='__main__':
 for z in LIST:
  try:
   r=run(z); print(r['id'],r['observations'],r['seconds'],flush=True)
  except Exception:
   traceback.print_exc();raise
