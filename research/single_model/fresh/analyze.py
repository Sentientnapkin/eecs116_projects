import json, glob, sys, os
import numpy as np
H = 'research/single_model/fresh/'
tags = json.load(open(H + 'tags.json'))
feats = {r['episode']: r for r in json.load(open(H + 'truth_feats.json'))}
C = [c for c in ('base', 'f0', 'gate', 'tails', 'fgt') if os.path.exists(H + f'table_{c}.json')]
tab = {c: {r['episode']: r for r in json.load(open(H + f'table_{c}.json'))} for c in C}
eps = sorted(tags)
A = {c: np.array([tab[c][e]['ate'] for e in eps]) for c in C}
start = np.array([tags[e]['start'] for e in eps]); group = np.array([tags[e]['group'] for e in eps])
cat = np.array([tags[e]['catalog'] for e in eps]); scene = np.array([tags[e]['catalog'] + ':' + tags[e]['scene'] for e in eps])
spd = np.array([feats[e]['speed0'] for e in eps]); ang = np.array([feats[e]['angle'] if feats[e]['angle'] is not None else np.nan for e in eps])
out = []
P = lambda *a: out.append(' '.join(str(x) for x in a))

def st(v):
    return f'n={len(v):3d} mean {v.mean():.3f} med {np.median(v):.2f} p90 {np.percentile(v, 90):.2f} max {v.max():5.2f} | >3: {(v > 3).sum():2d} ({100 * (v > 3).mean():.1f}%) >5: {(v > 5).sum():2d} ({100 * (v > 5).mean():.1f}%) >10: {(v > 10).sum():2d}'

def boot(d, sc, n=4000, seed=1):
    rng = np.random.default_rng(seed)
    u, inv = np.unique(sc, return_inverse=True)
    s = np.bincount(inv, weights=d); k = np.bincount(inv)
    idx = rng.integers(0, len(u), (n, len(u)))
    b = s[idx].sum(1) / k[idx].sum(1)
    return d.mean(), *np.percentile(b, [2.5, 97.5])

P('# Fresh-pool results (711 flights not among the 171 selected)\n')
P('## Overall, mean unaligned ATE (m)'); P('```')
for c in C: P(f'{c:6s}', st(A[c]))
P('```')
for lab, mask in [('static', start == 'static'), ('mid', start == 'mid')] + [(f'group={g}', group == g) for g in np.unique(group)] + [(f'catalog={g}', cat == g) for g in np.unique(cat)]:
    P(f'\n### {lab}'); P('```')
    for c in C: P(f'{c:6s}', st(A[c][mask]))
    P('```')
for g in np.unique(group):
    for s_ in ('static', 'mid'):
        m = (group == g) & (start == s_)
        P(f'\n### group={g} {s_}'); P('```')
        for c in C: P(f'{c:6s}', st(A[c][m]))
        P('```')
P('\n## Paired scene-bootstrap differences (mean(new)-mean(ref), 95%% CI resampling scenes; %d scenes)' % len(np.unique(scene)))
pairs = [('f0', 'base'), ('gate', 'base'), ('tails', 'base'), ('fgt', 'base'), ('gate', 'f0'), ('tails', 'f0'), ('fgt', 'f0'), ('fgt', 'gate'), ('fgt', 'tails'), ('tails', 'gate')]
P('```')
for a, b in pairs:
    if a in C and b in C:
        for lab, m in (('all', np.ones(len(eps), bool)), ('static', start == 'static'), ('mid', start == 'mid')):
            d, lo, hi = boot(A[a][m] - A[b][m], scene[m])
            P(f'{a:6s} - {b:6s} {lab:6s} {d:+.3f} [{lo:+.3f}, {hi:+.3f}]')
P('```')
P('\n## Worse than reference per flight'); P('```')
for c in C:
    if c == 'base': continue
    for ref in ('base', 'f0'):
        if c == ref or ref not in C: continue
        d = A[c] - A[ref]
        P(f'{c:6s} vs {ref:4s}: worse by >1 m: {(d > 1).sum():3d} ({100 * (d > 1).mean():.1f}%), >2 m: {(d > 2).sum():3d}; better by >1 m: {(d < -1).sum():3d}; mid worse>1: {(d[start == "mid"] > 1).mean() * 100:.1f}%, static worse>1: {(d[start == "static"] > 1).mean() * 100:.1f}%')
P('```')
P('\n## Regression flights (candidate worse than base by >2 m)')
for c in C:
    if c == 'base': continue
    d = A[c] - A['base']; idx = np.where(d > 2)[0]
    P(f'\n### {c}: {len(idx)} flights'); P('```')
    for i in idx[np.argsort(-d[idx])]:
        P(f'{eps[i]:38s} {start[i]:6s} {group[i]:5s} spd0 {spd[i]:.2f} ang {ang[i]:6.1f} | ' + ' '.join(f'{k} {A[k][i]:.2f}' for k in C))
    P('```')
P('\n## Tail flights (any candidate >5 m)'); P('```')
tl = [i for i in range(len(eps)) if any(A[c][i] > 5 for c in C if c != 'base')]
for i in sorted(tl, key=lambda i: -max(A[c][i] for c in C if c != 'base')):
    P(f'{eps[i]:38s} {start[i]:6s} {group[i]:5s} spd0 {spd[i]:.2f} ang {ang[i]:6.1f} | ' + ' '.join(f'{k} {A[k][i]:.2f}' for k in C))
P('```')
# angle / speed bins, mid flights
mid = start == 'mid'
P('\n## Mid flights by angle between true start velocity (mean first 0.5 s) and camera axis'); 
for lab, bins, vals in (('angle deg', [0, 45, 90, 135, 180.01], ang), ('start speed m/s', [0, 0.3, 0.6, 1.0, 1.5, 10], spd)):
    P(f'\n### by {lab} (mid)'); P('```')
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = mid & (vals >= lo) & (vals < hi)
        if not m.any(): continue
        P(f'[{lo},{hi}) n={m.sum()}')
        for c in C: P(f'   {c:6s} mean {A[c][m].mean():.3f} med {np.median(A[c][m]):.2f} max {A[c][m].max():5.2f} >3m {(A[c][m] > 3).sum():2d} ({100 * (A[c][m] > 3).mean():.1f}%) >5m {(A[c][m] > 5).sum():2d}')
    P('```')
P('\n### angle x speed (mid, speed>0.5 only), angle>90 deg vs <=90'); P('```')
for lab, m in (('speed>0.5, ang<=90', mid & (spd > .5) & (ang <= 90)), ('speed>0.5, ang>90', mid & (spd > .5) & (ang > 90)), ('speed>1, ang>90', mid & (spd > 1) & (ang > 90)), ('speed>1, ang>120', mid & (spd > 1) & (ang > 120))):
    P(f'{lab} n={m.sum()}')
    for c in C: P(f'   {c:6s} mean {A[c][m].mean():.3f} med {np.median(A[c][m]):.2f} max {A[c][m].max():5.2f} >3m {(A[c][m] > 3).sum()} >5m {(A[c][m] > 5).sum()}')
P('```')
# detector confusion
P('\n## f0 detector (|mean f|>8.8 or |gyro|>0.2 on frame-0 IMU window, from the zip) vs sidecar start type'); P('```')
det = np.array([feats[e]['det_moving'] for e in eps])
for s_ in ('static', 'mid'):
    P(f'{s_:7s}: detector moving {int((det & (start == s_)).sum())}, not moving {int((~det & (start == s_)).sum())}')
sf = np.array([feats[e]['det_f'] for e in eps]); sg = np.array([feats[e]['det_g'] for e in eps])
P('static |f| min/med/max', np.percentile(sf[start == 'static'], [0, 50, 100]).round(3), 'gyro', np.percentile(sg[start == 'static'], [0, 50, 100]).round(3))
P('mid    |f| min/med/max', np.percentile(sf[mid], [0, 50, 100]).round(3), 'gyro', np.percentile(sg[mid], [0, 50, 100]).round(3))
P('static flights with |f|>8.7:', [(e, round(feats[e]['det_f'], 3)) for e in eps if tags[e]['start'] == 'static' and feats[e]['det_f'] > 8.7])
P('mid flights detected by force only (gyro<=0.2):', int(((sg <= 0.2) & mid).sum()), ' by gyro only (f<=8.8):', int(((sf <= 8.8) & mid).sum()), ' min f mid', sf[mid].min().round(3))
P('mid with true start speed<0.1 m/s:', int((mid & (spd < .1)).sum()))
P('```')
# gate release
for dbg in ('gatedbg', 'fgtdbg'):
    fs = glob.glob(f'research/results/single_model/fresh_{dbg}/eval/{dbg}-*/*/report/logs/*/estimate.tum')
    if len(fs) < 700: continue
    rel = {}
    for f in fs:
        e = f.split('/')[-5]
        last = open(f).read().strip().splitlines()[-1].split()
        rel[e] = (float(last[2]), float(last[3]))   # released flag, pairs+1000*moving
    json.dump(rel, open(H + f'gate_{dbg}.json', 'w'))
    P(f'\n## Gate release ({dbg}: GATE_DEBUG=1 build; released flag and detector `moving` read from the guest)'); P('```')
    r = np.array([rel[e][0] > 0.5 for e in eps]); mv = np.array([rel[e][1] >= 1000 for e in eps])
    P('guest detector moving vs sidecar: static moving', int((mv & (start == 'static')).sum()), '/', int((start == 'static').sum()), ' mid moving', int((mv & mid).sum()), '/', int(mid.sum()))
    P('released: static', int((r & (start == 'static')).sum()), ' mid', int((r & mid).sum()))
    m = r & (spd > .5)
    P('released with true start speed>0.5 m/s:', int(m.sum()), [(eps[i], round(spd[i], 2), round(ang[i], 0), {c: round(A[c][i], 2) for c in C}) for i in np.where(m)[0]])
    m = r & mid
    P('released mid flights speed list:', sorted(np.round(spd[m], 2).tolist()))
    for c in ('f0', 'gate', 'fgt'):
        if c in C and len(m): P(f'  released mid flights: {c} mean {A[c][m].mean():.3f} vs f0 {A["f0"][m].mean():.3f}')
    P('static released fraction', round(float((r & (start == "static")).sum() / (start == "static").sum()), 3), ' static not released (prior kept):', [(eps[i], round(A['f0'][i], 2), round(A['gate'][i], 2)) for i in np.where((~r) & (start == 'static'))[0]][:20])
    P('```')
open(H + 'REPORT.md', 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
