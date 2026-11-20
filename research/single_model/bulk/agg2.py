import json, sys, numpy as np
RUN=sys.argv[1]
R = json.load(open('research/single_model/bulk/decomp_'+RUN+'.json'))
tab = {r['episode']: r for r in json.load(open('research/single_model/fresh/table_fe2_fbh.json'))}
st = np.array([tab[r['ep']]['start'] for r in R]); ate = np.array([r['ate'] for r in R])
q25, q75 = np.percentile(ate, [25, 75]); m = (ate >= q25) & (ate <= q75)
E = np.array([r['en1hz'][:60] for r in R])
for lab, mm in [('typical', m), ('typ static', m & (st == 'static')), ('typ mid', m & (st == 'mid'))]:
    print(lab, 'median |err| at t=1,2,3,5,8,10,15,20,30,40,50,59 s:', [round(float(np.median(E[mm][:, t])), 3) for t in (1,2,3,5,8,10,15,20,30,40,50,59)])
    print('  mean-sq err share by time bin (0-5,5-10,10-20,20-40,40-60):', [round(float((E[mm][:, a:b] ** 2).sum() / (E[mm] ** 2).sum()), 3) for a, b in [(0,5),(5,10),(10,20),(20,40),(40,60)]])
hf = np.array([r['hf'] for r in R]); lf = np.array([r['lf'] for r in R]); rp = np.array([r['rpe1s'] for r in R])
for lab, mm in [('typical', m), ('all', np.ones(len(R), bool))]:
    print(lab, 'hf(<2s) rms', hf[mm].mean(), 'lf rms', lf[mm].mean(), 'rpe1s', rp[mm].mean(), 'median ate', np.median(ate[mm]))
# smoothness of error: is error random walk? sqrt of mean sq err growth: lag structure
d = E[m]
for lag in (1,2,5,10,20):
    print('lag', lag, 'rms |e(t+lag)-e(t)| (norm diff, lower bound)', float(np.sqrt(np.mean((d[:, lag:] - d[:, :-lag]) ** 2))))
# vertical
V = np.array([r['ev1hz'][:60] for r in R])
print('vertical error rms typical', float(np.sqrt((V[m]**2).mean())), 'total', float(np.sqrt((E[m]**2).mean())))
# jump in error between 2 s and 5 s and 5-10 on static
for lab, mm in [('typ static', m & (st == 'static'))]:
    print(lab, 'mean|e| at 2,3,4,5,6,8,10', [round(float(E[mm][:, t].mean()), 3) for t in (2,3,4,5,6,8,10)])
