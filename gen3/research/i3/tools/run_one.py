"""run_one.py NAME "EXTRA FLAGS" [pool=i3s120] [workers=8] : build (src_or.c, OR=1 + EXTRA) -> eval -> ana/NAME.json (per flight ate/peak/ORS) + results.tsv row.
Resumable: skips if ana/NAME.json exists."""
import shutil, sys, json, subprocess, os, re, statistics as st, hashlib, time
from pathlib import Path
P = Path('/data/backups/rganapa/Sebastian/gen3/research/i3'); G = P.parent.parent
name, extra = sys.argv[1], sys.argv[2]; pool = sys.argv[3] if len(sys.argv) > 3 else 'i3s120'; W = sys.argv[4] if len(sys.argv) > 4 else '8'
out = P / 'ana' / (name + '.json')
if out.exists(): sys.exit(0)
BASE = 'PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0'
import re as _re
ton = ''.join(' OR_%s_ON=1' % m for m in _re.findall(r'\bOR_(VEL|GRAV|BG|BA|ROT|RT|DZ|ALT|POS|DEP)=(?!0(?:\.0*)?(?:\s|$))', extra + ' '))
extra = extra + ton if extra != 'BASELINE' else extra
flags = BASE + (' OR=1 ' + extra if extra != 'BASELINE' else '')
src = P / ('src_or.c' if extra != 'BASELINE' else 'src_base.c')
t0 = time.time()
wasm = P / 'builds' / name / 'solution.wasm'
if not wasm.exists():
    r = subprocess.run([sys.executable, str(P / 'tools/mk.py'), name, flags, str(src)], capture_output=True, text=True)
    if r.returncode: print('BUILD FAIL', name, r.stdout[-500:], r.stderr[-500:]); sys.exit(1)
r = subprocess.run(['/data/backups/rganapa/Sebastian/venv-teacher/bin/python', '-B', str(G / 'evalpool.py'), name, str(wasm), str(P / 'pools' / pool), W], cwd=G, capture_output=True, text=True)
sc = list((G / 'evals' / name / pool).glob('*/scores.json'))
if not sc: print('EVAL FAIL', name, r.stdout[-500:], r.stderr[-500:]); sys.exit(1)
rows = json.load(open(sc[0]))['rows']; ev = {}
for x in rows:
    ors = None
    txt = ''.join(Path(p).read_text() for p in (G / 'evals' / name / pool).glob('*/%s/report/logs/*/stderr.txt' % x['episode']))
    m = re.search(r'ORS (\d+) (\d+)((?: [-\d.e+naninf]+)+)', txt)
    if m: ors = [float(v) for v in m.group(3).split()]
    ev[x['episode']] = dict(ate=x.get('ate_full'), peak=x.get('peak_fuel_per_frame'), p95=x.get('p95_fuel_per_frame'), fail=x.get('failure'), scene=x.get('scene'), ors=ors)
json.dump(dict(name=name, flags=flags, pool=pool, flights=ev), open(out, 'w'))
a = [v['ate'] for v in ev.values() if v['ate'] is not None]
with open(P / 'results.tsv', 'a') as f:
    f.write('%s\t%d\t%.4f\t%.4f\t%d\t%s\n' % (name, len(a), st.mean(a), st.median(a), max(v['peak'] or 0 for v in ev.values()), extra))
print(name, 'done', len(a), '%.3f' % st.mean(a), '%.0fs' % (time.time() - t0))

dg = hashlib.sha256(wasm.read_bytes()).hexdigest() if wasm.exists() else ''
shutil.rmtree(P / 'builds' / name, ignore_errors=True); shutil.rmtree(G / 'evals' / name, ignore_errors=True)
if dg: shutil.rmtree('/dev/shm/sebastian-vio/guard-cache/' + dg, ignore_errors=True)
