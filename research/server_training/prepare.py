"""Prepare N3 pilot from nonselected flights in campaign TRAIN scenes only.

The selected171 clean/dev flights are held out from training; original development
selects checkpoints. New images/features use the frozen N2 kf_grid_native derivation.
Run from research: python -m server_training.prepare --config configs/server_train_pool.json
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def resolve(p): return (ROOT / p).resolve()
def digest(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()


def choose(config):
    roster = json.loads(resolve(config['campaign_roster']).read_text())['flights']
    allowed = {r['scene'] for r in roster if r['split'] == 'train'}
    denied = {r['scene'] for r in roster if r['split'] != 'train'}
    if allowed & denied: raise ValueError('campaign train/heldout scene overlap')
    selected = set(json.loads(resolve(config['selection']).read_text())['selected'])
    rows = [json.loads(p.read_text()) for p in sorted((Path(config['raw_root'])/'bench').glob('*.json'))]
    candidates = [r for r in rows if r['id'] not in selected and r['scene'] in allowed and r['scene'] not in denied and r['group'] == 'seen']
    rng = np.random.default_rng(config['seed']); chosen = []
    for mid in (False, True):
        pool = [r for r in candidates if r['id'].startswith('fastmid-') == mid]
        if len(pool) < config['per_start']: raise ValueError('not enough disjoint training flights')
        chosen += [pool[i] for i in rng.permutation(len(pool))[:config['per_start']]]
    holdout = [r for r in rows if r['id'] in selected and r['group'] in ('clean', 'dev')]
    if {r['scene'] for r in chosen} & {r['scene'] for r in holdout}: raise ValueError('train/evaluation scene overlap')
    return chosen, holdout


def job(task):
    meta, root, output, sensor, training = task
    import cv2
    cv2.setNumThreads(1); cv2.setRNGSeed(217)
    from odometry_pool import prepare
    from common import Flight
    from attitude_bias import attitudes
    from input_attitude import derive
    output = Path(output); marker = output/'records'/(meta['id']+'.json')
    archive = Path(root)/'bench'/meta['file']
    if marker.exists():
        records = json.loads(marker.read_text())
        if all((output/r['file']).exists() and digest(output/r['file']) == r['sha256'] for r in records): return records
        raise ValueError(f'incomplete/changed cached records: {marker}')
    if digest(archive) != meta['sha256']: raise ValueError(f'archive checksum changed: {archive}')
    # A cropped raw-fast episode is already in its own camera-0 gauge; no second crop.
    legacy, audit = prepare(archive, {'scene': meta['scene'], 'domain': 'server-t0', 'tier': 'server', 'regime': 'benchmark'}, sensor, [0], 217, output, gate_flights=False)
    records = []
    for record in legacy:
        with np.load(output/record['file'], allow_pickle=False) as data: row = {k: data[k] for k in data.files}
        flight = Flight(archive)
        if not np.allclose(flight.ft, row['times']-row['times'][0], atol=1e-6): raise ValueError('native/shard timestamps differ')
        trace = []; rotations, windows, _ = attitudes(flight, 'kf_grid', trace=trace)
        derived, _ = derive(row, 'kf_grid', (rotations, np.asarray(trace)))
        tmp = output/f"tmp-native-{meta['id']}-{os.getpid()}.npz"
        np.savez_compressed(tmp, **derived); sha = digest(tmp); tmp.replace(output/(sha+'.npz'))
        records.append({**record, 'file': sha+'.npz', 'sha256': sha, 'derived_from': record['sha256'],
                        'input_policy': 'kf_grid_native', 'kf_resolution': 'native', 'kf_windows': windows,
                        'flight_id': meta['id'], 'parent_file': meta['file'], 'parent_sha256': meta['sha256'],
                        'catalog': meta['catalog'], 'group': meta['group'], 'split': 'train' if training else 'heldout',
                        'start_type': 'mid' if meta['id'].startswith('fastmid-') else 'static',
                        'raw_archive': str(archive), 'raw_sha256': meta['sha256']})
        if record['file'] != sha+'.npz': (output/record['file']).unlink()
    marker.parent.mkdir(exist_ok=True)
    tmp = marker.with_suffix('.partial'); tmp.write_text(json.dumps(records, indent=2)+'\n'); tmp.replace(marker)
    return records


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--config', default='configs/server_train_pool.json'); p.add_argument('--workers', type=int)
    p.add_argument('--roster-only', action='store_true'); a = p.parse_args()
    cfg = json.loads(resolve(a.config).read_text()); chosen, holdout = choose(cfg)
    output = resolve(cfg['output']); output.mkdir(parents=True, exist_ok=True)
    roster = {'declared_at': datetime.now(timezone.utc).isoformat(), 'config': cfg, 'train': chosen, 'heldout': holdout,
              'data_policy': 'nonselected episode IDs, campaign train scenes; clean/dev/test excluded; no remote writes'}
    roster_path = output/'roster.json'
    if roster_path.exists():
        old = json.loads(roster_path.read_text())
        if old['config'] != cfg or old['train'] != chosen or old['heldout'] != holdout: raise ValueError('immutable roster changed')
    else: roster_path.write_text(json.dumps(roster, indent=2)+'\n')
    print(f'predeclared {len(chosen)} train / {len(holdout)} heldout; {output}', flush=True)
    if a.roster_only: return
    baseline = json.loads(resolve(cfg['baseline_manifest']).read_text()); sensor = baseline['sensor_config']
    tasks = [(m, cfg['raw_root'], str(output), sensor, True) for m in chosen] + [(m, cfg['raw_root'], str(output), sensor, False) for m in holdout]
    results = {'train': [], 'heldout': []}
    workers = min(a.workers or cfg['workers'], 32)
    with ProcessPoolExecutor(workers) as pool:
        pending = {pool.submit(job, t): t[0]['id'] for t in tasks}
        for count, fut in enumerate(as_completed(pending), 1):
            records = fut.result()
            for r in records: results['train' if r['split']=='train' else 'heldout'].append(r)
            if count % 10 == 0 or count == len(tasks): print(f'{count}/{len(tasks)} prepared', flush=True)
    for records in results.values(): records.sort(key=lambda r: r['flight_id'])
    manifest = {'status': 'completed', 'input_policy': 'kf_grid_native', 'sensor_config': sensor, 'datasets': results,
                'source_config_sha256': digest(resolve(a.config)), 'roster_sha256': digest(roster_path),
                'sources': {name: digest(ROOT/name) for name in ('server_training/prepare.py', 'odometry_pool.py', 'input_attitude.py', 'attitude_bias.py', 'common.py', 'streaming.py')}}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('completed', output/'manifest.json', flush=True)


if __name__ == '__main__': main()
