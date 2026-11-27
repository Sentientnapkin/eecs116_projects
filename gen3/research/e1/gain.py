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
