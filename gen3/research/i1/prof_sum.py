"""prof_sum.py PROFDIR OUT.md: component fuel breakdown of the baseline (A160+Ze0) over all profiled flights.
Totals, per-component share of (a) all fuel, (b) the per-flight peak frames, (c) frames above the pooled p95,
per-component own max / p95; net micro-steps grouped by k-range; uninstrumented-vs-instrumented peak check."""
import sys, json, glob, numpy as np
from pathlib import Path
D, OUT = Path(sys.argv[1]), Path(sys.argv[2])
NAMES = {0: 'host entry', 1: 'IMU input filter (hz_filter)', 2: 'init frame (pyramid+detect+net begin)', 19: 'pre-propagation setup',
         3: 'IMU mean propagation', 4: 'covariance propagation', 5: 'IMU measurements (gravity/zupt/priors)',
         6: 'net re-anchor/startup (lc_begin/lc_step, incl. tc_prior)', 7: 'image->gray + pyramid', 8: 'KLT tracking',
         9: 'clone + record obs + vision zupt', 10: 'MSCKF batching/governor selection', 11: 'triangulation + Jacobians + nullspace (build_rows)',
         12: 'EKF visual update (update)', 13: 'clone marginalization/bookkeeping', 14: 'feature detection', 15: 'map relocalize',
         16: 'net governor loop + monitor', 17: 'health watch (hz_watch)', 18: 'write_state + output guard', 299: 'after last mark'}
NETK = [(0, 16, 'net: gray conversion (k<16)'), (16, 32, 'net: k16-31'), (32, 56, 'net: k32-55'), (56, 62, 'net: k56-61'), (62, 74, 'net: k62-73'),
        (74, 86, 'net: k74-85'), (86, 92, 'net: k86-91'), (92, 95, 'net: k92-94'), (95, 99, 'net: head k95+')]
def groups(seg):
    G = {NAMES[i]: seg[:, i] for i in NAMES}
    for a, b, n in NETK: G[n] = seg[:, 200 + a:200 + b].sum(1)
    return G
tots, segs, names = [], [], []
for f in sorted(D.glob('*.npz')):
    z = np.load(f); tots.append(z['tot']); segs.append(z['seg']); names.append(f.stem)
T = np.concatenate(tots); S = np.concatenate(segs); G = groups(S)
fl_peak_idx = [int(np.argmax(t)) for t in tots]
P = np.array([s[i] for s, i in zip(segs, fl_peak_idx)]); GP = groups(P)
p95 = np.percentile(T, 95); hi = T >= p95; GH = groups(S[hi])
gp = np.argmax([t.max() for t in tots]); W = segs[gp][fl_peak_idx[gp]]
L = [f'# Baseline fuel breakdown (A160+Ze0, instrumented build i1_prof) — {len(tots)} flights, {len(T)} frames\n',
     f'Per-frame fuel: max {T.max():,.0f}, p99 {np.percentile(T, 99):,.0f}, p95 {p95:,.0f}, median {np.median(T):,.0f}, mean {T.mean():,.0f}; '
     f'init frame excluded below unless named.\n',
     f'Per-flight peaks: median {np.median([t.max() for t in tots]):,.0f}, p90 {np.percentile([t.max() for t in tots], 90):,.0f}; '
     f'peak frame index median {np.median(fl_peak_idx):.0f} (0 = init frame); peak frame is the init frame in {np.mean(np.array(fl_peak_idx) == 0) * 100:.0f}% of flights.\n',
     f'Global peak: flight {names[gp]} frame {fl_peak_idx[gp]} fuel {tots[gp].max():,.0f}.\n',
     '| component | share of all fuel % | mean/frame | own p95 | own max | mean on per-flight peak frames | share on peak frames % | mean on frames >= p95 | share >= p95 % | on global-peak frame |',
     '|---|---|---|---|---|---|---|---|---|---|']
WG = groups(W[None, :])
for n in G:
    v = G[n]
    if v.sum() == 0: continue
    L.append(f'| {n} | {v.sum() / T.sum() * 100:.1f} | {v.mean():,.0f} | {np.percentile(v, 95):,.0f} | {v.max():,.0f} | {GP[n].mean():,.0f} | '
             f'{GP[n].sum() / P.sum() * 100:.1f} | {GH[n].mean():,.0f} | {GH[n].sum() / S[hi].sum() * 100:.1f} | {WG[n][0]:,.0f} |')
# compare to uninstrumented eval peaks
try:
    ev = {r['id']: r['peak'] for r in json.load(open('/data/backups/rganapa/Sebastian/gen3/evals/sw_a1_Ze0__v3val.json'))}
    r = [tots[i].max() / ev[n] for i, n in enumerate(names) if n in ev and ev[n]]
    L.append(f'\nInstrumented/uninstrumented per-flight peak ratio (vs evals/sw_a1_Ze0__v3val.json): median {np.median(r):.4f}, min {np.min(r):.4f}, max {np.max(r):.4f} (n={len(r)}).')
    L.append(f'Uninstrumented peak over these flights: {max(ev[n] for n in names if n in ev):,.0f}.')
except Exception as ex: L.append(f'peak check failed: {ex}')
# frames over thresholds
for th in [1e6, 2e6, 3e6, 3.6e6]: L.append(f'- frames >= {th:,.0f}: {np.mean(T >= th) * 100:.2f}%')
# what peak would be if a component were free (max over frames of total minus component)
L.append('\n## Peak if one component cost zero (max over all frames of frame total minus that component)\n')
for n in G:
    if G[n].sum() == 0: continue
    L.append(f'- {n}: {(T - G[n]).max():,.0f}')
# typical frame types
L.append('\n## Frame-type breakdown (mean fuel per component)\n')
nb = G['EKF visual update (update)'] > 0; net = sum(G[n] for _, _, n in NETK) > 0
for lab, m in [('frames with MSCKF update', nb), ('frames without update', ~nb), ('frames running net micro-steps', net)]:
    L.append(f'- {lab}: {m.mean() * 100:.0f}% of frames, mean total {T[m].mean():,.0f}, p95 {np.percentile(T[m], 95):,.0f}')
OUT.write_text('\n'.join(L) + '\n'); print('\n'.join(L))
