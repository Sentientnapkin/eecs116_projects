import json, sys, numpy as np, collections
R = json.load(open(sys.argv[1])); T = {r['ep']: r for r in json.load(open(sys.argv[2]))}
E = collections.defaultdict(list)
for r in R: E[r['ep']].append(r)
for ep, rs in sorted(E.items(), key=lambda kv: -T[kv[0]]['ate_rmse'])[:15]:
    ne = np.array([r['nerr'] for r in rs]); fe = np.array([r['ferr'] for r in rs]); pv = np.array([r['pv'] for r in rs]); sp = np.array([r['spd'] for r in rs]); lv = np.array([r['live'] for r in rs])
    b = fe > 0.5
    print('%-34s ATE %.2f vel %.2f scale %.2f | filt>0.5 %3d/%d net there %.2f filt %.2f Pv %.2f spd %.2f live %.0f | net all %.2f filt all %.2f' % (ep, T[ep]['ate_rmse'], T[ep]['velocity_rmse'], T[ep]['sim3_scale'], b.sum(), len(b), ne[b].mean() if b.any() else 0, fe[b].mean() if b.any() else 0, pv[b].mean() if b.any() else 0, sp[b].mean() if b.any() else 0, lv[b].mean() if b.any() else 0, ne.mean(), fe.mean()))
