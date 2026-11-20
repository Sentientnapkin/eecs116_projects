"""T4: frame-0 IMU window (first 10 rows delivered) for static vs mid starts: transient, detector separability, gravity/bias observability."""
import sys; sys.path.insert(0,'research/single_model/simstruct')
from load import *
def first_window(e):
    return e.imu_window(0)
S=[];M=[]
for kind,n,store in (('static',150,S),('mid',150,M)):
    for d in roster(kind,n,seed=5):
        e=load(d); w=first_window(e); store.append(dict(w=w,d=d,ft=e.frame_times[0],imu0=e.imu[:12].copy()))
def feat(r):
    w=r['w']; f=w[:,1:4]; g=w[:,4:7]
    return dict(fz=f[:,2].mean(), fnorm=np.linalg.norm(f.mean(0)), gyro=np.linalg.norm(g.mean(0)), fxy=np.linalg.norm(f[:,:2].mean(0)), fz0=f[0,2], fz_last=f[-1,2], rows=len(w), t0=w[0,0], t9=w[-1,0])
fs=[feat(r) for r in S]; fm=[feat(r) for r in M]
for k in ('fz','fnorm','gyro','fxy','fz0','fz_last'):
    a=np.array([x[k] for x in fs]); b=np.array([x[k] for x in fm])
    print(f'{k:8s} static p5/50/95 {np.percentile(a,[5,50,95]).round(2)}   mid p5/50/95 {np.percentile(b,[5,50,95]).round(2)}')
print('window rows',set(x['rows'] for x in fs+fm),'static t range',fs[0]['t0'],fs[0]['t9'],' mid',fm[0]['t0'],fm[0]['t9'])
print('static first 12 z samples (mean over flights):',np.mean([r['imu0'][:12,3] for r in S],0).round(2))
print('static first 12 z, sample flight',S[0]['imu0'][:12,3].round(2))
print('mid first-window row0==row1 (hold duplicate)? static:',np.mean([np.allclose(r['w'][0,1:],r['w'][1,1:]) for r in S]),' mid:',np.mean([np.allclose(r['w'][0,1:],r['w'][1,1:]) for r in M]))
# separability: static if fnorm in [8.8? ...]
from itertools import product
def acc(rule): return np.mean([rule(x) for x in fs]), np.mean([not rule(x) for x in fm])
for name,rule in (('gyro<0.2 & fz<9.4',lambda x:x['gyro']<0.2 and x['fz']<9.4),('gyro<0.2',lambda x:x['gyro']<0.2),('fz<9.0',lambda x:x['fz']<9.0),('fnorm<8.8',lambda x:x['fnorm']<8.8),('gyro<.1',lambda x:x['gyro']<0.1)):
    a,b=acc(rule); print(f'rule {name:22s} -> P(label static|static)={a:.3f}  P(label mid|mid)={b:.3f}')
np.save('research/single_model/simstruct/t4_static_gyro.npy',np.array([x['gyro'] for x in fs])); 
