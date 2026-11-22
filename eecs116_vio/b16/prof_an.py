import sys, glob, numpy as np
N = {0:'step entry/glue',1:'propagate',2:'imu_measurements',3:'lc_step',4:'vision glue',5:'pyramid',6:'track_all glue',7:'clone ops',8:'map_relocalize',9:'detect',10:'write_state',
     11:'build_rows/QR',12:'solve_dx',13:'update',14:'feature_rows',15:'triangulate',20:'lc_prep',21:'conv0',22:'conv1',23:'conv2',24:'conv3',25:'head',26:'lc_apply',27:'gray128',28:'save/restore',
     29:'inject',30:'klt',31:'fr:jac',32:'fr:nullspace',33:'fr:gate H0P',34:'fr:gate S',35:'fr:chol/chi2',36:'fr:copy rows',37:'fr:map_add',40:'msckf entry',41:'rows pre-QR',47:'tail'}
seg = np.concatenate([np.load(f)['seg'] for f in sorted(glob.glob(sys.argv[1] + '/*.npz'))])
tot = seg.sum(1)
print(f"frames {len(tot)}  max {tot.max()/1e6:.2f}M  p99 {np.percentile(tot,99)/1e6:.2f}M  median {np.median(tot)/1e6:.2f}M  mean {tot.mean()/1e6:.2f}M")
pk = tot >= np.percentile(tot, 99.5)
print(f"{'component':22s} {'mean k':>8s} {'peak0.5% k':>10s}")
for i in np.argsort(-seg.mean(0)):
    if seg[:, i].mean() < 2000 and seg[pk, i].mean() < 5000: continue
    print(f"{N.get(i, str(i)):22s} {seg[:, i].mean()/1e3:8.0f} {seg[pk, i].mean()/1e3:10.0f}")
