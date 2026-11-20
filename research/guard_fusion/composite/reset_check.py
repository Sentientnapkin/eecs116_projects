"""Exercise the actual ABI init twice, including estimator startup, in one instance."""
import argparse
import hashlib
import json
from pathlib import Path
import os
import sys

import numpy as np

sys.path.insert(0,os.environ.get('VIOBENCH_SRC','/dev/shm/sebastian-vio/viobench'))
from viobench.tools.runner.sandbox import Sandbox


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--wasm',required=True,type=Path)
    p.add_argument('--fixture',required=True,type=Path)
    p.add_argument('--frames',default=200,type=int)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    with np.load(a.fixture,allow_pickle=False) as f: data={k:f[k].copy() for k in f.files}
    camera=json.loads(str(data['camera_json'])); n=min(a.frames,len(data['frames']))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    box=Sandbox(a.wasm,log_dir=a.output.parent/(a.output.stem+'-logs')); box.init(camera)
    def replay():
        states=[]
        for i in range(n):
            lo,hi=data['packet_offsets'][i:i+2]
            packet=data['packets'][lo:hi].copy();packet[:,0]+=data['absolute_times'][0]
            row=box.step(float(data['absolute_times'][i]),data['frames'][i],packet)
            states.append(np.r_[row.pose,row.twist])
        return np.asarray(states)
    first=replay()
    # Sandbox deliberately enforces once-per-episode init at its public interface;
    # the reset test invokes the real exported ABI a second time explicitly.
    encoded=json.dumps(camera).encode(); ptr=box.alloc(len(encoded));box.write(ptr,encoded)
    box._arm(box.limits.init_fuel,box.limits.init_wall_seconds)
    status=box._guard(lambda:box._init(box.store,ptr,len(encoded)))
    second=replay() if status==0 else np.full_like(first,np.nan)
    report={'wasm_sha256':hashlib.sha256(a.wasm.read_bytes()).hexdigest(),'frames':n,
            'fixture':str(a.fixture),'second_init_status':status,
            'first_pose_identity':bool(np.array_equal(first[0,:7],[0,0,0,0,0,0,1]) and
                                      np.array_equal(second[0,:7],[0,0,0,0,0,0,1])),
            'init_twice_reproduces':bool(np.array_equal(first,second)),
            'max_component_delta':float(np.max(np.abs(first-second))) if np.all(np.isfinite(second)) else None}
    report['pass']=report['first_pose_identity'] and report['init_twice_reproduces'] and status==0
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    if not report['pass']:raise SystemExit(1)


if __name__=='__main__':main()
