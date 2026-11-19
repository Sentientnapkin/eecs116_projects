"""Finish the declared N2 visual-direction port against per-seed kf_grid controls.

Uses public and campaign DEV archives only. Existing s218 control is reused only
when its artifact hash and full archive roster match. No selection thresholds change.
"""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import wasm_eval as we

ROOT = Path(__file__).resolve().parent
MAIN = Path('/data/backups/rganapa/Sebastian/eecs116_projects/research')
BASE = Path('/data/backups/rganapa/Sebastian/baselines')
OUT = ROOT / 'results/loop/fusion-completion'
TEACHER = '/data/backups/rganapa/Sebastian/venv-teacher/bin/python'
SDK = Path('/dev/shm/sebastian-vio/viobench/viobench/solution/build/toolchain/wasi-sdk')
CV = SDK.parent.parent / 'runtime/opencv-build'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rosters = {
        'public': sorted(Path('/data/backups/rganapa/Sebastian/tmp/viobench-public-replay').glob('*/*.zip')),
        'campaign': sorted(Path('/data/backups/rganapa/Sebastian/gen/raw/dev').glob('*.zip'))
                    + sorted((BASE / 'campaign-dev-crop5').glob('*.zip')),
    }
    assert len(rosters['public']) == 10 and len(rosters['campaign']) == 120
    (OUT / 'predeclared-completion.json').write_text(json.dumps({
        'seeds': [217, 218, 219], 'arms': ['kf_grid', 'knownrot_a_replace'],
        'rule': 'Complete existing port; unchanged original/proxy gates remain required for qualification.',
        'rosters': {k: list(map(str, v)) for k, v in rosters.items()},
    }, indent=2))
    jobs, groups, artifacts = [], [], {}
    for seed in (217, 218, 219):
        run = MAIN / 'results/loop' / ('N2-ssm-x3-gpu' if seed == 217 else f'N2-ssm-x3-s{seed}-gpu')
        manifest = MAIN / 'data/hub-cache/B-D0-ssm-x3-gpu/manifests/teacher-full.json'
        for arm in ('kf_grid', 'knownrot_a_replace'):
            name = f'n2-{seed}-{arm}'
            build = OUT / 'artifacts' / name
            env = os.environ.copy()
            env['ODO_WASM_EXTRA_FLAGS'] = '-DODO_VEL_FUSION' if arm == 'knownrot_a_replace' else ''
            env['CUDA_VISIBLE_DEVICES'] = ''
            if not (build / 'odometry.wasm').exists():
                subprocess.run([TEACHER, str(ROOT / 'native_odometry/export.py'), str(run), str(manifest),
                                str(build), '--wasi-sdk', str(SDK), '--kf-grid-opencv', str(CV)],
                               env=env, check=True)
            wasm = build / 'odometry.wasm'
            artifacts[name] = {'wasm_sha256': we.sha256(wasm),
                               'checkpoint_sha256': we.sha256(run / 'best.safetensors'),
                               'kernel': 'simd-4x16', 'flags': env['ODO_WASM_EXTRA_FLAGS']}
            for population, archives in rosters.items():
                out = OUT / f'{population}-{name}'
                if seed == 218 and arm == 'kf_grid':
                    old = BASE / 'runs' / f'{population}-n2-218-ungated'
                    if (old / 'guest.json').exists():
                        guest = json.loads((old / 'guest.json').read_text())
                        if guest['sha256'] == we.sha256(wasm) and set(guest['archives']) == set(map(str, archives)):
                            out = old
                out.mkdir(parents=True, exist_ok=True)
                if not (out / 'guest.json').exists():
                    (out / 'guest.json').write_text(json.dumps({'wasm': str(wasm), 'sha256': we.sha256(wasm),
                        'evaluator_src': str(we.SRC), 'archives': list(map(str, archives))}, indent=2))
                groups.append((name, population, out))
                jobs.extend((wasm, archive, out) for archive in archives
                            if not (out / archive.stem / 'report/report.json').exists())
    (OUT / 'artifacts.json').write_text(json.dumps(artifacts, indent=2))
    print(f'Built six matched guests; {len(jobs)} new replays', flush=True)
    with concurrent.futures.ThreadPoolExecutor(48) as pool:
        for i, result in enumerate(pool.map(lambda j: we.run_one(*j), jobs), 1):
            print(i, str(result), result.exists(), flush=True)
    for name, population, out in groups:
        guest = json.loads((out / 'guest.json').read_text())
        rows = [we.score_one(a, out / Path(a).stem) for a in guest['archives']]
        target = ROOT / 'results/eval/fusion-completion' / f'{population}-{name}.json'
        target.write_text(json.dumps({'guest': guest, 'rows': rows}, indent=1))
        print(name, population, len(rows), sum(r.get('ate_full', 0) for r in rows)/len(rows), flush=True)


if __name__ == '__main__':
    main()
