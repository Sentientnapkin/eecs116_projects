"""Edge-case labels (truth-derived, analysis/constraints only) for the VISIBLE selected flights (folds 0-3; fold 4 is never touched)
and the fresh split. Output: categories.json. Run once: python -m research.single_model.autoloop.cats"""
import hashlib, json, os, sys
from pathlib import Path
import numpy as np
from research.single_model import run_variant as RV

HERE = Path(__file__).resolve().parent
RAW = RV.ROOT.parent / 'Sebastian' if False else Path('/data/backups/rganapa/Sebastian/gen/raw-fast')
FRESH = RV.ROOT / 'research/single_model/fresh'
FRESH_POOL = Path('/data/backups/rganapa/Sebastian/tmp/fresh_pool')
ANG_BINS = [(0, 45), (45, 90), (90, 135), (135, 181)]


def fresh_fold(t):
    return int(hashlib.sha256((t['catalog'] + ':' + t['scene']).encode()).hexdigest()[:8], 16) % 5


def truth_one(arg):
    # ground_truth_state twist is expressed in the CAMERA frame (verified: forward flight gives +z; the fresh/ truth_feats.json angle used
    # body +x on a camera-frame velocity and is NOT the camera-axis angle), so the optical axis is +z of v.
    from viobench.tools.datasets.storage import read_episode
    ep, root = arg
    e = read_episode(Path(root) / f'{ep}.zip', frames='none')
    s = np.asarray(e.ground_truth_state()); t = np.asarray(e.frame_times)
    axis = np.array([0.0, 0.0, 1.0])
    n = int(np.sum(t - t[0] <= 0.5 + 1e-9))
    v = s[:n, 7:10].mean(0); sp = float(np.linalg.norm(v))
    ang = float(np.degrees(np.arccos(np.clip(v @ axis / max(sp, 1e-9), -1, 1)))) if sp > 1e-6 else None
    yaw = float(np.mean(np.linalg.norm(s[:, 10:13], axis=1)))
    return dict(speed0=sp, angle=ang, yawrate=yaw)


def main():
    from multiprocessing import Pool
    tg = RV.tags(); vis = sorted(e for e in tg if RV.slice_of(RV.fold(tg[e])) != 'sealed')
    with Pool(12) as p:
        tr = p.map(truth_one, [(e, RV.EPISODES) for e in vis])
    rows = {}
    for e, t in zip(vis, tr):
        a = json.loads((RAW / 'bench' / f'{e}.json').read_text()).get('audit', {})
        rows[e] = dict(t, start=tg[e]['start'], group=tg[e]['group'], flat=a.get('flat_fraction', 0), dark=a.get('dark_fraction', 0),
                       travel=a.get('travel_m', 0), fold=RV.fold(tg[e]), scene=tg[e]['scene'])
    yaw_thr = float(np.percentile([r['yawrate'] for r in rows.values()], 75))
    cats = {'all': [], 'wrong_dir_gt90': [], 'fast_start_gt1.5': [], 'slow_start_lt0.3': [], 'static_start': [], 'textureless_dark': [],
            'long_path_gt58m': [], 'high_yaw_top25': [], 'clean_scene': [], 'mid_ang_0_45': [], 'mid_ang_45_90': [], 'mid_ang_90_135': [], 'mid_ang_135_180': []}
    for e, r in rows.items():
        cats['all'].append(e)
        if r['start'] == 'static': cats['static_start'].append(e)
        if r['start'] != 'static':
            if r['angle'] is not None and r['speed0'] > 0.05:
                if r['angle'] > 90: cats['wrong_dir_gt90'].append(e)
                for lo, hi in ANG_BINS:
                    if lo <= r['angle'] < hi: cats[f'mid_ang_{lo}_{min(hi,180)}'].append(e)
            if r['speed0'] > 1.5: cats['fast_start_gt1.5'].append(e)
            if r['speed0'] < 0.3: cats['slow_start_lt0.3'].append(e)
        if r['flat'] > 0.05 or r['dark'] > 0.05: cats['textureless_dark'].append(e)
        if r['travel'] > 58: cats['long_path_gt58m'].append(e)
        if r['yawrate'] >= yaw_thr: cats['high_yaw_top25'].append(e)
        if r['group'] == 'clean': cats['clean_scene'].append(e)
    # fresh split A (tuning confirmation, folds 0-2 of the fresh tags, ~60%) / B (held out, folds 3-4)
    ft = json.loads((FRESH / 'tags.json').read_text())
    with Pool(12) as p:
        tfl = p.map(truth_one, [(e, FRESH_POOL) for e in sorted(ft)])
    tf = dict(zip(sorted(ft), tfl))
    fr = {}
    for e, t in ft.items():
        f = fresh_fold(t); a = tf[e]
        fr[e] = dict(split='A' if f <= 2 else 'B', start=t['start'], group=t['group'], scene=t['scene'], speed0=a['speed0'], angle=a['angle'])
    fcats = {}
    for sp in 'AB':
        eps = [e for e in fr if fr[e]['split'] == sp]
        fcats[sp] = {'all': eps, 'static': [e for e in eps if fr[e]['start'] == 'static'], 'mid': [e for e in eps if fr[e]['start'] != 'static']}
        for lo, hi in ANG_BINS:
            fcats[sp][f'mid_ang_{lo}_{min(hi,180)}'] = [e for e in fcats[sp]['mid'] if fr[e]['angle'] is not None and fr[e]['speed0'] > 0.05 and lo <= fr[e]['angle'] < hi]
    out = dict(visible=rows, cats=cats, yaw_thr=yaw_thr, fresh=fr, fresh_cats=fcats)
    (HERE / 'categories.json').write_text(json.dumps(out, indent=1))
    print({k: len(v) for k, v in cats.items()}); print({sp: {k: len(v) for k, v in c.items()} for sp, c in fcats.items()})
    print('verify frame convention: wrong-dir count among visible mid', len(cats['wrong_dir_gt90']), 'of', sum(1 for r in rows.values() if r['start'] != 'static'))

if __name__ == '__main__':
    main()
