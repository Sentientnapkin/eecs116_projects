import sys, glob, numpy as np
N = {0:'entry',1:'prop',2:'imu',3:'lc',4:'vis',5:'pyr',6:'trk',7:'clone',8:'map',9:'det',10:'out',11:'QR',12:'sdx',13:'upd',14:'fr',15:'tri',20:'prep',27:'g128',28:'sv',29:'inj',30:'klt',31:'jac',32:'ns',33:'H0P',34:'S',35:'chi',36:'cp',37:'madd',47:'tail'}
z = [np.load(f) for f in sorted(glob.glob(sys.argv[1] + '/*.npz'))]
seg = np.concatenate([a['seg'][60:] for a in z]); cnt = np.concatenate([a['cnt'][60:] for a in z])
ph = np.concatenate([np.arange(60, len(a['seg'])) % 4 for a in z])
for p in range(4):
    m = ph == p; tot = seg[m].sum(1); hi = tot >= np.percentile(tot, 99)
    comp = sorted(((seg[m][:, k].mean(), k) for k in range(48)), reverse=True)[:9]
    print(f"mod4={p} mean {tot.mean()/1e6:.2f}M  upd calls {cnt[m][:,13].mean():.1f}  ", ' '.join(f"{N.get(k,k)}:{v/1e3:.0f}k/{seg[m][hi][:,k].mean()/1e3:.0f}k" for v, k in comp))
