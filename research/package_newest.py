"""Package already-built newest-model Wasm files; no submission or model selection."""
import hashlib
import json
from pathlib import Path
import shutil

root = Path(__file__).resolve().parent
base = root / 'results/loop/new-model-wasm'
out = base / 'package';out.mkdir(exist_ok=False)
entries = {}
for seed in (217, 218, 219):
    build = base / f'isolated-grid/seed{seed}-opencv510'
    meta = json.loads((build / 'artifact.json').read_text())
    assert 'check: ok (5 steps)' in (base / f'seed{seed}-abi-check.log').read_text()
    name = f'vio_n2_kfinputs_s{seed}.wasm'
    target = out / name;shutil.copyfile(build / 'odometry.wasm', target)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == meta['wasm_sha256']
    entries[str(seed)] = {**meta, 'file':name, 'bytes':target.stat().st_size,
                          'abi_check':'5 steps passed', 'status':'experimental; strict backend parity not established'}
public = json.loads((base / 'public-seed217-opencv510-isolated/summary.json').read_text())
campaign = json.loads((base / 'campaign-seed217-opencv510-isolated/summary.json').read_text())
manifest = {'model_family':'RA-N2-kfgrid-x3 (36-epoch best EMA checkpoints)', 'canonical_seed':217,
            'entries':entries, 'canonical_measured_results':{name:{k:v for k,v in d.items() if k not in ('rows','guest')}
             for name,d in [('public',public),('campaign_dev',campaign)]},
            'qualification':'Created and benchmarked, but strict Python/native/Wasm parity remains unresolved; not submitted',
            'inference':'C++17 FP32 CNN/correlation/SSM plus complete causal kf_grid_native input preprocessing; no Python or truth inputs',
            'opencv_source_commit':'e4f78fbcf1a773fbed69e14500e8b734963eb585',
            'evaluator_commit':'9b1b07906aff5a3e6f00155e7aecf967d90aa960'}
(out / 'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(out / 'SHA256SUMS').write_text(''.join(f"{entries[str(s)]['wasm_sha256']}  {entries[str(s)]['file']}\n" for s in (217,218,219)))
print(json.dumps({'directory':str(out),'files':{s:{k:v for k,v in e.items() if k in ('file','bytes','wasm_sha256')} for s,e in entries.items()}},indent=2))
