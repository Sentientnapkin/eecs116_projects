"""Characterize high-variance flights from out/<name>/replicates_fresh.json. usage: characterize.py <name>"""
import json, sys, numpy as np
from pathlib import Path
SM = Path(__file__).resolve().parent.parent
name = sys.argv[1]
d = json.loads((SM / 'robust/out' / name / 'replicates_fresh.json').read_text()); rows = d['rows']
tf = {r['episode']: r for r in json.loads((SM / 'fresh/truth_feats.json').read_text())}
POOL = Path('/data/backups/rganapa/Sebastian/tmp/fresh_pool')
def side(e):
    return json.loads((POOL / f'{e}.json').read_text())
for r in rows:
    t = tf[r['episode']]; s = side(r['episode']); a = s.get('audit', {})
    r.update(angle=t['angle'], speed0=t['speed0'], travel=a.get('travel_m'), dark=a.get('dark_fraction'), flat=a.get('flat_fraction'),
             turn=a.get('turning_fraction'), hover=a.get('hover_fraction'), p50=(a.get('speed_p10_p50_p90') or [0, 0, 0])[1], p90=(a.get('speed_p10_p50_p90') or [0, 0, 0])[2],
             maxyaw=s.get('task_overrides', {}).get('MAX_YAW_RATE'), cruise=s.get('task_overrides', {}).get('CRUISE_SPEED_MAX'), setting=s.get('setting'))
def frac(sel): return len(sel)
tot = sum(r['mean'] for r in rows); N = len(rows)
hv = [r for r in rows if r['high_variance']]; cb = [r for r in rows if r['consistently_bad']]
out = []
P = lambda *x: out.append(' '.join(str(i) for i in x))
P(f'N={N}  mean-of-means {tot/N:.3f}  high-variance {len(hv)} ({100*len(hv)/N:.1f}%) carry {100*sum(r["mean"] for r in hv)/tot:.1f}% of mean; hv excl. consistently-bad {len([r for r in hv if not r["consistently_bad"]])}; consistently bad {len(cb)} carry {100*sum(r["mean"] for r in cb)/tot:.1f}%')
hvm = np.mean([r['mean'] for r in hv]) if hv else 0; oth = [r for r in rows if not r['high_variance']]
P(f'mean ATE hv {hvm:.2f} vs rest {np.mean([r["mean"] for r in oth]):.3f};  if hv flights were replaced by the rest mean: {np.mean([r["mean"] for r in oth]):.3f}; if hv replaced by their min: mean {(sum(r["min"] if r["high_variance"] else r["mean"] for r in rows))/N:.3f}')
def bins(key, edges, labels=None):
    P(f'-- by {key}')
    for i in range(len(edges) - 1):
        sel = [r for r in rows if r[key] is not None and edges[i] <= r[key] < edges[i + 1]]
        if not sel: continue
        h = sum(r['high_variance'] for r in sel)
        P(f'  [{edges[i]},{edges[i+1]}) n={len(sel):3d} hv={h:3d} ({100*h/len(sel):4.1f}%) mean {np.mean([r["mean"] for r in sel]):.3f} mean-std {np.mean([r["std"] for r in sel]):.3f}')
P('-- by start'); 
for st in ('static', 'mid'):
    sel = [r for r in rows if r['start'] == st]; h = sum(r['high_variance'] for r in sel)
    P(f'  {st} n={len(sel)} hv={h} ({100*h/len(sel):.1f}%) mean {np.mean([r["mean"] for r in sel]):.3f} mean-std {np.mean([r["std"] for r in sel]):.3f}')
mid = [r for r in rows if r['start'] == 'mid']
rows_all = rows
rows = mid; bins('angle', [0, 45, 90, 135, 181]); bins('speed0', [0, .3, .6, 1.0, 1.8, 10]); rows = rows_all
bins('travel', [0, 30, 45, 60, 80, 1000]); bins('turn', [0, .3, .5, .7, 1.01]); bins('flat', [0, 1e-9, .1, .3, 1.01]); bins('dark', [0, 1e-9, .1, .3, 1.01])
bins('p90', [0, 1.5, 2.5, 3.5, 100])
P('-- by catalog')
for c in sorted({r['catalog'] for r in rows}):
    sel = [r for r in rows if r['catalog'] == c]; h = sum(r['high_variance'] for r in sel)
    P(f'  {c} n={len(sel)} hv={h} ({100*h/len(sel):.1f}%) mean {np.mean([r["mean"] for r in sel]):.3f}')
P('-- by scene: scenes with >=3 hv flights')
from collections import Counter
c = Counter(r['scene'] for r in hv); n = Counter(r['scene'] for r in rows)
for sc, k in c.most_common(8):
    if k >= 2: P(f'  {sc}: {k}/{n[sc]}')
P('-- worst 25 hv flights (by std)')
for r in sorted(hv, key=lambda r: -r['std'])[:25]:
    P(f'  {r["episode"]} {r["start"]} ang {r["angle"]:.0f} v0 {r["speed0"]:.2f} travel {r["travel"]} flat {r["flat"]} dark {r["dark"]} reps ' + ' '.join(f'{x:.2f}' for x in r['reps']))
txt = '\n'.join(out); (SM / 'robust/out' / name / 'characterization.txt').write_text(txt + '\n'); print(txt)
