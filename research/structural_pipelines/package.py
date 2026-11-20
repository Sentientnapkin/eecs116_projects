"""Run ABI checks and package an already validated structural suite; never score or enqueue."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
RESEARCH=HERE.parent

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('build',type=Path); a=p.parse_args(); build=a.build.resolve()
    meta=json.loads((build/'build.json').read_text()); validation=json.loads((build/'validation.json').read_text())
    geometry=json.loads((build/'geometry.json').read_text())
    if not geometry['passed'] or 'passed' not in validation['status']: raise SystemExit('Validation incomplete')
    for name,record in meta['variants'].items():
        if validation['guest_sha256'][name]!=record['sha256']: raise SystemExit(f'Validation hash mismatch: {name}')
        if validation['checks'][name]['native_wasm_max_component_delta']>.002: raise SystemExit('Synthetic parity tolerance failed')
        if sha(record['wasm'])!=record['sha256']: raise SystemExit(f'Changed guest: {name}')
    def check(item):
        name,record=item
        command=['/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python','-m','viobench','check',record['wasm']]
        result=subprocess.run(command,text=True,capture_output=True,env={**os.environ,'PYTHONPATH':'/dev/shm/sebastian-vio/viobench'})
        (build/name/'abi-check.log').write_text(result.stdout+result.stderr)
        if result.returncode: raise RuntimeError(f'{name}: ABI check failed; see abi-check.log')
        print(name,'official ABI passed',flush=True)
        return name,{'passed':True,'command':command,'log_sha256':sha(build/name/'abi-check.log')}
    with ThreadPoolExecutor(4) as pool: abi=dict(pool.map(check,meta['variants'].items()))
    tools=build/'pipeline-tools'; tools.mkdir(exist_ok=True)
    for file in HERE.iterdir():
        if file.is_file() and file.suffix in ('.py','.cpp','.hpp','.md'): shutil.copy2(file,tools/file.name)
    # Copy small reviewable metadata, keep binaries and source snapshot in ignored artifact storage.
    ready={'status':'ready for experimental dataset scoring; no dataset scores produced',
           'build_directory':str(build),'pipeline_tools_sha256':{f.name:sha(f) for f in tools.iterdir()},'variants':meta['variants'],'abi':abi,'geometry':geometry,'synthetic':validation,
           'source_sha256':meta['source_sha256'],'canonical_archive_sha256':meta['canonical_archive_sha256'],
           'scoring_command':f'EPISODES=/path/to/episodes SCORES=/path/to/new-results bash {build}/score.sh',
           'limitations':['Base visual backend long parity remains unresolved; control is byte-identical to frozen seed217.',
                          'New modules change integration only, not learned inputs.',
                          'Manhattan assumes one persistent orthogonal room frame; rotated rooms may reject updates.',
                          'Gravity is qualified from observed near-1g low-rotation windows, not known ground truth.',
                          'No whole-dataset accuracy or peak fuel claim; no submission qualification.']}
    (build/'ready.json').write_text(json.dumps(ready,indent=2)+'\n')
    dest=RESEARCH/'results/eval/structural-pipelines'; dest.mkdir(parents=True,exist_ok=True)
    shutil.copy2(build/'ready.json',dest/'ready.json')
    print('Ready index:',dest/'ready.json',flush=True)

if __name__=='__main__': main()
