"""r5 detached pipeline. queue.txt lines: NAME|GOV_B|EXTRA_FLAGS|POOL   (pool v3val or v1val)
Builds research/r5/builds/r5_NAME, evals gen3/evals/r5_NAME__POOL.json, compares vs the reference of the same GOV_B
(3-rep mean of the sweep agent's builds), appends results.tsv + NOTES.md, auto-queues replicates (_r1,_r2) when the single
run d < -0.02 and, after 3 reps with mean d < -0.01, a v1val check. Resumable: done items are skipped (eval json exists)."""
import os, sys, json, time, glob, subprocess, random, statistics as S, math
import numpy as np
G = '/data/backups/rganapa/Sebastian/gen3'; R5 = f'{G}/research/r5'
BASEF = 'PRIOR_MODE=1 START_STD=2.0 SPEED_STD=1.0 AB_ZUPT=0 ITER_UPD=1 INV_LAT=0 INV_VZ=0 EDGE=0'
REP = {'': '', '_r1': 'PIXEL_STD=1.515 DETECT_MIN_SCORE=1010.0', '_r2': 'PIXEL_STD=1.485 DETECT_MIN_SCORE=990.0'}
REFS = {'3.6e6': ['sw_a1_Ze0', 'sw_a1_Ze0_r1', 'sw_a1_Ze0_r2'], '2.7e6': ['sw_a1_b27', 'sw_a1_b27_r1', 'sw_a1_b27_r2'],
        '2.1e6': ['sw_a1_b21', 'sw_a1_b21_r1', 'sw_a1_b21_r2'], '2.4e6': ['sw_a1_b24'], '3.0e6': ['sw_a1_b30'], '1.8e6': ['sw_a1_b18']}
REFV1 = {'3.6e6': ['sw_a1_Ze0_v1'], '2.7e6': ['sw_a1_b27_v1'], '2.1e6': ['sw_a1_b21_v1']}
W = {'room': (12/24, 1/12), 'warehouse': (6/24, 4/6), 'forest': (6/24, 1/6)}
Q = f'{R5}/queue.txt'; TSV = f'{R5}/results.tsv'; NOTES = f'{R5}/NOTES.md'

def log(m): print(time.strftime('%H:%M:%S'), m, flush=True)
def load(n, pool):
    p = f'{G}/evals/{n}__{pool}.json'
    return {r['id']: r for r in json.load(open(p)) if r.get('ate') is not None} if os.path.exists(p) else None
def swm(rows):
    t = 0
    for c, (wc, hv) in W.items():
        h = [r['ate'] for r in rows if r['setting_class'] == c and r['start'] == 'hover']; m = [r['ate'] for r in rows if r['setting_class'] == c and r['start'] != 'hover']
        if not h or not m: return float('nan')
        t += wc*(hv*S.mean(h)+(1-hv)*S.mean(m))
    return t
def fuel(n, pool):
    fs = [np.load(f).ravel() for f in glob.glob(f'{G}/evals/{n}/{pool}/*/*/report/logs/*/fuel.npy')]
    if not fs: return (0, 0, 0)
    a = np.concatenate(fs); return a.max()/1e6, np.percentile(a, 99)/1e6, np.percentile(a, 95)/1e6
def compare(names, refs, pool):
    """per-flight mean over names vs per-flight mean over refs"""
    V = [load(n, pool) for n in names]; Rf = [x for x in (load(n, pool) for n in refs) if x]
    ids = sorted(set.intersection(*[set(x) for x in V+Rf]))
    va = {i: S.mean(x[i]['ate'] for x in V) for i in ids}; ra = {i: S.mean(x[i]['ate'] for x in Rf) for i in ids}
    d = [va[i]-ra[i] for i in ids]; rng = random.Random(0); bs = sorted(S.mean(rng.choices(d, k=len(d))) for _ in range(2000))
    rows = [dict(V[0][i], ate=va[i]) for i in ids]; rrows = [dict(V[0][i], ate=ra[i]) for i in ids]
    cl = '/'.join('%.3f' % S.mean(r['ate'] for r in rows if r['setting_class'] == c) for c in W)
    pk = max(fuel(n, pool)[0] for n in names); p99 = max(fuel(n, pool)[1] for n in names); p95 = max(fuel(n, pool)[2] for n in names)
    m = S.mean(va.values())
    return dict(n=len(ids), mean=m, ref=S.mean(ra.values()), sw=swm(rows), swref=swm(rrows), d=S.mean(d), lo=bs[50], hi=bs[1949],
                gt3=sum(v > 3 for v in va.values()), worst=max(va.values()), cls=cl, peak=pk, p99=p99, p95=p95,
                dscore=0.4*math.log2(3.77/pk)-2.2*math.log(m/(0.665 if pool == 'v3val' else 0.556)) if pk else float('nan'))
def run(name, gov, extra, pool):
    out = f'{G}/evals/r5_{name}__{pool}.json'
    if os.path.exists(out): return True
    while int(open('/proc/loadavg').read().split('.')[0]) > 170: time.sleep(60)
    flags = f'{BASEF} GOV_B={gov} {extra}'.strip()
    b = subprocess.run(['python3', f'{R5}/mk.py', f'r5_{name}', flags, f'{R5}/base.c'], capture_output=True, text=True)
    if b.returncode: log(f'BUILD FAIL {name}: {b.stdout[-500:]}{b.stderr[-500:]}'); return False
    log(f'build {name} {b.stdout.split()[-1]} flags {flags}')
    e = subprocess.run([f'{G}/../venv-teacher/bin/python', '-B', 'evalpool.py', f'r5_{name}', f'{R5}/builds/r5_{name}/solution.wasm', f'pools/{pool}', '8'],
                       cwd=G, capture_output=True, text=True)
    log(f'eval {name} {pool}: ' + (e.stdout.splitlines()[0] if e.stdout else e.stderr[-300:]))
    return os.path.exists(out)
def queue():
    return [l.strip().split('|') for l in open(Q) if l.strip() and not l.startswith('#')]
def push(line):
    if line not in [ '|'.join(x) for x in queue()]: open(Q, 'a').write(line+'\n')

if not os.path.exists(TSV):
    open(TSV, 'w').write('name\tpool\tgov\textra\tnrep\tn\tmean\tref\td\tlo\thi\tsw\tswref\tgt3\tworst\tro/wa/fo\tpeak\tp99\tp95\tdscore\n')
done = set(l.split('\t')[0]+'|'+l.split('\t')[1]+'|'+l.split('\t')[4] for l in open(TSV).read().splitlines()[1:])
i = 0
while True:
    q = queue()
    if i >= len(q): break
    name, gov, extra, pool = q[i]; i += 1
    if not run(name, gov, extra, pool): continue
    base = name.rsplit('_r', 1)[0] if name[-3:-1] == '_r' else name
    reps = [base+s for s in ('', '_r1', '_r2') if load('r5_'+base+s, pool)]
    key = f'{base}|{pool}|{len(reps)}'
    if key in done: continue
    refs = (REFS if pool == 'v3val' else REFV1).get(gov, [])
    if not refs: log(f'no ref for {gov}'); continue
    c = compare(['r5_'+r for r in reps], refs, pool); done.add(key)
    line = (f"{base}\t{pool}\t{gov}\t{extra}\t{len(reps)}\t{c['n']}\t{c['mean']:.3f}\t{c['ref']:.3f}\t{c['d']:+.3f}\t{c['lo']:+.3f}\t{c['hi']:+.3f}\t"
            f"{c['sw']:.3f}\t{c['swref']:.3f}\t{c['gt3']}\t{c['worst']:.2f}\t{c['cls']}\t{c['peak']:.2f}\t{c['p99']:.2f}\t{c['p95']:.2f}\t{c['dscore']:+.3f}")
    open(TSV, 'a').write(line+'\n')
    open(NOTES, 'a').write(f"- [pipe {time.strftime('%H:%M')}] {base} ({pool}, GOV_B {gov}, {extra}, {len(reps)} rep): mean {c['mean']:.3f} vs ref {c['ref']:.3f} "
                           f"d {c['d']:+.3f} [{c['lo']:+.3f},{c['hi']:+.3f}] sw {c['sw']:.3f}/{c['swref']:.3f} ro/wa/fo {c['cls']} >3m {c['gt3']} peak {c['peak']:.2f}M p95 {c['p95']:.2f}M dscore {c['dscore']:+.3f}\n")
    log(line)
    if pool == 'v3val' and len(reps) == 1 and c['d'] < -0.02:
        for s in ('_r1', '_r2'): push(f"{base}{s}|{gov}|{(extra+' '+REP[s]).strip()}|v3val")
    if pool == 'v3val' and len(reps) == 3 and c['d'] < -0.01:
        push(f"{base}_v1|{gov}|{extra}|v1val")
open(f'{R5}/PIPE_DONE', 'w').write(time.strftime('%c')+'\n'); log('PIPE DONE')
