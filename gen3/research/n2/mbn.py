import sys
sys.path.insert(0,'/dev/shm/sebastian-vio/viobench')
import wasmtime
from viobench.tools.runner.engine import make_config
cfg=make_config();cfg.epoch_interruption=False
e=wasmtime.Engine(cfg);m=wasmtime.Module.from_file(e,'mbn.wasm')
s=wasmtime.Store(e);li=wasmtime.Linker(e);li.define_wasi();s.set_wasi(wasmtime.WasiConfig());inst=li.instantiate(s,m);ex=inst.exports(s);s.set_fuel(10**12)
ex['_initialize'](s);ex['t_init'](s)
for n in ['t_gray','t_setup','t_rows','t_feed','t_s0','t_s1','t_s2','t_s3','t_s4','t_h0','t_h1','t_h2','t_h3']:
    ex[n](s);f0=s.get_fuel();ex[n](s);print(n,f0-s.get_fuel())
