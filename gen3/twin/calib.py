"""Calibration of twin24 / twin120 / v3val120 against the stage-3 server.   python calib.py  -> calib.txt
Server means: stage3/comparison.json + memory (F_sp10 0.664, auto_727 0.586). Per-episode server ATE: GSLV-linejac only
(stage3/41e08d67acd6a988.json, the only stage-3 per-episode result of a build we have)."""
import json, os, glob, math
import numpy as np

T = '/data/backups/rganapa/Sebastian/gen3/twin'; G = '/data/backups/rganapa/Sebastian/gen3'
E3 = '/data/backups/rganapa/Sebastian/eecs116_projects/eecs116_vio/stage3'
BUILDS = json.load(open(f'{T}/builds.json'))  # name -> [wasm, server_mean]
CLS = ['room'] * 12 + ['warehouse'] * 6 + ['forest'] * 6
srv_ep = [e['metrics']['ate_rmse'] for e in json.load(open(f'{E3}/41e08d67acd6a988.json'))['results']['episodes']]
t24 = [l.split('\t')[1] for l in open(f'{T}/twin24.txt')]
t120 = {}
for l in open(f'{T}/twin120.txt'):
    e, i = l.split('\t')[:2]; t120.setdefault(int(e) - 1, []).append(i)


def load(name, pool):
    p = f'{G}/evals/tw_{name}__{pool}.json'
    if not os.path.exists(p): return None
    return {r['id']: (r['ate'] if r['ate'] is not None else float('nan')) for r in json.load(open(p))}


def meta(i): return json.load(open(f'{G}/out/up/{i}.json'))


def spearman(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b)); return float(np.corrcoef(ra, rb)[0, 1])


L = []; res = {}
for b, (w, sm) in BUILDS.items():
    r = {'server': sm}
    a = load(b, 'twin24')
    if a: v = [a.get(i, np.nan) for i in t24]; r['twin24'] = float(np.nanmean(v)); r['t24_ep'] = v; r['t24_fail'] = int(np.isnan(v).sum())
    a = load(b, 'twin120')
    if a:
        ep = [float(np.nanmean([a.get(i, np.nan) for i in t120[e]])) for e in range(24)]
        r['twin120'] = float(np.nanmean(ep)); r['t120_ep'] = ep
    a = load(b, 'v3val120')
    if a:
        cm = {}
        for i, x in a.items():
            if np.isfinite(x): cm.setdefault(meta(i)['setting_class'], []).append(x)
        r['v3val120_raw'] = float(np.mean([x for v in cm.values() for x in v]))
        r['v3val120_cw'] = 0.5 * np.mean(cm['room']) + 0.25 * np.mean(cm['warehouse']) + 0.25 * np.mean(cm['forest'])
        r['v3_cls'] = {k: float(np.mean(v)) for k, v in cm.items()}
    res[b] = r

L.append('## Calibration: build means (m, mean unaligned ATE). ratio = local / server')
L.append(f'{"build":10s} {"server":>7s} | {"twin24":>7s} {"ratio":>5s} | {"twin120":>7s} {"ratio":>5s} | {"v3v120raw":>9s} {"ratio":>5s} | {"v3v120cw":>8s} {"ratio":>5s}')
for b, r in res.items():
    f = lambda k: (f'{r[k]:7.3f} {r[k] / r["server"]:5.2f}' if k in r else '      -     -')
    L.append(f'{b:10s} {r["server"]:7.3f} | {f("twin24")} | {f("twin120")} | {f("v3val120_raw")}   | {f("v3val120_cw")}')
L.append('')
L.append('predictor quality across builds (only builds with all sets): Spearman rank corr, Pearson r of log means, and leave-one-build-out')
L.append('RMS log error after a constant log offset fitted on the other builds (i.e. how well the set predicts a NEW build\'s server mean).')
keys = ['twin24', 'twin120', 'v3val120_raw', 'v3val120_cw']
full = [b for b, r in res.items() if all(k in r for k in keys)]
summ = {}
for k in keys:
    if len(full) < 3: break
    x = np.log([res[b][k] for b in full]); y = np.log([res[b]['server'] for b in full])
    loo = [(y[j] - x[j] - np.mean(np.delete(y - x, j))) for j in range(len(full))]
    # also with a fitted slope (log-log regression), LOO
    loo2 = []
    for j in range(len(full)):
        A = np.delete(x, j); B = np.delete(y, j); s, c = np.polyfit(A, B, 1); loo2.append(y[j] - (s * x[j] + c))
    summ[k] = dict(spearman=spearman(x, y), r=float(np.corrcoef(x, y)[0, 1]), loo_rms=float(np.sqrt(np.mean(np.square(loo)))),
                   loo_rms_slope=float(np.sqrt(np.mean(np.square(loo2)))))
    L.append(f'  {k:13s} n={len(full)} spearman {summ[k]["spearman"]:+.3f}  r(log) {summ[k]["r"]:+.3f}  LOO rms log err {summ[k]["loo_rms"]:.3f} (x{math.exp(summ[k]["loo_rms"]):.2f})'
             f'  with slope {summ[k]["loo_rms_slope"]:.3f} (x{math.exp(summ[k]["loo_rms_slope"]):.2f})')
# top-3 builds only (the regime we tune in)
top = [b for b in ('gslvlj', 'F_sp10', 'auto727') if b in full]
if len(top) == 3:
    L.append('  top builds ' + ', '.join(f'{k}: ' + ' > '.join(sorted(top, key=lambda b: -res[b][k])) for k in keys + ['server']))
L.append('')
g = res.get('gslvlj', {})
if 't24_ep' in g:
    s = np.array(srv_ep)
    L.append('## Per-episode (GSLV-linejac eb2799cb, the only build with server per-episode ATE)')
    L.append('ep cls   server | twin24 | twin120(mean of 5) | v3val120 class mean')
    for e in range(24):
        L.append(f'{e + 1:2d} {CLS[e][:4]} {s[e]:7.2f} | {g["t24_ep"][e]:6.2f} | {g["t120_ep"][e]:6.2f} | {g["v3_cls"][CLS[e]] if "v3_cls" in g else float("nan"):6.2f}')
    preds = {'twin24': np.array(g['t24_ep']), 'twin120': np.array(g['t120_ep'])}
    if 'v3_cls' in g: preds['v3val120 class mean'] = np.array([g['v3_cls'][c] for c in CLS])
    for k, p in preds.items():
        ok = np.isfinite(p)
        lr = np.log(np.maximum(p[ok], 1e-3)) - np.log(s[ok])
        L.append(f'  {k:20s} pearson(log) {np.corrcoef(np.log(np.maximum(p[ok], 1e-3)), np.log(s[ok]))[0, 1]:+.3f}  spearman {spearman(p[ok], s[ok]):+.3f}  '
                 f'mean log ratio {lr.mean():+.3f}  rms log err {np.sqrt(np.mean(lr ** 2)):.3f}  rms log err after offset {lr.std():.3f}')
    # within-class correlation (removes the scene-class effect that class means already capture)
    for k in ('twin24', 'twin120'):
        p = preds[k]; rr = []
        for c in ('room', 'warehouse', 'forest'):
            idx = [e for e in range(24) if CLS[e] == c and np.isfinite(p[e])]
            rr.append(f'{c} {spearman(p[idx], s[idx]):+.2f}')
        L.append(f'  {k} within-class spearman: ' + ', '.join(rr))
cal = {}
good = [b for b, r in res.items() if 'twin120' in r and r['server'] < 2.5]   # the regime we tune in (drop the 5 m builds)
if good:
    cal = dict(ratio120=float(np.exp(np.mean([np.log(res[b]['server'] / res[b]['twin120']) for b in good]))), builds=good,
               loo120=float(math.exp(summ['twin120']['loo_rms'])) if 'twin120' in summ else None)
    L.append(f'calibration used by eval.sh: server ~= twin120 x {cal["ratio120"]:.3f} (geo-mean over {good})')
open(f'{T}/calib.txt', 'w').write('\n'.join(L) + '\n')
json.dump(dict(res=res, summary=summ, server_ep=srv_ep, calib=cal), open(f'{T}/calib.json', 'w'), indent=0, default=float)
print('\n'.join(L))

# --- snace6e1 per-episode (server per-episode ATE supplied by coordinator)
SN = [0.128,0.423,0.191,0.120,0.257,0.161,0.640,0.708,0.374,0.258,0.147,0.378,0.571,0.351,0.714,0.398,0.482,0.364,0.478,1.165,0.753,0.432,0.628,0.542]
g = res.get('snace6e1', {})
if 't24_ep' in g:
    s = np.array(SN); M = ['## Per-episode snace6e1 (server 0.444)']
    for k, p in (('twin24', np.array(g['t24_ep'])), ('twin120', np.array(g['t120_ep']))):
        ok = np.isfinite(p); lp = np.log(np.maximum(p[ok], 1e-3)); ls = np.log(s[ok]); lr = lp - ls
        M.append(f'  {k}: pearson(log) {np.corrcoef(lp, ls)[0,1]:+.3f} spearman {spearman(p[ok], s[ok]):+.3f} mean log ratio {lr.mean():+.3f} rms after offset {lr.std():.3f}; mean {np.nanmean(p):.3f}')
    open(f'{T}/calib.txt', 'a').write('\n' + '\n'.join(M) + '\n'); print('\n'.join(M))
