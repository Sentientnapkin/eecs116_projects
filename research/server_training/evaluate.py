"""Evaluate fixed final-epoch pilot EMA and frozen N2 on untouched clean+dev.

python -m server_training.evaluate --pilot data/server-training/pilot12 --seed 217
Run independently per seed/GPU, then --summarize to combine all three seeds.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import numpy as np
from .prepare import ROOT, resolve, digest
sys.path.insert(0, str(ROOT))


def final_ema(run, epoch):
    import torch
    path = run/'checkpoints'/f'epoch-{epoch:04d}'
    if not (path/'complete.json').exists(): raise ValueError(f'final checkpoint incomplete: {path}')
    cfg = json.loads((run/'config.json').read_text())
    if cfg['training'].get('weight_ema'):
        state = torch.load(path/'custom_checkpoint_1.pkl', map_location='cpu', weights_only=False)
        return {k[len('module.'):]: v for k, v in state.items() if k.startswith('module.')}
    return torch.load(path/'pytorch_model.bin', map_location='cpu', weights_only=True)


def evaluate_seed(config, pilot, seed, batch_size):
    os.environ.setdefault("TORCHINDUCTOR_CACHE_DIR", str(pilot/f"compile-eval-s{seed}"))
    os.environ.setdefault("TMPDIR", str(pilot))
    import torch
    from safetensors.torch import load_file
    from odometry_data import load_row
    from odometry_eval import replay_model, batched_velocities, integrate, metrics
    torch.set_num_threads(4); torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    data = resolve(config['output']); manifest = json.loads((data/'manifest.json').read_text())
    recs = manifest['datasets']['heldout']; original = resolve(config['baseline_runs'])/('RA-N2-kfgrid-x3'+(f'-s{seed}' if seed != 217 else '')+'-codexfinish')
    runs = {'n2': original, 'control': pilot/'runs'/f'control-s{seed}', 'treatment': pilot/'runs'/f'treatment-s{seed}'}
    for name, run in runs.items():
        if name != 'n2' and json.loads((run/'manifest.json').read_text()).get('status') != 'completed': raise ValueError(f'pilot run not completed: {run}')
    target = pilot/f'heldout-s{seed}.json'
    if target.exists(): raise ValueError('heldout already evaluated; preserve the single final pass')
    result = {'seed': seed, 'checkpoint_policy': 'fixed final epoch EMA', 'input_policy': 'kf_grid_native',
              'heldout_manifest_sha256': digest(data/'manifest.json'), 'rows': [], 'weights': {}}
    nets = {}
    for name, run in runs.items():
        weights = load_file(str(run/'best.safetensors')) if name == 'n2' else final_ema(run, config['training']['epochs'])
        nets[name] = replay_model(run, weights, 'cuda')
        result['weights'][name] = {'run': str(run), 'source': 'frozen best' if name == 'n2' else f"fixed epoch {config['training']['epochs']} EMA"}
    for first in range(0, len(recs), batch_size):
        records = recs[first:first+batch_size]
        with ThreadPoolExecutor(min(4, batch_size)) as pool: rows = list(pool.map(lambda r: load_row(data, r), records))
        for name, net in nets.items():
            velocities = batched_velocities(net, rows, 'cuda')
            for r, row, v in zip(records, rows, velocities):
                score = metrics(integrate(v, row), row['cam_gt'], row['times'], v, row['v'])
                result['rows'].append({**r, 'arm': name, 'seed': seed, **score})
        print(f"seed{seed} {min(first+batch_size,len(recs))}/{len(recs)} evaluated", flush=True)
    result['summary'] = {name: {'mean_unaligned_ate_m': float(np.mean([r['ate'] for r in result['rows'] if r['arm']==name])),
                                'median_unaligned_ate_m': float(np.median([r['ate'] for r in result['rows'] if r['arm']==name]))} for name in runs}
    target.write_text(json.dumps(result, indent=2)+'\n'); print(json.dumps(result['summary']), flush=True)
    return result


def summarize(config, pilot):
    from campaign.report import distribution, paired_scene_bootstrap
    results = [json.loads((pilot/f'heldout-s{seed}.json').read_text()) for seed in config['training']['seeds']]
    summary = {'seeds': config['training']['seeds'], 'slice': 'selected171 clean+dev 70 flights', 'metric': 'mean_unaligned_ate_m', 'per_seed': {str(d['seed']): d['summary'] for d in results}}
    means = {arm: np.mean([r['summary'][arm]['mean_unaligned_ate_m'] for r in results]) for arm in ('n2','control','treatment')}
    summary['three_seed_mean_m'] = {k: float(v) for k,v in means.items()}
    summary['mean_of_three_seed_medians_m'] = {arm: float(np.mean([r['summary'][arm]['median_unaligned_ate_m'] for r in results])) for arm in ('n2', 'control', 'treatment')}
    summary['splits_per_seed'] = {}
    for result in results:
        splits = {}
        for tag in ('group', 'catalog', 'start_type'):
            splits[tag] = {}
            for label in sorted({r[tag] for r in result['rows']}):
                splits[tag][label] = {}
                for arm in ('n2', 'control', 'treatment'):
                    vals = [r['ate'] for r in result['rows'] if r[tag]==label and r['arm']==arm]
                    splits[tag][label][arm] = {'n': len(vals), 'mean_unaligned_ate_m': float(np.mean(vals)), 'median_unaligned_ate_m': float(np.median(vals))}
        summary['splits_per_seed'][str(result['seed'])] = splits
    summary['relative_improvement_vs_n2'] = float(1-means['treatment']/means['n2'])
    summary['relative_improvement_vs_control'] = float(1-means['treatment']/means['control'])
    per_seed = all(r['summary']['treatment']['mean_unaligned_ate_m'] < r['summary']['n2']['mean_unaligned_ate_m'] for r in results)
    dev_guards = []
    for seed in config['training']['seeds']:
        treatment = json.loads((pilot/'runs'/f'treatment-s{seed}'/'metrics.json').read_text())[-1]
        original = resolve(config['baseline_runs'])/('RA-N2-kfgrid-x3'+(f'-s{seed}' if seed != 217 else '')+'-codexfinish')
        # The frozen deployed checkpoint is selected by original dev, so its best score is
        # the comparison; treatment final checkpoint must remain within the declared5%.
        old = min(r['selection_score'] for r in json.loads((original/'metrics.json').read_text()))
        dev_guards.append({'seed': seed, 'frozen_n2_original_dev_m': old, 'treatment_final_original_dev_m': treatment['selection_score'], 'pass': treatment['selection_score'] <= 1.05*old})
    summary['original_dev_guards'] = dev_guards
    summary['gate_pass'] = bool(summary['relative_improvement_vs_n2'] >= .1 and per_seed and all(r['pass'] for r in dev_guards))
    summary['every_seed_improves'] = per_seed
    pooled = []
    for d in results:
        for r in d['rows']: pooled.append({**r, 'ate_full': r['ate'], 'episode': r['flight_id'], 'catalog': r['catalog'], 'scene': r['scene']})
    summary['paired_scene_bootstrap'] = {}
    # Bootstrap each seed's scene-paired treatment delta separately, preserving all flights;
    # three-seed mean above accounts for training variability without pretending 210 independent flights.
    for seed in config['training']['seeds']:
        subset = [r for r in pooled if r['seed']==seed]
        summary['paired_scene_bootstrap'][str(seed)] = paired_scene_bootstrap([r for r in subset if r['arm']=='treatment'], [r for r in subset if r['arm']=='n2'])
    (pilot/'heldout-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--config', default='configs/server_train_pool.json'); p.add_argument('--pilot', default='data/server-training/pilot12')
    p.add_argument('--seed', type=int, choices=(217,218,219), default=217); p.add_argument('--batch-size', type=int, default=8); p.add_argument('--summarize', action='store_true')
    a = p.parse_args(); cfg = json.loads(resolve(a.config).read_text()); pilot = resolve(a.pilot)
    if a.summarize: summarize(cfg, pilot)
    else: evaluate_seed(cfg, pilot, a.seed, a.batch_size)


if __name__ == '__main__': main()
