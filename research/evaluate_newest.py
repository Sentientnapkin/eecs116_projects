"""Official actual-Wasm evaluation of newest-model artifacts; public/campaign DEV only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import numpy as np
import wasm_eval as we

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("build", type=Path); p.add_argument("--out", type=Path, required=True)
p.add_argument("--set", choices=("public", "campaign-dev"), default="public")
p.add_argument("--workers", type=int, default=16)
a = p.parse_args(); a.out = a.out.resolve(); wasm = (a.build / "odometry.wasm").resolve()
pin = subprocess.check_output(["git", "-C", str(we.SRC), "rev-parse", "HEAD"], text=True).strip()
assert pin == "9b1b07906aff5a3e6f00155e7aecf967d90aa960"
if a.set == "public":
    archives = sorted(Path('/data/backups/rganapa/Sebastian/tmp/viobench-public-replay').glob('*/*.zip'))
    assert len(archives) == 10
else:
    archives = sorted(Path('/data/backups/rganapa/Sebastian/gen/raw/dev').glob('*.zip'))
    archives += sorted(Path('/data/backups/rganapa/Sebastian/baselines/campaign-dev-crop5').glob('*.zip'))
    assert len(archives) == 120 and all(p.stem.startswith('dev-') for p in archives)
guest = {'wasm': str(wasm), 'sha256': we.sha256(wasm), 'evaluator_commit': pin,
         'archives': list(map(str, archives)), 'archive_sha256': {str(p): we.sha256(p) for p in archives},
         'input_policy': 'kf_grid_native', 'seed': json.loads((a.build/'artifact.json').read_text())['seed'],
         'backend': 'actual metered Wasm', 'set': a.set}
if a.out.exists():
    assert json.loads((a.out / 'guest.json').read_text()) == guest, 'Existing replay has different artifact/input identity'
else:
    a.out.mkdir(parents=True)
    (a.out / 'guest.json').write_text(json.dumps(guest, indent=2) + '\n')
with ThreadPoolExecutor(a.workers) as pool:
    for result in pool.map(lambda archive: we.run_one(wasm, archive, a.out), archives):
        print(result, result.exists(), flush=True)
rows = [we.score_one(archive, a.out / archive.stem) for archive in archives]
(a.out / 'scores.json').write_text(json.dumps({'guest': guest, 'rows': rows}, indent=2) + '\n')
assert all('ate_full' in r for r in rows), 'Missing results preserved, never excluded from mean'
summary = {'guest': guest, 'rows': rows, 'episodes': len(rows), 'completed': sum(r['completed'] for r in rows),
           'frames': sum(r['frames'] for r in rows), 'filled_frames': sum(r['filled_full'] for r in rows),
           'mean_unaligned_ate_m': float(np.mean([r['ate_full'] for r in rows])),
           'peak_whole_guest_fuel_per_frame': max(r['peak_fuel_per_frame'] for r in rows)}
assert we.sha256(wasm) == guest['sha256']
(a.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({k: v for k, v in summary.items() if k not in ('guest', 'rows')}, indent=2), flush=True)
