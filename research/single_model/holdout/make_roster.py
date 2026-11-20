"""Roster builder for the holdout set. stage1: one static flight per eligible scene (pilot + candidates).
stage2: extra static + mid candidates in scenes whose stage-1 extent was high (truth statistics only).
Usage (teacher python): python make_roster.py stage1 | stage2
"""
import glob, json, os, random, sys, collections
R = '/data/backups/rganapa/Sebastian'
RES = R + '/eecs116_projects/research'
OUT = R + '/gen/raw-holdout'
K = {"CRUISE_SPEED_MIN": 3.0, "CRUISE_SPEED_MAX": 4.5, "MAX_ACCELERATION": 6.0, "MAX_JERK": 30.0, "MAX_YAW_RATE": 2.0, "ROADMAP_SPACING": 1.0, "CONNECTION_DISTANCE": 6.0}
K2 = {"CRUISE_SPEED_MIN": 4.0, "CRUISE_SPEED_MAX": 6.0, "MAX_ACCELERATION": 8.0, "MAX_JERK": 40.0, "MAX_YAW_RATE": 2.0, "ROADMAP_SPACING": 1.0, "CONNECTION_DISTANCE": 6.0}
SETTINGS = {"K": K, "K2": K2}
CRASH_PT = {121, 124}; CRASH_HS = {"103997940_171031257"}
TEST_PT = set(range(162, 166)) | set(range(172, 176))

def existing_seeds():
    seeds = collections.defaultdict(set)  # seed -> {(catalog, scene)}
    for p in glob.glob(R + '/gen/raw*/**/*.json', recursive=True):
        if 'sealed' in p or '/raw/test/' in p or p.startswith(OUT): continue
        try: d = json.load(open(p))
        except Exception: continue
        if isinstance(d, dict) and 'seed' in d and 'scene' in d: seeds[d['seed']].add((d['catalog'], d['scene']))
        if isinstance(d, dict) and isinstance(d.get('flights'), list):
            for f in d['flights']:
                if 'seed' in f: seeds[f['seed']].add((f.get('catalog'), f.get('scene')))
    for p in glob.glob(RES + '/configs/*.json'):
        try: d = json.load(open(p))
        except Exception: continue
        if isinstance(d, dict):
            for f in d.get('flights', []):
                if 'seed' in f: seeds[f['seed']].add((f.get('catalog'), f.get('scene')))
    return seeds

def raw_fast_scenes():
    s = set()
    for p in glob.glob(R + '/gen/raw-fast/bench/*.json'):
        d = json.load(open(p)); s.add((d['catalog'], d['scene']))
    return s

def eligible():
    used = raw_fast_scenes()
    nc = json.load(open(RES + '/configs/native_campaign.json'))['flights']
    hs_train = sorted({f['scene'] for f in nc if f['catalog'] == 'hssd-train'} - CRASH_HS)
    hv_dev = sorted({f['scene'] for f in nc if f['catalog'] == 'hssd-val' and f['split'] == 'dev'})
    pt = [f'ProcTHOR-Train-{i}' for i in range(200) if i not in CRASH_PT and i not in TEST_PT]
    new_pt = [s for s in pt if ('procthor', s) not in used]
    new_hs = [s for s in hs_train if ('hssd-train', s) not in used]
    return new_pt, new_hs, hv_dev

def mk(fid, catalog, scene, seed, mid, crop, setting):
    d = {"id": fid, "split": "bench", "group": "new" if catalog != 'hssd-val' else 'reused-dev', "catalog": catalog, "scene": scene,
         "seed": seed, "seconds": round(60 + crop, 2) if mid else 60, "regime": "benchmark",
         "hold_seconds": 0.2 if mid else 1.0, "waypoints_per_second": 0.8, "task_overrides": SETTINGS[setting], "setting": setting}
    if mid: d["crop_start_s"] = crop
    return d

def main():
    stage = sys.argv[1]
    seeds = existing_seeds()
    print('existing seeds', len(seeds), 'range', min(seeds), max(seeds))
    new_pt, new_hs, hv = eligible()
    print('eligible new scenes: procthor', len(new_pt), 'hssd-train', len(new_hs), 'hssd-val dev (reused)', len(hv))
    rng = random.Random(20261120 + {'stage1': 1, 'stage2': 2}[stage])
    flights = []
    nxt = {'stage1': 970000, 'stage2': 972000}[stage]
    smid = 980000 if stage == 'stage1' else 982000
    def seed_for(mid):
        nonlocal nxt, smid
        while True:
            if mid: s = smid; smid += 1
            else: s = nxt; nxt += 1
            if s not in seeds: return s
    if stage == 'stage1':
        scenes = [('procthor', s, 1) for s in new_pt] + [('hssd-train', s, 1) for s in new_hs] + [('hssd-val', s, 2) for s in hv]
        for cat, sc, n in scenes:
            for i in range(n):
                setting = rng.choice(['K', 'K2'])
                flights.append(mk(f'fast-{sc}-{50+i:02d}', cat, sc, seed_for(False), False, 0, setting))
    else:
        ext = json.load(open(OUT + '/cfg/scene_extent.json'))  # {"catalog|scene": mean extent from stage 1}
        plan = json.load(open(OUT + '/cfg/stage2_plan.json'))  # {"catalog|scene": [n_static, n_mid]}
        have = collections.Counter()
        for k, (ns, nm) in plan.items():
            cat, sc = k.split('|')
            for i in range(ns):
                flights.append(mk(f'fast-{sc}-{60+i:02d}', cat, sc, seed_for(False), False, 0, rng.choice(['K', 'K2'])))
            for i in range(nm):
                crop = round(round(rng.uniform(3, 40) / 0.05) * 0.05, 2)
                flights.append(mk(f'fastmid-{sc}-{50+i:02d}', cat, sc, seed_for(True), True, crop, rng.choice(['K', 'K2'])))
    rng.shuffle(flights)
    ss = [f['seed'] for f in flights]
    assert len(set(ss)) == len(ss) and not (set(ss) & set(seeds)), 'seed collision'
    out = OUT + f'/cfg/roster_{stage}.json'
    json.dump({"spec": "holdout " + stage, "flights": flights}, open(out, 'w'), indent=1)
    print(stage, len(flights), 'flights ->', out, collections.Counter((f['catalog'], f['id'].startswith('fastmid')) for f in flights))
main()
