"""prof.py WASM OUTDIR ZIP... [-j N] : per-frame per-phase self fuel of a PROF build (env.mark(id, val) host import records
the remaining fuel at each mark). Writes OUTDIR/<flight>.npz: seg[frame, 200] (self fuel per phase id, id 0 = before the
first mark), cnt[frame, 200] (calls), vals[frame, 100] (PV values), tot[frame] (step fuel as the runner reports it)."""
import os, sys, numpy as np
from multiprocessing import Pool
ST = {}
def run(args):
    wasm, out, z = args
    try:
        import wasmtime
        from viobench.tools.runner import sandbox as S
        from viobench.tools.runner.engine import Engine
        from viobench.tools.datasets.sources import episodes
        from viobench.tools.runner.sandbox import Limits
        if not ST.get('p'):
            ST['p'] = 1; od = wasmtime.Linker.define_wasi
            def define(self):
                od(self)
                def mark(i, v): ST['cur'].append((i, v, ST['store'].get_fuel()))
                self.define_func('env', 'mark', wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], []), mark)
            wasmtime.Linker.define_wasi = define
            oa = S.Sandbox._arm
            def arm(self, fuel, wall): ST['store'] = self.store; ST['f0'] = fuel; oa(self, fuel, wall)
            S.Sandbox._arm = arm
        name = os.path.basename(z)[:-4]
        e = next(iter(episodes([z])))
        sb = S.Sandbox(wasm, Engine(), limits=Limits(), log_dir=os.path.join(out, 'log_' + name))
        config, frames = e.adapt(sb.resolution); sb.init(config)
        segs, cnts, vals, tot, poses, evs, zs = [], [], [], [], [], [], []
        for idx, (t, frame, imu) in enumerate(e.steps(frames)):
            ST['cur'] = []
            r = sb.step(t, frame, imu)
            f0 = ST['f0']
            sg = np.zeros(200); ct = np.zeros(200); vv = np.zeros(100)
            mk = [(i, v, f0 - fl) for i, v, fl in ST['cur'] if i < 100]
            for i, v, fl in ST['cur']:
                if i >= 100: vv[i - 100] = v
            ev = []; st = {}
            for i, v, fl in ST['cur']:
                if 180 <= i < 185: st.setdefault(i, []).append((v, f0 - fl))
                elif i == 170: zk = [idx, v]
                elif 171 <= i <= 173:
                    zk.append(v)
                    if i == 173: zs.append(zk)
                elif 190 <= i < 195 and st.get(i - 10): kk, c0 = st[i - 10].pop(); ev.append((idx, i - 190, kk, v, f0 - fl - c0))
            evs.extend(ev)
            cur_id, last = 0, 0
            for i, v, c in mk:
                sg[cur_id] += c - last; last = c; cur_id = i; ct[i] += 1
            sg[cur_id] += r.fuel - last
            segs.append(sg); cnts.append(ct); vals.append(vv); tot.append(r.fuel)
            poses.append(np.concatenate([np.asarray(r.pose, float), np.asarray(r.twist, float)]))
        np.savez_compressed(os.path.join(out, name + '.npz'), seg=np.array(segs, np.float32), cnt=np.array(cnts, np.int32),
                            vals=np.array(vals, np.int32), tot=np.array(tot, np.int64), poses=np.array(poses), ev=np.array(evs, np.int64).reshape(-1, 5), zs=np.array(zs, np.int64).reshape(-1, 5))
        return name + ' frames %d max %d' % (len(tot), max(tot))
    except BaseException as ex:
        import traceback
        return 'ERR %s %s' % (z, traceback.format_exc()[-1500:])
if __name__ == '__main__':
    a = sys.argv[1:]; j = 4
    if '-j' in a: k = a.index('-j'); j = int(a[k + 1]); del a[k:k + 2]
    wasm, out, zips = os.path.realpath(a[0]), a[1], a[2:]
    os.makedirs(out, exist_ok=True)
    with Pool(j) as p:
        for s in p.imap_unordered(run, [(wasm, out, z) for z in zips]): print(s, flush=True)
