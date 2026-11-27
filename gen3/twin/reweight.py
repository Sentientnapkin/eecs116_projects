"""Can feature weights be learned so twin matches predict per-episode server ATE better?  python reweight.py -> reweight.txt
Pool = flights with a GSLV-linejac (eb2799cb) local ATE and python features (v3val + v1val + twin evals). For a weight set w,
pred[e] = mean GSLV ATE of the 5 nearest pool flights (same class). Score = rms log error vs server (after a constant offset)
and Spearman. Nested leave-one-episode-out: pick the best w on 23 episodes, predict the held-out one."""
import json, glob, os, sys
import numpy as np
sys.argv = [sys.argv[0], 'x']
sys.path.insert(0, '/data/backups/rganapa/Sebastian/gen3/twin')
import match as M

T = M.T; G = M.G
srv = np.array([e['metrics']['ate_rmse'] for e in json.load(open('/data/backups/rganapa/Sebastian/eecs116_projects/eecs116_vio/stage3/41e08d67acd6a988.json'))['results']['episodes']])
ate = {}
for p in [f'{G}/evals/gslvlj__v3val.json', f'{G}/evals/gslvlj__v1val.json'] + glob.glob(f'{G}/evals/tw_gslvlj__*.json'):
    for r in json.load(open(p)):
        if r['ate'] is not None: ate[r['id']] = r['ate']
C = M.candidates(); P = {}
for fn in glob.glob(f'{T}/feat_*.jsonl'):
    for l in open(fn):
        r = json.loads(l)
        if 'error' not in r and r['id'] in ate and r['id'] in C: P[r['id']] = M.py_feats(r)
ids = sorted(P); server = [M.server_feats(e) for e in M.SRV]
FS = list(M.W_FULL)
S = {c: M.scales([P[i] for i in ids if C[i]['cls'] == c], M.W_FULL) for c in ('room', 'warehouse', 'forest')}
Z = {}
for e in range(24):
    c = M.CLS[e]
    for i in ids:
        if C[i]['cls'] == c: Z[e, i] = M.zgaps(server[e], P[i], S[c], M.W_FULL)


def predict(W, e, k=5):
    d = sorted((M.dist({f: z for f, z in Z[e, i].items() if W.get(f, 0) > 0}, W), i) for i in ids if (e, i) in Z)
    return float(np.mean([ate[i] for _, i in d[:k]]))


def score(pred, eps):
    lr = np.log([pred[e] for e in eps]) - np.log(srv[eps])
    return float(np.std(lr)), lr


rng = np.random.default_rng(0)
groups = {'start': ['hover', 'start_forward_speed', 'start_gyro_rms'], 'fov': ['hfov_deg'], 'blur': ['blur_x0', 'blur_y0', 'blur_x1', 'blur_y1'],
          'motion': ['mean_speed', 'rms_dist_from_start', 'rms_spread', 'tilt_rms', 'yaw_rms', 'jerk_rms'], 'image': ['Y_mean', 'grad2_mean', 'chroma_b', 'Y_tb']}
cands = {'default': dict(M.W_FULL)}
for g in groups:
    cands[f'only_{g}'] = {f: (M.W_FULL[f] if f in groups[g] else 0) for f in FS}
    cands[f'no_{g}'] = {f: (0 if f in groups[g] else M.W_FULL[f]) for f in FS}
    cands[f'x4_{g}'] = {f: M.W_FULL[f] * (4 if f in groups[g] else 1) for f in FS}
for j in range(60):
    m = {g: float(np.exp(rng.uniform(-2.5, 2))) for g in groups}
    cands[f'rand{j}'] = {f: M.W_FULL[f] * m[g] for g in groups for f in groups[g]}
pred = {n: {e: predict(W, e) for e in range(24)} for n, W in cands.items()}
L = [f'pool: {len(ids)} flights with GSLV ATE + features; k=5 nearest', 'in-sample (all 24 eps): rms log err after offset / spearman']
allep = np.arange(24)
rows = []
for n in cands:
    s, lr = score(pred[n], allep)
    p = np.array([pred[n][e] for e in range(24)])
    rows.append((s, n, float(np.corrcoef(np.argsort(np.argsort(p)), np.argsort(np.argsort(srv)))[0, 1])))
for s, n, sp in sorted(rows)[:12] + [r for r in rows if r[1] == 'default']:
    L.append(f'  {n:14s} {s:.3f}  spearman {sp:+.3f}')
# nested LOO-episode
loo = []
for e in range(24):
    rest = np.delete(allep, e)
    best = min(cands, key=lambda n: score(pred[n], rest)[0])
    off = np.mean(np.log([pred[best][x] for x in rest]) - np.log(srv[rest]))
    loo.append((e, best, np.log(pred[best][e]) - off - np.log(srv[e])))
d_off = np.mean(np.log([pred['default'][x] for x in allep]) - np.log(srv))
lr_def = [np.log(pred['default'][e]) - np.mean(np.log([pred['default'][x] for x in np.delete(allep, e)]) - np.log(srv[np.delete(allep, e)])) - np.log(srv[e]) for e in range(24)]
L.append(f'nested LOO-episode rms log err: learned weights {np.sqrt(np.mean([x[2] ** 2 for x in loo])):.3f}  vs default weights {np.sqrt(np.mean(np.square(lr_def))):.3f}')
L.append('  chosen per fold: ' + ', '.join(sorted(set(x[1] for x in loo))))
open(f'{T}/reweight.txt', 'w').write('\n'.join(L) + '\n'); print('\n'.join(L))
