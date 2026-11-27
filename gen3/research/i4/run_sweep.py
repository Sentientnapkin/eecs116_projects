"""i4 relaxed-compute sweep (resumable). nohup setsid python -B run_sweep.py > logs/sweep.log 2>&1 &
Phase 1 screen on pools/s80 (1 run), phase 2 replicates (_r1/_r2 nudges) for key + top configs, phase 3 v1val check.
Results: results.tsv (one line per eval), NOTES.md lines, done marker out/SWEEP_DONE."""
import json, os, subprocess, time, statistics as S, random
from pathlib import Path
I4 = Path('/data/backups/rganapa/Sebastian/gen3/research/i4'); G = I4.parents[1]
PY = '/data/backups/rganapa/Sebastian/venv-teacher/bin/python'
B = 'PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0'
G0 = B + ' GOV_B=1e12'
NONET = ' LC_ENABLE=0 LV_PERIOD=0'
KLT = ' KLT_R=6 KLT_ITERS=15 KLT_EPS=0.005 LEVELS=3'
CFG = {
    'ctl': B, 'g0': G0, 'nonet': B + NONET, 'nonet_g0': G0 + NONET,
    'muf': G0 + ' MAX_UPDATE_FEATURES=200',
    'gr2': G0 + ' GRID_X=14 GRID_Y=9 MAX_UPDATE_FEATURES=60',
    'gr5': G0 + ' GRID_X=22 GRID_Y=14 MAX_UPDATE_FEATURES=150',
    'gr10': G0 + ' GRID_X=32 GRID_Y=19 MAX_UPDATE_FEATURES=300',
    'c12': G0 + ' MAX_CLONES=12 MAX_OBS=12', 'c20': G0 + ' MAX_CLONES=20 MAX_OBS=20',
    'c30': G0 + ' MAX_CLONES=30 MAX_OBS=30', 'c20o8': G0 + ' MAX_CLONES=20 MAX_OBS=8',
    'c12e2': G0 + ' MAX_CLONES=12 CLONE_EVERY=2 MAX_OBS=12',
    'klt': G0 + KLT, 'it2': G0.replace('ITER_UPD=1', 'ITER_UPD=2'), 'it3': G0.replace('ITER_UPD=1', 'ITER_UPD=3'),
    'combo': G0 + ' GRID_X=22 GRID_Y=14 MAX_UPDATE_FEATURES=300 MAX_CLONES=20 MAX_OBS=20' + KLT,
    'combo_nonet': G0 + ' GRID_X=22 GRID_Y=14 MAX_UPDATE_FEATURES=300 MAX_CLONES=20 MAX_OBS=20' + KLT + NONET,
}
NUDGE = {'': '', '_r1': ' PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0', '_r2': ' PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0'}
BASE = {'': 'sw_a1_Ze0', '_r1': 'sw_a1_Ze0_r1', '_r2': 'sw_a1_Ze0_r2'}

def log(s):
    print(time.strftime('%H:%M:%S'), s, flush=True)

def wait_load():
    while int(open('/proc/loadavg').read().split('.')[0]) > 170: time.sleep(60)

def build(name, flags):
    w = I4 / 'builds' / name / 'solution.wasm'
    if (I4 / 'builds' / name / 'flags.txt').exists() and w.exists(): return w
    p = subprocess.run([PY, 'mk.py', name, flags, 'src.c'], cwd=I4, capture_output=True, text=True)
    if p.returncode: log('BUILD FAIL ' + name + p.stdout[-500:] + p.stderr[-500:]); return None
    return w

def evaluate(ev, wasm, pool, workers=8):
    out = G / 'evals' / f'{ev}__{Path(pool).name}.json'
    if out.exists(): return json.load(open(out))
    wait_load()
    subprocess.run([PY, '-B', 'evalpool.py', ev, str(wasm), str(pool), str(workers)], cwd=G,
                   stdout=open(I4 / 'logs' / f'{ev}.log', 'w'), stderr=subprocess.STDOUT)
    return json.load(open(out)) if out.exists() else None

def boot(d, n=4000):
    rnd = random.Random(1); m = len(d)
    bs = sorted(S.mean(d[rnd.randrange(m)] for _ in range(m)) for _ in range(n))
    return bs[int(.025 * n)], bs[int(.975 * n)]

def summarize(ev, res, basefile, pool):
    b = {r['id']: r for r in json.load(open(G / 'evals' / basefile))}
    ok = [r for r in res if r['ate'] is not None]
    ids = [r['id'] for r in ok if r['id'] in b and b[r['id']]['ate'] is not None]
    a = {r['id']: r for r in ok}
    d = [a[i]['ate'] - b[i]['ate'] for i in ids]; lo, hi = boot(d)
    peaks = sorted(r['peak'] for r in ok if r['peak'])
    cls = {c: (S.mean(v) if (v := [r['ate'] for r in ok if r['setting_class'] == c]) else float('nan')) for c in ('room', 'warehouse', 'forest')}
    row = [ev, Path(pool).name, len(ok), len(res), '%.3f' % S.mean(r['ate'] for r in ok), '%.3f' % S.median(r['ate'] for r in ok),
           '%.3f' % S.mean(b[i]['ate'] for i in ids), '%+.3f' % S.mean(d), '[%+.3f,%+.3f]' % (lo, hi),
           '%.3f' % cls['room'], '%.3f' % cls['warehouse'], '%.3f' % cls['forest'],
           '%.3g' % peaks[-1], '%.3g' % peaks[int(.95 * (len(peaks) - 1))], sum(r['ate'] > 3 for r in ok)]
    line = '\t'.join(map(str, row))
    rf = I4 / 'results.tsv'
    if not rf.exists(): rf.write_text('eval\tpool\tn_ok\tn\tmean\tmedian\tbase_mean\td\tCI95\troom\twarehouse\tforest\tpeak\tp95peak\tgt3m\n')
    if not any(l.startswith(ev + '\t') for l in rf.read_text().splitlines()): open(rf, 'a').write(line + '\n')
    log(line)
    return S.mean(r['ate'] for r in ok)

def run(cfg, rep, pool, basefile):
    name = cfg + rep; ev = 'i4_' + name + ('' if Path(pool).name == 's80' else '_' + Path(pool).name)
    w = build(name, CFG[cfg] + NUDGE[rep])
    if w is None: return None
    res = evaluate(ev, w, pool)
    if res is None: log('EVAL FAIL ' + ev); return None
    return summarize(ev, res, basefile, pool)

S80 = I4 / 'pools/s80'
means = {}
for c in CFG:
    means[c] = run(c, '', S80, 'sw_a1_Ze0__v3val.json')
open(I4 / 'NOTES.md', 'a').write('- %s phase1 screen done (results.tsv)\n' % time.strftime('%F %T'))
ranked = [c for c in sorted((c for c in means if means[c] is not None and c not in ('ctl',)), key=lambda c: means[c])]
reps = list(dict.fromkeys(['g0', 'combo', 'nonet_g0', 'ctl'] + ranked[:3]))
log('replicates for ' + ' '.join(reps))
for c in reps:
    for r in ('_r1', '_r2'):
        run(c, r, S80, BASE[r] + '__v3val.json')
open(I4 / 'NOTES.md', 'a').write('- %s phase2 replicates done (%s)\n' % (time.strftime('%F %T'), ' '.join(reps)))
for c in ['g0', ranked[0]]:
    run(c, '', G / 'pools/v1val', 'sw_a1_Ze0_v1__v1val.json')
open(I4 / 'NOTES.md', 'a').write('- %s phase3 v1val done\n' % time.strftime('%F %T'))
(I4 / 'out/SWEEP_DONE').write_text('done\n')
log('ALL DONE')
