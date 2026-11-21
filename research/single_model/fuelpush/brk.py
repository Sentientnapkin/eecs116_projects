"""brk.py TAG [rowmin] : per-phase breakdown (k instr) of heavy-row frames and zero-row frames for profile fp_prof_TAG"""
import numpy as np, glob, sys
sys.path.insert(0, '.')
F=[np.load(f) for f in sorted(glob.glob('../../results/single_model/fp_prof_%s/*.npz'%sys.argv[1]))]
S=np.concatenate([z['seg'] for z in F]); V=np.concatenate([z['vals'] for z in F]); T=np.concatenate([z['tot'] for z in F])
src=open('an.py').read(); L=eval(src[src.index('L = {')+4:src.index('}',src.index('L = {'))+1])
r=V[:,45]; rm=int(sys.argv[2]) if len(sys.argv)>2 else 26
for name,m in [('rows>=%d'%rm,r>=rm),('rows 8-14',(r>=8)&(r<=14)),('rows 0',r==0)]:
    print('%s n %d rows %.1f tot %.3f M'%(name,m.sum(),r[m].mean(),T[m].mean()/1e6))
    print('   '+'  '.join('%s %.0f'%(L.get(i,str(i)),S[m][:,i].mean()/1e3) for i in sorted(range(S.shape[1]),key=lambda i:-S[m][:,i].mean()) if S[m][:,i].mean()>3e3))
print('peak %.2f p99 %.2f p95 %.2f mean %.3f'%(T.max()/1e6,np.percentile(T,99)/1e6,np.percentile(T,95)/1e6,T.mean()/1e6))
