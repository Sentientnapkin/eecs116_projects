"""Batched, resumable generation + immediate preprocessing for the learned_c training pool.
python driver2.py ROSTER.json [--workers 36] [--batch 200]
Per batch: wait while load > 170; run native_campaign.py generate (unmodified) into gen/raw-train2; then prep2 each new zip into the C-matched cache, record rows in new_rows.json, DELETE the raw zip."""
import argparse, json, os, subprocess, sys, time
from multiprocessing import Pool
R = '/data/backups/rganapa/Sebastian'; RES = R + '/eecs116_projects/research'; OUT = R + '/gen/raw-train2'
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
LOG = OUT + '/logs/driver.log'; ROWS = HERE + '/new_rows.json'

def log(m):
    with open(LOG, 'a') as f: f.write(time.strftime('%F %T ') + m + '\n')
    print(m, flush=True)

def gpus():
    q = subprocess.run(['nvidia-smi', '--query-gpu=index,utilization.gpu,memory.used', '--format=csv,noheader,nounits'], capture_output=True, text=True).stdout
    ok = [7]
    for line in q.strip().splitlines():
        i, u, m = [int(x) for x in line.split(',')]
        if 1 <= i <= 6 and u < 60 and m < 40000: ok.append(i)
    return sorted(set(ok))

def load(): return float(open('/proc/loadavg').read().split()[0])

def prep_one(row):
    os.environ['OPENBLAS_NUM_THREADS'] = '1'
    import prep2
    try: return prep2.one(row)
    except Exception as e: return row['name'], 'ERR ' + repr(e)[:200]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('roster'); ap.add_argument('--workers', type=int, default=36); ap.add_argument('--batch', type=int, default=200); ap.add_argument('--prep_workers', type=int, default=16)
    a = ap.parse_args(); roster = json.load(open(a.roster))['flights']
    done_rows = json.load(open(ROWS)) if os.path.exists(ROWS) else {}
    todo = [f for f in roster if f['id'] not in done_rows]
    log(f'{a.roster}: todo {len(todo)}/{len(roster)}')
    for b in range(0, len(todo), a.batch):
        chunk = todo[b:b + a.batch]
        while load() > 170: log(f'load {load():.0f} > 170, sleeping'); time.sleep(120)
        g = gpus(); log(f'batch {b // a.batch}: {len(chunk)} flights on GPUs {g}, workers {a.workers}')
        path = f'{OUT}/cfg/batch_current.json'; json.dump({'flights': chunk}, open(path, 'w'))
        procs = []
        for w in range(a.workers):
            env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(g[w % len(g)]), CUDAARCHS='90', HYPERLUX_CACHE_DIR='/dev/shm/sebastian-holdout/hyperlux-hl',
                       VIOBENCH_CACHE='/dev/shm/sebastian-holdout/viobench-c', TMPDIR=R + '/tmp', CONTA_CACHE=R + '/gen/conta', VIOBENCH_SPOOL=R + '/gen/spool',
                       XDG_CACHE_HOME=R + '/gen/xdg', HF_HOME=R + '/hf', PATH=R + '/venv-sim/bin:/usr/local/cuda/bin:' + os.environ['PATH'])
            cmd = [R + '/venv-sim/bin/python', 'native_campaign.py', 'generate', '--gen-roster', path, '--gen-raw', OUT, '--worker', str(w), '--workers', str(a.workers)]
            procs.append(subprocess.Popen(cmd, cwd=RES, env=env, stdout=open(f'{OUT}/logs/worker{w}.log', 'a'), stderr=subprocess.STDOUT))
        for p in procs: p.wait()
        ok = [f for f in chunk if os.path.exists(f"{OUT}/bench/{f['id']}.zip")]
        log(f'batch {b // a.batch} generated {len(ok)}/{len(chunk)}; preprocessing')
        rows = [dict(name=f['id'], catalog=f['catalog'], scene=f['scene'], dir=OUT + '/bench', role='train', pool='new', start='new', round=os.path.basename(a.roster), setting=f['setting']) for f in ok]
        with Pool(a.prep_workers) as p: res = p.map(prep_one, rows)
        bad = [r for r in res if str(r[1]).startswith('ERR')]
        for row, (n, s) in zip(rows, res):
            if not str(s).startswith('ERR'):
                done_rows[row['name']] = row
                for ext in ('zip',):
                    try: os.remove(f"{OUT}/bench/{row['name']}.{ext}")
                    except OSError: pass
        json.dump(done_rows, open(ROWS, 'w'))
        log(f'batch {b // a.batch} preprocessed {len(res) - len(bad)}, errors {len(bad)} {bad[:3]}; cache rows total {len(done_rows)}')
    log('DONE ' + a.roster)
main()
