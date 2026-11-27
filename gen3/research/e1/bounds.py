import numpy as np,glob
F=sorted(glob.glob('cache/*.npz'));D=[np.load(f) for f in F]
def ate(e,g):return np.sqrt(((e-g)**2).sum(1).mean())
def rep(name,fn):
    a=[ate(fn(d),d['gt']) for d in D];print('%-52s mean %.2f med %.2f'%(name,np.mean(a),np.median(a)))
rep('zero pose',lambda d:np.zeros_like(d['gt']))
for s in (0.5,0.7,0.8,0.9,1.1,1.25,1.5,2.0): rep(f'GT path x{s} (scale error)',lambda d:d['gt']*s)
def rotz(d,deg):
    # rotate the path around the gravity axis (world z) : cam0 axes -> use Rg[0] cam->world
    R0=d['Rgt'][0];up=R0.T@np.array([0,0,1.]);a=np.radians(deg);K=np.array([[0,-up[2],up[1]],[up[2],0,-up[0]],[-up[1],up[0],0]])
    R=np.eye(3)+np.sin(a)*K+(1-np.cos(a))*K@K;return d['gt']@R.T
for deg in (2,5,10,20): rep(f'GT path, heading error {deg} deg',lambda d:rotz(d,deg))
# straight-line from origin to final point (shape lost)
rep('straight line origin->final GT point',lambda d:np.linspace(0,1,len(d['gt']))[:,None]*d['gt'][-1])
rep('path mean-shifted: ATE of constant mean position',lambda d:np.tile(d['gt'].mean(0),(len(d['gt']),1)))
# constant-speed along GT direction (oracle direction, speed prior c m/s)
def cspeed(d,c):
    p=d['gt'];v=np.diff(p,axis=0);n=np.linalg.norm(v,axis=1);u=v/np.maximum(n,1e-6)[:,None]
    hov=n<0.01   # hover: stop
    e=np.zeros_like(p);
    for k in range(1,len(p)): e[k]=e[k-1]+(0 if hov[k-1] else c*0.05)*u[k-1]
    return e
for c in (0.5,1.0,1.5): rep(f'oracle direction + hover flag, const speed {c} m/s',lambda d:cspeed(d,c))
sp=[np.linalg.norm(np.diff(d['gt'],axis=0),axis=1)/0.05 for d in D];sp=np.concatenate(sp)
print('GT speed pct 10/50/90:',np.percentile(sp,[10,50,90]).round(2),'frac<0.1 m/s',(sp<0.1).mean().round(2))
