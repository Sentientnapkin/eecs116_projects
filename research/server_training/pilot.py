"""Matched local warm-start control/treatment, seeds 217/218/219; no Hub writes.

python -m server_training.pilot --config configs/server_train_pool.json --launch
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from .prepare import ROOT, resolve, digest


def link_shard(destination, source, record):
    dest = destination/record['file']
    src = source/record['file']
    if not src.exists(): raise FileNotFoundError(src)
    if not dest.exists(): dest.symlink_to(src.resolve())
    elif dest.resolve() != src.resolve(): raise ValueError(f'shard path collision: {dest}')


def compose(config, output):
    source = resolve(config['baseline_manifest']); baseline = json.loads(source.read_text())
    server_root = resolve(config['output']); server_path = server_root/'manifest.json'; server = json.loads(server_path.read_text())
    if server['status'] != 'completed' or server['input_policy'] != baseline['input_policy']: raise ValueError('incomplete or incompatible input policies')
    # Clean ProcTHOR plus all campaign nontrain scenes are excluded from TRAIN.
    campaign = json.loads(resolve(config['campaign_roster']).read_text())['flights']
    denied = {r['scene'] for r in campaign if r['split'] != 'train'}
    for records in (baseline['datasets']['train'], server['datasets']['train']):
        for r in records:
            if r['scene'] in denied: raise ValueError(f'reserved/dev training scene: {r["scene"]}')
            if r['scene'].startswith('ProcTHOR-Train-') and 150 <= int(r['scene'].rsplit('-', 1)[1]) <= 179:
                raise ValueError(f'clean/reserved training scene: {r["scene"]}')
    dirs = {}
    for arm in ('control', 'treatment'):
        path = output/'datasets'/arm; path.mkdir(parents=True, exist_ok=True)
        groups = {'train': [], 'development': baseline['datasets']['development']}
        for split in groups:
            if split == 'train':
                for record in baseline['datasets']['train']:
                    groups['train'].append({**record, 'original_domain': record.get('domain'), 'domain': 'baseline'})
            for record in groups[split]: link_shard(path, source.parent, record)
        if arm == 'treatment':
            for record in server['datasets']['train']:
                groups['train'].append({**record, 'domain': 'server-t0'})
                link_shard(path, server_root, record)
        manifest = {**baseline, 'datasets': groups, 'server_pilot': {'arm': arm, 'baseline_manifest_sha256': digest(source),
                    'server_manifest_sha256': digest(server_path), 'training_scene_policy': 'no dev/clean/reserved',
                    'heldout_flights': [r['flight_id'] for r in server['datasets']['heldout']]}}
        payload = json.dumps(manifest, indent=2)+'\n'; target = path/'manifest.json'
        if target.exists() and target.read_text() != payload: raise ValueError('immutable composed manifest changed')
        target.write_text(payload); dirs[arm] = path
    return dirs


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--config', default='configs/server_train_pool.json')
    p.add_argument('--output', default='data/server-training/pilot12'); p.add_argument('--launch', action='store_true'); p.add_argument('--gpus', nargs=6, type=int, default=[1, 2, 3, 4, 5, 6])
    a = p.parse_args(); cfg = json.loads(resolve(a.config).read_text()); output = resolve(a.output); output.mkdir(parents=True, exist_ok=True)
    dirs = compose(cfg, output); runs = resolve(cfg['baseline_runs']); commands = []
    for index, (arm, seed) in enumerate((arm, seed) for arm in ('control', 'treatment') for seed in cfg['training']['seeds']):
        original = runs/('RA-N2-kfgrid-x3'+(f'-s{seed}' if seed != 217 else '')+'-codexfinish')
        train_cfg = json.loads((original/'config.json').read_text())
        train_cfg['training']['epochs'] = cfg['training']['epochs']
        train_cfg['training']['sampler']['windows_per_epoch'] = cfg['training']['windows_per_epoch']
        train_cfg['training']['preload'] = True
        # Each arm sees the same 122 optimizer updates per epoch and restarts the same LR schedule.
        if arm == 'treatment': train_cfg['training']['sampler']['domain_share'] = {'baseline': .5, 'server-t0': .5}
        else: train_cfg['training']['sampler'].pop('domain_share', None)
        config_path = output/f'{arm}-s{seed}.json'; config_path.write_text(json.dumps(train_cfg, indent=2)+'\n')
        run = output/'runs'/f'{arm}-s{seed}'
        cmd = [sys.executable, '-u', str(ROOT/'odometry_train.py'), '--config', str(config_path), '--data', str(dirs[arm]),
               '--output', str(run), '--init-weights', str(original/'best.safetensors')]
        if run.exists():
            complete = sorted(run.glob('checkpoints/epoch-*/complete.json'))
            if complete:
                if json.loads((run/'manifest.json').read_text()).get('status') == 'completed': continue
                cmd += ['--resume', str(complete[-1].parent)]
            else:
                raise ValueError(f'existing run without complete checkpoint: preserve and choose new --output ({run})')
        commands.append({'arm': arm, 'seed': seed, 'gpu': a.gpus[index], 'command': cmd,
                         'initial_weights_sha256': digest(original/'best.safetensors'), 'run': str(run)})
    declaration = {'declared_at': datetime.now(timezone.utc).isoformat(), 'gate': cfg['training']['gate'],
                   'epochs': cfg['training']['epochs'], 'checkpoint': 'final epoch, fixed in advance',
                   'heldout': 'selected171 clean+dev: no checkpoint selection or tuning', 'commands': commands,
                   'config_sha256': digest(resolve(a.config)), 'remote_writes': False}
    declaration_path = output/'declaration.json'
    if not declaration_path.exists(): declaration_path.write_text(json.dumps(declaration, indent=2)+'\n')
    launched = []
    for index, entry in enumerate(commands):
        print(' '.join(entry['command']), flush=True)
        if a.launch:
            env = {**os.environ, 'CUDA_VISIBLE_DEVICES': str(entry['gpu']), 'OMP_NUM_THREADS': '4', 'OPENBLAS_NUM_THREADS': '1',
                   'HF_HUB_OFFLINE': '1', 'TORCHINDUCTOR_CACHE_DIR': str(output/f"compile-{entry['arm']}-{entry['seed']}")}
            log = output/f"{entry['arm']}-s{entry['seed']}.log"
            allowed = sorted(os.sched_getaffinity(0))
            cpu_set = set(allowed[-24:][index*4:(index+1)*4])
            with log.open('a') as handle:
                proc = subprocess.Popen(entry['command'], cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=lambda: os.sched_setaffinity(0, cpu_set))
            launched.append({**entry, 'pid': proc.pid, 'log': str(log)})
    if launched: (output/'processes.json').write_text(json.dumps(launched, indent=2)+'\n')


if __name__ == '__main__': main()
