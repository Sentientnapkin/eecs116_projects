"""Build the three pre-existing newest-model checkpoints; canonical seed217, no seed selection."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--out', type=Path, default=Path('results/loop/new-model-wasm'))
p.add_argument('--seeds', nargs='+', type=int, default=[217, 218, 219])
a = p.parse_args()
root = Path(__file__).resolve().parent
training = root.parent.parent / 'training-finish/research'
report = json.loads((training / 'results/eval/training-finish/kf_grid_native.json').read_text())
manifest = Path(report['datasets']['dev']['manifest'])
assert json.loads(manifest.read_text())['input_policy'] == 'kf_grid_native'
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
sdk = '/dev/shm/sebastian-vio/viobench/viobench/solution/build/toolchain/wasi-sdk'
entries = {}
for seed in a.seeds:
    assert seed in (217, 218, 219)
    record = report['weights'][str(seed)]; run = Path(record['run'])
    assert digest(run / 'best.safetensors') == record['sha256']
    out = a.out.resolve() / f'seed{seed}-opencv510'
    command = ['/data/backups/rganapa/Sebastian/venv-teacher/bin/python', '-B',
               str(root / 'native_odometry/export.py'), str(run), str(manifest), str(out),
               '--wasi-sdk', sdk, '--wasm-kernel', 'simd-8x32-k2', '--input-kf-grid',
               '--kf-grid-opencv', '/dev/shm/sebastian-vio/new-model-opencv510-wasm',
               '--native-opencv', '/dev/shm/sebastian-vio/new-model-opencv510-native']
    source = {str(p.relative_to(root)): digest(p) for p in (root / 'native_odometry').glob('*') if p.suffix in ('.hpp', '.cpp', '.py')}
    if out.exists():
        if not (out / 'artifact.json').exists():
            raise RuntimeError(f'Unidentified/incomplete existing build {out}; preserve it and choose a new --out')
        previous = json.loads((out / 'artifact.json').read_text())
        if previous['source_sha256'] != source or previous['checkpoint_sha256'] != record['sha256']:
            raise RuntimeError(f'Build identity changed for {out}; use a new output directory')
        assert digest(out/'odometry.wasm') == previous['wasm_sha256']
        assert digest(out/'host.so') == previous['host_sha256']
        assert digest(out/'weights.f32') == previous['weights_sha256']
        entries[str(seed)] = previous
        print(seed, previous['wasm_sha256'], 'verified existing build', flush=True)
        continue
    subprocess.run(command, env={**os.environ, 'CUDA_VISIBLE_DEVICES': ''}, check=True)
    assert b'input_features' in (out / 'odometry.wasm').read_bytes(), 'Not the full changed-input guest'
    entry = {'seed': seed, 'canonical': seed == 217, 'run': str(run), 'checkpoint_sha256': record['sha256'],
             'input_policy': 'kf_grid_native', 'manifest': str(manifest), 'manifest_sha256': digest(manifest),
             'wasm': str(out / 'odometry.wasm'), 'wasm_sha256': digest(out / 'odometry.wasm'),
             'weights_sha256': digest(out / 'weights.f32'), 'host_sha256': digest(out / 'host.so'),
             'source_sha256': source, 'command': command, 'opencv_version': '5.1.0',
             'opencv_source_commit': 'e4f78fbcf1a773fbed69e14500e8b734963eb585',
             'wasm_kernel': 'simd-8x32-k2', 'timing': 'first camera origin; original absolute sensor delivery'}
    (out / 'artifact.json').write_text(json.dumps(entry, indent=2) + '\n')
    entries[str(seed)] = entry
    print(seed, entry['wasm_sha256'], flush=True)
a.out.mkdir(parents=True, exist_ok=True)
(a.out / ('artifacts-' + '-'.join(map(str, a.seeds)) + '.json')).write_text(json.dumps(entries, indent=2) + '\n')
