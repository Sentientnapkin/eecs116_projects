import sys;sys.path.insert(0,'lib');import numpy as np, r1dir as D
rng=np.random.default_rng(0);f=116.
for trial in range(5):
    X=rng.uniform([-5,-4,2],[5,4,12],(80,3))       # points in cam i
    R=D.so3_exp(rng.normal(0,.05,3)); d=D.unit(rng.normal(0,1,3)); d*=0.1  # motion of camera, in cam j coords
    # camera j centre in cam i coords: c = R^T d ; X_j = R (X_i - c) = R X_i - d  -> t=-d
    Xj=X@R.T - d
    bi=D.unit(X)+rng.normal(0,0.5/f,(80,3)); bj=D.unit(Xj)+rng.normal(0,.5/f,(80,3)); bi=D.unit(bi);bj=D.unit(bj)
    bj[:8]=D.unit(rng.normal(0,1,(8,3))*[1,1,0]+[0,0,3])  # outliers
    for m in ['eig','irls','ransac_irls','joint']:
        r=D.estimate(bi,bj,R,f,m); print(trial,m,'err deg %.2f'%np.degrees(np.arccos(np.clip(r['d']@D.unit(d),-1,1))),'sig_pred %.2f'%np.degrees(r['sig_pred']),'vote %.2f'%r['vote'])
