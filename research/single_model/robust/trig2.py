import json, numpy as np, sys
sys.argv=['x']
exec(open('triggers.py').read().split("res = []")[0])
res = json.load(open('out/B7/triggers.json'))
# reproduction check vs replicates_B7
rows = {r['episode']: r for r in base.values()}
dev = [abs(reps[k][e][0] - rows[e]['reps'][k]) for e in rows if e in reps[0] for k in range(5)]
print('debug build vs release ATE: max abs diff %.2e (n=%d)' % (max(dev), len(dev)))
from collections import Counter
c = Counter(); sz = []
for r in res:
    e = r['episode']; a, b = r['best'], r['worst']; f = r['fjump']
    Da, Db = reps[a][e][2], reps[b][e][2]
    if f < 1 or f - 1 >= min(len(Da), len(Db)): continue
    x, y = Da[f-1], Db[f-1]
    # worse run minus best run at the jump frame
    c['used worse>best' if y['used'] > x['used'] else 'used worse<best' if y['used'] < x['used'] else 'used equal'] += 1
    c['tri worse>best' if y['tri'] > x['tri'] else 'tri worse<best' if y['tri'] < x['tri'] else 'tri equal'] += 1
    c['gate worse>best' if y['gate'] > x['gate'] else 'gate worse<best' if y['gate'] < x['gate'] else 'gate equal'] += 1
    c['near>0 in either'] += int(x['near'] > 0 or y['near'] > 0)
    c['rmax>5 either'] += int(max(x['rmax'], y['rmax']) > 5)
    sz.append(max(x['used'], y['used']))
print(c); print('features used at jump frame median', np.median(sz))
# update-size: how many flights have the jump at a frame with <=3 used features
print('jump frame used<=3:', sum(s <= 3 for s in sz), '/', len(sz))
print('--- jump frame context (worse run)')
nc=[];tt=[];pv=[];ls=[];fl=[]
for r in res:
    e=r['episode']; Db=reps[r['worst']][e][2]; f=r['fjump']
    if f<1 or f-1>=len(Db): continue
    x=Db[f-1]; nc.append(x['nc']); tt.append(x['t']); pv.append(x['Pv']); ls.append(x['live3']); fl.append((x['mov'],x['rel'],x['hold']))
print('nclones at jump', Counter(nc).most_common()); print('t median %.1f quartiles'%np.median(tt), np.percentile(tt,[25,75]))
print('Pv median', np.median(pv), np.percentile(pv,[25,75])); print('flags(mov,rel,hold)',Counter(fl))
# frame parity in cycle: f%4
print('frame mod 4 at jump', Counter([r['fjump']%4 for r in res]))
