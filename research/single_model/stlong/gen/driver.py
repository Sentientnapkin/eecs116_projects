"""Batched, resumable generation + immediate preprocessing for the learned_c training pool.
python driver2.py ROSTER.json [--workers 36] [--batch 200]
Per batch: wait while load > 170; run native_campaign.py generate (unmodified) into gen/raw-train2; then prep2 each new zip into the C-matched cache, record rows in new_rows.json, DELETE the raw zip."""
import argparse, json, os, subprocess, sys, time
from multiprocessing import Pool
R = '/data/backups/rganapa/Sebastian'; RES = R + '/eecs116_projects/research'; OUT = R + '/gen/raw-stlong'
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '../../learned_c')); sys.path.insert(0, os.path.join(HERE, '../../learned')); sys.path.insert(0, os.path.join(HERE, '../../learned_c/gen')); sys.path.insert(0, os.path.join(HERE, '..')); LMAX = float(os.environ.get('LMAX', 250))
LOG = OUT + '/logs/driver.log'; ROWS = HERE + '/sl_rows.json'

def log(m):
    with open(LOG, 'a') as f: f.write(time.strftime('%F %T ') + m + '\n')
    print(m, flush=True)


def render_gpus(done):
    # Once >=3000 safe flights are cached, release GPUs1–3 to the next training stage.
    if done >= 260: return [4]
    jobs = json.load(open(os.path.join(HERE, '../logs/jobs.json')))
    out = [3, 4]
    for gpu, name in [(1, 'pilot'), (2, 'pilot_mm')]:
        pid = jobs.get(name)
        try: alive = bool(open(f'/proc/{pid}/cmdline', 'rb').read())
        except FileNotFoundError: alive = False
        if not alive: out.append(gpu)
    return sorted(out)

def load(): return float(open('/proc/loadavg').read().split()[0])

def prep_one(row):
    os.environ['OPENBLAS_NUM_THREADS'] = '1'
    import prep2
    from pathlib import Path
    prep2.CACHE = Path('/data/backups/rganapa/Sebastian/tmp/sl_cache_train'); prep2.CACHE.mkdir(parents=True, exist_ok=True)
    try:
        r = prep2.one(row)
        pass
        return r
    except Exception as e: return row['name'], 'ERR ' + repr(e)[:200]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('roster'); ap.add_argument('--workers', type=int, default=36); ap.add_argument('--batch', type=int, default=200); ap.add_argument('--prep_workers', type=int, default=16)
    a = ap.parse_args(); roster = json.load(open(a.roster))['flights']
    assert 1 <= a.workers <= 48 and 1 <= a.prep_workers <= 48
    from pathlib import Path
    sys.path.insert(0, str(Path(HERE).parent)); import audit
    _, bad, ho, _ = audit.manifests()
    assert all(audit.fold(f['catalog'],f['scene']) in (0,1,2) and f['scene'] not in bad and (f['catalog'],f['scene']) not in ho for f in roster)
    for sub in ('logs','cfg','bench','partial'): Path(OUT,sub).mkdir(parents=True,exist_ok=True)
    done_rows = json.load(open(ROWS)) if os.path.exists(ROWS) else {}
    todo = [f for f in roster if f['id'] not in done_rows]
    log(f'{a.roster}: todo {len(todo)}/{len(roster)}')
    for b in range(0, len(todo), a.batch):
        chunk = todo[b:b + a.batch]
        while load() > LMAX: log(f'load {load():.0f} > 170, sleeping'); time.sleep(120)
        g = render_gpus(len(done_rows)); log(f'batch {b // a.batch}: {len(chunk)} flights, CPU simulation + OPTIX GPUs{g}, workers {a.workers}')
        path = f'{OUT}/cfg/{os.path.basename(a.roster)}.batch.json'; json.dump({'flights': chunk}, open(path, 'w'))
        procs = []
        for w in range(a.workers):
            env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(g[w % len(g)]), CUDAARCHS='90', HYPERLUX_BACKEND='OPTIX', HYPERLUX_CACHE_DIR=R + '/tmp/stlong_optix',
                       VIOBENCH_CACHE=R + '/tmp/stlong_gen_viobench', TMPDIR=R + '/tmp', CONTA_CACHE=R + '/gen/conta', VIOBENCH_SPOOL=R + '/gen/spool',
                       XDG_CACHE_HOME=R + '/gen/xdg', HF_HOME=R + '/tmp/stlong_hf', PATH=R + '/venv-sim/bin:/usr/local/cuda/bin:' + os.environ['PATH'])
            cmd = [R + '/venv-sim/bin/python', 'native_campaign.py', 'generate', '--gen-roster', path, '--gen-raw', OUT, '--worker', str(w), '--workers', str(a.workers)]
            procs.append(subprocess.Popen(cmd, cwd=RES, env=env, stdout=open(f'{OUT}/logs/{Path(a.roster).stem}.worker{w}.log', 'a'), stderr=subprocess.STDOUT))
        for p in procs: p.wait()
        ok = [f for f in chunk if os.path.exists(f"{OUT}/bench/{f['id']}.zip")]
        log(f'batch {b // a.batch} generated {len(ok)}/{len(chunk)}; preprocessing')
        rows = [dict(name=f['id'], catalog=f['catalog'], scene=f['scene'], dir=OUT + '/bench', role='train', pool='new', start='new', round=os.path.basename(a.roster), setting=f['setting'], fold=__import__('make_roster2').fold(f['catalog'], f['scene'])) for f in ok]
        with Pool(a.prep_workers) as p: res = p.map(prep_one, rows)
        bad = [r for r in res if str(r[1]).startswith('ERR')]
        for row, (n, s) in zip(rows, res):
            if not str(s).startswith('ERR'):
                done_rows[row['name']] = row
                for ext in ('zip',):
                    try: os.remove(f"{OUT}/bench/{row['name']}.{ext}")
                    except OSError: pass
        if os.path.exists(ROWS):
            existing = json.load(open(ROWS)); existing.update(done_rows); done_rows = existing
        json.dump(done_rows, open(ROWS, 'w'))
        log(f'batch {b // a.batch} preprocessed {len(res) - len(bad)}, errors {len(bad)} {bad[:3]}; cache rows total {len(done_rows)}')
        if len(done_rows) >= 260:
            log('Target >=3000 total safe flights reached; stopping generation.'); break
    log('DONE ' + a.roster)
main()
