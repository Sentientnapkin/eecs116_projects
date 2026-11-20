import pickle, sys, numpy as np
r=pickle.load(open(sys.argv[1]+'/perflight.pkl','rb'))
S=[d for d in r.values() if d['slice']=='search']
def m(x): x=x[np.isfinite(x)]; return np.mean(x) if len(x) else np.nan
for st in ('static','mid','all'):
    G=[d for d in S if st=='all' or d['start']==st]
    for lab,sl in (('0-5s',slice(0,100)),('5-60s',slice(100,None))):
        pv=[m(d['nees_v'][sl]) for d in G]; pp=[m(d['nees_p'][sl]) for d in G]
        medv=[np.nanmedian(d['nees_v'][sl]) for d in G]; medp=[np.nanmedian(d['nees_p'][sl]) for d in G]
        print(f'{st:6s}{lab:6s} n={len(G)} NEES vel: mean-of-flight-means {np.mean(pv):7.1f} median of flight medians {np.median(medv):6.1f} | pos: mean {np.mean(pp):8.1f} median {np.median(medp):7.1f}')
