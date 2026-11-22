import sys, glob, numpy as np
N = {0:'entry',1:'prop',2:'imu',3:'lc',4:'vis',5:'pyr',6:'trk',7:'clone',8:'map',9:'det',10:'out',11:'QR',12:'sdx',13:'upd',14:'fr',15:'tri',20:'prep',21:'c0',22:'c1',23:'c2',24:'c3',25:'head',26:'apply',27:'g128',28:'sv',29:'inj',30:'klt',31:'jac',32:'ns',33:'H0P',34:'S',35:'chi',36:'cp',37:'madd',47:'tail'}
segs = [np.load(f)['seg'] for f in sorted(glob.glob(sys.argv[1] + '/*.npz'))]
allt = np.concatenate([s.sum(1) for s in segs])
thr = float(sys.argv[2]) * 1e6 if len(sys.argv) > 2 else np.percentile(allt, 99)
from collections import Counter
cause = Counter(); ex = []
for s in segs:
    t = s.sum(1)
    for i in np.where(t > thr)[0]:
        top = sorted(((s[i, k], k) for k in range(48)), reverse=True)[:3]
        key = '+'.join(N.get(k, str(k)) for v, k in top[:2])
        cause[key] += 1
        if len(ex) < 12: ex.append((i, i % 4, round(t[i] / 1e6, 2), [(N.get(k, str(k)), round(v / 1e6, 2)) for v, k in top]))
print('frames over', round(thr / 1e6, 2), 'M:', sum(cause.values()), dict(cause.most_common(8)))
for e in ex: print(' ', e)
