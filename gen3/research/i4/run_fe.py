"""Frontend diagnostics over pools/s80 with diag build (resumable). python -B run_fe.py > logs/fe.log"""
import os, subprocess, sys, json, glob
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
I4 = Path('/data/backups/rganapa/Sebastian/gen3/research/i4')
V = '/data/backups/rganapa/Sebastian/venv-viobench-9b1b079/bin/python'
PY = '/data/backups/rganapa/Sebastian/venv-teacher/bin/python'
EM = '/data/backups/rganapa/Sebastian/eecs116_projects/research/single_model/evalmain.py'
W = str(I4 / 'builds/diag/solution.wasm')
env = dict(os.environ, PYTHONPATH='/dev/shm/sebastian-vio/viobench',
           OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
def one(z):
    z = Path(z); w = I4 / 'fe' / z.stem; o = I4 / 'fe' / (z.stem + '.json')
    if o.exists(): return
    w.mkdir(parents=True, exist_ok=True)
    with open(w / 'stdout.txt', 'w') as so:
        subprocess.run([V, '-B', EM, 'evaluate', W, str(z)], cwd=w, env=env, stdout=so, stderr=subprocess.STDOUT)
    se = list(w.glob('report*/logs/*/stderr.txt'))
    if not se: print('NO STDERR', z.stem, flush=True); return
    r = subprocess.run([PY, '-B', str(I4 / 'tools/fe_ana.py'), str(z), str(se[0]), str(o)], capture_output=True, text=True)
    if r.returncode: print('ANA FAIL', z.stem, r.stderr[-300:], flush=True)
    else:
        import shutil
        for f in w.glob('report*'): shutil.rmtree(f, ignore_errors=True)
    print('done', z.stem, flush=True)
zs = sorted(glob.glob(str(I4 / 'pools/s80/*.zip')))
while int(open('/proc/loadavg').read().split('.')[0]) > 170: __import__('time').sleep(60)
with ThreadPoolExecutor(6) as ex: list(ex.map(one, zs))
(I4 / 'out/FE_DONE').write_text('done\n')
