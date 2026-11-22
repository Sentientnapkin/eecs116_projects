"""sl_roster.py ROUND N SEED0 -> roster_<ROUND>.json : more fast/starved training flights for stlong.
Scenes: learned_c eligible() (fold 0-2, non-holdout, not crashers/test) MINUS st2 (dev+conf) scenes (st3 lives in st2-dev scenes).
Weights: low texture strongly favoured ((0.13/tex)^2 capped [0.3,8]); ProcTHOR x1.5. Variants: servertail K/P1-P6 + K1 (3-4.5 m/s)."""
import json, sys, random, collections, os, glob
HERE = os.path.dirname(os.path.abspath(__file__)); SM = os.path.join(HERE, '../..')
sys.path.insert(0, os.path.join(SM, 'learned_c/gen'))
import make_roster2 as M
rnd, n, seed0 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
K = {"CRUISE_SPEED_MIN": 4.0, "CRUISE_SPEED_MAX": 6.0, "MAX_ACCELERATION": 8.0, "MAX_JERK": 40.0, "MAX_YAW_RATE": 2.0, "ROADMAP_SPACING": 1.0, "CONNECTION_DISTANCE": 6.0}
V = {'K': ({}, 3), 'P1': ({"PHASE_ACCELERATION": 0.6, "PHASE_JERK": 2.0, "MAX_YAW_RATE": 3.0}, 2),
     'P2': ({"PHASE_ACCELERATION": 0.6, "PHASE_JERK": 2.0, "MAX_YAW_RATE": 3.0, "TRACKING_MARGIN": 0.4}, 1),
     'P3': ({"PHASE_ACCELERATION": 0.6, "PHASE_JERK": 2.0, "MAX_YAW_RATE": 3.0, "ROADMAP_SPACING": 1.5, "CONNECTION_DISTANCE": 9.0}, 1),
     'P4': ({"PHASE_ACCELERATION": 0.4, "PHASE_JERK": 1.0, "MAX_YAW_RATE": 2.5}, 1),
     'P5': ({"PHASE_ACCELERATION": 1.0, "PHASE_JERK": 4.0, "MAX_YAW_RATE": 4.0, "MAX_ACCELERATION": 12.0, "MAX_JERK": 80.0}, 2),
     'P6': ({"PHASE_ACCELERATION": 0.8, "PHASE_JERK": 3.0, "MAX_YAW_RATE": 3.0, "ROADMAP_SPACING": 2.0, "CONNECTION_DISTANCE": 12.0}, 1),
     'K1': ({"CRUISE_SPEED_MIN": 3.0, "CRUISE_SPEED_MAX": 4.5, "MAX_ACCELERATION": 6.0, "MAX_JERK": 30.0}, 1)}
ST2 = {f['scene'] for f in json.load(open(os.path.join(SM, 'servertail/gen/st2.json')))['flights']}
ST3 = {f['scene'] for f in json.load(open(os.path.join(SM, 'learnvel/gen/st3.json')))['flights']}
assert ST3 <= ST2
el, _, ho = M.eligible(); el = [s for s in el if s[1] not in ST2 and s not in ho]
tex = json.load(open(os.path.join(SM, 'learnvel/tables/scenetex.json')))
wt = [min(8, max(0.3, (0.13 / tex[f'{c}|{s}']['tex']) ** 2)) * (1.5 if c == 'procthor' else 1.0) if f'{c}|{s}' in tex else 1.0 for c, s in el]
seeds = M.existing_seeds()
for p in glob.glob(os.path.join(SM, '*/gen/*.json')) + glob.glob(os.path.join(HERE, 'roster_*.json')):
    try: d = json.load(open(p))
    except Exception: continue
    if isinstance(d, dict) and isinstance(d.get('flights'), list): seeds |= {f['seed'] for f in d['flights'] if isinstance(f, dict) and 'seed' in f}
rng = random.Random(seed0); nxt = seed0; fl = []; cnt = collections.Counter()
vs = list(V); vw = [V[v][1] for v in vs]
for i in range(n):
    c, s = rng.choices(el, wt)[0]; cnt[s] += 1
    while nxt in seeds: nxt += 1
    v = rng.choices(vs, vw)[0]
    fl.append({"id": f"sl{rnd}{v}-{s}-{cnt[s]:02d}", "split": "bench", "group": "train2", "catalog": c, "scene": s, "seed": nxt, "seconds": 60, "regime": "benchmark",
               "hold_seconds": 1.0, "waypoints_per_second": 0.8, "task_overrides": {**K, **V[v][0]}, "setting": v}); seeds.add(nxt)
assert all(M.fold(f['catalog'], f['scene']) in (0, 1, 2) and f['scene'] not in ST2 for f in fl)
json.dump({"spec": "stlong " + rnd, "flights": fl}, open(f'{HERE}/roster_{rnd}.json', 'w'), indent=1)
print(len(fl), 'scenes', len(el), 'used', len(cnt), 'top', cnt.most_common(8), collections.Counter(f['setting'] for f in fl), collections.Counter(f['catalog'] for f in fl))
