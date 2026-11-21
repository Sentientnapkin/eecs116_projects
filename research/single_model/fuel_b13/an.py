import sys, glob, numpy as np
d = sys.argv[1]
L = {0:'step other',1:'propagate',2:'imu_meas(updates)',3:'lc_step (net conv stages+misc)',4:'vision other',5:'pyramid',6:'track_all (klt)',7:'clone ops/record/zupt/remove',8:'map_relocalize',9:'detect',10:'write_state',
 11:'build_rows other(QR)',12:'solve_dx (iter)',13:'update() EKF',14:'feature_rows other(jac,nullspace,gate)',15:'triangulate',20:'net prep',24:'-',25:'net head',26:'net apply',27:'gray128',28:'save/restore',29:'inject',30:'klt()',31:'fr jac build',32:'fr nullspace',33:'fr gate H0P',34:'fr gate S',35:'fr chol+chi2',36:'fr copy rows',37:'fr map_add'}
F=[np.load(f) for f in sorted(glob.glob(d+'/*.npz'))]
S=np.concatenate([z['seg'] for z in F]); T=np.concatenate([z['tot'] for z in F])
ids=[i for i in L if S[:,i].sum()>0]
print('flights',len(F),'frames',len(T),'peak %.2fM p99 %.2fM p95 %.2fM median %.2fM mean %.2fM'%tuple(x/1e6 for x in (T.max(),np.percentile(T,99),np.percentile(T,95),np.median(T),T.mean())))
def table(mask,title):
    print('\n'+title,'n=',mask.sum())
    for i in ids: print('  %-42s %8.3f M'%(L[i],S[mask][:,i].mean()/1e6))
    print('  %-42s %8.3f M'%('TOTAL',T[mask].mean()/1e6))
table(np.ones(len(T),bool),'ALL')
table(np.abs(T-np.median(T))<0.05*np.median(T),'median frames')
table(T>=np.percentile(T,99.5),'top 0.5%')
# per frame-index mean/max total + net share
n=len(F[0]['tot']); 
TT=np.stack([z['tot'] for z in F if len(z['tot'])==n]); SS=np.stack([z['seg'] for z in F if len(z['tot'])==n])
print('\nframe idx: mean / max total (M); top phases of the max frame mean')
for fi in list(range(0,14))+[19,20,21,22,23,24,25,26,59,60,61,62,63,64,65,100,101,102,103,200,300]:
    j=np.argmax(TT[:,fi]); ph=sorted(((SS[j,fi,i],L[i]) for i in ids),reverse=True)[:4]
    print(' %4d  %6.2f / %6.2f   '%(fi,TT[:,fi].mean()/1e6,TT[:,fi].max()/1e6)+'; '.join('%s %.2f'%(n_,v/1e6) for v,n_ in ph))
print('\nper-flight peak frame index histogram:', np.bincount(np.argmax(TT,1)//20)[:10] if len(TT) else '')
pk=np.array([z['tot'].max() for z in F]); print('per-flight peaks: median %.2f max %.2f min %.2f'%(np.median(pk)/1e6,pk.max()/1e6,pk.min()/1e6))
