"""T2: kinematic structure from truth: heading-vs-velocity, tilt-acceleration (flatness), accel/jerk/yaw-rate envelope, start-state distribution."""
import sys; sys.path.insert(0,'research/single_model/simstruct')
from load import *
def smooth(x,k):
    ker=np.ones(k)/k; return np.stack([np.convolve(x[:,i],ker,'same') for i in range(x.shape[1])],1)
def wrap(a): return (a+np.pi)%(2*np.pi)-np.pi
out={}
def analyse(d):
    e=load(d); gt=e.ground_truth; t=gt[:,0]; p=gt[:,1:4]; Rm=q2R(gt[:,4:8])
    dt=0.005
    v=smooth(np.gradient(p,dt,axis=0),5)      # 25 ms smooth
    a=smooth(np.gradient(v,dt,axis=0),9)
    jk=smooth(np.gradient(a,dt,axis=0),9)
    zb=Rm[:,:,2]; xb=Rm[:,:,0]
    f=a+np.array([0,0,9.81]); fn=f/np.linalg.norm(f,axis=1,keepdims=True)
    flat_err=np.degrees(np.arccos(np.clip((fn*zb).sum(1),-1,1)))     # angle between thrust axis and (a-g)
    tilt=np.degrees(np.arccos(np.clip(zb[:,2],-1,1)))
    yaw=np.arctan2(xb[:,1],xb[:,0])
    yawrate=np.gradient(np.unwrap(yaw),dt)
    yawrate=smooth(yawrate[:,None],9)[:,0]
    vh=v[:,:2]; sh=np.linalg.norm(vh,axis=1)
    hd=np.arctan2(vh[:,1],vh[:,0]); delta=np.degrees(wrap(hd-yaw))
    wb=rotvec_rel(Rm[:-1],Rm[1:])/dt; wb=np.vstack([wb,wb[-1]])
    return dict(t=t,v=v,a=a,jk=jk,flat_err=flat_err,tilt=tilt,yaw=yaw,yawrate=yawrate,sh=sh,delta=delta,wb=smooth(wb,5),zb=zb,xb=xb,Rm=Rm,
                crop=d.get('crop_start_s'),p=p,setting=d.get('setting'))
if __name__=='__main__':
    R={}
    for kind,n in (('static',40),('mid',40)):
        for d in roster(kind,n,seed=2): R[d['id']]=analyse(d)
    import pickle; pickle.dump(R,open('research/single_model/simstruct/t2.pkl','wb'))
