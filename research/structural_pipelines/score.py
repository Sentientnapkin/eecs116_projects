"""Score the prepared four-guest suite on an explicitly supplied dataset, with content-addressed provenance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
RESEARCH=HERE.parent
PIN='9b1b07906aff5a3e6f00155e7aecf967d90aa960'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''): h.update(block)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite',type=Path,default=RESEARCH/'results/eval/structural-pipelines/ready.json')
    p.add_argument('--episodes',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--workers',type=int,default=8)
    p.add_argument('--evaluator',type=Path,default=Path('/dev/shm/sebastian-vio/viobench'))
    a=p.parse_args()
    if a.workers<1: p.error('--workers must be positive')
    ready=json.loads(a.suite.read_text())
    if not ready['status'].startswith('ready for experimental'): raise SystemExit('Suite is not ready')
    pin=subprocess.check_output(['git','-C',str(a.evaluator),'rev-parse','HEAD'],text=True).strip()
    if pin!=PIN: raise SystemExit(f'Evaluator pin mismatch: {pin}')
    # A dirty evaluator changes semantics even with the right commit.
    if subprocess.check_output(['git','-C',str(a.evaluator),'status','--porcelain','--untracked-files=no'],text=True).strip():
        raise SystemExit('Evaluator has tracked changes; use the clean pinned checkout')
    episodes=sorted(a.episodes.glob('*.zip')) if a.episodes.is_dir() else [a.episodes]
    if not episodes or any(not f.is_file() or f.suffix!='.zip' for f in episodes): raise SystemExit('No episode ZIP archives found')
    guests={}
    for name,record in ready['variants'].items():
        file=Path(record['wasm'])
        if sha(file)!=record['sha256']: raise SystemExit(f'Guest hash mismatch: {name}')
        guests['struct_'+name]={'path':str(file),'sha256':record['sha256']}
    identity={'evaluator_commit':PIN,'guests':guests,
              'episodes':{str(f.resolve()):sha(f) for f in episodes}}
    identity_path=a.out/'scoring-inputs.json'
    if a.out.exists():
        if not identity_path.exists() or json.loads(identity_path.read_text())!=identity:
            raise SystemExit('Output directory has unknown or different inputs; choose a fresh --out')
    else:
        a.out.mkdir(parents=True)
        identity_path.write_text(json.dumps(identity,indent=2)+'\n')
    command=['/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python',str(RESEARCH/'bench_eval.py')]
    for name,record in guests.items(): command+=['--guest',f'{name}={record["path"]}']
    command+=['--episodes',str(a.episodes.resolve()),'--out',str(a.out.resolve()),'--workers',str(a.workers)]
    env={**os.environ,'PYTHONPATH':str(a.evaluator.resolve()),'TMPDIR':os.environ.get('TMPDIR','/dev/shm/sebastian-vio/tmp')}
    subprocess.run(command,env=env,check=True)

if __name__=='__main__': main()
