"""mkroster.py OUT TAG N_PER_VARIANT SEED0 VARIANTS(comma) : roster of fresh-dev scenes (no holdout scenes), half static half mid"""
import json, glob, random, sys
out, tag, n, seed0, vs = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5].split(',')
K = {"CRUISE_SPEED_MIN": 4.0, "CRUISE_SPEED_MAX": 6.0, "MAX_ACCELERATION": 8.0, "MAX_JERK": 40.0, "MAX_YAW_RATE": 2.0, "ROADMAP_SPACING": 1.0, "CONNECTION_DISTANCE": 6.0}
V = {'K': {}, 'P1': {"PHASE_ACCELERATION": 0.6, "PHASE_JERK": 2.0, "MAX_YAW_RATE": 3.0},
     'P2': {"PHASE_ACCELERATION": 0.6, "PHASE_JERK": 2.0, "MAX_YAW_RATE": 3.0, "TRACKING_MARGIN": 0.4},
     'P3': {"PHASE_ACCELERATION": 0.6, "PHASE_JERK": 2.0, "MAX_YAW_RATE": 3.0, "ROADMAP_SPACING": 1.5, "CONNECTION_DISTANCE": 9.0},
     'P4': {"PHASE_ACCELERATION": 0.4, "PHASE_JERK": 1.0, "MAX_YAW_RATE": 2.5},
     'P6': {"PHASE_ACCELERATION": 0.8, "PHASE_JERK": 3.0, "MAX_YAW_RATE": 3.0, "ROADMAP_SPACING": 2.0, "CONNECTION_DISTANCE": 12.0},
     'P5': {"PHASE_ACCELERATION": 1.0, "PHASE_JERK": 4.0, "MAX_YAW_RATE": 4.0, "MAX_ACCELERATION": 12.0, "MAX_JERK": 80.0}}
hold = set()
for f in glob.glob('/data/backups/rganapa/Sebastian/gen/raw-holdout/**/*.json', recursive=True):
    try: d = json.load(open(f)); hold.add(d['scene'])
    except Exception: pass
sc = {}
for f in glob.glob('/data/backups/rganapa/Sebastian/tmp/fresh_pool/*.json'):
    d = json.load(open(f))
    if d['scene'] not in hold: sc[d['scene']] = d['catalog']
scenes = sorted(sc); rng = random.Random(seed0); fl = []
for v in vs:
    for i in range(n):
        s = rng.choice(scenes); mid = i % 2 == 1; crop = round(rng.uniform(3, 40) / 0.05) * 0.05 if mid else None
        f = {"id": f"{tag}{v}{'m' if mid else 's'}-{s}-{i:03d}", "split": "bench", "group": "dev", "catalog": sc[s], "scene": s, "seed": seed0 + len(fl),
             "seconds": round(60 + (crop or 0), 2), "regime": "benchmark", "hold_seconds": 1.0, "waypoints_per_second": 0.8,
             "task_overrides": {**K, **V[v]}, "setting": v}
        if mid: f["crop_start_s"] = round(crop, 2)
        fl.append(f)
json.dump({"spec": f"servertail {tag}", "flights": fl}, open(out, 'w'), indent=1)
print(len(fl), len(scenes))
