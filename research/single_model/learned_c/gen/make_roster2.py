"""Roster for the new TRAINING pool (learned_c data loop). Server-like fast static flights (same planner overrides K/K2 as gen/raw-fast and the holdout), 60 s, hold 1.0 s.
Eligible scenes: fold in {0,1,2} (hash of catalog:scene), NOT in the clean holdout (gen/raw-holdout/final), not reserved test scenes, not known crashers, never fold 3/4.
Seeds 990000+ checked against every sidecar/roster seed.
  python make_roster2.py ROUND N [--yaw 2.0] [--k2 0.5] [--scenes sceneweights.json]  -> gen/roster_r<ROUND>.json (resumable ids)"""
import argparse, collections, glob, hashlib, json, os, random, sys
R = '/data/backups/rganapa/Sebastian'; RES = R + '/eecs116_projects/research'; HERE = os.path.dirname(os.path.abspath(__file__))
K = {"CRUISE_SPEED_MIN": 3.0, "CRUISE_SPEED_MAX": 4.5, "MAX_ACCELERATION": 6.0, "MAX_JERK": 30.0, "MAX_YAW_RATE": 2.0, "ROADMAP_SPACING": 1.0, "CONNECTION_DISTANCE": 6.0}
K2 = {"CRUISE_SPEED_MIN": 4.0, "CRUISE_SPEED_MAX": 6.0, "MAX_ACCELERATION": 8.0, "MAX_JERK": 40.0, "MAX_YAW_RATE": 2.0, "ROADMAP_SPACING": 1.0, "CONNECTION_DISTANCE": 6.0}
CRASH_PT = {121, 124}; CRASH_HS = {"103997940_171031257"}; TEST_PT = set(range(162, 166)) | set(range(172, 176))
fold = lambda c, s: int(hashlib.sha256(f'{c}:{s}'.encode()).hexdigest()[:8], 16) % 5

def existing_seeds():
    seeds = set()
    for p in glob.glob(R + '/gen/raw*/**/*.json', recursive=True) + glob.glob(RES + '/configs/*.json') + glob.glob(HERE + '/roster_r*.json'):
        if '/sealed' in p or '/raw/test/' in p: continue
        try: d = json.load(open(p))
        except Exception: continue
        if isinstance(d, dict) and 'seed' in d: seeds.add(d['seed'])
        if isinstance(d, dict) and isinstance(d.get('flights'), list):
            for f in d['flights']:
                if 'seed' in f: seeds.add(f['seed'])
    return seeds

def holdout_scenes():
    s = set()
    for f in os.listdir(R + '/gen/raw-holdout/final'):
        if f.endswith('.zip'):
            for d in ('bench', 'final', 'partial'):
                p = f'{R}/gen/raw-holdout/{d}/{f[:-4]}.json'
                if os.path.exists(p): j = json.load(open(p)); s.add((j['catalog'], j['scene'])); break
    return s

def eligible():
    nc = json.load(open(RES + '/configs/native_campaign.json'))['flights']
    sc = {('procthor', f'ProcTHOR-Train-{i}') for i in range(200) if i not in CRASH_PT and i not in TEST_PT}
    sc |= {('hssd-train', f['scene']) for f in nc if f['catalog'] == 'hssd-train' and f['scene'] not in CRASH_HS}
    sc |= {('hssd-val', f['scene']) for f in nc if f['catalog'] == 'hssd-val' and f['split'] == 'dev'}
    ho = holdout_scenes()
    return sorted(s for s in sc if fold(*s) in (0, 1, 2) and s not in ho), sc, ho

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('round'); ap.add_argument('n', type=int); ap.add_argument('--yaw', default='2.0', help='MAX_YAW_RATE, or a mix like 2.0:0.5,0.6:0.5')
    ap.add_argument('--k2', type=float, default=0.5); ap.add_argument('--weights', default=''); ap.add_argument('--seed0', type=int, default=990000)
    a = ap.parse_args()
    el, allsc, ho = eligible()
    print('scenes: eligible', len(el), 'of', len(allsc), 'holdout', len(ho), collections.Counter(c for c, s in el))
    seeds = existing_seeds(); rng = random.Random(20261121 + int(a.round[-1]) if a.round[-1].isdigit() else 1)
    w = json.load(open(a.weights)) if a.weights else {}
    wt = [w.get(f'{c}|{s}', 1.0) for c, s in el]
    nxt = a.seed0 + int(a.round[-1]) * 100000 if a.round[-1].isdigit() else a.seed0
    ym = [float(x.split(':')[0]) for x in a.yaw.split(',')]; yw = [float(x.split(':')[1]) if ':' in x else 1.0 for x in a.yaw.split(',')]
    flights = []; cnt = collections.Counter()
    for i in range(a.n):
        c, s = rng.choices(el, wt)[0]; cnt[(c, s)] += 1
        while nxt in seeds: nxt += 1
        setting = 'K2' if rng.random() < a.k2 else 'K'; ov = dict(K2 if setting == 'K2' else K); ov['MAX_YAW_RATE'] = ym[rng.choices(range(len(ym)), yw)[0]]
        flights.append({"id": f"nw{a.round}-{s}-{cnt[(c, s)]:02d}", "split": "bench", "group": "train2", "catalog": c, "scene": s, "seed": nxt, "seconds": 60, "regime": "benchmark",
                        "hold_seconds": 1.0, "waypoints_per_second": 0.8, "task_overrides": ov, "setting": setting}); seeds.add(nxt)
    assert len({f['seed'] for f in flights}) == len(flights) and all(fold(f['catalog'], f['scene']) in (0, 1, 2) for f in flights)
    json.dump({"spec": "learned_c train2 " + a.round, "flights": flights}, open(f'{HERE}/roster_{a.round}.json', 'w'), indent=1)
    print(a.round, len(flights), 'flights, seeds', flights[0]['seed'], '-', flights[-1]['seed'], collections.Counter(f['setting'] for f in flights))
