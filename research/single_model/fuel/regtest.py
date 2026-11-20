"""Registry compatibility: render random/extreme vectors from the autoloop registry into BOTH sources (adopted.c and adopted_c1_exact.c), build,
and compare every pose bit for bit on N search flights. Read-only use of autoloop.params."""
import sys, random, subprocess, glob, numpy as np, json
sys.path.insert(0, '.')
from pathlib import Path
from research.single_model.autoloop import params as P
F = Path('research/single_model/fuel'); T = Path('/data/backups/rganapa/Sebastian/tmp/regt'); T.mkdir(exist_ok=True)
mine = F / 'adopted_c1_exact.c'
assert P.render(P.default_vec(), 1.0, mine) == mine.read_text(), 'default render of exact source not identical'
print('registry', P.check_registry(), 'ok on adopted.c; exact source: every name has exactly one #define and default render is identical', flush=True)
rng = random.Random(7); vecs = []
lo = {n: P.REG[n]['lo'] for n in P.NAMES}; hi = {n: P.REG[n]['hi'] for n in P.NAMES}
vecs.append(('allhi', dict(hi))); vecs.append(('alllo', dict(lo)))
vecs.append(('struct_hi', dict(MAX_CLONES=8, CLONE_EVERY=3, MAX_UPDATE_FEATURES=40, MIN_OBS=2, KLT_ITERS=10, GATE_PAIRS=1)))
vecs.append(('struct_lo', dict(MAX_CLONES=4, CLONE_EVERY=6, MAX_UPDATE_FEATURES=10, MIN_OBS=5, KLT_ITERS=3, GATE_PAIRS=3)))
for i in range(6):
    v = {}
    for n in P.NAMES:
        r = P.REG[n]; u = rng.random()
        import math
        x = math.exp(math.log(r['lo']) + u * (math.log(r['hi']) - math.log(r['lo']))) if r['scale'] == 'log' else r['lo'] + u * (r['hi'] - r['lo'])
        v[n] = x
    vecs.append((f'rnd{i}', v))
ok = 0; tot = 0
for name, v in vecs:
    if P.ill_posed(v): print(name, 'ill-posed, skipped', P.ill_posed(v)); continue
    for tag, src in (('ref', 'research/single_model/fuel/adopted_base.c'), ('new', None)):
        text = P.render(v, 1.0, Path(src) if src else mine); (T / f'{name}_{tag}.c').write_text(text)
        subprocess.run([str(F / 'buildfuel.sh'), str(T / f'{name}_{tag}.c'), str(T / f'{name}_{tag}.wasm')] + (['-O3'] if tag == 'new' else []), check=False)
        subprocess.run(['/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python', '-B', str(F / 'prof_run.py'), str(T / f'{name}_{tag}.wasm'), str(T / f'{name}_{tag}_out'), '24', '12'],
                       env=dict(__import__('os').environ, PYTHONPATH='/dev/shm/sebastian-vio/viobench'), capture_output=True)
    n = bad = 0
    for f in sorted(glob.glob(str(T / f'{name}_ref_out/*.npz'))):
        a = np.load(f); b = np.load(f.replace('_ref_out', '_new_out')); n += 1
        bad += not np.array_equal(a['pose'], b['pose'])
    pk = lambda t: max(np.load(f)['tot'].max() for f in glob.glob(str(T / f'{name}_{t}_out/*.npz'))) / 1e6
    print(f'{name:10s} flights {n} not-identical {bad} | peak ref {pk("ref"):.2f}M new {pk("new"):.2f}M', flush=True)
    tot += n; ok += n - bad
print('TOTAL', ok, '/', tot, 'bit-identical')
