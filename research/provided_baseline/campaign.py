"""Matched baseline public / campaign-dev replay, never reserved splits."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import numpy as np
from replay import replay, digest


def run(task):
    wasm,archive,crop,count,output,metadata=task
    cached=output/'result.json'
    if cached.exists():
        old=json.loads(cached.read_text())
        assert old['wasm_sha256']==digest(wasm)
        assert old['archive_sha256']==digest(archive)
        assert old['crop_s']==crop
        return old
    return replay(wasm,archive,crop,count,output,metadata)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('wasm',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--set',choices=['public','campaign-dev'],required=True)
    p.add_argument('--workers',type=int,default=4)
    args=p.parse_args()
    tasks=[]
    if args.set=='public':
        for archive in sorted(Path('/data/backups/rganapa/Sebastian/tmp/viobench-public-replay').glob('sim-*/*.zip')):
            tasks.append((args.wasm,archive,0,None,args.output/archive.stem,dict(catalog='procthor',scene='ProcTHOR-Train-1',dataset_revision='eecdfdf2502fa50c30bdde17a809d31cc2a9bb6b')))
        assert len(tasks)==10
    else:
        manifest=Path('/data/backups/rganapa/Sebastian/eecs116_projects/research/data/native-campaign/dev-records.json')
        for r in json.loads(manifest.read_text())['records']:
            assert r['split']=='dev'
            archive=Path('/data/backups/rganapa/Sebastian/gen/raw/dev')/r['parent_file']
            tasks.append((args.wasm,archive,r['crop_s'],None,args.output/(r['flight_id']+'-'+str(r['crop_s'])),{k:r[k] for k in ('catalog','scene','regime','parent_sha256','backward_fraction','lateral_fraction')}))
        assert len(tasks)==120
    args.output.mkdir(parents=True,exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows=list(pool.map(run,tasks))
    result=dict(rows=rows,mean_unaligned_ate_m=float(np.mean([r['unaligned_ate_m'] for r in rows])),peak_fuel_per_frame=max(r['peak_fuel_per_frame'] for r in rows),completed=sum(r['completed'] for r in rows),filled_frames=sum(r['filled_frames'] for r in rows))
    (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    main()
