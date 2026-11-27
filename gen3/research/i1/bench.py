"""bench.py OUT.tsv: MEASURED wasmtime fuel of 3x3 conv stacks (valid padding, HWC) in three kernels:
f32 (f32x4 mul+add, 16 output channels per block), i16 (i32x4.dot_i16x8_s, 4 oc per block), i8r (relaxed i8 dot-add, 4 oc).
Compiled with the competition toolchain (wasi-sdk clang -O3 -msimd128 [-mrelaxed-simd]), run under viobench's own engine
config (make_config) so validation/fuel rules match the evaluator. Stacks are sized to ~1..1000 M fuel."""
import sys, subprocess, json, tempfile, itertools
from pathlib import Path
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
CC = '/data/backups/rganapa/Sebastian/tmp/viobench-toolchain/wasi-sdk/bin/clang'
TMP = Path(__file__).parent / 'bench_tmp'; TMP.mkdir(exist_ok=True)
KER = r'''
#include <stdint.h>
#include <string.h>
#include <wasm_simd128.h>
static void conv_f32(const float *in, float *out, const float *w, const float *b, int H, int W, int CI, int CO, int s) {
  int OH = (H - 3) / s + 1, OW = (W - 3) / s + 1;
  for (int oy = 0; oy < OH; oy++) for (int ox = 0; ox < OW; ox++) for (int oc = 0; oc < CO; oc += 16) {
    v128_t a0 = wasm_v128_load(b + oc), a1 = wasm_v128_load(b + oc + 4), a2 = wasm_v128_load(b + oc + 8), a3 = wasm_v128_load(b + oc + 12);
    for (int ky = 0; ky < 3; ky++) for (int kx = 0; kx < 3; kx++) {
      const float *ip = in + ((oy * s + ky) * W + ox * s + kx) * CI; const float *wp = w + ((ky * 3 + kx) * CI) * CO + oc;
      for (int ic = 0; ic < CI; ic++, wp += CO) { v128_t v = wasm_v128_load32_splat(ip + ic);
        a0 = wasm_f32x4_add(a0, wasm_f32x4_mul(v, wasm_v128_load(wp))); a1 = wasm_f32x4_add(a1, wasm_f32x4_mul(v, wasm_v128_load(wp + 4)));
        a2 = wasm_f32x4_add(a2, wasm_f32x4_mul(v, wasm_v128_load(wp + 8))); a3 = wasm_f32x4_add(a3, wasm_f32x4_mul(v, wasm_v128_load(wp + 12))); } }
    v128_t z = wasm_f32x4_splat(0); float *op = out + (oy * OW + ox) * CO + oc;
    wasm_v128_store(op, wasm_f32x4_max(a0, z)); wasm_v128_store(op + 4, wasm_f32x4_max(a1, z)); wasm_v128_store(op + 8, wasm_f32x4_max(a2, z)); wasm_v128_store(op + 12, wasm_f32x4_max(a3, z)); }
}
static inline int32_t hsum(v128_t a) { return wasm_i32x4_extract_lane(a, 0) + wasm_i32x4_extract_lane(a, 1) + wasm_i32x4_extract_lane(a, 2) + wasm_i32x4_extract_lane(a, 3); }
/* weights per oc contiguous over (ky,kx,ic) */
static void conv_i16(const int16_t *in, int16_t *out, const int16_t *w, const int32_t *b, int H, int W, int CI, int CO, int s) {
  int OH = (H - 3) / s + 1, OW = (W - 3) / s + 1, K = 9 * CI;
  for (int oy = 0; oy < OH; oy++) for (int ox = 0; ox < OW; ox++) for (int oc = 0; oc < CO; oc += 4) {
    v128_t a0 = wasm_i32x4_splat(0), a1 = a0, a2 = a0, a3 = a0; const int16_t *w0 = w + oc * K;
    for (int ky = 0; ky < 3; ky++) for (int kx = 0; kx < 3; kx++) {
      const int16_t *ip = in + ((oy * s + ky) * W + ox * s + kx) * CI; int o = (ky * 3 + kx) * CI;
      for (int ic = 0; ic < CI; ic += 8) { v128_t v = wasm_v128_load(ip + ic);
        a0 = wasm_i32x4_add(a0, wasm_i32x4_dot_i16x8(v, wasm_v128_load(w0 + o + ic))); a1 = wasm_i32x4_add(a1, wasm_i32x4_dot_i16x8(v, wasm_v128_load(w0 + K + o + ic)));
        a2 = wasm_i32x4_add(a2, wasm_i32x4_dot_i16x8(v, wasm_v128_load(w0 + 2 * K + o + ic))); a3 = wasm_i32x4_add(a3, wasm_i32x4_dot_i16x8(v, wasm_v128_load(w0 + 3 * K + o + ic))); } }
    int16_t *op = out + (oy * OW + ox) * CO + oc; int32_t r;
    r = (hsum(a0) + b[oc]) >> 8; op[0] = r < 0 ? 0 : r > 32767 ? 32767 : r; r = (hsum(a1) + b[oc + 1]) >> 8; op[1] = r < 0 ? 0 : r > 32767 ? 32767 : r;
    r = (hsum(a2) + b[oc + 2]) >> 8; op[2] = r < 0 ? 0 : r > 32767 ? 32767 : r; r = (hsum(a3) + b[oc + 3]) >> 8; op[3] = r < 0 ? 0 : r > 32767 ? 32767 : r; }
}
#ifdef RELAXED
static void conv_i8r(const int8_t *in, int8_t *out, const int8_t *w, const int32_t *b, int H, int W, int CI, int CO, int s) {
  int OH = (H - 3) / s + 1, OW = (W - 3) / s + 1, K = 9 * CI;
  for (int oy = 0; oy < OH; oy++) for (int ox = 0; ox < OW; ox++) for (int oc = 0; oc < CO; oc += 4) {
    v128_t a0 = wasm_i32x4_splat(0), a1 = a0, a2 = a0, a3 = a0; const int8_t *w0 = w + oc * K;
    for (int ky = 0; ky < 3; ky++) for (int kx = 0; kx < 3; kx++) {
      const int8_t *ip = in + ((oy * s + ky) * W + ox * s + kx) * CI; int o = (ky * 3 + kx) * CI;
      for (int ic = 0; ic < CI; ic += 16) { v128_t v = wasm_v128_load(ip + ic);
        a0 = wasm_i32x4_relaxed_dot_i8x16_i7x16_add(v, wasm_v128_load(w0 + o + ic), a0); a1 = wasm_i32x4_relaxed_dot_i8x16_i7x16_add(v, wasm_v128_load(w0 + K + o + ic), a1);
        a2 = wasm_i32x4_relaxed_dot_i8x16_i7x16_add(v, wasm_v128_load(w0 + 2 * K + o + ic), a2); a3 = wasm_i32x4_relaxed_dot_i8x16_i7x16_add(v, wasm_v128_load(w0 + 3 * K + o + ic), a3); } }
    int8_t *op = out + (oy * OW + ox) * CO + oc; int32_t r;
    r = (hsum(a0) + b[oc]) >> 7; op[0] = r < 0 ? 0 : r > 127 ? 127 : r; r = (hsum(a1) + b[oc + 1]) >> 7; op[1] = r < 0 ? 0 : r > 127 ? 127 : r;
    r = (hsum(a2) + b[oc + 2]) >> 7; op[2] = r < 0 ? 0 : r > 127 ? 127 : r; r = (hsum(a3) + b[oc + 3]) >> 7; op[3] = r < 0 ? 0 : r > 127 ? 127 : r; }
}
#endif
'''
def stack(H, W, c0, c, n_per):
    """layers: (CI, CO, stride); stages c, 2c, 4c, 8c each n_per convs, first conv of stages 2..4 stride 2"""
    L, ci, h, w = [], c0, H, W
    for st in range(4):
        co = c * 2 ** st
        for j in range(n_per):
            s = 2 if (st > 0 and j == 0) else 1
            L.append((ci, co, s, h, w)); h, w = (h - 3) // s + 1, (w - 3) // s + 1; ci = co
    return L
def macs(L): return sum(9 * ci * co * ((h - 3) // s + 1) * ((w - 3) // s + 1) for ci, co, s, h, w in L)
def gen(kind, L):
    T = {'f32': 'float', 'i16': 'int16_t', 'i8r': 'int8_t'}[kind]
    maxa = max(max(h * w * ci for ci, co, s, h, w in L), max(((h - 3) // s + 1) * ((w - 3) // s + 1) * co for ci, co, s, h, w in L))
    nw = sum(9 * ci * co for ci, co, s, h, w in L); nb = sum(co for ci, co, s, h, w in L)
    bt = 'float' if kind == 'f32' else 'int32_t'
    src = [KER, f'static {T} A[{maxa}], B[{maxa}]; static {T} Wt[{nw}]; static {bt} Bs[{nb}];',
           '__attribute__((export_name("init"))) void init(void) { uint32_t s = 1; for (int i = 0; i < (int)(sizeof Wt / sizeof Wt[0]); i++) { s = s * 1103515245u + 12345u; Wt[i] = (' + T + ')((int)(s >> 24) - 128) * ' + ('0.003f' if kind == 'f32' else '1') + '; }',
           '  for (int i = 0; i < (int)(sizeof A / sizeof A[0]); i++) { s = s * 1103515245u + 12345u; A[i] = (' + T + ')((s >> 25)); } }',
           '__attribute__((export_name("run"))) void run(void) {']
    ow = ob = 0; cur, nxt = 'A', 'B'
    for ci, co, s, h, w in L:
        src.append(f'  conv_{kind}({cur}, {nxt}, Wt + {ow}, Bs + {ob}, {h}, {w}, {ci}, {co}, {s});'); ow += 9 * ci * co; ob += co; cur, nxt = nxt, cur
    src += ['}', 'int main(void) { return 0; }']
    return '\n'.join(src), nw
def measure(kind, L, tag):
    import wasmtime
    from viobench.tools.runner.engine import make_config
    src, nw = gen(kind, L)
    c = TMP / f'{tag}.c'; o = TMP / f'{tag}.wasm'; c.write_text(src)
    fl = ['-O3', '-msimd128'] + (['-mrelaxed-simd', '-DRELAXED'] if kind == 'i8r' else [])
    r = subprocess.run([CC] + fl + ['-mexec-model=reactor', '-o', str(o), str(c)], capture_output=True, text=True)
    if r.returncode: return None, 'compile: ' + r.stderr[-300:]
    cfg = make_config(); cfg.epoch_interruption = False
    e = wasmtime.Engine(cfg); s = wasmtime.Store(e)
    try:
        m = wasmtime.Module.from_file(e, str(o))
    except Exception as ex: return None, 'validate: ' + str(ex)[:200]
    li = wasmtime.Linker(e); li.define_wasi(); s.set_wasi(wasmtime.WasiConfig())
    inst = li.instantiate(s, m); ex = inst.exports(s)
    s.set_fuel(10 ** 13)
    if '_initialize' in ex: ex['_initialize'](s)
    ex['init'](s); f0 = s.get_fuel(); ex['run'](s); return f0 - s.get_fuel(), nw
if __name__ == '__main__':
    out = open(sys.argv[1], 'w'); out.write('kind\ttarget_M\tH\tW\tc\tn_per\tlayers\tMACs\tparams\tfuel\tfuel_per_MAC\tnote\n')
    H, W, c0 = 96, 128, 16  # 16-ch input (e.g. a cheap stem output / stacked frames) at 128x96
    # calibrate one small stack per kernel, then size stacks to each target with that kernel's fuel/MAC
    for kind in ['f32', 'i16', 'i8r']:
        Lc = stack(H, W, c0, 16, 2); fc, nw = measure(kind, Lc, f'{kind}_cal')
        if fc is None: out.write(f'{kind}\tcal\t\t\t\t\t\t\t\t\t\t{nw}\n'); out.flush(); continue
        fpm = fc / macs(Lc); out.write(f'{kind}\tcal\t{H}\t{W}\t16\t2\t{len(Lc)}\t{macs(Lc)}\t{nw}\t{fc}\t{fpm:.4f}\tcalibration\n'); out.flush()
        for T in [1, 5, 10, 25, 100, 500, 1000]:
            best = None
            for c, n_per, hw in itertools.product([16, 32, 48, 64, 96, 128, 192, 256], [1, 2, 3, 4], [(48, 64), (96, 128), (192, 256), (384, 512)]):
                L = stack(hw[0], hw[1], c0, c, n_per)
                if any(hh < 3 or ww < 3 for _, _, _, hh, ww in L) or min((h - 3) // s + 1 for _, _, s, h, _ in L) < 1: continue
                d = abs(macs(L) * fpm / (T * 1e6) - 1)
                if best is None or d < best[0]: best = (d, c, n_per, hw, L)
            d, c, n_per, hw, L = best
            f, nw = measure(kind, L, f'{kind}_{T}M')
            out.write(f'{kind}\t{T}\t{hw[0]}\t{hw[1]}\t{c}\t{n_per}\t{len(L)}\t{macs(L)}\t{nw}\t{f}\t{(f / macs(L)) if f else 0:.4f}\t\n'); out.flush()
    out.close(); (Path(sys.argv[1]).with_suffix('.done')).write_text('ok')
