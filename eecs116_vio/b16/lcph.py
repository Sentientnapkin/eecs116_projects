import sys, glob, numpy as np
N = {0:'entry',1:'prop',2:'imu',3:'lc',4:'vis',5:'pyr',6:'trk',7:'clone',8:'map',9:'det',10:'out',11:'QR',12:'sdx',13:'upd',14:'fr',15:'tri',20:'prep',21:'c0',22:'c1',23:'c2',24:'c3',25:'head',26:'apply',27:'g128',28:'sv',29:'inj',30:'klt',31:'jac',32:'ns',33:'H0P',34:'S',35:'chi',36:'cp',37:'madd',47:'tail'}
f = sorted(glob.glob(sys.argv[1] + '/*.npz'))[int(sys.argv[2]) if len(sys.argv)>2 else 0]
s = np.load(f)['seg']; t = s.sum(1)
a, b = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (0, 35)
for i in range(a, b):
    top = sorted(((s[i, k], k) for k in range(48)), reverse=True)[:5]
    print(i, round(t[i]/1e6, 2), [(N.get(k, k), round(v/1e6, 2)) for v, k in top if v > 2e4])
