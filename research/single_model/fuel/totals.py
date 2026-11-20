import sys,glob,numpy as np
for d in sys.argv[1:]:
    T=[np.load(f)['tot'] for f in sorted(glob.glob(d+'/*.npz'))]
    pk=np.array([t.max() for t in T]); A=np.concatenate(T)
    print('%-28s flights %3d  maxpeak %6.2fM  medpeak %6.2fM  p99 %6.2fM  p95 %6.2fM  median %6.2fM  mean %6.2fM'%(d.split('/')[-1],len(T),pk.max()/1e6,np.median(pk)/1e6,np.percentile(A,99)/1e6,np.percentile(A,95)/1e6,np.median(A)/1e6,A.mean()/1e6))
