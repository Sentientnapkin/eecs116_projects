"""Run local T0 prep, matched 3-seed pilot, then one final heldout pass.

No uploads. Logs and checkpoints remain resumable under data/server-training.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from .prepare import ROOT, resolve


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default='configs/server_train_pool.json')
    p.add_argument('--pilot',default='data/server-training/pilot12');p.add_argument('--wait-existing-preparation',action='store_true')
    a=p.parse_args();cfg=json.loads(resolve(a.config).read_text());data=resolve(cfg['output']);pilot=resolve(a.pilot)
    env={**os.environ,'OMP_NUM_THREADS':'4','OPENBLAS_NUM_THREADS':'1','HF_HUB_OFFLINE':'1'}
    if a.wait_existing_preparation:
        start=time.monotonic()
        while not (data/'manifest.json').exists():
            if time.monotonic()-start>3600:raise TimeoutError('preparation did not finish in1h')
            time.sleep(10)
    else:subprocess.run([sys.executable,'-u','-m','server_training.prepare','--config',a.config],cwd=ROOT,env=env,check=True)
    subprocess.run([sys.executable,'-u','-m','server_training.pilot','--config',a.config,'--output',a.pilot,'--launch'],cwd=ROOT,env=env,check=True)
    processes=json.loads((pilot/'processes.json').read_text())
    started=time.monotonic()
    while True:
        ready=True
        for r in processes:
            manifest=Path(r['run'])/'manifest.json'
            status=json.loads(manifest.read_text()).get('status') if manifest.exists() else 'starting'
            if status=='completed':continue
            ready=False
            state_path=Path('/proc')/str(r['pid'])/'stat'
            if state_path.exists() and state_path.read_text().split()[2]=='Z':raise RuntimeError(f"training zombie: {r['arm']} seed{r['seed']}; inspect {r['log']}")
            try:os.kill(r['pid'],0)
            except ProcessLookupError:raise RuntimeError(f"training died: {r['arm']} seed{r['seed']}; inspect {r['log']}")
        if ready:break
        if time.monotonic()-started>3600:raise TimeoutError('training still incomplete after1h; jobs preserved')
        time.sleep(10)
    evaluations=[]
    for index,seed in enumerate(cfg['training']['seeds']):
        log=pilot/f'heldout-s{seed}.log'
        with log.open('a') as handle:
            proc=subprocess.Popen([sys.executable,'-u','-m','server_training.evaluate','--config',a.config,'--pilot',a.pilot,'--seed',str(seed)],cwd=ROOT,env={**env,'CUDA_VISIBLE_DEVICES':str(index+1)},stdout=handle,stderr=subprocess.STDOUT)
        evaluations.append(proc)
    for proc in evaluations:
        if proc.wait()!=0:raise RuntimeError('heldout evaluation failed; inspect per-seed log')
    subprocess.run([sys.executable,'-u','-m','server_training.evaluate','--config',a.config,'--pilot',a.pilot,'--summarize'],cwd=ROOT,env=env,check=True)


if __name__=='__main__':main()
