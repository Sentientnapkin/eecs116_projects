"""prof_run.py WASM FLIGHTLIST OUTDIR [workers]: per-frame, per-segment fuel of a mark-instrumented build (env.mark(id)).
Writes OUTDIR/<flight>.npz (tot[frame], seg[frame, 300]) and OUTDIR/<flight>.done; resumable."""
import sys, numpy as np
from pathlib import Path
from multiprocessing import Pool
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
import os
ST = {}; MAXF = int(os.environ.get("MAXF", "100000"))
def run(args):
    wasm, ep, out = args
    o = Path(out) / (Path(ep).stem + '.npz')
    if o.with_suffix('.done').exists(): return Path(ep).stem, 'cached'
    try:
        import wasmtime
        from viobench.tools.runner import sandbox as S
        from viobench.tools.runner.engine import Engine
        from viobench.tools.datasets.sources import episodes
        from viobench.tools.runner.sandbox import Limits
        st = ST
        if not st.get('p'):
            st['p'] = 1; od = wasmtime.Linker.define_wasi
            def define(self):
                od(self)
                def mark(i): st['cur'].append((i, st['store'].get_fuel()))
                self.define_func('env', 'mark', wasmtime.FuncType([wasmtime.ValType.i32()], []), mark)
            wasmtime.Linker.define_wasi = define
            oa = S.Sandbox._arm
            def arm(self, fuel, wall): st['store'] = self.store; st['arm'] = fuel; oa(self, fuel, wall)
            S.Sandbox._arm = arm
        e = next(iter(episodes([str(ep)])))
        sb = S.Sandbox(wasm, Engine(), limits=Limits(), log_dir=str(Path(out) / 'tmp'))
        config, frames = e.adapt(sb.resolution); sb.init(config)
        tot, seg = [], []
        for idx, (t, frame, imu) in enumerate(e.steps(frames)):
            if idx >= MAXF: break
            st["cur"] = []; res = sb.step(t, frame, imu); tot.append(res.fuel)
            row = np.zeros(300, np.int64); prev = st['arm']
            for i, f in st['cur']: row[i] += prev - f; prev = f
            row[299] = res.fuel - (st['arm'] - prev)  # after the last mark (+ host-side mark overhead outside the store)
            seg.append(row)
        np.savez_compressed(o, tot=np.array(tot), seg=np.array(seg))
        o.with_suffix('.done').write_text('ok')
        return Path(ep).stem, len(tot)
    except BaseException as ex:
        return Path(ep).stem, 'ERR ' + repr(ex)[:300]
if __name__ == '__main__':
    wasm, fl, out = str(Path(sys.argv[1]).resolve()), sys.argv[2], sys.argv[3]; w = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    Path(out).mkdir(parents=True, exist_ok=True)
    eps = [l.strip() for l in open(fl) if l.strip()]
    with Pool(w, maxtasksperchild=1) as p:
        for name, r in p.imap_unordered(run, [(wasm, e, out) for e in eps]): print(name, r, flush=True)
