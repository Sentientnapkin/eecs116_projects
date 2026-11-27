import sys,subprocess
sys.path.insert(0,'/dev/shm/sebastian-vio/viobench')
import wasmtime
from viobench.tools.runner.engine import make_config
CC='/data/backups/rganapa/Sebastian/tmp/viobench-toolchain/wasi-sdk/bin/clang'
subprocess.check_call([CC,'-O3','-msimd128','-mexec-model=reactor','-o','mb.wasm','mb.c','-lm'],cwd='.')
cfg=make_config();cfg.epoch_interruption=False
e=wasmtime.Engine(cfg);m=wasmtime.Module.from_file(e,'mb.wasm')
for name in [x.name for x in m.exports if x.name not in('memory','init','_initialize') and not x.name.startswith('__')]:
    s=wasmtime.Store(e);li=wasmtime.Linker(e);li.define_wasi();s.set_wasi(wasmtime.WasiConfig());inst=li.instantiate(s,m);ex=inst.exports(s)
    s.set_fuel(10**12)
    if '_initialize' in ex: ex['_initialize'](s)
    ex['init'](s)
    r=[]
    for _ in range(2):
        f0=s.get_fuel();ex[name](s);r.append(f0-s.get_fuel())
    print(f'{name:16s} {r[1]}')
