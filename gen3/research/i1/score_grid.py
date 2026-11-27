"""score_grid.py: exact server area-gain (viobench/tools/server/evaluations.py, copied verbatim logic) for hypothetical
(peak fuel, mean ATE) points against the stage-3 shared baselines (eecs116_vio/stage3/comparison.json). Writes score_grid.md."""
import json
from math import log, isfinite
from pathlib import Path
FUEL_FLOOR, ERROR_FLOOR = 1, 0.001
def dominated_area(points, max_fuel, max_error, *, min_fuel=FUEL_FLOOR, min_error=ERROR_FLOOR):
    if max_fuel <= min_fuel or max_error <= min_error:
        return 0.0
    max_x, max_y = log(max_fuel / min_fuel), log(max_error / min_error)
    ordered = sorted((log(max(f, min_fuel) / min_fuel), log(max(e, min_error) / min_error))
                     for f, e in points if isfinite(f) and isfinite(e) and 0 <= f < max_fuel and 0 <= e < max_error)
    area, px, by = 0.0, 0.0, max_y
    for x, y in ordered:
        if y >= by: continue
        area += (x - px) * (max_y - by); px, by = x, y
    return area + (max_x - px) * (max_y - by)
C = json.load(open('/data/backups/rganapa/Sebastian/eecs116_projects/eecs116_vio/stage3/comparison.json'))
FREF = C['fuel_reference']
base = [(max(p['fuel_per_frame_max'], 1), max(p['ate_rmse_mean'], .001)) for p in C['points'] if p['is_baseline']]
EREF = 1.2 * min(base)[1]
RECT = log(FREF) * log(EREF / ERROR_FLOOR)
BA = dominated_area(base, FREF, EREF)
def gain(f, e, extra=()):
    b = list(base) + list(extra)
    return max(0.0, dominated_area(b + [(f, e)], FREF, EREF) - dominated_area(b, FREF, EREF)) / RECT * 100
L = []
L.append(f'# Score grid (exact server formula) vs stage-3 shared baselines\n')
L.append(f'fuel_reference {FREF:.3g}, error_reference {EREF:.4f} m (1.2 x fastest baseline), rectangle {RECT:.2f} ln-units^2; '
         f'check: server claimed_area {C["claimed_area"]:.3f} for {C["best_submission_id"]}; recomputed '
         f'{gain(*[(p["fuel_per_frame_max"], p["ate_rmse_mean"]) for p in C["points"] if p["id"] == C["best_submission_id"]][0]) * RECT / 100:.3f}\n')
L.append('Baseline frontier: ' + ', '.join(f'{p["label"]} ({p["fuel_per_frame_max"]:.3g}, {p["ate_rmse_mean"]:.3f} m)'
                                         for p in C['points'] if p['id'] in C['baseline_frontier']) + '\n')
fu = [1e3, 1e4, 1e5, 3e5, 1e6, 2e6, 4.1e6, 1e7, 2.7e7, 1e8, 5e8, 1e9, 5e9]
at = [0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.586, 0.7, 0.9, 1.2, 2.0]
L.append('\n## Gain (% of rectangle) by peak fuel (columns) and mean ATE (rows)\n')
L.append('| ATE m \\ fuel | ' + ' | '.join(f'{f:.3g}' for f in fu) + ' |')
L.append('|' + '---|' * (len(fu) + 1))
for e in at: L.append(f'| {e} | ' + ' | '.join(f'{gain(f, e):.2f}' for f in fu) + ' |')
L.append('\n## Named points\n')
named = [('current best server (auto_727)', 4.1e6, 0.586), ('Ze0 if server ~ same', 3.77e6, 0.586),
         ('Target A', 1e6, 0.5), ('Target C', 1e8, 0.15), ('Target D', 1e9, 0.05),
         ('A160 ATE at 1M fuel', 1e6, 0.586), ('half ATE same fuel', 4.1e6, 0.293), ('0.5 m @ 4.1M', 4.1e6, 0.5),
         ('0.3 m @ 25M', 2.5e7, 0.3), ('0.15 m @ 25M', 2.5e7, 0.15), ('0.586 @ 100k', 1e5, 0.586), ('1.0 m @ 1e4', 1e4, 1.0)]
L.append('| point | fuel | ATE | gain % | d gain / d ln(fuel) | d gain / d ln(ATE) |')
L.append('|---|---|---|---|---|---|')
for n, f, e in named:
    g = gain(f, e); h = 1e-3
    L.append(f'| {n} | {f:.3g} | {e} | {g:.2f} | {(gain(f * (1 + h), e) - g) / log(1 + h):.3f} | {(gain(f, e * (1 + h)) - g) / log(1 + h):.3f} |')
L.append('\n## Sensitivity: a new strong shared baseline (another team selected as baseline)\n')
L.append('| hypothetical new baseline | gain of 0.586@4.1M | Target A | Target C | Target D |')
L.append('|---|---|---|---|---|')
for nb in [None, (2e7, 1.0), (5e6, 0.6), (1e6, 1.0), (1e8, 0.3), (1e9, 0.2)]:
    ex = [] if nb is None else [nb]
    L.append(f'| {nb} | {gain(4.1e6, .586, ex):.2f} | {gain(1e6, .5, ex):.2f} | {gain(1e8, .15, ex):.2f} | {gain(1e9, .05, ex):.2f} |')
L.append('\n## Fuel needed at a given ATE to match the gain of 0.586 m @ 4.1 M\n')
g0 = gain(4.1e6, 0.586)
for e in [0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5]:
    lo, hi = 1.0, FREF
    if gain(hi * 0.999, e) >= g0: L.append(f'- ATE {e}: any fuel up to 2.4e10 matches'); continue
    for _ in range(200):
        mid = (lo * hi) ** .5
        lo, hi = (mid, hi) if gain(mid, e) >= g0 else (lo, mid)
    L.append(f'- ATE {e} m: break-even peak fuel {lo:.3g}')
Path(__file__).with_name('score_grid.md').write_text('\n'.join(L) + '\n')
print('\n'.join(L))
