"""prof.py WASM OUT.npz NFLIGHTS [workers] [maxframes]: per-micro-step fuel (NSPROF builds: mark(1,k) before / mark(2,k) after ns_do)
on the first NFLIGHTS of pools/nv2sub30. Saves per flight: steps (frame, k, fuel), per-frame total fuel."""
import sys, numpy as np
from pathlib import Path
from multiprocessing import Pool
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench')
EPIS = Path('/data/backups/rganapa/Sebastian/gen3/agents/netv2/pools/nv2sub30k')
STATE = {}
def run(args):
    wasm, ep, maxf = args
    try:
        import wasmtime
        from viobench.tools.runner import sandbox as S
        from viobench.tools.runner.engine import Engine
        from viobench.tools.datasets.sources import episodes
        from viobench.tools.runner.sandbox import Limits
        st = STATE
        if not st.get('p'):
            st['p'] = 1; od = wasmtime.Linker.define_wasi
            def define(self):
                od(self)
                def mark(i, v): st['cur'].append((i, v, st['store'].get_fuel()))
                self.define_func('env', 'mark', wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], []), mark)
            wasmtime.Linker.define_wasi = define
            oa = S.Sandbox._arm
            def arm(self, fuel, wall): st['store'] = self.store; oa(self, fuel, wall)
            S.Sandbox._arm = arm
        e = next(iter(episodes([str(ep)])))
        sb = S.Sandbox(wasm, Engine(), limits=Limits(), log_dir='/data/backups/rganapa/Sebastian/gen3/agents/netv2/logs/prof_tmp')
        config, frames = e.adapt(sb.resolution); sb.init(config)
        steps, tot = [], []
        for idx, (t, frame, imu) in enumerate(e.steps(frames)):
            if idx >= maxf: break
            st['cur'] = []; res = sb.step(t, frame, imu); tot.append(res.fuel)
            c = st['cur']
            for (i1, k1, f1), (i2, k2, f2) in zip(c[:-1], c[1:]):
                if i1 == 1 and i2 == 2: steps.append((idx, k1, f1 - f2))
        return ep.stem, np.array(steps), np.array(tot)
    except BaseException as ex:
        return ep.stem, repr(ex)[:300], None
if __name__ == '__main__':
    wasm, out, n = str(Path(sys.argv[1]).resolve()), sys.argv[2], int(sys.argv[3]); w = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    mf = int(sys.argv[5]) if len(sys.argv) > 5 else 400
    eps = sorted(EPIS.glob('*.zip'))[:n]; res = {}
    with Pool(w) as p:
        for name, s, t in p.imap_unordered(run, [(wasm, e, mf) for e in eps]):
            if t is None: print('ERR', name, s); continue
            res[name + '_steps'] = s; res[name + '_tot'] = t; print('done', name, len(s), flush=True)
    np.savez(out, **res)
