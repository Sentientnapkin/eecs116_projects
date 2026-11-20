"""Per-component per-frame fuel via host-import marks. usage: prof_run.py wasm outdir nflights [workers]
Runs SEARCH-fold flights only (folds 0-2). Writes outdir/<ep>.npz with cum[frame,14] (fuel consumed at each mark) and vals."""
import sys, os, json, hashlib, numpy as np
from pathlib import Path
from multiprocessing import Pool
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, '/dev/shm/sebastian-vio/viobench'); sys.path.insert(0, str(ROOT / 'research/single_model'))
EPIS = Path('/data/backups/rganapa/Sebastian/gen/raw-fast/selected')

STATE = {}

def search_eps():
    out = []
    for line in (ROOT / 'research/campaign/perflight.jsonl').read_text().splitlines():
        r = json.loads(line)
        f = int(hashlib.sha256((r['catalog'] + ':' + r['scene']).encode()).hexdigest()[:8], 16) % 5
        if f in (0, 1, 2): out.append(r['episode'])
    return sorted(set(out))

def run_one(args):
    try:
        return run_one_(args)
    except BaseException as e:
        return 'ERR %s %r' % (args[2], str(e)[:300])

def run_one_(args):
    wasm, outdir, ep = args
    import wasmtime, png_cache; png_cache.install()
    from viobench.tools.runner import sandbox as S
    from viobench.tools.runner.engine import Engine
    from viobench.tools.datasets.sources import episodes
    from viobench.tools.runner.sandbox import Limits
    state = STATE
    state.update(store=None, cur=None)
    if not state.get('patched'):
        state['patched'] = True
        orig_define = wasmtime.Linker.define_wasi
        def define(self):
            orig_define(self)
            def mark(i, v):
                state['cur'].append((i, v, state['store'].get_fuel()))
            self.define_func('env', 'mark', wasmtime.FuncType([wasmtime.ValType.i32(), wasmtime.ValType.i32()], []), mark)
        wasmtime.Linker.define_wasi = define
        orig_arm = S.Sandbox._arm
        def arm(self, fuel, wall):
            state['store'] = self.store; orig_arm(self, fuel, wall); state['fuel0'] = fuel
        S.Sandbox._arm = arm
    name = ep; ep = next(iter(episodes([str(EPIS / (name + '.zip'))])))
    sb = S.Sandbox(wasm, Engine(), limits=Limits(), log_dir=str(Path(outdir) / ('log_' + name)))
    config, frames = ep.adapt(sb.resolution); sb.init(config)
    seg, cnt, tot, last, poses = [], [], [], [], []
    for idx, (t, frame, imu) in enumerate(ep.steps(frames)):
        state['cur'] = []
        res = sb.step(t, frame, imu)
        f0 = state['fuel0']
        sg = np.zeros(48); ct = np.zeros(48); vv = np.zeros(48)
        marks = [(i, v, f0 - fl) for i, v, fl in state['cur']] + [(47, 0, res.fuel)]
        for (i, v, c0), (_, _, c1) in zip(marks[:-1], marks[1:]):
            sg[i] += c1 - c0; ct[i] += 1; vv[i] = v
        sg[0] = marks[0][2]  # fuel before the first mark (step entry)
        poses.append(np.concatenate([res.pose,res.twist])); seg.append(sg); cnt.append(ct); last.append(vv); tot.append(res.fuel)
    cum, vals = np.array(seg), np.array(last)
    np.savez(Path(outdir) / (name + '.npz'), seg=np.array(seg), cnt=np.array(cnt), vals=vals, tot=np.array(tot), pose=np.array(poses))
    return name

if __name__ == '__main__':
    wasm, outdir, n = sys.argv[1], sys.argv[2], int(sys.argv[3]); workers = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    Path(outdir).mkdir(parents=True, exist_ok=True)
    eps = search_eps(); step = max(1, len(eps) // n); eps = eps[::step][:n]
    with Pool(workers) as p:
        for k in p.imap_unordered(run_one, [(wasm, outdir, e) for e in eps]): print('done', k, flush=True)
