"""Build a gp_msckf variant, score it on the 171 selected flights, report search/val slices.

  python -m research.single_model.run_variant --name c1_tilt15 --defines "INIT_TILT_STD=0.15" --workers 32

Slices (scene-disjoint, fold = sha256(catalog:scene)[:8] % 5, same rule as guard_fusion):
  search = folds 0,1,2   val = fold 3   sealed = fold 4 (aggregate written to a file, NEVER printed).
Metric: mean unaligned ATE (m), raw. Paired bootstrap resamples scenes vs the baseline run.
Run with the teacher python: /data/backups/rganapa/Sebastian/venv-teacher/bin/python -B -m research.single_model.run_variant
"""
import argparse, hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC_DEFAULT = ROOT / 'Final Project/classical_vio/gp_msckf/solution.c'
CMAKE_DEFAULT = ROOT / 'Final Project/classical_vio/gp_msckf/CMakeLists.txt'
OUT = ROOT / 'research/results/single_model'
EPISODES = Path('/data/backups/rganapa/Sebastian/gen/raw-fast/selected')
TOOLCHAIN = Path('/data/backups/rganapa/Sebastian/tmp/viobench-toolchain')
NATIVE = Path('/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native')
VIOBENCH_PY = '/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python'
BASELINE = ROOT / 'research/results/loop/gp-msckf-pool/gp_msckf-c7413a81/scores.json'  # submitted gp_msckf.wasm
PERFLIGHT = ROOT / 'research/campaign/perflight.jsonl'


def tags():
    t = {}
    for line in PERFLIGHT.read_text().splitlines():
        r = json.loads(line)
        t[r['episode']] = dict(scene=r['scene'], catalog=r['catalog'], start=r['start_type'], group=r.get('group'))
    return t


def fold(tag):
    return int(hashlib.sha256((tag['catalog'] + ':' + tag['scene']).encode()).hexdigest()[:8], 16) % 5


def slice_of(f):
    return 'search' if f in (0, 1, 2) else 'val' if f == 3 else 'sealed'


def build(src, cmake, defines, name):
    work = OUT / name / 'src'
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    shutil.copy(src, work / 'solution.c'); shutil.copy(cmake, work / 'CMakeLists.txt')
    flags = ' '.join('-D' + d for d in defines.split()) if defines else ''
    cfg = ['cmake', '-S', str(work), '-B', str(work / 'build'),
           f'-DCMAKE_TOOLCHAIN_FILE={TOOLCHAIN}/wasi-sdk/share/cmake/wasi-sdk-p1.cmake',
           f'-DVIOBENCH_NATIVE_DIR={NATIVE}', f'-DCMAKE_C_FLAGS={flags}']
    for cmd in (cfg, ['cmake', '--build', str(work / 'build')]):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode:
            raise SystemExit(p.stdout[-2000:] + p.stderr[-2000:])
    wasm = OUT / name / 'solution.wasm'
    shutil.copy(work / 'build/solution.wasm', wasm)
    return wasm



def run_guest_fast(wasm, episodes, out, workers=32, name='guest'):
    """Same layout/results as score.run_guest but `viobench evaluate` WITHOUT -o: that skips the per-flight
    trajectory.mp4 (a second full PNG decode + mp4 encode, ~2x slower, ~30 MB/flight). ATE, estimate.tum, twist,
    fuel and stderr are identical (verified on one flight)."""
    import fcntl, time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    sys.path.insert(0, str(ROOT))
    from research import wasm_eval
    from research.guard_fusion.composite.score import sha
    wasm = Path(wasm).resolve(); source = Path(episodes).resolve()
    archives = sorted(source.glob('*.zip'))
    digest = sha(wasm)
    base = Path(out).resolve(); base.mkdir(parents=True, exist_ok=True)
    folder = base / (name + '-' + digest[:8]); folder.mkdir(parents=True, exist_ok=True)
    shared = Path(os.environ.get('VIOBENCH_SHARED_CACHE', '/dev/shm/sebastian-vio/guard-cache/' + digest)).resolve()
    shared.mkdir(parents=True, exist_ok=True)
    lock = Path(os.environ.get('VIOBENCH_COMPILE_LOCK', str(shared / 'compile.lock'))).resolve()
    env = os.environ.copy()
    env.update(PYTHONPATH=str(wasm_eval.SRC), XDG_CACHE_HOME=str(shared), VIOBENCH_COMPILE_LOCK=str(lock),
               OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    guest = {'name': name, 'wasm': str(wasm), 'sha256': digest, 'archives': list(map(str, archives)),
             'evaluator_src': str(wasm_eval.SRC), 'shared_cache': str(shared), 'compile_lock': str(lock), 'video': False}
    (folder / 'guest.json').write_text(json.dumps(guest, indent=2) + '\n')
    todo = [a for a in archives if not (folder / a.stem / 'report/report.json').exists()]
    if todo:
        with (folder / 'cache-warm.log').open('w') as log:
            subprocess.run([VIOBENCH_PY, '-c', 'from pathlib import Path; import sys; from viobench.tools.runner.engine import Engine; '
                            'Engine().module(Path(sys.argv[1]).read_bytes())', str(wasm)], env=env, stdout=log,
                           stderr=subprocess.STDOUT, check=True)

    def one(archive):
        work = folder / archive.stem; work.mkdir(parents=True, exist_ok=True)
        with (work / 'run.lock').open('a') as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            if not (work / 'report/report.json').exists():
                with (work / 'evaluate.log').open('w') as log:
                    subprocess.run([VIOBENCH_PY, '-B', str(Path(__file__).with_name('evalmain.py')), 'evaluate', str(wasm), str(archive)],
                                   cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
                made = work / ('report-' + wasm.stem)
                if made.exists():
                    if (work / 'report').exists():
                        shutil.rmtree(work / 'report')
                    made.rename(work / 'report')
            return wasm_eval.score_one(archive, work)
    started = time.monotonic(); lookup = {}
    print(f'{len(archives)} episodes, {len(archives) - len(todo)} cached, workers={min(workers, 64)} (no video)', flush=True)
    with ThreadPoolExecutor(min(workers, 64)) as pool:
        fut = {pool.submit(one, a): a for a in archives}
        for i, f in enumerate(as_completed(fut), 1):
            a = fut[f]
            try:
                row = f.result()
            except Exception as exc:
                row = {'episode': a.stem, 'error': f'{type(exc).__name__}: {exc}'}
            lookup[a.stem] = row
            if i % 20 == 0 or i == len(archives):
                print(f'{i}/{len(archives)} finished, {time.monotonic() - started:.1f}s', flush=True)
            snap = {'guest': guest, 'rows': [lookup.get(x.stem, {'episode': x.stem, 'error': 'pending'}) for x in archives]}
            tmp = folder / 'scores.partial.json'; tmp.write_text(json.dumps(snap, indent=1) + '\n'); tmp.replace(folder / 'scores.json')
    return folder / 'scores.json'


def evaluate(wasm, name, workers):
    return run_guest_fast(wasm, EPISODES, OUT / name / 'eval', workers=workers, name=name)


def ate_rows(scores_path):
    d = json.loads(Path(scores_path).read_text())
    return {r['episode']: r['ate_full'] for r in d['rows']}


def stats(v):
    v = np.asarray(v, float)
    return dict(n=len(v), mean=float(v.mean()), median=float(np.median(v)), p90=float(np.percentile(v, 90)),
                above5=int((v > 5).sum()), above10=int((v > 10).sum()), max=float(v.max()))


def paired(base, new, scenes, n=4000, seed=20261120):
    """mean(new)-mean(base), bootstrap over scenes."""
    rng = np.random.default_rng(seed)
    d = np.asarray(new) - np.asarray(base)
    u = sorted(set(scenes)); idx = {s: [i for i, x in enumerate(scenes) if x == s] for s in u}
    boots = []
    for _ in range(n):
        pick = rng.integers(0, len(u), len(u))
        sel = [i for p in pick for i in idx[u[p]]]
        boots.append(d[sel].mean())
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(d.mean()), float(lo), float(hi)


def profile(folder, episodes, tg):
    """mean position error at 2/5/30 s per start type (uses the saved estimate.tum)."""
    sys.path.insert(0, str(ROOT))
    from research.guard_fusion import traj as T
    out = {}
    for e in episodes:
        t, truth, _ = T.load_truth(T.DEFAULT_RAW, e)
        paths = sorted((Path(folder) / e / 'report/logs').glob('*/estimate.tum'))
        if not paths:
            continue
        est = T.fill_missing_states(T.load_estimates(paths[0], t))
        err = np.linalg.norm(est[:, :3] - truth[:, :3], axis=1)
        out[e] = [float(err[min(int(s * 20), len(err) - 1)]) for s in (2, 5, 30)]
    return out


def report(name, folder, quiet_sealed=True):
    tg = tags()
    new = ate_rows(Path(folder) / 'scores.json'); base = ate_rows(BASELINE)
    eps = sorted(new)
    rows = [dict(e=e, **tg[e], fold=fold(tg[e]), new=new[e], base=base[e]) for e in eps]
    prof = profile(folder, eps, tg)
    res = {'name': name, 'wasm_sha': json.loads((Path(folder) / 'guest.json').read_text())['sha256']}
    sealed = [r for r in rows if slice_of(r['fold']) == 'sealed']
    (OUT / name / 'sealed_aggregate.json').write_text(json.dumps(
        dict(note='sealed fold 4; integrator only', **stats([r['new'] for r in sealed]),
             base=stats([r['base'] for r in sealed])), indent=1))
    os.chmod(OUT / name / 'sealed_aggregate.json', 0o600)
    lines = [f'== {name}  (wasm {res["wasm_sha"][:12]})  baseline = submitted gp_msckf (pool mean 2.21)']
    for sl in ('search', 'val'):
        for st in ('all', 'static', 'mid'):
            sel = [r for r in rows if slice_of(r['fold']) == sl and (st == 'all' or r['start'] == st)]
            if not sel:
                continue
            s = stats([r['new'] for r in sel]); b = stats([r['base'] for r in sel])
            dm, lo, hi = paired([r['base'] for r in sel], [r['new'] for r in sel], [r['scene'] for r in sel])
            p = [prof[r['e']] for r in sel if r['e'] in prof]
            pe = np.mean(p, axis=0) if p else [np.nan] * 3
            lines.append(f'{sl:6s} {st:6s} n={s["n"]:3d} mean {s["mean"]:6.3f} (base {b["mean"]:6.3f}) '
                         f'median {s["median"]:5.2f} p90 {s["p90"]:5.2f} >5m {s["above5"]:2d} >10m {s["above10"]:2d} '
                         f'| paired d={dm:+.3f} [{lo:+.3f},{hi:+.3f}] | err@2/5/30s {pe[0]:.2f}/{pe[1]:.2f}/{pe[2]:.2f}')
    res['rows_visible'] = [r for r in rows if slice_of(r['fold']) != 'sealed']
    (OUT / name / 'report.json').write_text(json.dumps(res, indent=1))
    (OUT / name / 'report.txt').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--name', required=True)
    ap.add_argument('--src', type=Path, default=SRC_DEFAULT, help='solution.c (a variant copy under research/single_model/<wp>/)')
    ap.add_argument('--defines', default='', help='space-separated NAME=VALUE list passed as -D flags')
    ap.add_argument('--wasm', type=Path, help='score a prebuilt wasm instead of building')
    ap.add_argument('--workers', type=int, default=32)
    ap.add_argument('--report-only', action='store_true', help='re-report an existing run')
    a = ap.parse_args()
    (OUT / a.name).mkdir(parents=True, exist_ok=True)
    if a.report_only:
        folder = next((OUT / a.name / 'eval').glob(a.name + '-*'))
    else:
        wasm = a.wasm or build(a.src, a.src.parent / 'CMakeLists.txt' if (a.src.parent / 'CMakeLists.txt').exists() else CMAKE_DEFAULT,
                               a.defines, a.name)
        folder = evaluate(wasm, a.name, a.workers).parent
    report(a.name, folder)


if __name__ == '__main__':
    main()
