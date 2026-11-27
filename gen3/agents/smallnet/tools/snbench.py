"""snbench.py RUN [--stepf F]: wasmtime fuel per SN component (gray, each micro-step) for the generated block, outside GSLV
(same -O3 -msimd128 wasi-sdk clang). Inputs: random image / rotation (cost is data-independent except the prep border path)."""
import sys, subprocess, tempfile, argparse
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent)); import mksn
ap = argparse.ArgumentParser(); ap.add_argument('run'); ap.add_argument("--stepf", type=float, default=120e3); ap.add_argument("--q16", type=int, default=0); a = ap.parse_args()
blk, info = mksn.gen(a.run, a.stepf, q16=a.q16)
tmp = Path(tempfile.mkdtemp(dir='/data/backups/rganapa/Sebastian/tmp/claude-1000'))
src = ['#include <stdint.h>', '#include <math.h>', '#include <string.h>', '#include <wasm_simd128.h>', blk,
       'static uint8_t img[230400];',
       '__attribute__((export_name("init"))) void init(void) { uint32_t s = 1; for (int i = 0; i < 230400; i++) { s = s * 1103515245u + 12345u; img[i] = s >> 24; }',
       '  double c = cos(0.03), s_ = sin(0.03); double R[9] = {c, 0, s_, 0, 1, 0, -s_, 0, c}; for (int i = 0; i < 9; i++) sn_Rc[i] = R[i];',
       '  sn_fx320 = 160; sn_cx320 = 159.5; sn_cy320 = 119.5; for (int i = 0; i < 19; i++) sn_vec[i] = 0.1f * i; }',
       '__attribute__((export_name("gray"))) void gray(void) { sn_gray(img, sn_g0); }',
       '__attribute__((export_name("gray5"))) void gray5(void) { sn_gray(img, sn_g5); }',
       '__attribute__((export_name("step"))) int step(int k) { return sn_step(k); }',
       'int main(void) { return 0; }']
(tmp / 'b.c').write_text('\n'.join(src))
cc = '/data/backups/rganapa/Sebastian/tmp/viobench-toolchain/wasi-sdk/bin/clang'
r = subprocess.run([cc, '-O3', '-msimd128', '-mexec-model=reactor', '-o', str(tmp / 'b.wasm'), str(tmp / 'b.c'), '-lm'], capture_output=True, text=True)
if r.returncode: print(r.stderr[-3000:]); sys.exit(1)
code = r'''
import wasmtime, sys, json
cfg = wasmtime.Config(); cfg.consume_fuel = True; e = wasmtime.Engine(cfg); s = wasmtime.Store(e); s.set_fuel(10**12)
w = wasmtime.WasiConfig(); s.set_wasi(w); l = wasmtime.Linker(e); l.define_wasi(); m = wasmtime.Module.from_file(e, sys.argv[1]); i = l.instantiate(s, m)
ex = i.exports(s); ex['init'](s)
def f(fn, *a):
    f0 = s.get_fuel(); fn(s, *a); return f0 - s.get_fuel()
out = {'gray': f(ex['gray']), 'gray5': f(ex['gray5'])}
k = 0; st = []
while True:
    f0 = s.get_fuel(); d = ex['step'](s, k); st.append(f0 - s.get_fuel()); k += 1
    if d: break
out['steps'] = st; print(json.dumps(out))
'''
r = subprocess.run(['/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python', '-c', code, str(tmp / 'b.wasm')], capture_output=True, text=True)
if r.returncode: print(r.stderr[-3000:]); sys.exit(1)
import json; o = json.loads(r.stdout)
names = [x[0] for x in info['sched']]
agg = {}
for n, v in zip(names, o['steps']): agg[n] = agg.get(n, 0) + v
print(f"gray {o['gray']/1e3:.0f}k | steps {len(o['steps'])} total {sum(o['steps'])/1e6:.3f}M max {max(o['steps'])/1e3:.0f}k | " + ' '.join(f'{k} {v/1e3:.0f}k' for k, v in agg.items()))
print('per step', [round(x / 1e3) for x in o['steps']])
