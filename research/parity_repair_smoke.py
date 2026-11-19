"""Predeclared paired N2-218 PUBLIC port repair; diagnostic, not model selection.

Historical 353243f controls are retained. Repairs align recoverPose's input mask
and visual-direction acceptance with the frozen Python reference. Run both
corrected control and corrected fusion over exactly the ten public archives;
measure actual guest and compare the attitude/accepted windows separately.
Only advance three-seed replay after this smoke establishes useful parity.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess

import wasm_eval as we
from finish_fusion import ROOT, MAIN, OUT, TEACHER, SDK, CV


def main():
    archives = sorted(Path('/data/backups/rganapa/Sebastian/tmp/viobench-public-replay').glob('*/*.zip'))
    assert len(archives) == 10
    (OUT / 'parity-repair-predeclared.json').write_text(json.dumps({
        'seed': 218, 'population': 'public', 'archives': list(map(str, archives)),
        'interventions': ['recoverPose RANSAC input mask', 'direction requires accepted rotation'],
        'decision': 'Diagnostic parity repair only; no revised accuracy guardrails.',
    }, indent=2))
    jobs, groups = [], []
    for arm in ('kf_grid', 'knownrot_a_replace'):
        build = OUT / 'artifacts' / f'n2-218-{arm}-parity-repair-trace'
        env = os.environ.copy()
        env['ODO_WASM_EXTRA_FLAGS'] = '-DODO_KFG_RECOVER_RANSAC_MASK -DODO_KF_GRID_TRACE'
        if arm != 'kf_grid':
            env['ODO_WASM_EXTRA_FLAGS'] += ' -DODO_VEL_FUSION -DODO_FUSION_REQUIRE_ACCEPTED_ROTATION'
        env['CUDA_VISIBLE_DEVICES'] = ''
        subprocess.run([TEACHER, str(ROOT / 'native_odometry/export.py'),
            str(MAIN / 'results/loop/N2-ssm-x3-s218-gpu'),
            str(MAIN / 'data/hub-cache/B-D0-ssm-x3-gpu/manifests/teacher-full.json'),
            str(build), '--wasi-sdk', str(SDK), '--kf-grid-opencv', str(CV)], env=env, check=True)
        wasm = build / 'odometry.wasm'
        out = OUT / f'public-n2-218-{arm}-parity-repair-trace'
        out.mkdir(parents=True, exist_ok=True)
        guest = {'wasm': str(wasm), 'sha256': we.sha256(wasm), 'evaluator_src': str(we.SRC),
                 'archives': list(map(str, archives)), 'flags': env['ODO_WASM_EXTRA_FLAGS']}
        if (out / 'guest.json').exists():
            previous = json.loads((out / 'guest.json').read_text())
            if previous['sha256'] != guest['sha256'] or previous['archives'] != guest['archives']:
                raise RuntimeError('Existing results have a different guest or roster; use a new named output.')
        (out / 'guest.json').write_text(json.dumps(guest, indent=2))
        groups.append((out, guest))
        jobs.extend((wasm, archive, out) for archive in archives)
    with concurrent.futures.ThreadPoolExecutor(20) as pool:
        for result in pool.map(lambda j: we.run_one(*j), jobs):
            print(result, result.exists(), flush=True)
    for out, guest in groups:
        rows = [we.score_one(a, out / Path(a).stem) for a in guest['archives']]
        (ROOT / 'results/eval/fusion-completion' / (out.name + '.json')).write_text(
            json.dumps({'guest': guest, 'rows': rows}, indent=1))
        print(out.name, sum(r['ate_full'] for r in rows)/len(rows), flush=True)


if __name__ == '__main__':
    main()
