"""Area gain of a candidate point, computed exactly as the viobench server does (evaluations.py: area_gains).

    python area_gain.py FUEL ATE            # gain of one (max fuel/frame, mean unaligned ATE) point
    python area_gain.py FUEL ATE --refresh  # first re-download the live /comparison (needs ~/.viobench_token)

Standard library only, so it runs on Windows and in WSL. The baselines come from ../comparison_live.json.
The server scores a team by its single best submission, so a candidate matters only if its gain beats `claimed_area`.
"""
import json
import math
import pathlib
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
COMPARISON = HERE.parent / "comparison_live.json"
FUEL_FLOOR, ERROR_FLOOR = 1, 0.001


def dominated_area(points, max_fuel, max_error, min_fuel=FUEL_FLOOR, min_error=ERROR_FLOOR):
    if max_fuel <= min_fuel or max_error <= min_error:
        return 0.0
    max_x, max_y = math.log(max_fuel / min_fuel), math.log(max_error / min_error)
    ordered = sorted((math.log(max(f, min_fuel) / min_fuel), math.log(max(e, min_error) / min_error))
                     for f, e in points if math.isfinite(f) and math.isfinite(e) and 0 <= f < max_fuel and 0 <= e < max_error)
    area, prev_x, best_y = 0.0, 0.0, max_y
    for x, y in ordered:
        if y >= best_y:
            continue
        area += (x - prev_x) * (max_y - best_y)
        prev_x, best_y = x, y
    return area + (max_x - prev_x) * (max_y - best_y)


def refresh():
    token_file = next(p for p in (pathlib.Path.home() / ".viobench_token", pathlib.Path.home() / ".viobench_token.txt") if p.exists())
    token = token_file.read_text(encoding="utf-8-sig").strip()
    req = urllib.request.Request("https://viobench.rl.tools/comparison",
                                 headers={"Authorization": f"Bearer {token}", "User-Agent": "viobench-client/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        COMPARISON.write_text(json.dumps(json.load(r), indent=1))


def load():
    return json.loads(COMPARISON.read_text())


def gain(fuel, ate, comparison=None):
    c = comparison or load()
    base = [(max(p["fuel_per_frame_max"], FUEL_FLOOR), max(p["ate_rmse_mean"], ERROR_FLOOR)) for p in c["points"] if p["is_baseline"]]
    ref_err, ref_fuel = 1.2 * min(base)[1], c["fuel_reference"]
    b = dominated_area(base, ref_fuel, ref_err)
    return max(0.0, dominated_area([*base, (max(fuel, FUEL_FLOOR), max(ate, ERROR_FLOOR))], ref_fuel, ref_err) - b)


def best(comparison=None):
    c = comparison or load()
    p = next((p for p in c["points"] if p["id"] == c["best_submission_id"]), None)
    return c["claimed_area"], p


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    if "--refresh" in sys.argv:
        refresh()
    c = load()
    fuel, ate = float(sys.argv[1]), float(sys.argv[2])
    g = gain(fuel, ate, c)
    area, p = best(c)
    print(f"candidate {ate:.3f} m @ {fuel:,.0f} fuel -> gain {g:.3f}")
    if p:
        print(f"current best: {p['label']!r} {p['ate_rmse_mean']:.3f} m @ {p['fuel_per_frame_max']:,.0f} -> claimed {area:.3f}")
    print("BEATS current best" if g > area else f"does NOT beat current best (short by {area - g:.3f})")
