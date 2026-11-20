import sys, glob, numpy as np
d = sys.argv[1]
L = {0:'step entry',1:'propagate (10 IMU rows)',2:'imu_measurements',25:'vision entry',3:'gray+pyramid',4:'tex_scale',5:'klt: other (iter loop, track_all glue)',6:'clone ops + batch assembly (+zupt,vi_reset)',
     26:'msckf entry',7:'fr: setup/clone_index',8:'fr: triangulate',9:'fr: Hx/Hf Jacobians',10:'fr: null-space (Householder)',11:'fr: gate (H0P,S,chol,chi2)',12:'fr: copy rows',28:'fr: loop tail',
     13:'qr compress',14:'upd: nz scan',15:'upd: HP=HP',16:'upd: S',17:'upd: chol+y',18:'upd: Kt solves',19:'upd: P update (+dx)',20:'upd: inject',21:'post-update (remove_oldest etc)',
     27:'detect',29:'klt: setup+template extract(r=5)',30:'klt: template grad/hessian loop',31:'klt: iter prep',32:'klt: iter extract(r=4)',23:'vision tail',24:'write_state'}
Sg=[];T=[];V=[];C=[]
for f in sorted(glob.glob(d+'/*.npz')):
    z=np.load(f); Sg.append(z['seg']); T.append(z['tot']); V.append(z['vals']); C.append(z['cnt'])
S=np.concatenate(Sg); T=np.concatenate(T); V=np.concatenate(V); C=np.concatenate(C)
ids=[i for i in L if S[:,i].sum()>0]
print('flights',len(Sg),'frames',len(T),'peak %.2fM p99 %.2fM p95 %.2fM median %.2fM mean %.2fM'%(T.max()/1e6,np.percentile(T,99)/1e6,np.percentile(T,95)/1e6,np.median(T)/1e6,T.mean()/1e6))
def table(mask,title):
    print('\n'+title,'n=',mask.sum())
    for i in ids: print('  %-46s %8.3f M'%(L[i],S[mask][:,i].mean()/1e6))
    print('  %-46s %8.3f M'%('TOTAL',T[mask].mean()/1e6))
table(np.ones(len(T),bool),'ALL frames (mean)')
table(np.abs(T-np.median(T))<0.05*np.median(T),'median frames (+-5%)')
table(T>=np.percentile(T,95),'top 5% frames')
table(T>=np.percentile(T,99.9),'top 0.1% frames')
pk=[t.max() for t in [np.load(f)['tot'] for f in sorted(glob.glob(d+'/*.npz'))]]
print('\nper-flight peak: median %.2fM max %.2fM min %.2fM'%(np.median(pk)/1e6,max(pk)/1e6,min(pk)/1e6))
top=np.argsort(-T)[:200]
print('top200 frames: mean nbatch %.1f (all %.1f), mean nrows after fr %.1f (all %.1f)'%(V[top,26].mean(),V[:,26].mean(),V[top,13].mean(),V[:,13].mean()))
print('frames nbatch=0: %.1f%%; fuel at nbatch=0 frames mean %.2fM'%(100*(V[:,26]==0).mean(),T[V[:,26]==0].mean()/1e6))
