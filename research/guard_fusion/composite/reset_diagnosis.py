"""Isolated debug export of sub-estimator outputs to diagnose actual ABI resets.

No source guest/binary is modified. The debug variant retains the original
objects except its wrapper, which records read-only latest source outputs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np

sys.path.insert(0,os.environ.get('VIOBENCH_SRC','/dev/shm/sebastian-vio/viobench'))
from viobench.tools.runner.sandbox import Sandbox


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def debug_build(build,out):
    meta=json.loads((build/'build.json').read_text())
    out.mkdir(parents=True,exist_ok=True)
    file=out/'guest.cpp'
    original=(build/'source/guest.cpp').read_text()
    source=original.replace('uint64_t source_rng[3];','uint64_t source_rng[3];\ndouble debug_last[3][13]; double debug_flags[3];')
    source=source.replace('selector.step(t,x,ready,out);','std::memcpy(debug_last,x,sizeof debug_last);\n    for(int s=0;s<3;++s) debug_flags[s]=ready[s];\n    selector.step(t,x,ready,out);')
    source+='\nextern "C" VIOBENCH_EXPORT(debug_sources) void debug_sources(double *p) { std::memcpy(p,debug_last,sizeof debug_last); std::memcpy(p+39,debug_flags,sizeof debug_flags); }\n'
    file.write_text(source)
    cc=next(c.copy() for c in meta['commands'] if '-c' in c and any(str(p).endswith('/source/guest.cpp') for p in c))
    index=cc.index('-c'); cc[index+1]=str(file)
    original_obj=cc[cc.index('-o')+1]; cc[cc.index('-o')+1]=str(out/'guest.o')
    subprocess.run(cc,cwd=build,check=True)
    link=meta['commands'][-1].copy()
    link=[str(out/'guest.o') if p==original_obj else p for p in link]
    link[link.index('-o')+1]=str(out/'debug.wasm')
    subprocess.run(link,cwd=build,check=True)
    (out/'build.json').write_text(json.dumps({'scope':'read-only source-output diagnostic',
        'parent_wasm_sha256':meta['wasm_sha256'],'debug_wasm_sha256':sha(out/'debug.wasm'),
        'commands':[cc,link]},indent=2)+'\n')
    return out/'debug.wasm'


def run(wasm,fixture,frames,output):
    with np.load(fixture,allow_pickle=False) as f:data={k:f[k].copy() for k in f.files}
    camera=json.loads(str(data['camera_json']));n=min(frames,len(data['frames']))
    box=Sandbox(wasm,log_dir=output.parent/(output.stem+'-logs'));box.init(camera)
    pointer=box.alloc(42*8);debug=box.instance.exports(box.store)['debug_sources']
    def replay():
        states=[];sources=[]
        for i in range(n):
            lo,hi=data['packet_offsets'][i:i+2]
            imu=data['packets'][lo:hi].copy();imu[:,0]+=data['absolute_times'][0]
            row=box.step(float(data['absolute_times'][i]),data['frames'][i],imu)
            debug(box.store,pointer)
            sources.append(np.frombuffer(box.read(pointer,42*8),dtype=np.float64).copy())
            states.append(np.r_[row.pose,row.twist])
        return np.asarray(states),np.asarray(sources)
    first,s1=replay()
    encoded=json.dumps(camera).encode();ptr=box.alloc(len(encoded));box.write(ptr,encoded)
    box._arm(box.limits.init_fuel,box.limits.init_wall_seconds)
    status=box._guard(lambda:box._init(box.store,ptr,len(encoded)))
    if status!=0:raise ValueError(f'reinit failed {status}')
    second,s2=replay()
    report={'wasm_sha256':sha(wasm),'frames':n,'fixture':str(fixture),'sources':{}}
    def stats(a,b):
        eq=(a==b)|(np.isnan(a)&np.isnan(b))
        changed=np.where(~eq.all(axis=1))[0]
        return {'first_changed_frame':int(changed[0]) if len(changed) else None,
            'changed_frames':int(len(changed)),'max_finite_delta':float(np.nanmax(np.abs(a-b)))}
    for i,name in enumerate(('vins','openvins','n2')):
        report['sources'][name]=stats(s1[:,i*13:(i+1)*13],s2[:,i*13:(i+1)*13])
        report['sources'][name]['ready_mismatch_frames']=np.where(s1[:,39+i]!=s2[:,39+i])[0].tolist()
    report['output']=stats(first,second)
    np.savez_compressed(output.with_suffix('.npz'),first=first,second=second,sources_first=s1,sources_second=s2)
    output.write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2),flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--fixture',type=Path,required=True)
    p.add_argument('--frames',type=int,default=200)
    a=p.parse_args();build=a.build.resolve();out=a.out.resolve()
    wasm=out/'debug.wasm'
    if not wasm.exists():wasm=debug_build(build,out)
    run(wasm,a.fixture,a.frames,out/'diagnosis.json')

if __name__=='__main__':main()
