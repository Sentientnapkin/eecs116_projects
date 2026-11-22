"""Per-episode results of our viobench submissions, for diagnosis.

Reads the team token from %USERPROFILE%\\.viobench_token (one line, never printed).
    python fetch_results.py                 # list submissions
    python fetch_results.py <submission id> # per-episode metrics of one submission (also saved as results_<id>.json)
"""
import json
import math
import pathlib
import sys
import urllib.request

SERVER = "https://viobench.rl.tools"
_token_file = next(p for p in (pathlib.Path.home() / ".viobench_token", pathlib.Path.home() / ".viobench_token.txt")
                   if p.exists())
TOKEN = _token_file.read_text(encoding="utf-8-sig").strip()


def get(path):
    request = urllib.request.Request(SERVER + path, headers={"Authorization": f"Bearer {TOKEN}",
                                                             "User-Agent": "viobench-client/0.1"})  # the default is blocked
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def fmt(value, spec):
    return format(value, spec) if isinstance(value, (int, float)) and math.isfinite(value) else "-"


if len(sys.argv) == 1:
    for row in get("/submissions"):
        s = row.get("summary") or {}
        print(f"{row['id']}  {row.get('label') or '':40s}  ATE {fmt(s.get('ate_rmse_mean'), '.2f')} m  "
              f"max fuel {fmt(s.get('fuel_per_frame_max'), ',.0f')}  {row.get('status', '')}")
    sys.exit()

data = get(f"/submissions/{sys.argv[1]}")
out = pathlib.Path(__file__).with_name(f"results_{sys.argv[1]}.json")
out.write_text(json.dumps(data, indent=1))
results = data.get("results") or {}
print(f"{'episode':12s} {'frames':>6s} {'dist m':>7s} {'ATE':>6s} {'Sim3':>6s} {'scale':>6s} {'rot deg':>7s} "
      f"{'vel err':>7s} {'drift/m':>7s} {'filled':>6s} {'max fuel':>12s} {'p95 fuel':>12s}")
for e in results.get("episodes", []):
    m = e.get("metrics", {})
    fuel = e.get("fuel") or {}
    print(f"{str(e.get('hash', ''))[:10]:12s} {m.get('frames', 0):6d} {fmt(m.get('distance_travelled'), '7.1f')} "
          f"{fmt(m.get('ate_rmse'), '6.2f')} {fmt(m.get('sim3_ate_rmse'), '6.2f')} {fmt(m.get('sim3_scale'), '6.2f')} "
          f"{fmt(m.get('rotation_rmse', float('nan')) * 57.2958, '7.1f')} {fmt(m.get('velocity_rmse'), '7.2f')} "
          f"{fmt(m.get('drift_per_metre'), '7.2f')} {m.get('filled_frames', 0):6d} "
          f"{fmt(e.get('fuel_per_frame_max', fuel.get('max') if isinstance(fuel, dict) else None), '12,.0f')} "
          f"{fmt(e.get('fuel_per_frame_p95', fuel.get('p95') if isinstance(fuel, dict) else None), '12,.0f')}")
s = results.get("summary") or {}
print(f"\nmean ATE {fmt(s.get('ate_rmse_mean'), '.2f')} m, mean Sim3 ATE {fmt(s.get('sim3_ate_rmse_mean'), '.2f')} m, "
      f"max fuel {fmt(s.get('fuel_per_frame_max'), ',.0f')}  (full JSON: {out.name})")
