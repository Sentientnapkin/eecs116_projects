"""Realized-distribution audit: holdout final set vs selected-171 and fresh-711 (truth statistics from sidecars)."""
import glob, json, os, sys
import numpy as np
R = '/data/backups/rganapa/Sebastian/gen'
def load(d): return {os.path.basename(p)[:-5]: json.load(open(p)) for p in glob.glob(d + '/*.json')}
pool = load(R + '/raw-fast/bench')
sel = {os.path.basename(p)[:-4] for p in glob.glob(R + '/raw-fast/selected/*.zip')}
hold_all = load(R + '/raw-holdout/bench')
final = {os.path.basename(p)[:-4] for p in glob.glob(R + '/raw-holdout/final/*.zip')}
sets = {'holdout': [hold_all[i] for i in final], 'selected171': [d for i, d in pool.items() if i in sel], 'fresh711': [d for i, d in pool.items() if i not in sel]}
F = [('travel_m', lambda d: d['audit']['travel_m']), ('extent(zeroATE)', lambda d: d['audit']['zero_motion_ate_m']), ('speed_p10', lambda d: d['audit']['speed_p10_p50_p90'][0]),
     ('speed_p50 (start-speed proxy)', lambda d: d['audit']['speed_p10_p50_p90'][1]), ('speed_p90', lambda d: d['audit']['speed_p10_p50_p90'][2]),
     ('flat_fraction', lambda d: d['audit']['flat_fraction']), ('dark_fraction', lambda d: d['audit']['dark_fraction']), ('hover_fraction', lambda d: d['audit']['hover_fraction'])]
out = []
P = lambda s='': out.append(s)
for start, pre in (('ALL', ''), ('static', 'fast-'), ('mid', 'fastmid-')):
    P(f'\n## {start}   (server anchors: travel 59.6, extent 4.694)')
    P('| set | n | stat | mean | q10 | q50 | q90 |'); P('|---|---|---|---|---|---|---|')
    for name, ds in sets.items():
        ds = [d for d in ds if d['id'].startswith(pre)]
        for fn, f in F:
            x = np.array([f(d) for d in ds], float)
            P(f'| {name} | {len(ds)} | {fn} | {x.mean():.3f} | {np.percentile(x, 10):.3f} | {np.percentile(x, 50):.3f} | {np.percentile(x, 90):.3f} |')
P('\n## Composition')
for name, ds in sets.items():
    import collections
    P(f'- {name}: n={len(ds)} catalogs={dict(collections.Counter(d["catalog"] for d in ds))} settings={dict(collections.Counter(d["setting"] for d in ds))} scenes={len({(d["catalog"], d["scene"]) for d in ds})}')
mids = [d['crop_start_s'] for d in sets['holdout'] if 'crop_start_s' in d]
P(f'- holdout mid crop_start_s: min {min(mids)} max {max(mids)} mean {np.mean(mids):.1f}; selected: ' + str(
    (min(d['crop_start_s'] for d in sets['selected171'] if 'crop_start_s' in d), max(d['crop_start_s'] for d in sets['selected171'] if 'crop_start_s' in d))))
hs = {(d['catalog'], d['scene']) for d in sets['holdout']}
used_pool = {(d['catalog'], d['scene']) for d in pool.values()}; used_sel = {(d['catalog'], d['scene']) for d in sets['selected171']}
P(f'- holdout scenes {len(hs)}: absent from gen/raw-fast {len(hs - used_pool)}; absent from selected171 {len(hs - used_sel)}; by catalog (absent from raw-fast) '
  + str(dict(collections.Counter(c for c, s in hs - used_pool))))
seeds_pool = {(d['catalog'], d['scene'], d['seed']) for d in pool.values()}
P(f'- seed collisions with raw-fast sidecars: {len({d["seed"] for d in sets["holdout"]} & {d["seed"] for d in pool.values()})}; (scene,seed) pair collisions: {len({(d["catalog"], d["scene"], d["seed"]) for d in sets["holdout"]} & seeds_pool)}')
P(f'- audit flags in holdout: {dict(collections.Counter(tuple(d["audit"]["flags"]) for d in sets["holdout"]))}; max truth_integration_rms_m {max(d["audit"]["truth_integration_rms_m"] for d in sets["holdout"])}')
open(os.path.dirname(os.path.abspath(__file__)) + '/AUDIT.md', 'w').write('# Realized distribution audit\n' + '\n'.join(out) + '\n')
print('\n'.join(out))
