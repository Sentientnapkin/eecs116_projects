import sys, subprocess, numpy as np
from pathlib import Path
TC='/data/backups/rganapa/Sebastian/tmp/viobench-toolchain/wasi-sdk'
NATIVE='/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native'
def build(kernel,n=100000,extra=()):
    out=f'/data/backups/rganapa/Sebastian/tmp/mb_{kernel}_{n}.wasm'
    cmd=[f'{TC}/bin/clang','--sysroot',f'{TC}/share/wasi-sysroot','--target=wasm32-wasip1','-O2','-msimd128',f'-DKERNEL={kernel}',f'-DN={n}',f'-I{NATIVE}',
         '-mexec-model=reactor','-Wl,--initial-memory=67108864',*extra,'mb.c','-o',out,'-lm']
    subprocess.run(cmd,check=True); return out
def fuel(wasm):
    from viobench.tools.runner.sandbox import Sandbox
    from viobench.tools.abi.config import default_guest_config
    sb=Sandbox(wasm); w,h=sb.resolution; sb.init(default_guest_config(width=w,height=h))
    fr=np.zeros((h,w,3),np.uint8); imu=np.zeros((10,7))
    return [sb.step(0.05*(k+1),fr,imu).fuel for k in range(3)]
if __name__=='__main__':
    rows={}
    for k in range(13):
        a=fuel(build(k,100000)); b=fuel(build(k,200000))
        print(k, a, b, 'per-iter', (b[1]-a[1])/100000, flush=True)
